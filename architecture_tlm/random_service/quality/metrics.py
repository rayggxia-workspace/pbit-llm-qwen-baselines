import numpy as np


def corr(a, b):
    a = np.asarray(a, dtype=float); b = np.asarray(b, dtype=float)
    a = a-a.mean(); b = b-b.mean()
    d = np.sqrt(np.sum(a*a)*np.sum(b*b))
    return float(np.sum(a*b)/d) if d else None


def bit_metrics(bits):
    x = np.asarray(bits, dtype=np.uint8).reshape(-1)
    if len(x) < 2 or np.any(x > 1):
        raise ValueError('at least two binary samples required')
    p = float(x.mean())
    result = dict(n=len(x), p1=p, bias=p-.5,
                  rho={str(k):corr(x[:-k], x[k:]) for k in (1,2,4,8,16,32,64,128) if k<len(x)},
                  transition_fraction=float(np.mean(x[:-1] != x[1:])), windows={})
    for t in (32,128):
        n = len(x)//t
        if n < 2: continue
        means = x[:n*t].reshape(n,t).mean(axis=1)
        var = float(means.var(ddof=1))
        result['windows'][str(t)] = dict(blocks=n, variance=var,
            variance_over_iid_at_empirical_p=var/(p*(1-p)/t) if 0<p<1 else None,
            mse_to_half=float(np.mean((means-.5)**2)), discarded=len(x)-n*t)
    # Marginal collision diagnostic only; not an entropy rate estimate.
    result['marginal_min_entropy_only'] = float(-np.log2(max(p,1-p)))
    return result


def word_metrics(words):
    w = np.asarray(words,dtype=np.uint8)
    if w.ndim != 2: raise ValueError('frames x lanes required')
    n, lanes = w.shape
    hist = np.stack([np.bincount(w[:,i],minlength=256) for i in range(lanes)])
    cdf_error = np.cumsum(hist,axis=1)/n - np.arange(1,257)/256
    b = w < 128
    pairs = [(i,j) for i in range(lanes) for j in range(i+1,lanes)]
    c = np.corrcoef(b.astype(float),rowvar=False) if lanes>1 else None
    vals = [float(c[i,j]) for i,j in pairs if np.isfinite(c[i,j])]
    qs = (0,1,16,32,64,96,128,160,192,224,240,255,256)
    response = [dict(q=q,target=q/256,mean=float((w<q).mean()),
                     worst_lane_abs_error=float(np.max(np.abs((w<q).mean(axis=0)-q/256)))) for q in qs]
    return dict(frames=n,lanes=lanes,first_lane=bit_metrics(b[:,0]),
        worst_lane_cdf_error=float(np.max(np.abs(cdf_error))),
        max_abs_same_cycle_lane_rho=max(map(abs,vals),default=None),tested_pairs=len(pairs),
        undefined_pairs=len(pairs)-len(vals),response=response,
        first_lane_word_histogram=hist[0].tolist(),
        bitplane_p1=[float(((w>>k)&1).mean()) for k in range(8)],
        caveat='finite-sample diagnostics; max over many comparisons; no pass threshold or IID proof')


def probes(a,b):
    a=np.asarray(a);b=np.asarray(b)
    # Independent-endpoint AND assumption vs illegal shared-word counterexample.
    x=a[:,0]<64; y=b[:,0]<192; shared=a[:,0]<192
    same=np.mean(x & shared); independent=np.mean(x & y)
    # K32 FFN input encoding only, fixed signed W8 toy reduction, no complete FFN/PPL.
    q=np.arange(2,256,4,dtype=np.int32)
    weight=((np.arange(64)*37)%255-127).astype(float)
    t=(np.arange(len(a))%32)*8+(a[:,0]&7)
    masks=t[:,None]<q[None,:]
    groups=len(a)//32
    estimate=(masks[:groups*32].reshape(groups,32,64).mean(axis=1)*weight).sum(axis=1)
    target=float((q/256*weight).sum())
    # A shared Bernoulli frame cannot be judged by P1 alone.
    one=a<64
    expected_single=float(a.shape[1]*.25*.75**(a.shape[1]-1))
    return dict(and_target=.25*.75,and_measured=float(independent),
        and_error=float(independent-.25*.75),shared_word_and=float(same),shared_word_theory=.25,
        endpoint_first_word_match=float(np.mean(a[:,0]==b[:,0])),
        endpoint_first_bit_rho=corr(a[:,0]<128,b[:,0]<128),
        ffn_toy=dict(K=32,inputs=64,windows=groups,target=target,
            bias=float(estimate.mean()-target),rmse=float(np.sqrt(np.mean((estimate-target)**2)))),
        proposal_frame=dict(lanes=a.shape[1],q=64,one_hit_rate=float(np.mean(one.sum(axis=1)==1)),
            iid_one_hit_reference=expected_single,all_zero_rate=float(np.mean(one.sum(axis=1)==0)),
            iid_all_zero_reference=float(.75**a.shape[1])))
