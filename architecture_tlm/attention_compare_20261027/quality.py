"""Exploratory same-full-output MSE budget curve; synthetic, not PPL acceptance."""
import argparse
from collections import defaultdict
import hashlib
from pathlib import Path
import numpy as np
from .core import bf16, compare
from .schedule import run
from .run import write, sha


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False)
    length,d=2048,128
    rng=np.random.default_rng(12345+length+d)
    q,k,v=[bf16(x) for x in (rng.normal(size=d),rng.normal(size=(length,d)),rng.normal(size=(length,d)))]
    input_sha=hashlib.sha256(b''.join(x.astype('<f8').tobytes() for x in (q,k,v))).hexdigest()
    records=[]
    for samples in (32,128,512,1024):
        for seed in (17,503,1009):
            for r in compare(q,k,v,samples,seed):
                if r['status']!='completed':
                    records.append(dict(mode=r['mode'],samples=samples,seed=seed,status=r['status']));continue
                timing=run(r,d)
                records.append(dict(mode=r['mode'],samples=samples,seed=seed,status='completed',
                    mse_full=r['squared_error_full'],mse_screen=r['squared_error_screen'],
                    mse_sampling=r['squared_error_sampling'],normalized_mse_sampling=r['normalized_mse_sampling'],
                    analytic_IID128_full_target=r['full_single_sample_variance']/128,
                    cycles=timing['cycles'],K_bytes=r['K_physical_bytes'],V_bytes=r['V_physical_bytes']))
    grouped=defaultdict(list)
    for r in records:grouped[r['mode'],r['samples']].append(r)
    grid=[]
    for (mode,samples),rows in grouped.items():
        success=all(r['status']=='completed' for r in rows)
        x=dict(mode=mode,samples=samples,status='completed' if success else 'cap_failure_retained')
        if success:
            for key in ('mse_full','mse_screen','mse_sampling','normalized_mse_sampling','cycles','K_bytes','V_bytes'):
                x[key+'_mean']=float(np.mean([r[key] for r in rows]))
                x[key+'_std']=float(np.std([r[key] for r in rows],ddof=1))
            x['IID128_target']=rows[0]['analytic_IID128_full_target']
            x['observed_three_seed_mean_meets_target']=x['mse_full_mean']<=x['IID128_target']
        grid.append(x)
    matched={mode:next((r for r in grid if r['mode']==mode and r.get('observed_three_seed_mean_meets_target')),None)
             for mode in ('D0','P0','P1','P2','P3','P4')}
    write(a.output/'QUALITY.json',dict(input_sha256=input_sha,shape=[length,d],seeds=[17,503,1009],
        rule='first tested budget with three-seed mean full-output MSE <= analytic full IID128 expected MSE',
        status='exploratory same synthetic input; no confidence/transfer/PPL acceptance',records=records,grid=grid,matched=matched,
        source={f.name:sha(f) for f in Path(__file__).parent.glob('*.py')}))
    print({k:None if v is None else dict(S=v['samples'],cycles=v['cycles_mean']) for k,v in matched.items()})


if __name__=='__main__':main()
