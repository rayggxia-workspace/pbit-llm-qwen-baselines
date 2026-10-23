import os
import unittest
from .adapter import Profile
from .backend import load
from .run_cycle import execute, fixture, reference


class AdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.api, cls.hashes = load(os.environ['ENCODE_CYCLE_BACKEND'])

    def check(self, profile, rows=9, samples=32, sink=0):
        data=fixture(samples,rows=rows,groups=2)
        a,va,ra=execute(self.api,data,samples,'input_sign_twos_complement',profile,'cycle',sink)
        b,vb,rb=execute(self.api,data,samples,'input_sign_twos_complement',profile,'event',sink)
        self.assertEqual(a.equivalence_payload(),b.equivalence_payload())
        self.assertEqual(ra,rb)
        self.assertEqual(va,vb)
        self.assertEqual(vb,reference(data,samples))
        return b

    def test_every_output_is_a_complete_restore(self):
        result=self.check(Profile(),rows=64)
        self.assertEqual(result.actions['complete_restore_output_b4'],128)
        self.assertEqual(result.actions['complete_encode_group64'],2)
        self.assertEqual(result.actions['cross_k_fp32_add'],128)
        self.assertNotIn('legacy_72_ops',result.actions)

    def test_reserved_capacity_blocks_acceptance_while_sink_stalls(self):
        result=self.check(Profile(restore_depth=2),sink=400000)
        ids=[f'er.g000.row{i:03d}.restore' for i in range(3)]
        self.assertLess(result.accepted_ps[ids[1]],400000)
        self.assertGreater(result.accepted_ps[ids[2]],400000)
        self.assertLessEqual(result.buffer_peak['er.restore0.ready'],2)
        self.assertEqual(result.buffer_final['er.restore0.free'],2)

    def test_single_slot_and_slow_sink(self):
        r=self.check(Profile(restore_depth=1,add_latency=3,add_ii=4,add_capacity=1),sink=200000)
        for i in range(1,9):
            self.assertGreater(r.accepted_ps[f'er.g000.row{i:03d}.restore'],
                               r.completion_ps[f'er.g000.row{i-1:03d}.add'])

    def test_multiple_instances_preserve_bits(self):
        one=self.check(Profile(restore_lanes=1,restore_ii=4))
        four=self.check(Profile(restore_lanes=4,restore_ii=4))
        self.assertLess(four.finish_ps,one.finish_ps)
        for lane in range(4):
            self.assertLessEqual(four.resource_peak[f'er.restore{lane}'],4)

    def test_latency_is_not_initiation_interval(self):
        r=self.check(Profile(restore_latency=7,restore_ii=2,restore_depth=16),rows=5)
        ids=[f'er.g000.row{i:03d}.restore' for i in range(5)]
        self.assertEqual(r.accepted_ps[ids[1]]-r.accepted_ps[ids[0]],20000)
        self.assertEqual(r.completion_ps[ids[0]]-r.accepted_ps[ids[0]],70000)

    def test_layouts_produce_same_outputs(self):
        data=fixture(16,rows=4)
        profile=Profile(restore_lanes=2)
        a,va,_=execute(self.api,data,16,'input_sign_twos_complement',profile,'event')
        b,vb,_=execute(self.api,data,16,'product_sign_magnitude',profile,'event')
        self.assertEqual(va,vb)
        self.assertEqual(a.actions,b.actions)

    def test_invalid_profiles(self):
        for name in vars(Profile()):
            for bad in (0,-1,True,1.5):
                with self.assertRaises(ValueError):
                    Profile(**{name:bad})

    def test_encoded_credit_is_not_released_until_all_adds(self):
        r=self.check(Profile(restore_lanes=3),rows=5,sink=200000)
        self.assertGreater(r.accepted_ps['er.g001.encode'],r.completion_ps['er.g000.release'])
        for row in range(5):
            self.assertGreater(r.accepted_ps['er.g000.release'],r.completion_ps[f'er.g000.row{row:03d}.add'])


if __name__=='__main__':unittest.main()
