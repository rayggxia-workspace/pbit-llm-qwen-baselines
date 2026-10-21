"""CPU-only finite-kappa/full-sync/random-partition diagnostics, no fake PPL."""
import argparse,json,math,time,hashlib
from pathlib import Path
import numpy as np
from sampler import sample_indices,finite_equilibrium


def metrics(addresses,z):
    p=np.exp(z-z.max());p/=p.sum();a=addresses[addresses>=0]
    if not len(a):return dict(tv=None,normalized_mean_index=None)
    q=np.bincount(a,minlength=len(z))/len(a)
    return dict(tv=float(abs(q-p).sum()/2),target_ref_probability=float(p[z.argmax()]),
        empirical_ref_probability=float(q[z.argmax()]))


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--quick',action='store_true');p.add_argument('--reference',action='store_true');a=p.parse_args()
    rows=[];started=time.time()
    for n in ([32,512] if a.quick else [32,512,2000]):
        for shape in ['flat','ramp','peaked']:
            z=(np.zeros(n) if shape=='flat' else np.linspace(-8,0,n))
            if shape=='peaked':z=np.r_[0.,np.full(n-1,-8.)]
            if a.reference:
                import sys
                sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
                import torch
                from experiments.qwen_joint_stratified_attention_20261019.upstream_attention.ctmc import ct_mc_indices
                for seed in [0,1,2]:
                    out,st=ct_mc_indices(torch.tensor(np.tile(z,(16,1))),64,16.,4.,generator=torch.Generator().manual_seed(seed))
                    rows.append(dict(N=n,shape=shape,seed=seed,kind='unchanged_CTMC_S64',**metrics(out.numpy(),z),stats=st))
                    out=np.random.default_rng(seed).choice(n,(16,64),p=np.exp(z-np.logaddexp.reduce(z)))
                    rows.append(dict(N=n,shape=shape,seed=seed,kind='IID_softmax_S64_control',**metrics(out,z)))
            for k in [8.,12.,16.]:
                eq=finite_equilibrium(z,k)
                for block,enable in [(0,1.),(64,1.),(16,1.),(4,1.),(64,.125)]:
                    if block>n:continue
                    for seed in [0,1,2]:
                        t=time.time()
                        out,s=sample_indices(np.tile(z,(16,1)),64,kappa=k,block=block,
                            burn=16,spacing=4,seed=seed,max_slots=128,enable=enable,strict=False)
                        r=dict(N=n,shape=shape,seed=seed,**s,**eq,**metrics(out,z),seconds=time.time()-t)
                        rows.append(r)
                        print(json.dumps({q:r[q] for q in ['N','shape','kappa','block','seed','failed','invalid_fraction','tv']},allow_nan=False),flush=True)
    result=dict(issue=78,source='synthetic logits, CPU behavior; not LLM PPL',
        seeds=[0,1,2],samples=64,results=rows,elapsed_seconds=time.time()-started,
        source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('*.py')})
    out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('x',encoding='utf-8',newline='\n') as f:json.dump(result,f,indent=2);f.write('\n')

if __name__=='__main__':main()
