"""Targeted complete-model paired validation; sampling budget is explicit."""
import concurrent.futures as cf
import hashlib,json,sys,time
from pathlib import Path
from run_matrix import ROOT,run_one,source_record,write
OUT=ROOT/'architecture_tlm/unified_v6/results/integrated_rng_20261022_v3'

def case(spec):
    if 'diagnostic_samples' not in spec:return run_one(spec,str(OUT))
    from architecture_tlm.unified_v6.config import load
    from architecture_tlm.unified_v6.model import FullDecode
    from architecture_tlm.unified_v6.run import compact
    start=time.monotonic();cfg,shape=load(spec['model'])
    cfg.update(context_tokens=spec['context'],seed=spec['seed'],trace_event_limit=12,row_receipt_limit=4)
    cfg['ffn']['mode']=spec['ffn'];cfg['attention'].update(mode=spec['attention'],samples=spec['diagnostic_samples'],winner_update_multiplier=1)
    cfg['random'].update(backend=spec['backend'],clock_hz=cfg['core_hz'])
    r=FullDecode(cfg,shape).run();r['execution_commit']=spec['execution_commit']
    r['config_sha256']=hashlib.sha256(json.dumps(cfg,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    ident='{model}_L{context}_seed{seed}_{ffn}_{attention}_{backend}'.format(**spec)+'_S8_diagnostic'
    path=OUT/spec['model']/(ident+'.json');path.parent.mkdir(exist_ok=True);write(path,r)
    row=compact(spec['model'],spec['context'],spec['seed'],spec['ffn'],spec['attention'],r)
    row.update(backend=spec['backend'],diagnostic_samples=8,winner_multiplier=1,wall_seconds=time.monotonic()-start,
       path=path.relative_to(OUT).as_posix(),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),bytes=path.stat().st_size)
    return row

def main():
    if OUT.exists():raise ValueError('immutable output')
    src=source_record();specs=[]
    def add(model,ctx,seed,ffn,attn,diagnostic=False):
        for b in ['integrated_service','local_prng_interface']:
            s=dict(model=model,context=ctx,seed=seed,ffn=ffn,attention=attn,backend=b,execution_commit=src['commit'])
            if diagnostic:s['diagnostic_samples']=8
            specs.append(s)
    for ctx in [2048,8192]:
        for f,a in [('bf16','exact'),('sc','pv'),('sc','screen_pv')]:add('qwen',ctx,0,f,a)
    for seed in [1,2]:add('qwen',2048,seed,'sc','screen_pv')
    for f,a in [('sc','exact'),('sc','screen_exact')]:add('qwen',2048,0,f,a)
    for seed in [0,1,2]:
        for mode in ['screen_winner','screen_rejection']:add('qwen',2048,seed,'sc',mode,True)
    for model in ['llama1','llama2']:
        for f,a in [('bf16','exact'),('sc','pv')]:add(model,2048,0,f,a)
    OUT.mkdir(parents=True);write(OUT/'EXECUTION.json',src)
    plan=dict(case_count=len(specs),cases=specs,workers=6,scope='full layer count/shape, batch1decode; diagnostic S8 for winner/rejection; no quality/PPA claim',
      replaced_cancelled_plan='../integrated_rng_20261022_v2/PLAN.json')
    write(OUT/'PLAN.json',plan);rows=[];failed=[]
    with cf.ProcessPoolExecutor(max_workers=6) as pool:
        pending={pool.submit(case,s):s for s in specs}
        for f in cf.as_completed(pending):
            try:
                row=f.result();rows.append(row);write(OUT/('DONE_%03d.json'%len(rows)),row)
                print(json.dumps(dict(done=len(rows),total=len(specs),case=row['path'],ms=row['TPOT_ms'],host_s=round(row['wall_seconds'],1))),flush=True)
            except Exception as e:
                x=dict(case=pending[f],error=repr(e));failed.append(x);write(OUT/('FAILED_%03d.json'%len(failed)),x);print(x,flush=True)
    write(OUT/'SUMMARY.json',dict(rows=rows,failures=failed,complete=len(rows)==len(specs),
       caveats=['real PRNG/q256 changes addresses','S8 sampler cases diagnose integration only','endpoint energy subtotal is not total energy']))
    files={p.relative_to(OUT).as_posix():dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in OUT.rglob('*') if p.is_file()}
    write(OUT/'ARTIFACT_MANIFEST.json',files)
    return int(bool(failed))
if __name__=='__main__':sys.exit(main())
