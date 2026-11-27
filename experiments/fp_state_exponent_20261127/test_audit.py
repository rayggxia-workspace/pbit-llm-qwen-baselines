import unittest
import numpy as np
from audit import qformat,integer_codec,histogram,hist_summary
from formats import quantize,encode_gu

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

if __name__=='__main__':unittest.main()
