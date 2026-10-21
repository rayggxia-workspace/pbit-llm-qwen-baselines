"""Replay real Qwen logits captured by the unchanged CTMC64 pilot (CPU only)."""
import argparse,json,hashlib,time,sys
from pathlib import Path
import numpy as np
from sampler import sample_indices,finite_equilibrium


def main():
    p=argparse.ArgumentParser();p.add_argument('--capture',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    path=Path(a.capture);data=np.load(path)
    z=np.concatenate([data[f'layer_{i}'][:14] for i in (0,12,23)])
    target=np.exp(z-np.logaddexp.reduce(z,axis=1)[:,None])
    refs=z.argmax(1);rows=[];started=time.time()
    def quality(out):
        tv=[];ref=[]
        for j,ss in enumerate(out):
            ss=ss[ss>=0]
            if not len(ss):continue
            q=np.bincount(ss,minlength=z.shape[1])/len(ss)
            tv.append(float(np.abs(q-target[j]).sum()/2));ref.append(float(q[refs[j]]))
        return dict(mean_row_tv=float(np.mean(tv)) if tv else None,
            mean_empirical_reference_mass=float(np.mean(ref)) if ref else None,
            mean_target_reference_mass=float(target[np.arange(len(z)),refs].mean()))
    import torch
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
    from experiments.qwen_joint_stratified_attention_20261019.upstream_attention.ctmc import ct_mc_indices
    for seed in (0,1,2):
        out,stats=ct_mc_indices(torch.tensor(z,dtype=torch.float64),64,16.,4.,generator=torch.Generator().manual_seed(seed))
        rows.append(dict(method='unchanged_CTMC_S64',seed=seed,stats=stats,**quality(out.numpy())))
    for k in (8.,12.,16.):
        leakage=[finite_equilibrium(row,k)['equilibrium_invalid_fraction'] for row in z]
        for b,enable in [(0,1.),(64,1.),(16,1.),(4,1.),(64,.125)]:
            for seed in (0,1,2):
                out,s=sample_indices(z,64,kappa=k,block=b,enable=enable,seed=seed,max_slots=256,strict=False)
                rows.append(dict(method=f'parallel_B{b}_q{enable}',seed=seed,
                    equilibrium_leakage_mean=float(np.mean(leakage)),**s,**quality(out)))
                print(json.dumps({x:rows[-1].get(x) for x in ['method','seed','kappa','failed','invalid_fraction','mean_empirical_reference_mass','mean_target_reference_mass']}),flush=True)
    result=dict(issue=78,source='real CTMC pilot first-example logits from layers0/12/23; not model PPL',
        capture_path=str(path),capture_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        rows=int(len(z)),candidates=int(z.shape[1]),results=rows,elapsed_seconds=time.time()-started)
    out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('x',encoding='utf-8',newline='\n') as f:json.dump(result,f,indent=2);f.write('\n')

if __name__=='__main__':main()
