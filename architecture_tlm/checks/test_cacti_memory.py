import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from cacti_memory import designs,summarize,apply_cost_profile,overrides,parse
from system_decode import load


class Tests(unittest.TestCase):
    def test_parallel_output_and_capacity_match(self):
        for d in designs():
            if d['role']=='local_weight':
                self.assertEqual(d['replicas']*d['width'],36864)
                self.assertEqual(d['replicas']*d['bytes'],144*1024)

    def test_parse_and_unit_conversion(self):
        p=parse('Access time (ns): 2\nCycle time (ns): 11\n'
            'Total dynamic read energy per access (nJ): 0.04\n'
            'Total dynamic write energy per access (nJ): 0.06\n'
            'Total leakage power of a bank (mW): 2\n'
            'Total gate leakage power of a bank (mW): 0.3\n'
            'Cache height x width (mm): 0.1 x 0.2\n')
        d=next(d for d in designs() if d['name']=='weight_cache_b8')
        r=summarize(d,p)
        self.assertAlmostEqual(r['total_area_mm2'],.16)
        self.assertAlmostEqual(r['total_leakage_W'],.0184)
        self.assertEqual(r['read_pJ_per_byte'],40/64)
        self.assertEqual(r['issue_interval_ns'],20)
        self.assertEqual(r['parallel_peak_GBs'],25.6)
        cfg,_,_=load();before=cfg['weight_macro']['load_bandwidth_GBs']
        apply_cost_profile(cfg,dict(overrides=overrides(r),provenance={'source':'test'}))
        self.assertEqual(cfg['weight_macro']['load_bandwidth_GBs'],before)
        cfg['weight_macro']['cache_MiB']=32
        with self.assertRaises(ValueError):
            apply_cost_profile(cfg,dict(overrides=overrides(r),provenance={}))

    def test_missing_outputs_not_zero(self):
        with self.assertRaises(ValueError):parse('no valid cache organizations found')


if __name__=='__main__':unittest.main(verbosity=2)
