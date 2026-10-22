"""Ideal independent p-bit behavior kernels; software time is not chip time."""
import math
import numpy as np


def sigmoid(x):
    x=np.asarray(x,dtype=np.float64)
    return np.exp(-np.logaddexp(0.,-x))


def distribution(z):
    z=np.asarray(z,dtype=np.float64)
    if z.ndim!=1 or not len(z) or not np.isfinite(z).all():raise ValueError('finite nonempty row')
    w=np.exp(z-z.max());return w/w.sum()


def chains(z,steps,repeats,rng,method,shift=0.,drive_step=None):
    """All chains start at argmax; every completed update, including holds, is output.

    A p-bit draw means ideal Bernoulli device service, not a PRNG word. Bounded
    integer bit costs are theoretical expected fair-bit counts using rejection.
    Only current-state dependence is serial; parallel candidate generation is
    independent of winner state for fixed scores/bias.
    """
    z=np.asarray(z,dtype=np.float64);distribution(z)
    if min(steps,repeats)<1:raise ValueError('positive budget')
    n=len(z);state=np.full(repeats,z.argmax(),dtype=np.int32)
    out=np.empty((repeats,steps),dtype=np.int32)
    fair=np.zeros((repeats,steps+1),dtype=np.float64)
    rank=np.zeros_like(fair);switch=np.zeros((repeats,steps+1),dtype=np.int32)
    def drive(a):
        if drive_step is None:return a
        # Nonpositive 8-bit magnitude, sign supplied by score difference for Barker.
        return np.sign(a)*np.minimum(np.rint(np.abs(a)/drive_step),255)*drive_step
    p=sigmoid(drive(z-z.max()-shift))
    width=(n-1).bit_length();index_fair=width*(2**width/n)
    if method not in ('winner_hold','two_bits','barker','xor'):raise ValueError(method)
    for t in range(steps):
        previous=state.copy();extra=np.zeros(repeats);calls=np.zeros(repeats)
        if method=='winner_hold':
            bits=rng.random((repeats,n))<p
            counts=bits.sum(1);valid=np.flatnonzero(counts)
            chosen=state.copy()
            if len(valid):
                row,col=np.nonzero(bits)
                starts=np.cumsum(counts)-counts
                ranks=rng.integers(0,counts[valid])
                chosen[valid]=col[starts[valid]+ranks]
                k=np.ceil(np.log2(counts[valid])).astype(int)
                extra[valid]=k*(np.exp2(k)/counts[valid])
                calls[valid]=(counts[valid]>1)
            stay=bits[np.arange(repeats),state]
            state=np.where(stay|~counts.astype(bool),state,chosen)
        else:
            if method=='xor':
                challenger=state^(1<<(t%max(width,1)))
                valid=challenger<n;safe=np.minimum(challenger,n-1)
            else:
                challenger=rng.integers(0,n,size=repeats)
                valid=np.ones(repeats,dtype=bool);safe=challenger
                extra[:]=index_fair
            if method=='two_bits':
                accept=(rng.random(repeats)>=p[state])&(rng.random(repeats)<p[safe])
            else:accept=rng.random(repeats)<sigmoid(drive(z[safe]-z[state]))
            state=np.where(valid&accept,safe,state)
        out[:,t]=state
        fair[:,t+1]=fair[:,t]+extra
        rank[:,t+1]=rank[:,t]+calls
        switch[:,t+1]=switch[:,t]+(state!=previous)
    return out,dict(kind=method,shift=shift,drive_step=drive_step,pbit_draws_per_update=n if method=='winner_hold' else 2 if method=='two_bits' else 1,
                    fair_bit_prefix=fair,rank_call_prefix=rank,switch_prefix=switch,
                    time_unit='completed algorithm updates, not measured hardware clocks',
                    initialization='maximum-logit address',independent_ideal_response=True)


