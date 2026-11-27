"""Window continuation only; numerical source remains frozen at 0d1e8517."""
from pathlib import Path
import argparse, hashlib, importlib.util, json, math, os, sys

FIELDS=('window','start','end','first_scored','targets','target_token_sha256')

def checked_rows(rows, reference):
    ids=[x['window'] for x in rows]
    if ids!=sorted(set(ids)):raise ValueError('duplicate or unordered windows')
    refs={x['window']:x for x in reference}
    for x in rows:
        if x['window'] not in refs or any(x[k]!=refs[x['window']][k] for k in FIELDS):
            raise ValueError('window input/target mismatch')
        if not math.isfinite(x['nll_sum']):raise ValueError('nonfinite NLL')
    return rows

def merge_rows(old,new,reference):
    rows=sorted(old+new,key=lambda x:x['window'])
    checked_rows(rows,reference)
    if [x['window'] for x in rows]!=[x['window'] for x in reference]:raise ValueError('missing windows')
    n=sum(x['targets'] for x in rows);nll=sum(x['nll_sum'] for x in rows)
    return rows,dict(windows=len(rows),targets=n,nll_sum=nll,ppl=math.exp(nll/n))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--original',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    assert os.environ.get('SLURM_JOB_ID') and not a.output.exists()
    root=a.original;source=root/'source'
    def read(p):
        raw=p.read_bytes();h=hashlib.sha256(raw).hexdigest()
        assert h==p.with_suffix('.sha256').read_text().strip()
        return json.loads(raw),raw,h
    settings,_,_=read(root/'SETTINGS.json')
    manifest_raw=(source/'EXECUTION_MANIFEST.json').read_bytes()
    mf=json.loads(manifest_raw);msha=hashlib.sha256(manifest_raw).hexdigest()
    assert mf['git_commit']=='0d1e85176fd52205669148296c585a06c47bc369'
    assert msha==settings['manifest_sha256']
    assert hashlib.sha256(Path(settings['inputs']).read_bytes()).hexdigest()==settings['inputs_sha256']
    for n,h in mf['files'].items():assert hashlib.sha256((source/n).read_bytes()).hexdigest()==h,n
    gate,_,_=read(root/'outputs/GATE.json');assert gate['status']=='completed'
    selected,_,_=read(root/'outputs/FULL_SELECTION.json')
    assert selected['status']=='completed' and selected['selected']==[32,24]
    reference,_,_=read(root/'outputs/BF16_full/WINDOWS.json')
    assert len(reference)==292 and sum(x['targets'] for x in reference)==299077
    a.output.mkdir(parents=True)
    sys.path.insert(0,settings['runtime'])
    sys.path.insert(0,str(source/'experiments/t64_dynamic_scale_20261125'))
    from score_reference import save,score
    oldrows={};sources={}
    for width in selected['selected']:
        folder=root/('outputs/full'+str(width));p=folder/'WINDOWS.json'
        if not p.exists():p=folder/'PROGRESS.json'
        rows=[];entry=dict(status='absent',original=str(p))
        if p.exists():
            try:
                obj,raw,h=read(p);rows=obj if isinstance(obj,list) else obj['records']
                checked_rows(rows,reference)
                assert [x['window'] for x in rows]==list(range(len(rows)))
            except (AssertionError,ValueError,KeyError,json.JSONDecodeError):
                # An interrupted writer's unsealed file is never accepted.
                rows=[];entry=dict(status='unsealed_or_invalid_not_reused',original=str(p))
            else:
                evidence=a.output/('original'+str(width)+'_'+p.name)
                evidence.write_bytes(raw);evidence.with_suffix('.sha256').write_text(h+'\n')
                entry=dict(status='verified',original=str(p),sha256=h,reused_windows=len(rows))
        oldrows[width]=rows;sources[str(width)]=entry
    remaining={w:[x['window'] for x in reference if x['window'] not in {v['window'] for v in oldrows[w]}] for w in selected['selected']}
    save(a.output/'REUSE.json',dict(status='verified',source_commit=mf['git_commit'],sources=sources,remaining=remaining))
    model=None;results=[]
    if any(remaining.values()):
        import torch
        torch.set_num_threads(4);torch.backends.cuda.matmul.allow_tf32=False
        d=source/'experiments/t64_narrow_state_20261127';sys.path.insert(0,str(d))
        spec=importlib.util.spec_from_file_location('frozen_narrow',d/'runner.py')
        frozen=importlib.util.module_from_spec(spec);spec.loader.exec_module(frozen)
        from reference import prepare,load_model
        inputs,tokens,ledger,protocol=prepare(Path(settings['inputs']),Path(settings['runtime']),a.output/'prepared')
        assert protocol==gate['protocol']
        model,context,modules,identity=load_model(inputs);assert identity==gate['identity']
        import scale_patch
        scale_patch.ScaleOverride=frozen.Composite
        # A restarted context must reproduce an archived window, including NLL.
        probe=score(model,context,modules,tokens,ledger,[0],101,a.output/'replay_probe32',frozen.case(32))
        actual,_,_=read(a.output/'replay_probe32/WINDOWS.json')
        expected,_,_=read(root/'outputs/pilot32/WINDOWS.json')
        assert actual==expected[:1], 'resumed-window numerical replay differs'
        save(a.output/'REPLAY_GATE.json',dict(status='passed',width=32,window=0,
             actual_sha256=probe['records_sha256'],original_pilot_sha256=hashlib.sha256((root/'outputs/pilot32/WINDOWS.json').read_bytes()).hexdigest()))
    for width in selected['selected']:
        rows=[];extra=None
        if remaining[width]:
            extra=score(model,context,modules,tokens,ledger,remaining[width],101,a.output/('new'+str(width)),frozen.case(width))
            rows,_,h=read(a.output/('new'+str(width)+'/WINDOWS.json'))
            assert h==extra['records_sha256']
        combined,z=merge_rows(oldrows[width],rows,reference)
        save(a.output/('full'+str(width)+'_WINDOWS.json'),combined)
        z.update(width=width,status='completed',reused_windows=len(oldrows[width]),new_windows=len(rows),
                 reused_source=sources[str(width)],new_result=extra,seed=101)
        results.append(z);save(a.output/'PROGRESS.json',dict(status='running',full=results))
    save(a.output/'RESULT.json',dict(status='completed',full=results,source_commit=mf['git_commit'],
         original_gate_sha256=hashlib.sha256((root/'outputs/GATE.json').read_bytes()).hexdigest(),
         continuation_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
         slurm_job_id=os.environ['SLURM_JOB_ID'],no_training=True,no_PPA=True))

if __name__=='__main__':main()
