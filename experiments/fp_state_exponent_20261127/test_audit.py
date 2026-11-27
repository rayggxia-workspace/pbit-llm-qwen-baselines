import unittest
import numpy as np
from audit import qformat,integer_codec,histogram,hist_summary
from formats import quantize,encode_gu
from small_model import quantize_numpy

class Tests(unittest.TestCase):
    def test_E8_matches_frozen_format(self):
        x=np.ldexp(np.arange(-1000,1000,dtype=np.float64),-5)
        self.assertTrue(np.array_equal(qformat(x)[0],quantize(x,16)[0]))
    def test_exponent_storage_ranges(self):
        for b,lo,hi in [(6,-30,31),(5,-14,15)]:
            x=np.array([2.**(lo-1),2.**lo,2.**hi,2.**(hi+1)])
            q,u,o=qformat(x,16,b);self.assertEqual((u,o),(1,1))
            self.assertEqual(q[1],x[1]);self.assertEqual(q[2],x[2])
    def test_integer_codecs_all_exponents(self):
        rng=np.random.default_rng(225)
        for cap in [256.,512.]:
            x=np.ldexp(rng.integers(-65535,65536,(64,128)).astype(np.float64),rng.integers(-40,2,(64,128)))
            x=qformat(x)[0];a=integer_codec(x,cap);b=encode_gu(x,cap)
            for k in ['q','sign','exponent','field']:self.assertTrue(np.array_equal(a[k],b[k]),k)
            self.assertTrue(np.array_equal(a['raw_field'],np.rint(x*8).clip(-128,127).astype(np.int64)))
    def test_histogram_zero_exclusion(self):
        h=hist_summary(histogram(np.array([0.,0.,2.**-20,1.,-8.])))
        self.assertEqual((h['minimum'],h['maximum'],h['zero'],h['nonzero']),(-20,3,2,3))
    def test_new_model_weight_quantization(self):
        x=np.random.default_rng(101).integers(-1000,1001,(128,128)).astype(np.float32)/1024
        q,s=quantize_numpy(x);e=s.repeat(64,0).repeat(64,1)
        self.assertTrue(np.all(np.frexp(s)[0]==.5))
        self.assertTrue(np.all(np.abs(q.astype(np.float32)*e-x)<=e/2))
        self.assertTrue(np.all(np.abs(q.astype(np.int16))<=127))
    def test_zero_weight_block(self):
        q,s=quantize_numpy(np.zeros((64,64),dtype=np.float32))
        self.assertTrue(np.all(q==0));self.assertEqual(s[0,0],2.**-24)

if __name__=='__main__':unittest.main()
