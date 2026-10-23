import unittest
import numpy as np
from .metrics import bit_metrics,corr,probes,word_metrics
from .run import condition,pack,simulate,synthetic
from .prepare_physical import parse


class QualityTests(unittest.TestCase):
    def test_vn_known_pairs(self):
        self.assertEqual(condition([0,0,0,1,1,0,1,1,1],'vn').tolist(),[0,1])

    def test_lsb_packing_and_tail(self):
        x=[0]*65;x[0]=1;x[31]=1;x[33]=1;x[-1]=1
        self.assertEqual(pack(x),[0x80000001,2])

    def test_constant_is_not_independent(self):
        r=bit_metrics(np.ones(512,dtype=np.uint8))
        self.assertIsNone(r['rho']['1']);self.assertEqual(r['marginal_min_entropy_only'],0)

    def test_alternating(self):
        r=bit_metrics(np.tile([0,1],256))
        self.assertAlmostEqual(r['rho']['1'],-1);self.assertEqual(r['p1'],.5)
        self.assertEqual(r['windows']['32']['variance_over_iid_at_empirical_p'],0)

    def test_duplicate_seed_fault_detected_all_backends(self):
        words=pack(synthetic('iid_fixture',401))
        for kind in ('lfsr32','lfsr32_shared64','bivium'):
            r,a,b,c=simulate(kind,words,256,0,True)
            self.assertEqual(r['status'],'complete');np.testing.assert_array_equal(a,b)
            self.assertEqual(r['seed_stats']['repeated_state_loads'],1)
            self.assertAlmostEqual(r['probes']['endpoint_first_bit_rho'],1)

    def test_periodic_seed_transport(self):
        for kind in ('lfsr32','lfsr32_shared64','bivium'):
            r,a,b,c=simulate(kind,pack(synthetic('iid_fixture',503)),256,64)
            self.assertEqual(r['status'],'complete')
            self.assertGreater(r['seed_stats']['loads'],2)
            self.assertTrue(np.all(np.diff(c)>0))
            if kind=='bivium':self.assertEqual(r['seed_stats']['bus_words']%6,0)

    def test_zero_seed_refused(self):
        r,*_=simulate('lfsr32',[0]*20,256,0)
        self.assertEqual(r['status'],'incomplete');self.assertGreater(r['seed_stats']['zero_rejections'],0)

    def test_known_shared_and(self):
        a=np.tile(np.arange(256,dtype=np.uint8),2)[:,None]
        r=probes(a,a);self.assertEqual(r['shared_word_and'],.25)
        self.assertEqual(r['and_target'],.1875)
        self.assertEqual(word_metrics(a)['worst_lane_cdf_error'],0)

    def test_no_silent_incomplete_physical_trace(self):
        with self.assertRaises(ValueError):parse(b'VALUE\n"time" 0.002\n"out" 0.7\nEND\n','out',2e-8,.6)

if __name__=='__main__':unittest.main()
