import unittest
import torch
from .core import Config,attention,torch_winner_replay
from .vendor.sparq_reference import sparq_attention,SparQConfig
from .vendor.plans import full_window_plan,plan_batches


class Tests(unittest.TestCase):
    def test_exact_reference(self):
        for seed in range(3):
            torch.manual_seed(seed)
            for n in (7,33,80):
                q=torch.randn(2,8,1,16,dtype=torch.float64)
                k=torch.randn(2,2,n,16,dtype=torch.float64);v=torch.randn_like(k)
                cfg=Config(r=4,k=16,local=5,mode='exact')
                actual,info=attention(q,k,v,cfg,diagnostics=True)
                expect,diag=sparq_attention(q,k,v,config=SparQConfig(r=4,k_total=16,local_total=5),return_diagnostics=True)
                torch.testing.assert_close(actual,expect,rtol=0,atol=0)
                if n>16:self.assertTrue(torch.equal(info['candidate_ids'],diag['candidate_ids']))

    def test_local_and_zero(self):
        q=torch.zeros(1,4,1,8);k=torch.randn(1,1,40,8);v=torch.randn_like(k)
        y,info=attention(q,k,v,Config(r=2,k=8,local=3,mode='exact'),diagnostics=True)
        torch.testing.assert_close(y,v.mean(2)[:,None].expand(1,4,1,8))
        self.assertEqual(info['zero_fallback_groups'],1)
        q=torch.randn_like(q)
        _,info=attention(q,k,v,Config(r=2,k=8,local=3,mode='exact'),diagnostics=True)
        self.assertTrue({37,38,39}.issubset(set(info['candidate_ids'].flatten().tolist())))

    def test_replay_semantics(self):
        bits=torch.tensor([[[0,0,0],[0,1,1],[1,1,0],[1,0,1],[0,0,0]]],dtype=torch.bool)
        ranks=torch.tensor([[0,1,0,1,0]])
        self.assertEqual(torch_winner_replay(bits,ranks,torch.tensor([0]),0).tolist(),[[0,2,0,0,0]])

    def test_iid_direct_addresses(self):
        q=torch.randn(2,4,1,8);k=torch.randn(2,1,32,8);v=torch.randn_like(k)
        cfg=Config(r=2,k=8,local=2,mode='iid',samples=19)
        y,info=attention(q,k,v,cfg,seed=3,diagnostics=True)
        expected=torch.empty_like(y)
        for b in range(2):
            for h in range(4):expected[b,h,0]=v[b,0,info['token_ids'][b,0,h]].sum(0)/19
        torch.testing.assert_close(y,expected,rtol=0,atol=0)

    def test_full_coverage(self):
        plan=full_window_plan(30001)
        targets=[i for row in plan for i in range(row['first_target'],row['end'])]
        self.assertEqual(targets,list(range(1,30001)))
        self.assertEqual(sum(len(b) for b in plan_batches(plan,8)),len(plan))


def gpu_tests():
    from .vendor.kernels import sample,probabilities
    torch.manual_seed(19)
    z=torch.randn(32,17,device='cuda');burn=7;s=23;cap=burn+s
    u=torch.rand(32,cap,17,device='cuda')
    raw=torch.randint(1000,2**31,(32,cap),device='cuda',dtype=torch.int64)
    coins=torch.rand(32,cap,device='cuda')
    out,stats=sample(z,s,'winner',burn=burn,seed=73,replay=(u,raw,coins))
    bits=(u<probabilities(z,'winner')[:,0,None,:]).cpu()
    counts=bits.sum(-1).clamp_min(1)
    ranks=raw.cpu()%counts
    expected=torch_winner_replay(bits,ranks,z.argmax(-1).cpu(),burn)
    torch.testing.assert_close(out.cpu(),expected,rtol=0,atol=0)
    assert (stats[:,0]==cap).all() and (stats[:,1]==s).all()
    again,_=sample(z,s,'winner',burn=burn,seed=73,replay=(u,raw,coins))
    assert torch.equal(out,again)
    # Stationary-law diagnostic, separate from finite-chain PPL.
    z=torch.tensor([[0.,-0.5,-1.5,-3.]],device='cuda').expand(256,4).contiguous()
    out,_=sample(z,512,'winner',burn=64,seed=99)
    hist=torch.bincount(out.flatten(),minlength=4).float()/out.numel()
    tv=float((hist-z[0].softmax(-1)).abs().sum()/2)
    assert tv<.015,tv
    return dict(replay_frames=32*cap,replay_exact=True,stationary_tv=tv)


if __name__=='__main__':unittest.main()