def corrected_rejection(z,samples,repeats,rng,max_trials_per_sample=64):
    """Same RNG/update order as the existing reference, with prefix cost receipts."""
    z=np.broadcast_to(np.asarray(z,dtype=np.float64),(repeats,len(z))).copy()
    rows,width=z.shape;ref=z.argmax(1);d=z-z[np.arange(rows),ref,None]
    valid=np.ones_like(z,dtype=bool);valid[np.arange(rows),ref]=False
    shift=np.zeros(rows,dtype=np.int32);n=np.zeros(rows,dtype=np.int32)
    out=np.full((rows,samples),-1,dtype=np.int32)
    trials=np.zeros(rows,dtype=np.int64);coin=np.zeros(rows,dtype=np.int64)
    phase_at=np.zeros((rows,samples),dtype=np.int64);coin_at=phase_at.copy()
    budget=samples*max_trials_per_sample;failed=False
    for phase in range(budget):
        rr=np.flatnonzero((n<samples)&(trials<budget))
        if not len(rr):break
        m=shift[rr];r=np.exp2(-m.astype(float))
        q=sigmoid(d[rr]-m[:,None]*np.log(2.))
        bits=(rng.random(q.shape)<q)&valid[rr];count=bits.sum(1)
        trials[rr]+=1;single=count==1;empty=count==0;coin[rr]+=m*empty
        accept_ref=empty&(rng.random(len(rr))<r);take=single|accept_ref
        address=np.where(accept_ref,ref[rr],bits.argmax(1));chosen=rr[take]
        out[chosen,n[chosen]]=address[take]
        phase_at[chosen,n[chosen]]=trials[chosen];coin_at[chosen,n[chosen]]=coin[chosen]
        n[chosen]+=1
        shift[rr[count>1]]=np.minimum(m[count>1]+1,24)
        shift[rr[empty&~accept_ref]]=np.maximum(m[empty&~accept_ref]-1,0)
    failed=bool((n<samples).any())
    if failed:raise RuntimeError('rejection cap reached; no fallback or partial trajectory')
    return out,dict(kind='corrected_rejection',proposal_phase_at=phase_at,empty_coin_at=coin_at,
                    pbit_draws_per_proposal=width-1,time_unit='proposal frames, not clock cycles',
                    initialization='adaptive shift m0; no Markov burn required')


def output_metrics(indices,z,v,burns,budgets):
    """Exact V-mean error; IID variance is analytic, not a noisy sampled reference."""
    indices=np.asarray(indices);v=np.asarray(v,dtype=np.float64);pi=distribution(z)
    if v.ndim!=2 or v.shape[0]!=len(pi) or not np.isfinite(v).all():raise ValueError('V shape/finite')
    if indices.ndim!=2 or (indices<0).any() or (indices>=len(pi)).any():raise ValueError('address outside V')
    mu=pi@v;centered=v-mu
    variance=float(pi@np.square(centered).sum(1))
    requests=[(b,s) for b in burns for s in budgets if b>=0 and s>0 and b+s<=indices.shape[1]]
    cuts=sorted({0}|{b for b,s in requests}|{b+s for b,s in requests})
    rows=len(indices);counts=np.zeros((rows,len(pi)),dtype=np.int64)
    prefix={0:np.zeros((rows,v.shape[1]),dtype=np.float64)};prev=0
    offsets=np.arange(rows)[:,None]*len(pi)
    for cut in cuts[1:]:
        counts+=np.bincount((indices[:,prev:cut]+offsets).reshape(-1),minlength=rows*len(pi)).reshape(rows,len(pi))
        prefix[cut]=counts@v;prev=cut
    results=[]
    for burn,s in requests:
        estimates=(prefix[burn+s]-prefix[burn])/s
        errors=np.square(estimates-mu).sum(1)
        results.append(dict(burn=burn,samples=s,total_updates=burn+s,
            squared_error_per_repeat=errors.tolist(),
            normalized_error_per_repeat=(errors/variance).tolist() if variance>0 else [0.]*rows,
            iid_expected_squared_error=variance/s,
            mse=float(errors.mean()),normalized_mse=float(errors.mean()/variance) if variance>0 else 0.,
            variance_degenerate=variance==0))
    return results,dict(reference_output=mu.tolist(),iid_single_sample_variance=variance,
        entropy=float(-(pi*np.log(pi.clip(min=1e-300))).sum()),
        effective_categories=float(1/np.square(pi).sum()),top1=float(pi.max()),
        top2=float(np.sort(pi)[-2:].sum()),top8=float(np.sort(pi)[-8:].sum()))
