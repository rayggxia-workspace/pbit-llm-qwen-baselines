"""Validate block moments and exact recovery of the original head-scale encoder."""
import importlib.util
import json
from pathlib import Path
import torch
from sampling import encode


def main():
    spec=importlib.util.spec_from_file_location('previous_encoder',Path(__file__).parent.parent/'pbit_qk/sampling.py')
    old=importlib.util.module_from_spec(spec); spec.loader.exec_module(old)
    torch.manual_seed(941)
    q=torch.randn(3,14,1,64,device='cuda')
    for mode in ('iid','stratified'):
        g=torch.Generator(device='cuda').manual_seed(31)
        a,c=old.encode(q,4,mode,g)
        g.manual_seed(31)
        b,d=encode(q,4,mode,g,64)
        assert torch.equal(a,b) and torch.equal(c,d), '64-feature baseline changed'
    trials=50000
    # Different dynamic ranges in eight contiguous blocks, with a zero block.
    q=torch.linspace(-1,1,64,device='cuda') * torch.arange(1,9,device='cuda').repeat_interleave(8)
    q[:8]=0
    k=torch.randn(3,64,device='cuda')
    report=[]
    for block in (8,16,64):
        view=q.reshape(64//block,block)
        a=view.abs().amax(-1,keepdim=True).expand_as(view).reshape(64)
        a=torch.where(a>0,a,torch.ones_like(a)); p=q.abs()/a
        for mode in ('iid','stratified'):
            reconstructed,c=encode(q.expand(trials,-1),4,mode,block_size=block)
            assert torch.isfinite(reconstructed).all() and (reconstructed[:,:8]==0).all()
            f=4*p-(4*p).floor()
            var=a.square()*(p*(1-p)/4 if mode=='iid' else f*(1-f)/16)
            assert torch.allclose(reconstructed.mean(0),q,atol=.035,rtol=0)
            assert torch.allclose(reconstructed.var(0),var,atol=.018,rtol=.04)
            score=reconstructed@k.T; theory=var@k.square().T
            assert torch.allclose(score.mean(0),q@k.T,atol=.15,rtol=0)
            assert torch.allclose(score.var(0),theory,atol=.15,rtol=.04)
            report.append({'block':block,'mode':mode,'score_variance':score.var(0).tolist(),
                           'theory':theory.tolist()})
    print(json.dumps({'status':'passed','trials':trials,'legacy_block64_bitwise_identical':True,
                     'covered':['zero block','signed mean','block query variance','block score variance'],
                     'results':report},indent=2))


if __name__=='__main__': main()
