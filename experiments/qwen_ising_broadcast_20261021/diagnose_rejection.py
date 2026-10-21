"""Ideal parallel-proposal validation. CPU replay, no PPL or physical PPA."""
import argparse,json,hashlib,time
from pathlib import Path
import numpy as np
from rejection_sampler import rejection_indices


def main():
    p=argparse.ArgumentParser();p.add_argument('--capture',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    capture=Path(a.capture);data=np.load(capture)
    real=np.concatenate([data[f'layer_{i}'][:14] for i in (0,12,23)])
    profiles=dict(real512=real,flat2000=np.zeros((4,2000)),
        peaked2000=np.tile(np.r_[0.,np.full(1999,-20.)],(4,1)))
    records=[];before=time.time()
    for name,z in profiles.items():
        target=np.exp(z-np.logaddexp.reduce(z,axis=1)[:,None]);refs=z.argmax(1)
        for samples in [64,2048]:
            for seed in [0,1,2]:
                out,s=rejection_indices(z,samples,seed=seed,strict=False)
                if s['failed']:quality=dict(mean_row_tv=None,mean_reference_mass=None)
                else:
                    tv=[];mass=[]
                    for j,row in enumerate(out):
                        q=np.bincount(row,minlength=z.shape[1])/samples
                        tv.append(float(abs(q-target[j]).sum()/2));mass.append(float(q[refs[j]]))
                    quality=dict(mean_row_tv=float(np.mean(tv)),mean_reference_mass=float(np.mean(mass)))
                rng=np.random.default_rng(seed);iidtv=[];iidmass=[]
                for j,prob in enumerate(target):
                    x=rng.choice(z.shape[1],samples,p=prob/prob.sum())
                    q=np.bincount(x,minlength=z.shape[1])/samples
                    iidtv.append(float(abs(q-prob).sum()/2));iidmass.append(float(q[refs[j]]))
                r=dict(profile=name,samples=samples,seed=seed,stats=s,**quality,
                    target_reference_mass=float(target[np.arange(len(z)),refs].mean()),
                    iid64_or_2048_control_tv=float(np.mean(iidtv)),
                    iid64_or_2048_control_reference_mass=float(np.mean(iidmass)))
                records.append(r);print(json.dumps(r),flush=True)
    result=dict(issue=78,scope='ideal p-bit categorical proposal replay, not Ising Gibbs, PPL or physical timing',
        capture_path=str(capture),capture_sha256=hashlib.sha256(capture.read_bytes()).hexdigest(),
        source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('*.py')},
        results=records,elapsed_seconds=time.time()-before)
    with Path(a.output).open('x',encoding='utf-8',newline='\n') as f:
        json.dump(result,f,indent=2,allow_nan=False);f.write('\n')


if __name__=='__main__':main()
