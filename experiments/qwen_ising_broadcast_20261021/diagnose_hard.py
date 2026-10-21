"""Hard-inhibition versus kappa16, same real rows/seeds/scheduling. No new PPL."""
import argparse,json,hashlib,time
from pathlib import Path
import numpy as np
from sampler import sample_indices


def main():
    p=argparse.ArgumentParser();p.add_argument('--capture',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    src=Path(a.capture);raw=np.load(src)
    z=np.concatenate([raw[f'layer_{i}'][:14] for i in (0,12,23)])
    target=np.exp(z-np.logaddexp.reduce(z,axis=1)[:,None]);refs=z.argmax(1)
    rows=[];before=time.time()
    for b,q in [(0,1.),(64,1.),(16,1.),(4,1.),(64,.125)]:
        for seed in (0,1,2):
            finite,fs=sample_indices(z,64,kappa=16,block=b,enable=q,seed=seed,max_slots=256,strict=False)
            hard,hs=sample_indices(z,64,kappa=16,block=b,enable=q,seed=seed,max_slots=256,strict=False,hard_inhibit=True)
            valid=hard>=0
            ref=(hard==refs[:,None])&valid
            row=dict(block=b,enable=q,seed=seed,hard_stats=hs,finite_stats=fs,
                fraction_addresses_identical=float((finite==hard).mean()),
                mean_reference_probability=float((ref.sum(1)/valid.sum(1).clip(1)).mean()),
                mean_target_reference_probability=float(target[np.arange(len(z)),refs].mean()))
            rows.append(row);print(json.dumps({k:v for k,v in row.items() if k not in ['hard_stats','finite_stats']}),flush=True)
    result=dict(issue=78,capture_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),rows=len(z),
        source='42 real Qwen logit rows, CPU replay only; no new model PPL',results=rows,
        elapsed_seconds=time.time()-before,source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('*.py')})
    with Path(a.output).open('x',encoding='utf-8',newline='\n') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')

if __name__=='__main__':main()
