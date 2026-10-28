import copy
import unittest
from pathlib import Path
from .rebudget import estimate,merged_bitwork,read,state_energy


class EnergyAccounting(unittest.TestCase):
    def setUp(self):
        self.idle=dict(power_uW=20.,leakage_uW=5.)
        self.active=dict(power_uW=100.,leakage_uW=5.)

    def test_continuous_reference_reproduces_power(self):
        r=state_energy(self.active,self.idle,seconds=1e-6,cycles=100,work=100)
        self.assertAlmostEqual(r['energy_J'],100e-6*1e-6)

    def test_gating_never_stops_busy_clock(self):
        r=state_energy(self.active,self.idle,seconds=1e-6,cycles=100,work=100,idle_dynamic_keep=0)
        self.assertAlmostEqual(r['energy_J'],100e-6*1e-6)

    def test_gating_preserves_leakage(self):
        r=state_energy(self.active,self.idle,seconds=1e-6,cycles=100,work=0,idle_dynamic_keep=0)
        self.assertAlmostEqual(r['energy_J'],5e-6*1e-6)

    def test_high_frequency_does_not_scale_leakage(self):
        a=state_energy(self.active,self.idle,seconds=1e-6,cycles=100,work=0)
        b=state_energy(self.active,self.idle,seconds=1e-6,cycles=500,work=0)
        self.assertEqual(a['leakage_J'],b['leakage_J'])
        self.assertAlmostEqual(b['idle_clock_background_J'],5*a['idle_clock_background_J'])

    def test_reject_impossible_occupancy(self):
        with self.assertRaises(ValueError):
            state_energy(self.active,self.idle,seconds=1e-6,cycles=100,work=101)
        with self.assertRaises(ValueError):
            state_energy(self.active,self.idle,seconds=1e-6,cycles=100,work=40,on_cycles=39)

    def test_counter_geometry_matches_delivered_RTL(self):
        self.assertEqual(merged_bitwork(4,64)['aw'],26)
        self.assertEqual(merged_bitwork(7,128)['aw'],33)
        self.assertLess(merged_bitwork(7,128)['bitwork']/merged_bitwork(4,64)['bitwork'],7/4)

    def test_real_result_no_double_count_and_no_fake_HBM_total(self):
        here=Path(__file__).resolve().parent
        a=read(here/'ANCHORS.json')
        s=read(here.parent/'scheduling_v2_20261027/results_early_dma/case_1/RESULT_SUMMARY.json')
        r=estimate(s,a,counter_gate=True,digital_gate=True)
        self.assertAlmostEqual(sum(v['energy_J'] for v in r['modules']),r['covered_onchip_J'])
        names=[v['module'] for v in r['modules']]
        self.assertEqual(len(names),len(set(names)))
        self.assertNotIn('SC_bucket_shift_reduce',names)
        self.assertNotIn('AND_threeway_comparison',names)
        self.assertIsNone(r['full_calibrated_system_J'])
        self.assertGreater(r['conditional_budget_with_legacy_external_J'],r['covered_onchip_J'])

    def test_counter_gating_and_source_count_guard(self):
        here=Path(__file__).resolve().parent;a=read(here/'ANCHORS.json')
        s=read(here.parent/'scheduling_v2_20261027/results_early_dma/case_1/RESULT_SUMMARY.json')
        off=estimate(s,a);on=estimate(s,a,counter_gate=True)
        offrow=next(x for x in off['modules'] if x['module']=='FFN_counter')
        onrow=next(x for x in on['modules'] if x['module']=='FFN_counter')
        self.assertLess(onrow['energy_J'],offrow['energy_J'])
        bad=copy.deepcopy(s);bad['actions']['locality_endpoint_update']+=1
        with self.assertRaises(ValueError):estimate(bad,a)


if __name__=='__main__':unittest.main()
