"""GPU replay checks against a scalar winner-hold oracle, including all-zero."""
def gpu_gate():
    import numpy as np
    import torch
    from sampler import sample,thresholds
    results=[]
    rng=np.random.default_rng(1981112)
    for n in [1,127,255,2047]:
        z=np.tile(np.linspace(-3,3,n,dtype=np.float32),(4,1))
        scores=torch.from_numpy(z).cuda()
        _,t=thresholds(scores);p=t.cpu().numpy()/256
        u=rng.random((4,16,n),dtype=np.float32)
        u[:,0]=1  # Empty first proposal: cold winner0 must remain legal.
        if n>1:u[:,1]=0  # All-active proposal: prior winner must hold.
        raw=rng.integers(4096,2**32-1,(4,16),dtype=np.uint32)
        replay=(torch.from_numpy(u).cuda(),torch.from_numpy(raw.astype(np.int64)).cuda(),torch.zeros((4,16),device='cuda'))
        out,stats=sample(scores,16,'winner',seed=101,burn=0,replay=replay)
        expected=np.zeros((4,16),dtype=np.int64)
        for row in range(4):
            winner=0
            for step in range(16):
                active=np.flatnonzero(u[row,step]<p[row])
                if len(active) and winner not in active:
                    assert int(raw[row,step]) >= (2**32)%len(active)
                    winner=int(active[int(raw[row,step])%len(active)])
                expected[row,step]=winner
        assert np.array_equal(out.cpu().numpy(),expected)
        one,_=sample(scores,16,'winner',seed=71,burn=0)
        two,_=sample(scores,16,'winner',seed=71,burn=0)
        assert torch.equal(one,two)
        results.append(dict(n=n,scalar_replay=True,repeated_seed_equal=True))
    return dict(passed=True,checks=results)
