"""Independent scalar/dyadic checks for the new scale contract."""
from fractions import Fraction
import math
import random
import unittest
import torch
from onebit import encode, MIN_EXP


def scalar(values, cap, correction):
    m=max(abs(float(x)) for x in values)
    e=MIN_EXP if not m else math.ceil(math.log2(m))
    e=max(MIN_EXP, min(int(math.log2(cap)), e))
    rows=[]
    for value in values:
        small=correction and e>=MIN_EXP+2 and abs(float(value))<=2.**(e-2)
        chosen=e-2*small
        a=Fraction(abs(float(value)))/Fraction(2)**chosen
        q=256 if a>=1 and a else min(255, round(a*256))
        rows.append((q, (value>0)-(value<0), chosen, int(small)))
    return rows


class Tests(unittest.TestCase):
    def test_exact_scalar_oracle(self):
        r=random.Random(225)
        for correction in [False,True]:
            for cap in [256.,512.]:
                for exp in [-9,-6,-5,-4,-1,3,9,11]:
                    values=[r.randrange(-1024,1025)*2.**(exp-10) for _ in range(64)]
                    out=encode(torch.tensor(values),cap,correction)
                    actual=list(zip(out['q'].tolist(),out['sign'].tolist(),out['exponent'].tolist(),out['small'].int().tolist()))
                    self.assertEqual(actual,scalar(values,cap,correction))

    def test_endpoints_and_rne(self):
        v=torch.zeros(64)
        v[:7]=torch.tensor([1.,-1.,.25,-.25,2.5/1024,3.5/1024,0.])
        a=encode(v,256.)
        self.assertEqual(a['q'][:7].tolist(),[256,256,256,256,2,4,0])
        self.assertEqual(a['small'][:7].tolist(),[False,False,True,True,True,True,True])

    def test_group_axes_do_not_mix(self):
        v=torch.full((2,128),.1);v[0,0]=3.;v[1,64]=31.
        a=encode(v,512.)
        self.assertEqual(a['base_exponent'][0,0].item(),2)
        self.assertEqual(a['base_exponent'][0,64].item(),-3)
        self.assertEqual(a['base_exponent'][1,64].item(),5)

    def test_floor_keeps_strict_two_scales(self):
        v=torch.full((2,64),2.**-9);v[0,0]=2.**-5;v[1,0]=2.**-4
        a=encode(v,256.)
        self.assertFalse(bool(a['small'][0].any()))
        self.assertTrue(bool(a['small'][1,1:].all()))
        self.assertTrue(bool(((a['base_exponent']-a['exponent'])==2*a['small']).all()))

    def test_integer_product_scale_alignment(self):
        r=torch.Generator().manual_seed(225)
        g=torch.randn(2,128,generator=r)*4
        u=torch.randn(2,128,generator=r)
        a,b=encode(g,256.),encode(u,512.)
        counts=torch.randint(33,g.shape,generator=r)
        w=torch.randint(-127,128,g.shape,generator=r)
        shifts=a['shift']+b['shift'];rr=int(shifts.max())
        integer=((counts<<(rr-shifts))*a['sign']*b['sign']*w).sum(-1)
        restored=torch.ldexp(integer.double(),torch.tensor(17-rr))
        exact=(counts*a['sign']*b['sign']*w*a['scale'].double()*b['scale'].double()).sum(-1)
        self.assertTrue(torch.equal(restored,exact))


if __name__=='__main__':
    unittest.main()
