from fractions import Fraction
import math
import random
import unittest
import torch
from half import encode,FROZEN_ENCODE,MIN_EXP


def scalar(values,cap,bits):
    m=max(abs(float(v)) for v in values)
    e=MIN_EXP if m==0 else math.ceil(math.log2(m))
    e=max(MIN_EXP,min(int(math.log2(cap)),e))
    result=[]
    for v in values:
        small=e>=MIN_EXP+bits and abs(v)<=2.**(e-bits)
        chosen=e-bits*small
        p=Fraction(abs(v))/Fraction(2)**chosen
        q=256 if p>=1 and p else min(255,round(p*256))
        result.append((q,(v>0)-(v<0),chosen,small))
    return result


class Tests(unittest.TestCase):
    def test_independent_fraction_oracle(self):
        rng=random.Random(225)
        for bits in (1,2):
            for cap in (256.,512.):
                for exponent in (-9,-6,-5,-4,0,5,10):
                    v=[rng.randrange(-1024,1025)*2.**(exponent-10) for _ in range(64)]
                    a=encode(torch.tensor(v),cap,step_bits=bits)
                    self.assertEqual(list(zip(a['q'].tolist(),a['sign'].tolist(),a['exponent'].tolist(),a['small'].tolist())),scalar(v,cap,bits))

    def test_S4_is_exact_frozen_encoder(self):
        gen=torch.Generator().manual_seed(225)
        for cap in (256.,512.):
            for exponent in (-9,-6,-5,0,10):
                v=torch.randn(2,128,generator=gen)*2.**exponent
                a,b=encode(v,cap,step_bits=2),FROZEN_ENCODE(v,cap)
                for key in a:self.assertTrue(torch.equal(a[key],b[key]),key)

    def test_S2_boundary_and_endpoint(self):
        v=torch.zeros(64);v[:5]=torch.tensor([1.,.5,-.5,.5009765625,0.])
        a=encode(v,256.)
        self.assertEqual(a['small'][:5].tolist(),[False,True,True,False,True])
        self.assertEqual(a['q'][:5].tolist(),[256,256,256,128,0])

    def test_floor_never_adds_third_scale(self):
        v=torch.full((2,64),2.**-10);v[0,0]=2.**-6;v[1,0]=2.**-5
        a=encode(v,256.)
        self.assertFalse(bool(a['small'][0].any()))
        self.assertTrue(bool(a['small'][1,1:].all()))
        self.assertTrue(bool(((a['base_exponent']-a['exponent'])==a['small']).all()))

    def test_integer_restore_with_two_bit_product_span(self):
        gen=torch.Generator().manual_seed(225)
        a=encode(torch.randn(2,128,generator=gen)*4,256.)
        b=encode(torch.randn(2,128,generator=gen),512.)
        shift=a['shift']+b['shift'];rr=int(shift.max())
        product=(a['exponent']+b['exponent']).reshape(-1,64)
        self.assertLessEqual(int((product.amax(-1)-product.amin(-1)).max()),2)
        counts=torch.randint(33,shift.shape,generator=gen);w=torch.randint(-127,128,shift.shape,generator=gen)
        code=((counts<<(rr-shift))*a['sign']*b['sign']*w).sum(-1)
        actual=torch.ldexp(code.double(),torch.tensor(17-rr))
        expected=(counts*a['sign']*b['sign']*w*a['scale'].double()*b['scale'].double()).sum(-1)
        self.assertTrue(torch.equal(actual,expected))


if __name__=='__main__':unittest.main()
