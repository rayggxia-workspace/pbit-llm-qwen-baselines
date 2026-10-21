"""Independent p-bit proposals with exact empty-reference correction.

This is a new categorical rejection sampler, NOT parallel Gibbs/Ising evolution.
No digital exp/sum/normalization is required by the proposed hardware: sigmoid
here models the ideal p-bit response. Independence and calibrated response are
assumptions, not verified physical properties. No measured clocks/PPA.
"""
import numpy as np
from sampler import sigmoid


def rejection_indices(logits,samples=64,seed=0,rng=None,max_trials_per_sample=64,
                      adaptive=True,initial_shift=0,max_shift=24,strict=True):
    z=np.asarray(logits,dtype=np.float64)
    if z.ndim!=2 or not min(z.shape) or np.isnan(z).any() or np.isposinf(z).any():
        raise ValueError('nonempty 2D finite logits/-inf padding required')
    valid=np.isfinite(z)
    if not valid.any(1).all():raise ValueError('every row needs a finite logit')
    for v in [samples,max_trials_per_sample]:
        if type(v) is not int or v<1:raise ValueError('positive integer budget required')
    if not 0<=initial_shift<=max_shift<=24:raise ValueError('shift out of supported range')
    rng=np.random.default_rng(seed) if rng is None else rng
    rows,width=z.shape;ref=z.argmax(1);d=z-z[np.arange(rows),ref,None]
    valid[np.arange(rows),ref]=False
    shift=np.full(rows,initial_shift,dtype=np.int32)
    out=np.full((rows,samples),-1,dtype=np.int64);n=np.zeros(rows,dtype=np.int32)
    trials=np.zeros(rows,dtype=np.int64);collision=trials.copy();zero_reject=trials.copy()
    ref_accept=trials.copy();site_draws=0;peak_shift=initial_shift
    global_phases=0;empty_coin_fair_bits=0
    budget=samples*max_trials_per_sample
    for phase in range(budget):
        rr=np.flatnonzero((n<samples)&(trials<budget))
        if not len(rr):break
        global_phases+=1
        m=shift[rr];r=np.exp2(-m.astype(float))
        # ALL candidate p-bits propose independently, without old within-block
        # mutual inhibition; only accepted zero/one states are committed.
        q=sigmoid(d[rr]-m[:,None]*np.log(2.))
        bits=(rng.random(q.shape)<q)&valid[rr]
        count=bits.sum(1);trials[rr]+=1;site_draws+=int(valid[rr].sum())
        single=count==1;empty=count==0
        empty_coin_fair_bits+=int(m[empty].sum())
        accept_ref=empty&(rng.random(len(rr))<r)
        take=single|accept_ref;chosen=rr[take]
        address=np.where(accept_ref,ref[rr],bits.argmax(1))
        out[chosen,n[chosen]]=address[take];n[chosen]+=1
        ref_accept[rr[accept_ref]]+=1
        collision[rr[count>1]]+=1;zero_reject[rr[empty&~accept_ref]]+=1
        if adaptive:
            shift[rr[count>1]]=np.minimum(m[count>1]+1,max_shift)
            shift[rr[empty&~accept_ref]]=np.maximum(m[empty&~accept_ref]-1,0)
        peak_shift=max(peak_shift,int(shift.max()))
    pairs=(out[:,1:]>=0)&(out[:,:-1]>=0)
    stats=dict(kind='independent_parallel_proposals_corrected_rejection',
        samples=samples,candidates=width,rows=rows,logical_blocks=1,adaptive=adaptive,
        completed_rows=int((n==samples).sum()),failed=bool((n<samples).any()),
        collected_min=int(n.min()),proposal_trials_per_row=trials.tolist(),
        collision_retries_per_row=collision.tolist(),empty_retries_per_row=zero_reject.tolist(),
        reference_accepts_per_row=ref_accept.tolist(),final_shift=shift.tolist(),peak_shift=peak_shift,
        mean_trials_per_address=float(trials.sum()/max(1,n.sum())),
        global_proposal_phases=global_phases,independent_site_draws=site_draws,
        needed_fair_bits_for_empty_correction=empty_coin_fair_bits,
        adjacent_repeat_fraction=float((((out[:,1:]==out[:,:-1])&pairs).sum())/max(1,pairs.sum())),
        trial_budget_per_row=budget,iid_fallback=False,
        physical_PPA=None,time_unit='proposal rounds, not measured clock cycles',
        ideal_law='exact softmax on acceptance; fresh independent ideal p-bit proposals and correction coin')
    if strict and stats['failed']:raise RuntimeError('rejection trial cap; no fallback: '+str(stats))
    return out,stats
