import unittest
from planner import allocate,unique_area,plan
from workload import counts

class Budget(unittest.TestCase):
    def test_shared_pool_charged_once_and_legal_sizes(self):
        pool=dict(resource_id='all_matrix_pool',area55_mm2_per_slice=.25,lanes_per_slice=16)
        fixed=[dict(resource_id='SRAM',area55_mm2=7),dict(resource_id='DMA',area55_mm2=1),dict(resource_id='SRAM',area55_mm2=7)]
        r=allocate(10,fixed,pool,[4,8,12]);self.assertEqual(r['slices'],8)
        self.assertEqual(r['total_area55_mm2'],10);self.assertIsNone(r['latency_ms'])
        with self.assertRaises(ValueError):
            unique_area([dict(resource_id='same',area55_mm2=1),dict(resource_id='same',area55_mm2=2)])
    def test_infeasible_not_negative_lanes(self):
        r=allocate(1,[dict(resource_id='fixed',area55_mm2=2)],dict(resource_id='pool',area55_mm2_per_slice=.1,lanes_per_slice=16),[1,2])
        self.assertEqual(r['status'],'infeasible')
    def test_model_counts_and_weight_quantization_boundary(self):
        m=dict(hidden=2560,ffn=9728,layers=36,q_heads=32,kv_heads=8,head_dim=128,vocab=151936)
        r=counts(m);p=r['per_layer']
        self.assertEqual(p['GU_MAC']+p['Wd_MAC'],74711040)
        self.assertEqual(p['SparQ_coarse_MAC']+p['SparQ_selected_QK_MAC'],2621440)
        self.assertEqual(p['dense_PV_MAC'],8388608)
        self.assertEqual(p['selected_exact_PV_MAC'],524288)
        self.assertEqual(r['total_weight_bytes_including_head']['BF16']-r['total_weight_bytes_including_head']['W8_FFN'],36*74711040)
    def test_missing_modules_cannot_become_free_baseline(self):
        t=dict(versions={'100':dict(target_area55_mm2=10,SRAM_KiB=1088,target_status='reference',
            digital_host_fixed_components=[dict(resource_id='SRAM',area55_mm2=7)],
            pool_unit_reference=dict(area55_mm2_per_slice=.25))})
        rows=plan(t)['cases'];self.assertEqual(len(rows),3)
        self.assertTrue(all(r['status'].startswith('waiting_') for r in rows))

if __name__=='__main__':unittest.main()
