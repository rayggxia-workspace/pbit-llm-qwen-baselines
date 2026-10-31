"""Exact event-class CR law in float64; no model/quantization changes."""
import itertools,math
import numpy as np

def encode(z,lut):
    raw=np.rint(np.asarray(z,dtype=np.float64)*16)
    q=np.clip(raw,-2048,2047).astype(np.int64)
    ref=int(q.argmax());gap=q[ref]-q
    threshold=np.asarray(lut)[np.minimum(gap,255)]
    prob=threshold/256.
    odds=prob/(1-prob);pi=odds/odds.sum()
    return q,ref,gap,threshold,pi

def event_law(z,lut,m_table):
    q,ref,gap,threshold,pi=encode(z,lut)
    others=np.arange(len(q))!=ref
    a=np.minimum(gap[others][None,:]+np.asarray(m_table)[:,None],255)
    p=np.asarray(lut)[a]/256.
    odds=p/(1-p)
    # Some probabilities below float64's representable range underflow to zero.
    # These are event-class numeric probabilities, not altered P8 thresholds.
    p0=np.exp(np.log1p(-p).sum(1));single=p0[:,None]*odds
    p1=single.sum(1);reference=p0*np.exp2(-np.arange(25))
    up=np.maximum(0.,1-p0-p1);down=p0-reference
    F=np.zeros((25,25));emission=np.zeros((25,len(q)))
    for m in range(25):
        F[m,min(m+1,24)]+=up[m]
        F[m,max(m-1,0)]+=down[m]
    emission[:,others]=single;emission[:,ref]=reference
    assert np.allclose(F.sum(1)+emission.sum(1),1,atol=1e-13)
    return dict(ref=ref,q=q,gap=gap,threshold=threshold,pi=pi,F=F,E=emission,
                p0=p0,p1=p1,reference=reference,up=up,down=down)

def expected(z,lut,m_table,S=128,value=None):
    e=event_law(z,lut,m_table);F=e['F'];accept=e['E'].sum(1)
    fundamental=np.linalg.solve(np.eye(25)-F,np.eye(25))
    U=fundamental*accept[None,:]
    assert np.max(abs(U.sum(1)-1))<1e-7
    dist=np.zeros(25);dist[0]=1.;visits=np.zeros(25)
    for _ in range(S):
        visits+=dist@fundamental;dist=dist@U
    hist=visits@e['E']/S
    assert abs(hist.sum()-1)<1e-7 and hist.min()>-1e-10
    hist=np.maximum(hist,0);hist/=hist.sum()
    z=np.asarray(z,dtype=np.float64);target=np.exp(z-z.max());target/=target.sum()
    qz=e['q']/16.;quant_target=np.exp(qz-qz.max());quant_target/=quant_target.sum()
    result=dict(candidates=len(z),S=S,ref=e['ref'],expected_trials_uncapped=float(visits.sum()),
        expected_reference_fraction_uncapped=float(hist[e['ref']]),target_reference_probability=float(target[e['ref']]),
        p8_odds_reference_probability=float(e['pi'][e['ref']]),
        mean_histogram_tv_vs_softmax=float(.5*abs(hist-target).sum()),
        mean_histogram_tv_vs_P8_odds=float(.5*abs(hist-e['pi']).sum()),
        P8_odds_tv_vs_softmax=float(.5*abs(e['pi']-target).sum()),
        P8_odds_tv_vs_score_quantized_softmax=float(.5*abs(e['pi']-quant_target).sum()),
        zeroed_softmax_mass=float(target[e['threshold']==0].sum()),
        zero_threshold_fraction=float(np.mean(e['threshold']==0)),
        source_score_saturation=int(np.sum((z*16).round()!=e['q'])),gap_saturation=int(np.sum(e['gap']>255)),
        target_entropy=float(-(target*np.log(np.maximum(target,1e-300))).sum()))
    if value is not None:
        v=np.asarray(value,dtype=np.float64);exact=target@v;p8=e['pi']@v;cr=hist@v
        denom=max(float(np.linalg.norm(exact)),1e-30)
        result.update(P8_expected_V_relative_L2=float(np.linalg.norm(p8-exact)/denom),
            CR_uncapped_expected_V_relative_L2=float(np.linalg.norm(cr-exact)/denom),
            exact_V=exact.tolist(),P8_expected_V=p8.tolist(),CR_uncapped_expected_V=cr.tolist())
    return result,e,hist,target

