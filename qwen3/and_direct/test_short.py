import itertools
import unittest
import torch
from .short_core import joint_counts,joint_moments,literal_joint,encode_fixed,POLICIES,ShortStreamFFN
from .multiscale_core import encode_bins,MultiScaleFFN


class TestJoint(unittest.TestCase):
    def test_expectation_and_variance(self):
        q=torch.tensor(list(itertools.product([0,1,31,64,127,128,193,255,256],repeat=3))).T
        p=(q[0]*q[1]*q[2]).double()/256**3
        for t in (32,64,128):
            mean,var=joint_moments(tuple(q),t)
            self.assertTrue(torch.equal(mean,t*p))
            self.assertTrue(bool((var<=t*p*(1-p)+1e-12).all()))

    def test_cell_boundaries_exact(self):
        q=torch.tensor(list(itertools.product(range(0,257,64),range(0,257,128),range(0,257,64)))).T
        for t in (32,64,128):
            count,p=joint_counts(tuple(q),t,torch.Generator().manual_seed(1))
            literal=literal_joint(tuple(q),t,torch.Generator().manual_seed(9))
            self.assertTrue(torch.equal(count,literal));self.assertTrue(torch.equal(count.double(),p*t))

    def test_literal_and_compressed_distributions(self):
        q=torch.tensor([[13,129,199],[91,175,239],[223,47,193]],dtype=torch.int64)
        q=tuple(a[:,None].expand(3,30000) for a in q)
        mean,var=joint_moments(q,64)
        for fn in (joint_counts,literal_joint):
            r=fn(q,64,torch.Generator().manual_seed(722))
            y=r[0] if isinstance(r,tuple) else r
            self.assertTrue(bool(((y.double().mean(-1)-mean[:,0]).abs()<6*(var[:,0]/30000).sqrt()+1e-12).all()))
            self.assertTrue(torch.allclose(y.double().var(-1),var[:,0],rtol=.04,atol=.005))

    def test_synchronous_marginal_strata_are_biased(self):
        # Three identical layer orders give 16 successes for .5^3, target4.
        r=torch.arange(32)*8
        bad=((r<128)&(r<128)&(r<128)).sum()
        self.assertEqual(int(bad),16)
        good,_=joint_counts(tuple(torch.tensor([128]) for _ in range(3)),32)
        self.assertEqual(int(good),4)

    def test_fixed_scale_compatibility(self):
        v=torch.linspace(-1.2,1.2,128).reshape(2,64);top=torch.tensor([1.])
        a=encode_fixed(v,top,POLICIES['original']);b=encode_bins(v,top,4)
        self.assertTrue(all(torch.equal(x,y) for x,y in zip(a,b)))
        c=encode_fixed(v,top,POLICIES['lower_half'])
        self.assertTrue(set(c[3].flatten().tolist())<=set((1,3,5,7)))
        self.assertEqual(int(c[0][v.abs()>.5].min()),255)

    def test_budget_guard(self):
        for t in (1,16,33,256,4096):
            with self.assertRaises(ValueError):joint_counts(tuple(torch.tensor([1]) for _ in range(3)),t)

    def test_original_iid_module_replays_old(self):
        original=torch.nn.Module()
        torch.manual_seed(81)
        for name in ('gate_proj','up_proj','down_proj'):
            setattr(original,name,torch.nn.Linear(64,64,bias=False))
        old=MultiScaleFFN(original,0);new=ShortStreamFFN(original,0)
        x=torch.randn(3,64).bfloat16()
        for m in (old,new):
            m.mode='sampled';m.cycles=m.strata=64
            m.x_scales=torch.tensor([[4.,1.,.25,.0625]])
            m.freeze_down();m.rng_input.manual_seed(777)
        old.reset_multi(4,'sampled',64,0);new.reset_short('original','iid',64,0)
        self.assertTrue(torch.equal(old(x),new(x)))

    def test_new_module_only_x_stage_and_replay(self):
        original=torch.nn.Module()
        for name in ('gate_proj','up_proj','down_proj'):
            setattr(original,name,torch.nn.Linear(64,64,bias=False))
        m=ShortStreamFFN(original,0);m.freeze_down();m.mode='sampled';m.cycles=m.strata=64
        m.x_scales=torch.tensor([[4.,1.,.25,.0625]])
        x=torch.randn(2,64).bfloat16();calls=[];stage=m._stage
        def traced(v,s,w,r):calls.append(s);return stage(v,s,w,r)
        m._stage=traced
        for policy in POLICIES:
            m.rng_input.manual_seed(4);m.reset_short(policy,'joint32',128,0);a=m(x)
            m.rng_input.manual_seed(4);m.reset_short(policy,'joint32',128,0);b=m(x)
            self.assertTrue(torch.equal(a,b));self.assertFalse(m.short_report()['z_reencoding'])
        self.assertEqual(calls,['x']*6)

    @unittest.skipUnless(torch.cuda.is_available(),'CUDA unavailable')
    def test_cuda_moments_and_bounds(self):
        q=tuple(torch.arange(257,device='cuda',dtype=torch.int64) for _ in range(3))
        mean,var=joint_moments(q,128);counts,p=joint_counts(q,128)
        self.assertTrue(torch.equal(mean,128*p))
        self.assertTrue(bool(((counts>=0)&(counts<=128)).all()))

if __name__=='__main__':unittest.main()
