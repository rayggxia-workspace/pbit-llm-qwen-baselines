"""Integration guards: units,pricing ownership,and incomplete system reporting."""
from pathlib import Path
import os,unittest
from .prepare_bindings import prepare,ffn_core_cost

class Contracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.models=prepare(Path(os.environ['PBIT_WORKSPACE']))

    def test_distinct_frequency_contracts(self):
        a,b=(self.models[n] for n in ('250','500'))
        self.assertEqual(a['FFN_core']['modes']['GU']['frame_ns'],72)
        self.assertEqual(b['FFN_core']['modes']['GU']['frame_ns'],36)
        for m in self.models.values():
            self.assertEqual(m['area_multiplier'],1)
            self.assertEqual(m['FFN_core']['modes']['Wd']['frame_cycles'],34)

    def test_gross_idle_equivalence(self):
        core=self.models['250']['FFN_core'];frames=dict(GU=6080,Wd=3040)
        e=ffn_core_cost(core,frames,3,600000)
        idle=core['waiting_power_W']*1000
        incremental=sum(frames[m]*(core['modes'][m]['gross_pJ_per_frame']-
            idle*core['modes'][m]['frame_ns']) for m in frames)
        self.assertAlmostEqual(e['activity_pJ']+e['idle_pJ'],incremental+3*600000*idle)
        self.assertAlmostEqual(e['area_mm2'],3*core['area_mm2'])
        with self.assertRaises(AssertionError):ffn_core_cost(core,frames,1,1)

    def test_no_false_complete_system(self):
        for v in self.models.values():
            self.assertFalse(v['full_system_ready'])
            self.assertFalse(v['full_system_replay_run'])
            for k in ('area_mm2','time_ms_token','energy_mJ_token'):
                self.assertIsNone(v['full_system_'+k])
            self.assertIsNone(v['FFN_selected_core_count'])
            self.assertEqual(v['front_sampler_link']['shared_load_handshakes'],32)
            self.assertFalse(v['front_sampler_link']['fixed_service_cycle_guarantee'])

    def test_only_qualified_cards(self):
        for v in self.models.values():
            for c in v['attention_cards'].values():
                self.assertTrue(c['qualified_module_price'])
                self.assertTrue(all(x>=0 for x in c['slacks_ns'].values() if x is not None))
            self.assertTrue(all(c['timing_qualified'] for c in v['accepted_digital_components'].values()))

    def test_conditional_hold_does_not_waive_setup(self):
        for v in self.models.values():
            self.assertEqual(len(v['diagnostic_PV_cards']),2)
            for c in v['diagnostic_PV_cards']:
                self.assertLess(c['slacks_ns']['setup'],0)
                self.assertFalse(c['selected_by_SC_whole_model'])
            for c in v['conditional_attention_hold_cards'].values():
                self.assertGreaterEqual(c['slacks_ns']['setup'],0)
                self.assertGreaterEqual(c['slacks_ns']['gate_setup'],0)
                self.assertFalse(c['qualified_module_price'])
                self.assertFalse(c['hold_repaired'])
            self.assertFalse(set(v['conditional_attention_hold_cards']) & set(v['attention_cards']))

    def test_new_results_are_available_without_changing_random_path(self):
        self.assertIn('bf_explut_500',self.models['500']['attention_cards'])
        self.assertEqual(set(self.models['250']['accepted_digital_components']),
            {'integer_gu_250','nl_code8_250','w8_wd_250'})
        self.assertEqual(self.models['500']['FFN_core']['area_mm2'],0.564451146001)
        self.assertEqual(self.models['500']['shared_FMA']['status'],'NO_QUALIFIED_FMA500_PRICE')

if __name__=='__main__':unittest.main()
