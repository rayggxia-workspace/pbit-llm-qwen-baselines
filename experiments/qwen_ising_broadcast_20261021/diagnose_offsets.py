"""Offset presets/reuse for corrected rejection. No model PPL or hardware PPA."""
import argparse,json,hashlib,time
from pathlib import Path
import numpy as np
from rejection_sampler import rejection_indices


def main():
    p=argparse.ArgumentParser();p.add_argument('--capture',required=True)
    p.add_argument('--prior',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    capture=Path(a.capture);prior_path=Path(a.prior);prior=json.loads(prior_path.read_text())
    assert hashlib.sha256(capture.read_bytes()).hexdigest()==prior['capture_sha256']
    data=np.load(capture);real=np.concatenate([data[f'layer_{i}'][:14] for i in (0,12,23)])
    profiles=dict(real512=real,flat2000=np.zeros((4,2000)),
        peaked2000=np.tile(np.r_[0.,np.full(1999,-20.)],(4,1)))
    strategies=[('adaptive0',True,0),('adaptive2',True,2),('adaptive11',True,11),
                ('fixed0',False,0),('fixed2',False,2),('fixed11',False,11),
                ('reuse_adaptive',True,None),('reuse_fixed',False,None)]
    rows=[];before=time.time()
    for profile,z in profiles.items():
        for samples in [1,64]:
            for seed in [0,1,2]:
                setup=next(r for r in prior['results'] if r['profile']==profile and r['samples']==64 and r['seed']==seed)
                for name,adaptive,initial in strategies:
                    if initial is not None:
                        out,s=rejection_indices(z,samples,seed=seed,adaptive=adaptive,initial_shift=initial,strict=False)
                        shift=np.full(len(z),initial)
                    else:
                        # Same-logit continuation only. Not a new-token trace or
                        # free setup: the preceding S64 service is indexed below.
                        shift=np.array(setup['stats']['final_shift']);pieces=[];ss=[]
                        for j,(row,m) in enumerate(zip(z,shift)):
                            x,t=rejection_indices(row[None],samples,seed=100000+seed*1000+j,
                                adaptive=adaptive,initial_shift=int(m),strict=False)
                            pieces.append(x);ss.append(t)
                        out=np.concatenate(pieces)
                        trials=[t['proposal_trials_per_row'][0] for t in ss]
                        got=int((out>=0).sum())
                        s=dict(failed=any(t['failed'] for t in ss),completed_rows=sum(t['completed_rows'] for t in ss),
                            collected_min=min(t['collected_min'] for t in ss),proposal_trials_per_row=trials,
                            mean_trials_per_address=sum(trials)/max(1,got),
                            final_shift=[t['final_shift'][0] for t in ss])
                    item=dict(profile=profile,samples=samples,seed=seed,strategy=name,
                        adaptive=adaptive,initial_shift=shift.tolist(),stats=s,
                        mean_trials_if_all_rows_complete=None if s['failed'] else s['mean_trials_per_address'],
                        prior_setup_mean_trials_per_address=setup['stats']['mean_trials_per_address'] if initial is None else None,
                        reuse_scope='identical logits after prior S64; marginal cost, not new-token evidence' if initial is None else None)
                    if not adaptive:
                        d=z-z.max(1)[:,None];w=np.exp(d);w[np.arange(len(z)),z.argmax(1)]=0.
                        r=np.exp2(-shift.astype(float))
                        logA=np.log(r)+np.log1p(w.sum(1))-np.log1p(r[:,None]*w).sum(1)
                        item['fixed_theoretical_log_expected_trials_per_row']=(-logA).tolist()
                    rows.append(item)
                    print(json.dumps({k:item[k] for k in ['profile','samples','seed','strategy','mean_trials_if_all_rows_complete']}),flush=True)
    result=dict(issue=78,scope='ideal offset replay; not PPL/PPA; reuse is same-logit continuation',
        capture_sha256=prior['capture_sha256'],prior_sha256=hashlib.sha256(prior_path.read_bytes()).hexdigest(),
        source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('*.py')},
        results=rows,elapsed_seconds=time.time()-before)
    with Path(a.output).open('x',encoding='utf-8',newline='\n') as f:
        json.dump(result,f,indent=2,allow_nan=False);f.write('\n')


if __name__=='__main__':main()
