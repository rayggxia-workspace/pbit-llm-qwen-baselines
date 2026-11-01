import json
from pathlib import Path
import unittest
from .shared_memory import SharedMemory,AnalyticDRAM
from .shared_decode import SharedDecode
from .shared_clock import SharedClock

def execute(profile):
    h=SharedMemory(AnalyticDRAM());m=SharedDecode(h,layers=1,context=128,hidden=64,ffn_size=64,
        q_heads=4,kv_heads=1,vocab=320,gu=1,nl=1,include_lm=True,clock_profile=profile)
    r=m.run();s=h.report();h.backend.finish(h.now);return r,s

class ClockTests(unittest.TestCase):
    def test_legacy_frozen_timing_and_work_preserved(self):
        expected=json.loads((Path(__file__).parent/'fixtures/shared_clock_legacy.json').read_bytes())
        r,s=execute('legacy_mixed')
        for key in ['phases','actions','kernel_active','compute_macro_busy_sum_ns','work_spec_sha256']:
            self.assertEqual(r[key],expected['model'][key],key)
        self.assertEqual(s,expected['memory'])
    def test_common_clock_and_work_conservation(self):
        r,s=execute('chip100');old,os=execute('legacy_mixed')
        self.assertTrue(r['clock_contract']['all_onchip_one_clock'])
        for value in r['clock_contract']['frequencies_hz'].values():self.assertEqual(value,100000000)
        self.assertEqual(r['actions'],old['actions'])
        self.assertEqual(r['kernel_active'],old['kernel_active'])
        self.assertEqual(s['by_kind'],os['by_kind'])
        self.assertEqual(s['SRAM']['counts']['read_words'],os['SRAM']['counts']['read_words'])
        self.assertEqual(s['SRAM']['counts']['write_words'],os['SRAM']['counts']['write_words'])
        for p in r['phases']:
            self.assertAlmostEqual(p['start_ns']%10,0,places=4)
            self.assertAlmostEqual(p['end_ns']%10,0,places=4)
            self.assertAlmostEqual(p['duration_ns'],p['chip_cycles']*10)
    def test_fast_macro_contracts_are_cycles_not_old_ns(self):
        c=SharedClock('chip100');old=SharedClock('legacy_mixed')
        self.assertEqual(c.service_ns('GU_crossK_align_add_macro',10),50)
        self.assertEqual(c.service_ns('final_BF16_macro',6),30)
        self.assertEqual(c.service_ns('feature_topk_macro',1633.333333),1640)
        self.assertEqual(old.service_ns('GU_crossK_align_add_macro',10),10)
        self.assertEqual(c.mac_hz,100000000)
        self.assertEqual(old.mac_hz,500000000)
    def test_mismatched_front_clock_rejected(self):
        h=SharedMemory(AnalyticDRAM(),issue_period_ns=2)
        with self.assertRaises(ValueError):SharedDecode(h,clock_profile='chip100')

if __name__=='__main__':unittest.main()
