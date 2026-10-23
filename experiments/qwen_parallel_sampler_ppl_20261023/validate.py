"""GPU validation: independent trajectory oracle, padding, cap, distributions."""
import json
import numpy as np
import torch
from .kernels import sample,probabilities


def run():
    records=[]
    for seed in (0,1,2):
        rng=np.random.default_rng(seed)
        z=torch.tensor([[0.,-1.,2.,-3.,0.2,float('-inf'),-2.],
                        [0.,0.,0.,0.,0.,0.,0.],
                        [0.,float('-inf'),float('-inf'),float('-inf'),float('-inf'),float('-inf'),float('-inf')]],device='cuda')
        for method in ('winner','rejection'):
            s,burn=19,(7 if method=='winner' else 0)
            cap=s+burn if method=='winner' else s*128
            u=rng.random((3,cap,7)).astype('float32')
            ranks=rng.integers(1<<20,2**32,size=(3,cap),dtype=np.uint64).astype('int64')
            coin=rng.random((3,cap)).astype('float32')
            inputs=tuple(torch.as_tensor(x,device='cuda').contiguous() for x in (u,ranks,coin))
            actual,stats=sample(z,s,method,burn=burn,seed=seed,replay=inputs)
            p=probabilities(z,method).cpu().numpy()
            expected=[]; expected_stats=[]
            for row in range(3):
                ref=int(z[row].argmax());state=ref;m=0;out=[];coll=empty=refs=0
                for t in range(cap):
                    bits=u[row,t]<p[row,m];active=np.flatnonzero(bits);n=len(active)
                    if method=='winner':
                        if n and not bits[state]:state=int(active[int(ranks[row,t])%n])
                        if t>=burn:out.append(state)
                    else:
                        take_ref=n==0 and coin[row,t]<2.**(-m)
                        if n==1 or take_ref:out.append(ref if take_ref else int(active[0]))
                        if n>1:coll+=1;m=min(m+1,24)
                        if n==0 and not take_ref:empty+=1;m=max(m-1,0)
                        refs+=int(take_ref)
                    if len(out)==s:break
                expected.append(out);expected_stats.append([t+1,len(out),coll,empty,refs,m])
            assert actual.cpu().tolist()==expected,(method,seed,'trajectory')
            assert stats.cpu().tolist()==expected_stats,(method,seed,'activity')
            records.append(dict(check='independent_trajectory',method=method,seed=seed,rows=3,samples=s))
    # Independent scalar categorical expectation. Winner tests its finite-step
    # Markov law starting at argmax, not a false IID assumption.
    z=torch.tensor([[0.,.6,-.9]],device='cuda')
    p=torch.sigmoid(z-z.max()).cpu().numpy()[0]
    transition=np.zeros((3,3))
    for state in range(3):
        for mask in range(8):
            bits=np.array([(mask>>i)&1 for i in range(3)],dtype=bool)
            prob=np.prod(np.where(bits,p,1-p));active=np.flatnonzero(bits)
            if bits[state] or not len(active):transition[state,state]+=prob
            else:transition[state,active]+=prob/len(active)
    target=z.softmax(-1).cpu().numpy()[0]
    for seed in (0,1,2):
        for method in ('winner','rejection'):
            count=24000
            out,stats=sample(z.expand(count,-1).contiguous(),1,method,seed=seed)
            freq=torch.bincount(out.flatten(),minlength=3).cpu().numpy()/count
            expected=transition[1] if method=='winner' else target
            assert np.max(np.abs(freq-expected))<.015,(method,seed,freq,expected)
            records.append(dict(check='finite_law',method=method,seed=seed,observed=freq.tolist(),expected=expected.tolist()))
    # Uniform arbitration with three active proposals; state0 never proposes.
    z=torch.zeros((9000,4),device='cuda');p=probabilities(z,'winner')
    u=torch.zeros((9000,1,4),device='cuda');u[:,:,0]=1.
    ranks=torch.randint(1<<20,2**32,(9000,1),device='cuda',dtype=torch.int64)
    out,_=sample(z,1,'winner',seed=41,replay=(u,ranks,torch.zeros_like(ranks,dtype=torch.float32)))
    freq=torch.bincount(out.flatten(),minlength=4).cpu().numpy()/9000
    assert freq[0]==0 and np.max(np.abs(freq[1:]-1/3))<.025
    # Force every nonreference proposal to be active: cap must be an error.
    try:
        sample(torch.zeros((1,4),device='cuda'),1,'rejection',seed=1,cap_factor=1,
               replay=(torch.zeros((1,1,4),device='cuda'),torch.ones((1,1),device='cuda',dtype=torch.int64),torch.zeros((1,1),device='cuda')))
    except RuntimeError as e:
        assert 'cap reached' in str(e)
    else:raise AssertionError('cap silently accepted')
    return dict(status='passed',checks=records,arbitration=freq.tolist(),cap_failure_passed=True,
                torch=torch.__version__,gpu=torch.cuda.get_device_name())

if __name__=='__main__':print(json.dumps(run(),indent=2))
