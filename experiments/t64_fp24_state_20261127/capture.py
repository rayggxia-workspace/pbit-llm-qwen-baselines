"""Read-only exact FFN run, sample complete real cross-K chains, replay custom formats."""
from contextlib import AbstractContextManager
from pathlib import Path
import argparse,gc,hashlib,importlib.util,json,os,sys

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--original',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    assert os.environ.get('SLURM_JOB_ID') and not a.output.exists()
    settings=json.loads((a.original/'SETTINGS.json').read_bytes())
    assert hashlib.sha256((a.original/'SETTINGS.json').read_bytes()).hexdigest()==(a.original/'SETTINGS.sha256').read_text().strip()
    source=a.original/'source';raw=(source/'EXECUTION_MANIFEST.json').read_bytes();mf=json.loads(raw)
    assert hashlib.sha256(raw).hexdigest()==settings['manifest_sha256']
    assert mf['git_commit']=='0d1e85176fd52205669148296c585a06c47bc369'
    for n,h in mf['files'].items():assert hashlib.sha256((source/n).read_bytes()).hexdigest()==h,n
    own=Path(__file__).parent
    own_manifest=json.loads((own/'SOURCE_MANIFEST.json').read_bytes())
    for n,h in own_manifest['files'].items():assert hashlib.sha256((own/n).read_bytes()).hexdigest()==h,n
    sys.path.insert(0,settings['runtime']);sys.path.insert(0,str(source/'experiments/t64_dynamic_scale_20261125'))
    import torch,numpy as np
    torch.set_num_threads(4);torch.backends.cuda.matmul.allow_tf32=False
    assert torch.cuda.is_available() and torch.cuda.device_count()==1
    d=source/'experiments/t64_narrow_state_20261127';sys.path.insert(0,str(d))
    spec=importlib.util.spec_from_file_location('fp24_frozen',d/'runner.py')
    frozen=importlib.util.module_from_spec(spec);spec.loader.exec_module(frozen)
    from score_reference import score,save,sealed
    from reference import prepare,load_model
    a.output.mkdir(parents=True);(a.output/'prepared').mkdir();(a.output/'trace').mkdir()
    inputs,tokens,ledger,protocol=prepare(Path(settings['inputs']),Path(settings['runtime']),a.output/'prepared')
    old=sealed(a.original/'outputs/GATE.json');assert protocol==old['protocol']
    model,context,modules,native=load_model(inputs,native=True)
    bf=score(model,context,modules,tokens,ledger,list(range(292)),101,a.output/'BF16_full')
    native_gate=sealed(Path(settings['reference_root'])/'gate/RESULT.json')
    assert native==native_gate['native_identity'] and abs(bf['ppl']-old['BF16_full']['ppl'])<1e-6
    del model,context,modules;gc.collect();torch.cuda.empty_cache()
    model,context,modules,identity=load_model(inputs);assert identity==old['identity']
    from adapter import SamplingOverride
    from evaluate_trace import evaluate,summarize
    import seven_forward as sf,wide_wd,onebit
    rows=[];traces=[]
    class Capture(AbstractContextManager):
        def __enter__(self):
            self.old_coeff=sf.exact_coefficients;self.old_output=wide_wd.shifted_output
            def coefficients(*args,**kw):
                cf,ex=self.old_coeff(*args,**kw);self.ex=ex;return cf,ex
            def output(c,s,h,w,cf,T,R,qmax=127):
                result=self.old_output(c,s,h,w,cf,T,R,qmax)
                assert qmax==127 and c.shape[0]==128 and len(rows)<72
                role='GU' if w.shape[0]==19456 else 'Wd';assert w.shape[0] in (19456,2560)
                expected='GU' if len(rows)%2==0 else 'Wd';assert role==expected
                rowidx=torch.tensor([0,1,64,127],device=c.device)
                if role=='GU':
                    count=w.shape[0]//128;gs=[0,count//2,count-1]
                    blocks=gs+[x+count for x in gs]
                else:blocks=[0,1,w.shape[0]//64-2,w.shape[0]//64-1]
                cols=torch.cat([torch.arange(x*64,(x+1)*64,device=c.device) for x in blocks])
                cs=c[rowidx].cpu().numpy().astype(np.int64);ss=s[rowidx].cpu().numpy().astype(np.int64)
                hs=h[rowidx].cpu().numpy().astype(np.int64);ws=w[cols].cpu().numpy().astype(np.int64)
                coeff=cf[blocks].cpu().numpy().astype(np.int64);ex=self.ex[blocks].cpu().numpy().astype(np.int64)
                G=c.shape[-1]//64;hi=hs.reshape(4,G,64).max(-1);lo=hs.reshape(4,G,64).min(-1);parts=[]
                assert (hi-lo).max()<=2
                for k in range(G):
                    local=(cs[:,k*64:(k+1)*64]<<(hi[:,k,None]-hs[:,k*64:(k+1)*64]))*ss[:,k*64:(k+1)*64]
                    parts.append(local@ws[:,k*64:(k+1)*64].T)
                ref=result[rowidx][:,cols].contiguous();chosen_ex=self.ex[blocks].contiguous()
                z=dict(parts=np.stack(parts),hi=hi,minimum_shift=lo,coeff=coeff,ex=ex,reference=ref.cpu().numpy(),
                       samples=np.array(T),R=np.array(R),role=np.array(role),layer=np.array(len(rows)//2),
                       rows=rowidx.cpu().numpy(),columns=cols.cpu().numpy(),g_cap=np.array(onebit.CAPS['g']),u_cap=np.array(onebit.CAPS['u']))
                if role=='GU':z['reference_fp32']=sf.finish_fp32(ref,chosen_ex,T,R).cpu().numpy()
                else:z['reference_bf16']=sf.finish_bf16(ref,chosen_ex-R,T).view(torch.int16).cpu().numpy().view(np.uint16)
                path=a.output/'trace'/('%02d_%s.npz'%(len(rows)//2,role));np.savez_compressed(path,**z)
                zrow=evaluate(z);zrow['layer']=len(rows)//2;rows.append(zrow)
                traces.append(dict(name=path.name,sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
                save(a.output/'PROGRESS.json',dict(status='running',completed_cases=len(rows),summary=summarize(rows)))
                return result
            sf.exact_coefficients=coefficients;wide_wd.shifted_output=output;return self
        def __exit__(self,*exc):sf.exact_coefficients=self.old_coeff;wide_wd.shifted_output=self.old_output
    c=frozen.case(64);patch=SamplingOverride(c);patch.configure(modules)
    ids=torch.as_tensor(tokens[:128].astype('int64'),device='cuda')[None]
    context.seed=101;context.begin(0,0,domain='fp24-real-crossK-diagnostic')
    with Capture(),patch,frozen.XOnebitOverride(True),torch.no_grad():
        logits=model(ids,use_cache=False).logits.detach()
    assert len(rows)==72 and len(context.coverage)==36 and bool(torch.isfinite(logits).all())
    save(a.output/'RESULT.json',dict(status='completed',scope='real 128-token FFN traces; sampled outputs, complete K; not FP24 model PPL',
         source=own_manifest,original_numeric_commit=mf['git_commit'],identity=identity,protocol=protocol,BF16_full=bf,
         seed=101,cases=rows,summary=summarize(rows),traces=traces,rows=[0,1,64,127],
         tokens_sha256=hashlib.sha256(tokens[:128].astype('<u4').tobytes()).hexdigest(),
         format=dict(FP24='E8/M15,p16,RNE',BF16='E8/M7,p8,RNE',tiny='exact nonzero magnitude below 2^-126 flushes before RNE',
                     overflow='saturate; count; not valid if any occurs',roundings='Q(tile), then Q(accumulator+Q(tile))'),
         no_training=True,no_PPA=True,no_defaults_changed=True,job=os.environ['SLURM_JOB_ID']))

if __name__=='__main__':main()
