from fractions import Fraction
import math,unittest
import numpy as np
from formats import quantize,fraction_q,floating_chain,words,pot

class Tests(unittest.TestCase):
    def test_ties_and_signs(self):
        for p in [8,16]:
            values=[Fraction(1)+i*pot(-p) for i in range(8)]
            values+= [-v for v in values]
            q,_,_=quantize(np.array(list(map(float,values))),p)
            self.assertEqual(q.tolist(),[float(fraction_q(v,p)[0]) for v in values])
    def test_zero_underflow_and_overflow(self):
        for p in [8,16]:
            values=[0.,-0.,2.**-127,-2.**-127,2.**-126,2.**128]
            q,u,o=quantize(values,p)
            self.assertEqual((u,o),(2,1));self.assertFalse(np.signbit(q[:2]).any())
            self.assertEqual(q.tolist(),[float(fraction_q(Fraction(v),p)[0]) for v in values])
            self.assertTrue(np.all(words(q,p)<(1<<(p+8))))
    def test_random_integer_tile_conversion(self):
        rng=np.random.default_rng(225)
        for p in [8,16]:
            n=rng.integers(-(1<<22),(1<<22),3000);e=rng.integers(-160,140,3000)
            v=np.ldexp(n.astype(np.float64),e);q,u,o=quantize(v,p)
            refs=[fraction_q(int(a)*pot(int(b)),p) for a,b in zip(n,e)]
            self.assertEqual(q.tolist(),[float(x[0]) for x in refs])
            self.assertEqual((u,o),(sum(x[1] for x in refs),sum(x[2] for x in refs)))
    def test_float64_add_against_fraction(self):
        rng=np.random.default_rng(101)
        for p in [8,16]:
            n=rng.integers(-(1<<p),(1<<p),4000);e=rng.integers(-145,130,4000)
            x=[fraction_q(int(a)*pot(int(b)),p)[0] for a,b in zip(n,e)]
            q,_,_=quantize(np.array(list(map(float,x[::2])))+np.array(list(map(float,x[1::2]))),p)
            self.assertEqual(q.tolist(),[float(fraction_q(a+b,p)[0]) for a,b in zip(x[::2],x[1::2])])
    def test_FP32_double_rounding_is_not_the_contract(self):
        a=Fraction(1);b=pot(-16)+pot(-31)
        correct=fraction_q(a+b,16)[0]
        wrong=quantize([float(np.float32(a)+np.float32(b))],16)[0][0]
        good=quantize([float(a)+float(b)],16)[0][0]
        self.assertEqual(float(correct),good);self.assertNotEqual(float(correct),wrong)
    def test_every_update_is_rounded(self):
        parts=np.ones((101,1,1),dtype=np.int64);ex=np.full(parts.shape,-8,dtype=np.int64);ex[0]=0
        q,_=floating_chain(parts,ex,8)
        self.assertEqual(float(q[0,0]),1.)
        final_only=quantize([1+100/256],8)[0][0]
        self.assertNotEqual(float(q[0,0]),float(final_only))

if __name__=='__main__':unittest.main()
