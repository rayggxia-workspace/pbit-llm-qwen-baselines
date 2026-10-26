import copy
import unittest
from pathlib import Path
from .ppa import read,clock_account,estimate,usage_from_tlm


class TestAccounting(unittest.TestCase):
    def test_gating_cannot_remove_leakage(self):
        r=clock_account(2,100,0,.1,10,0,1e-6,1.)
        self.assertAlmostEqual(r['energy_J'],2*.1e-3*1e-6)
        self.assertAlmostEqual(r['ideal_ICG_saving_upper_bound_J'],200*10e-12)

    def test_active_cycle_cost_is_not_charged_twice(self):
        r=clock_account(1,72,72,.0697,14.843,726.24,720e-9,1.)
        # 100 MHz original frame reproduces total power with rounded PT numbers.
        self.assertAlmostEqual(r['energy_J']*1e12,1845.12,places=4)
        self.assertEqual(r['selected_clock_gating_saving_J'],0.)

    def test_capacity_guard(self):
        with self.assertRaises(ValueError):
            clock_account(2,100,201,.1,10,0,1e-6,1.)

    def test_power_anchor_boundary(self):
        a=read(Path(__file__).with_name('PPA_ANCHORS.json'))
        ratio=a['area_100MHz']['counter_b7_t128_m8']['area_um2']/1e6*256
        self.assertAlmostEqual(ratio,209.80279296,places=7)

    def test_automatic_output_boundary_and_500MHz(self):
        s={'config':{'core_hz':500000000,'ffn':{'mode':'sc','engines':1,
             'samples':64,'nonlinear_samples':128,'restore_lanes':8,'accumulate_lanes':8,
             'locality':{'tile':64}}},
           'metrics':{'elapsed_ns':10000},
           'FFN_activity':{'SC_4bucket_tiles':1,'SC_7bucket_tiles':1},
           'actions':{'SC_coefficient16_restore':128},
           'clock_gating':{'enabled':True,'resources':{
             'sc:0':{'clock_on_ns':424},
             'ffn_SC_bucket_shift_reduce':{'clock_on_ns':64},
             'ffn_SC_coefficient16_restore':{'clock_on_ns':72}}}}
        u=usage_from_tlm(s)
        self.assertEqual(u['counter']['output_channels'],64)
        self.assertEqual(u['counter']['frames'][0]['count'],64)
        self.assertEqual(u['counter']['on_instance_cycles'],64*212)
        self.assertEqual(u['gating_efficiency'],0.8)
        self.assertEqual(u['restore']['on_instance_cycles'],8*(64+72)/2)
        a=read(Path(__file__).with_name('PPA_ANCHORS.json'))
        r=estimate(s,u,a)
        counter=next(x for x in r['modules'] if x['module']=='FFN_counter')
        self.assertAlmostEqual(counter['area_mm2'],8*.819542159999,places=7)
        self.assertIsNone(r['full_chip_energy_J'])
        self.assertGreater(r['counter_restore_only_clock_gating']['maximum_dynamic_saving_J'],0)
        s['config']['ffn']['locality']['tile']=128
        with self.assertRaises(ValueError):
            usage_from_tlm(s)


if __name__=='__main__':
    unittest.main()
