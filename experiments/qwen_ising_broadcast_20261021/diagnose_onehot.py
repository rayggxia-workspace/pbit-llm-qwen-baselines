"""One-hot readout versus empty reference, same coarse block budget. No PPL."""
import argparse,hashlib,json,time
from pathlib import Path
import numpy as np
from sampler import sample_indices


def main():
    p=argparse.ArgumentParser();p.add_argument('--capture',required=True)
    p.add_argument('--case',choices=['real','flat2000'],required=True)
    p.add_argument('--output',required=True);a=p.parse_args()
    capture=Path(a.capture);data=np.load(capture)
    real=np.concatenate([data[f'layer_{i}'][:14] for i in (0,12,23)])
    z=real if a.case=='real' else np.zeros((4,2000))
    target=np.exp(z-np.logaddexp.reduce(z,axis=1)[:,None]);refs=z.argmax(1)
    records=[];started=time.time()
    for blocks in [2,4,8,16,32]:
        block=(z.shape[1]+blocks-1)//blocks
        for encoding in ['empty_reference','one_hot']:
            for seed in [0,1,2]:
                out,s=sample_indices(z,64,block=block,seed=seed,hard_inhibit=True,
                    encoding=encoding,max_slots=256,strict=False)
                tv=[];mass=[]
                for j,row in enumerate(out):
                    valid=row[row>=0]
                    if not len(valid):tv.append(None);mass.append(None);continue
                    q=np.bincount(valid,minlength=z.shape[1])/len(valid)
                    tv.append(float(abs(q-target[j]).sum()/2));mass.append(float(q[refs[j]]))
                # An incomplete service is not counted as a successful distribution.
                q=dict(mean_row_tv=float(np.mean(tv)) if all(v is not None for v in tv) else None,
                    mean_maximum_mass=float(np.mean(mass)) if all(v is not None for v in mass) else None,
                    target_maximum_mass=float(target[np.arange(len(z)),refs].mean()),
                    rows_with_no_address=sum(v is None for v in tv),
                    diagnostics_of_partial_service=bool(s['failed']))
                r=dict(requested_blocks=blocks,actual_blocks=(z.shape[1]+block-1)//block,
                    block_nodes=block,seed=seed,**q,stats=s)
                records.append(r);print(json.dumps(r),flush=True)
    result=dict(issue=78,case=a.case,source='logit replay only, no new model PPL or RTL/PPA',
        capture_path=str(capture),capture_sha256=hashlib.sha256(capture.read_bytes()).hexdigest(),
        rows=len(z),candidates=z.shape[1],results=records,elapsed_seconds=time.time()-started,
        source_sha256={f.name:hashlib.sha256(f.read_bytes()).hexdigest()
                       for f in Path(__file__).parent.glob('*.py')})
    with Path(a.output).open('x',encoding='utf-8',newline='\n') as f:
        json.dump(result,f,indent=2,allow_nan=False);f.write('\n')


if __name__=='__main__':main()
