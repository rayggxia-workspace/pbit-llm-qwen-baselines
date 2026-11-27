from fractions import Fraction
import random,unittest
import torch
from core import rne_signed_shift,ceil_log2_positive
from oracle import rne,state
class Tests(unittest.TestCase):
    def test_signed_RNE_ties(self):
        for d in range(-25,10):
            xs=[-4194304,-12345,-5,-3,-1,0,1,3,5,12345,4194303]
            actual=rne_signed_shift(torch.tensor(xs),torch.tensor(d)).tolist()
            self.assertEqual(actual,[rne(v,d) for v in xs])
    def test_integer_log_near_powers(self):
        xs=sorted({x for e in range(1,63) for x in [(1<<e)-1,1<<e,(1<<e)+1] if x<(1<<63)})
        self.assertEqual(ceil_log2_positive(torch.tensor(xs)).tolist(),[(x-1).bit_length() for x in xs])
    def test_error_bound_for_real_K(self):
        r=random.Random(225)
        for k in (40,152):
            for w in (24,32):
                vals=[r.randrange(-1040384,1040385) for _ in range(k)]
                exps=[r.randrange(0,25) for _ in range(k)]
                bound=sum(1040384<<e for e in exps)
                actual,base=state(vals,exps,bound,w)
                exact=sum(v<<e for v,e in zip(vals,exps))
                self.assertLessEqual(abs(actual-exact),Fraction(k,2)*Fraction(2)**base)
    def test_small_same_exponent_is_exact32(self):
        v,b=state([17,-29,83],[0,0,0],129,32)
        self.assertEqual(v,71)
    def test_overflow_is_an_error(self):
        with self.assertRaises(OverflowError):state([1<<30],[0],1,24)
    def test_not_final_output_dependent(self):
        b=1234567890123
        self.assertEqual(state([1,-1],[0,0],b,24)[1],state([1000000,1000000],[0,0],b,24)[1])
if __name__=='__main__':unittest.main()
