import copy,json,math,unittest
from pathlib import Path
from estimate import evaluate
HERE=Path(__file__).resolve().parent


class BudgetContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.i=json.loads((HERE/'INPUTS.json').read_bytes())

    def test_reference_16_component_reconstruction(self):
        r=self.i['reference'];t=r['time_ms']
        for k,x in r['energy_curves_mJ_plus_W_times_ms'].items():
            self.assertAlmostEqual(x['activity_mJ']+x['idle_W']*t,r['onchip_components_mJ'][k],places=10)

    def test_correct_lane_count_and_keep_independent_QK(self):
        x=evaluate(self.i)
        self.assertAlmostEqual(x['areas55_mm2']['ordinary_BF16_FMA'],9.794809008,places=9)
        self.assertEqual(x['areas55_mm2']['Attention_QK_FMA'],self.i['reference']['areas55_mm2']['Attention_QK_FMA'])
        self.assertTrue(x['independent_QK_retained'])
        self.assertEqual(x['areas55_mm2']['FFN_common_core'],self.i['reference']['areas55_mm2']['FFN_common_core'])

    def test_ordinary_MAC_work_not_scaled_by_lane_count(self):
        x=evaluate(self.i);p=self.i['prices']
        dynamic=x['components_mJ']['ordinary_BF16_FMA']-40*p['FMA16_idle_W']*50
        self.assertAlmostEqual(dynamic,self.i['reference']['actions']['digital_BF16_MAC']*p['FMA_incremental_pJ']*1e-9)

    def test_reduction_counts_change_not_adder_area(self):
        x=evaluate(self.i)
        self.assertEqual(x['activity_counts']['ordinary_final_FP32_ADD'],3256960)
        self.assertEqual(x['activity_counts']['ordinary_final_FP32_ADD']*9,self.i['reference']['actions']['digital_FP32_reduce_ADD'])
        self.assertEqual(x['areas55_mm2']['ordinary_final_reduction'],self.i['reference']['areas55_mm2']['ordinary_final_reduction'])

    def test_macro_scaling_once_and_candidate_difference(self):
        x=evaluate(self.i);y=evaluate(self.i,50,502,False)
        self.assertAlmostEqual(y['covered_area55_mm2']-x['covered_area55_mm2'],14*.03322622205*.81)
        self.assertEqual(x['SRAM_KiB'],1952)
        self.assertLess(x['covered_area55_mm2'],58)
        self.assertTrue(x['Attention_128KiB_per_group_retained'])

    def test_all_energy_and_area_groups_sum_and_power_units(self):
        for t in (45,50,55):
            x=evaluate(self.i,t)
            self.assertAlmostEqual(math.fsum(g['energy_mJ'] for g in x['groups'].values()),x['onchip_mJ'])
            self.assertAlmostEqual(math.fsum(g['area55_mm2'] for g in x['groups'].values()),x['covered_area55_mm2'])
            self.assertAlmostEqual(x['system_average_W_at4pJ']*t,x['system_mJ_at4pJ'])
            self.assertGreater(x['system_mJ_at4pJ'],x['onchip_mJ'])
            self.assertEqual(x['components_mJ']['FFN_random_service_proxy'],0)
            self.assertTrue(x['FFN_RNG_already_inside_core'])


if __name__=='__main__':unittest.main()