def capped_mc(laws,S=128,replicas=32,seeds=(101,102,103)):
    """No destination histogram: exact probability of each event class suffices.

    Completed runs and partial failed runs are separated; never refill/fallback.
    """
    p0=np.stack([x['p0'] for x in laws]);p1=np.stack([x['p1'] for x in laws]);ref=np.stack([x['reference'] for x in laws]);n=len(laws)
    complete=np.zeros(n,dtype=np.int64);reference_done=np.zeros(n,dtype=np.int64)
    trial_done=np.zeros(n,dtype=np.int64);partial_accepted=np.zeros(n,dtype=np.int64);partial_ref=np.zeros(n,dtype=np.int64)
    byseed=[]
    for seed in seeds:
        rng=np.random.default_rng(seed);m=np.zeros((n,replicas),dtype=np.int16)
        accepted=np.zeros_like(m);refs=np.zeros_like(m);trials=np.zeros((n,replicas),dtype=np.int32)
        for _ in range(S*64):
            row,col=np.nonzero(accepted<S)
            if not len(row):break
            mm=m[row,col];u=rng.random(len(row));P0=p0[row,mm];P1=p1[row,mm];R=ref[row,mm]
            r=u<R;single=(u>=P0)&(u<P0+P1);down=(u>=R)&(u<P0);up=u>=P0+P1
            accepted[row,col]+=r|single;refs[row,col]+=r;trials[row,col]+=1
            m[row,col]=np.clip(mm+up.astype(np.int16)-down.astype(np.int16),0,24)
        done=accepted==S;complete+=done.sum(1)
        reference_done+=np.where(done,refs,0).sum(1);trial_done+=np.where(done,trials,0).sum(1)
        partial_accepted+=np.where(~done,accepted,0).sum(1);partial_ref+=np.where(~done,refs,0).sum(1)
        byseed.append(dict(seed=seed,replicas=replicas,completed=int(done.sum()),attempts=n*replicas))
    reps=replicas*len(seeds)
    rows=[dict(replicas=reps,completed=int(complete[i]),failed=int(reps-complete[i]),completion_fraction=float(complete[i]/reps),
        mean_trials_completed=float(trial_done[i]/complete[i]) if complete[i] else None,
        reference_fraction_completed=float(reference_done[i]/(S*complete[i])) if complete[i] else None,
        accepted_samples_in_failed_runs=int(partial_accepted[i]),reference_samples_in_failed_runs=int(partial_ref[i]),cap=S*64) for i in range(n)]
    return rows,byseed

def unit(lut,m_table):
    assert list(lut)==[round(256/(1+math.exp(a/16))) for a in range(256)]
    for z in [np.zeros(4),np.array([0.,-1.,-2.,-7.])]:
        e=event_law(z,lut,m_table);ref=e['ref'];others=np.arange(len(z))!=ref
        for m in [0,4,8,9,24]:
            p=np.asarray(lut)[np.minimum(e['gap'][others]+m_table[m],255)]/256.
            P0=P1=up=0.
            for bits in itertools.product([0,1],repeat=3):
                mass=float(np.prod([p[i] if b else 1-p[i] for i,b in enumerate(bits)]))
                if sum(bits)==0:P0+=mass
                elif sum(bits)==1:P1+=mass
                else:up+=mass
            assert abs(P0-e['p0'][m])<1e-13 and abs(P1-e['p1'][m])<1e-13 and abs(up-e['up'][m])<1e-13
    a,_,_,_=expected(np.zeros(2048),lut,m_table)
    assert abs(a['expected_trials_uncapped']-55473.501)<.01
    assert abs(a['expected_reference_fraction_uncapped']-.42315497)<1e-6
    uniform256,_,_,_=expected(np.zeros(256),lut,m_table)
    return dict(status='passed',exhaustive_pattern_checks=10,uniform2048=a,uniform256=uniform256,
        scope='independent event-class/absorbing-chain implementation and small exact-pattern oracle, not model/PPA')

def literal_check(z,lut,m_table,seed):
    e=event_law(z,lut,m_table);rng=np.random.default_rng(seed);others=np.arange(len(z))!=e['ref'];peak=int(e['p1'].argmax());records=[]
    for m in sorted({max(peak-1,0),peak,min(peak+1,24)}):
        threshold=np.asarray(lut)[np.minimum(e['gap'][others]+m_table[m],255)]
        words=rng.integers(0,256,size=(1024,len(threshold)),dtype=np.int16)
        count=(words<threshold).sum(1)
        ref=(count==0)&(rng.integers(0,1<<m,size=1024)==0)
        observed=[int((count==0).sum()),int((count==1).sum()),int(ref.sum())]
        prob=[e['p0'][m],e['p1'][m],e['reference'][m]]
        for got,p in zip(observed,prob):assert abs(got-1024*p)<=6*math.sqrt(1024*p*(1-p))+4
        records.append(dict(m=m,proposals=1024,zero=observed[0],single=observed[1],reference_accepted=observed[2],expected_probabilities=[float(p) for p in prob]))
    return records
