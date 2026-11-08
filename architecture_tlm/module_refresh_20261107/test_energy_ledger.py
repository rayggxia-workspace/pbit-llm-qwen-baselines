"""Energy convention and double-counting gates; no simulator/PDK required."""
from pathlib import Path
import importlib.util,json,math,unittest

HERE=Path(__file__).parent
def read_module(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
B=read_module('tested_binding',HERE/'bindings.py')
L=read_module('tested_ledger',HERE/'energy_ledger.py')

class EnergyLedger(unittest.TestCase):
    def test_accepted_timing_and_sample_counts(self):
        x=B.core_contract(250)
        self.assertEqual((x['modes']['GU']['samples'],x['modes']['Wd']['samples']),(16,32))
        self.assertEqual((x['modes']['GU']['frame_cycles'],x['modes']['Wd']['frame_cycles']),(19,35))
        self.assertEqual((x['modes']['GU']['frame_ns'],x['modes']['Wd']['frame_ns']),(76,140))
        old=B.core_contract(100);self.assertEqual((old['modes']['GU']['frame_cycles'],old['modes']['Wd']['frame_cycles']),(18,34))
    def test_gross_remaining_equals_incremental_residency(self):
        for clock in (100,250):
            x=B.core_budget(dict(GU_frames=17,Wd_M128_frames=9),100000,3,clock)
            self.assertAlmostEqual(x['total_mJ'],x['equivalent_incremental_plus_idle_mJ'],places=13)
            self.assertGreater(x['idle_already_inside_active_gross_mJ'],0)
            self.assertEqual(x['active_core_ns']+x['waiting_core_ns'],300000)
    def test_no_service_and_overcommitted_service(self):
        x=B.core_budget({},1000,3,250);self.assertAlmostEqual(x['total_mJ'],3*1000*.001536/1e6)
        with self.assertRaises(ValueError):B.core_budget(dict(GU_frames=100),1,1,250)
    def test_ledger_shared_owner_and_sum(self):
        f=B.core_budget(dict(GU_frames=1),1000,1,250)
        active=f['active_gross_mJ']*1000;wait=f['waiting_mJ']*1000
        out=L.reconcile(area={'FFN':f['area55_mm2'],'SparQ_top_and_norm':1},shared_area={'SRAM':2},
            service_uJ={'FFN':active,'SparQ_top_and_norm':2},resident_uJ={'FFN':wait,'SparQ_top_and_norm':3},
            gating_uJ={'screen_top16':1,'screen_norm16':.5},status={},time_ns=1000,external_bytes=64,
            external_tariffs=(4.,),expected_onchip_uJ=active+wait+3.5,ffn_label='FFN',ffn=f)
        self.assertTrue(out['numerical_sum_closed']);self.assertFalse(out['silicon_complete'])
        self.assertAlmostEqual(out['external_pJ_per_bit_scenarios']['4.0']['external_uJ'],64*8*4/1e6)
        self.assertEqual(sum(x['resource_id']=='SparQ_top_and_norm' for x in out['components']),1)
        args=dict(area={'x':1},shared_area={'x':1},service_uJ={},resident_uJ={},gating_uJ={},status={},time_ns=1000,
            external_bytes=0,external_tariffs=(4.,),expected_onchip_uJ=0,ffn_label='FFN',ffn=f)
        with self.assertRaises(ValueError):L.reconcile(**args)

if __name__=='__main__':unittest.main()
