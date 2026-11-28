import unittest
import torch
from dynamic import encode


class Tests(unittest.TestCase):
    def test_power_endpoints(self):
        for group in [16,32,64]:
            for maximum,expected in [(0.,2**-6),(.125,.125),(.126,.25),(3.,4.),(512.,512.),(600.,512.)]:
                x=torch.zeros(group);x[0]=maximum
                q,s,e,h,scale=encode(x,group,512.)
                self.assertTrue(bool((scale==expected).all()))
                self.assertTrue(bool((e==int(torch.log2(torch.tensor(expected)))).all()))
                if maximum>=512.:self.assertEqual(int(q[0]),256)

    def test_groups_do_not_mix(self):
        x=torch.full((2,128),.1);x[0,0]=3.;x[1,64]=31.
        q,s,e,h,scale=encode(x,16,512.)
        self.assertEqual(float(scale[0,0]),4.)
        self.assertEqual(float(scale[0,16]),.125)
        self.assertEqual(float(scale[1,64]),32.)
        self.assertEqual(float(scale[1,80]),.125)

    def test_rne_sign_and_p8(self):
        x=torch.zeros(64);x[:5]=torch.tensor([1.,-1.,2.5/256,3.5/256,0.])
        q,s,e,h,scale=encode(x,64,512.)
        self.assertEqual(q[:5].tolist(),[256,256,2,4,0])
        self.assertEqual(s[:5].tolist(),[1,-1,1,1,0])

    def test_scale_alignment_is_exact(self):
        for group in [16,32,64]:
            gen=torch.Generator().manual_seed(17)
            g=torch.randn(2,128,generator=gen)*torch.exp2(torch.arange(128).float()%8-4)
            u=torch.randn(2,128,generator=gen)
            gq,gs,ge,gh,gscale=encode(g,group,256.)
            uq,us,ue,uh,uscale=encode(u,group,512.)
            c=torch.randint(33,g.shape,generator=gen);w=torch.randint(-127,128,g.shape,generator=gen)
            rr=int((gh+uh).max());aligned=(c<<(rr-gh-uh))*gs*us*w
            integer=aligned.sum(-1)
            exact=gs*us*c*w*gscale.double()*uscale.double()
            restored=torch.ldexp(integer.double(),torch.tensor(17-rr))
            self.assertTrue(torch.equal(restored,exact.sum(-1)))


if __name__=='__main__':unittest.main()
