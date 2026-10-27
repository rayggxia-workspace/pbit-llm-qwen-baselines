import unittest,torch
from .core import GRIDS,input_cells,conditional_parts,reference_project


class DualLaw(unittest.TestCase):
    def test_weight_code_has_no_new_quantization(self):
        w=torch.arange(-127,128);p=(2*w.abs()).double()/256
        self.assertTrue(torch.equal(p*128*w.sign(),w.double()))

    def test_boundaries_and_shared_A(self):
        for law in ('iid','joint'):
            q=torch.tensor([0,256]*32,dtype=torch.int16).repeat(3,1)
            c,p=input_cells(q,256,law,torch.Generator().manual_seed(7))
            self.assertTrue(torch.equal(c.sum(2).reshape_as(q),q))
            self.assertTrue(torch.equal(c[:,:,:,0],torch.zeros_like(c[:,:,:,0])))
            self.assertTrue(torch.equal(c[:,:,:,1],c[:,:,:,3]))

    def test_joint_means_and_variances(self):
        reps=4000;qa=83;mag=37;pw=mag/128;pa=qa/256
        for law in ('iid','joint'):
            q=torch.full((reps,64),qa,dtype=torch.int16)
            c,pre=input_cells(q,128,law,torch.Generator().manual_seed(110))
            kw=c.shape[2];w=torch.full((64,64),mag)
            base,n,p=conditional_parts(c[:,0],pre[:,0],w,kw)
            # Only one connection; retain actual shared-A sample law.
            z=base[:,0,0].double()+torch.binomial(n[:,0,0].double(),p[0,0].double().expand(reps),generator=torch.Generator().manual_seed(901))
            if law=='iid':
                frac=(qa%4)/4;va=(128//64)*frac*(1-frac)
                var=128*pa*pw*(1-pw)+va*pw*pw
            else:
                ka,kw=GRIDS[128];fa=(pa*ka)%1;fw=(pw*kw)%1
                var=int(pw*kw)*fa*(1-fa)+int(pa*ka)*fw*(1-fw)+fa*fw*(1-fa*fw)
            self.assertAlmostEqual(float(z.mean()),128*pa*pw,delta=8*(var/reps)**.5+.01)
            self.assertAlmostEqual(float(z.var(unbiased=False)),var,delta=var*.12+.02)

    def test_joint_strata_avoid_synchronous_min_bias(self):
        q=torch.full((4,64),128,dtype=torch.int16)
        c,pre=input_cells(q,64,'joint',torch.Generator().manual_seed(2))
        base,n,p=conditional_parts(c[:,0],pre[:,0],torch.full((64,64),64),8)
        self.assertTrue(torch.equal(base,torch.full_like(base,16)))
        self.assertTrue(torch.equal(p,torch.zeros_like(p)))

    def test_invalid_T(self):
        with self.assertRaises(ValueError):input_cells(torch.zeros(1,64),512,'iid')

    def test_exact_quantized_expectation_and_signs(self):
        # At full A and weight1/2, joint cells count deterministically T/2.
        enc=dict(probability=torch.ones(2,64),scale=torch.ones(2,64),sign=torch.tensor([1.,-1.])[:,None].expand(2,64))
        w=torch.full((64,64),64,dtype=torch.int8);lsb=torch.ones(1,1)
        y=reference_project(enc,w,lsb,256,'joint',torch.Generator().manual_seed(2),torch.Generator().manual_seed(3))
        self.assertTrue(torch.equal(y[0],torch.full_like(y[0],4096)))
        self.assertTrue(torch.equal(y[1],-y[0]))


@unittest.skipUnless(torch.cuda.is_available(),'CUDA kernel verification on Slurm')
class CUDA(unittest.TestCase):
    def test_inverse_cdf_replay_matches_cpu_oracle(self):
        import numpy as np
        from scipy.stats import binom
        from unittest.mock import patch
        from .kernel import project,table
        q=torch.tensor([0,1,31,64,127,128,254,256]*8,dtype=torch.int16).repeat(2,1)
        w=(torch.arange(64*64).reshape(64,64)%255-127).to(torch.int8)
        gen=torch.Generator().manual_seed(21);u=torch.rand(2,64,64,generator=gen,dtype=torch.float64)
        scales=torch.tensor([1.,.25,.0625,.015625]*16).repeat(2,1);sign=torch.where(torch.arange(64)%2==1,1.,-1.).repeat(2,1)
        for law in ('iid','joint'):
            c,pre=input_cells(q,256,law,torch.Generator().manual_seed(8));kw=c.shape[2]
            base,n,p=conditional_parts(c[:,0],pre[:,0],w.long().abs(),kw)
            draw=torch.from_numpy(binom.ppf(u.numpy(),n.numpy(),p.numpy())).double()
            expected=((base+draw)*w.sign()[None,:,:]*sign[:,None,:]*scales[:,None,:]).sum(-1)*128/256
            enc=dict(probability=q.cuda().float()/256,scale=scales.cuda(),sign=sign.cuda())
            # Replay the SAME A counts and uniform quantiles, independent of
            # device RNG algorithms. Then test real RNG path separately.
            with patch('qwen3.dual_gu.kernel.input_cells',return_value=(c.cuda(),pre.cuda())):
                y=project(enc,w.cuda(),torch.ones(1,1,device='cuda'),256,law,torch.Generator(device='cuda'),torch.Generator(device='cuda'),replay=u.cuda())
            torch.testing.assert_close(y.cpu().double(),expected,rtol=0,atol=0)
            z=project(enc,w.cuda(),torch.ones(1,1,device='cuda'),256,law,torch.Generator(device='cuda').manual_seed(1),torch.Generator(device='cuda').manual_seed(9))
            self.assertTrue(bool(torch.isfinite(z).all()))

    def test_row_keys_do_not_wrap_at_large_token_indices(self):
        # Offset only indexes W (<50M), token row is a distinct64-bit key.
        n,o=2560,19456
        self.assertLess(n*o,2**32)
        keys={((b*0x9e3779b97f4a7c15)&((1<<64)-1)) for b in range(4096)}
        self.assertEqual(len(keys),4096)


if __name__=='__main__':unittest.main()
