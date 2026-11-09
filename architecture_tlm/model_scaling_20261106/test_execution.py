"""Shape/bank/packing gates, independent of GPU/model payloads."""
from pathlib import Path
import json,os,sys,unittest

RUNTIME=Path(os.environ['CROSS_MODEL_RUNTIME']).resolve()
sys.path.insert(0,str(RUNTIME))
from architecture_tlm.model_scaling_20261106 import execution as e

class Gates(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mem=e.libraries(RUNTIME)[-1]
        cls.models=e.load(RUNTIME/'architecture_tlm/model_scaling_20261106/CURRENT_WORKLOAD_PLAN.json')['models']
    def test_physical_banks_and_live_metadata(self):
        for key,entry in self.models.items():
            for clock in (100,250):
                for scheme in ('SC_ising','BF16_dense','W8_dense','W8_screen'):
                    h=e.Host(RUNTIME,entry['shape'],clock,scheme,self.mem.AnalyticDRAM())
                    self.assertLessEqual(max(h.h.mem.bank_allocated),4096)
                    self.assertLessEqual(h.h.mem.top,h.h.mem.capacity)
                    m=entry['shape'];l=h.ffn_layout(m['hidden'],m['ffn'])
                    self.assertGreaterEqual(l['objects']['scales']['bytes'],entry['W8_exponent_metadata_bytes_per_layer'])
                    self.assertLessEqual(l['total_bytes'],h.scratch.size)
    def test_complete_packet_work(self):
        f=e.libraries(RUNTIME)[2]
        for entry in self.models.values():
            H,F=entry['shape']['hidden'],entry['shape']['ffn']
            for clock in (100,250):
                for path in ('BF16','W8'):
                    p=f.make_profile(clock,path);total=weights=0
                    for role,rows,K in [('Wg',F,H),('Wu',F,H),('Wd',H,F)]:
                        packets=list(f.packets(p,role,rows,K,0))
                        self.assertEqual(sum(q['rows'] for q in packets if q['last']),rows)
                        total+=sum(q['rows']*q['ks'] for q in packets)
                        weights+=sum(q['source_bytes'] for q in packets)
                        self.assertLessEqual(max(q['packed_bytes'] for q in packets),32768)
                    self.assertEqual(total,3*H*F);self.assertEqual(weights,3*H*F*(2 if path=='BF16' else 1))
    def test_reference_trace_address_coverage(self):
        records=e.load(RUNTIME/'inputs/SAMPLES.json')['samples']
        fixtures=e.load(RUNTIME/'inputs/SHAPE_FIXTURES.json')
        for key,entry in self.models.items():
            m=entry['shape'];qpg=m['q_heads']//m['kv_heads'];self.assertEqual(len(fixtures[key]),m['kv_heads'])
            for seed in (17,503,1009):
                for g in range(m['kv_heads']):
                    for layer in range(3):
                        for head in range(qpg):
                            r=records['ab_both/%d/%d/%d'%(seed,g%8,layer*4+head)]
                            self.assertEqual(len(r['indices']),64)
                            self.assertTrue(all(0<=i<128 for i in r['indices']))
                            self.assertGreaterEqual(r['cycles'],r['first']);self.assertGreaterEqual(r['first'],r['front'])
    def test_total_area_and_padding_are_explicit(self):
        for clock in (100,250):
            for scheme in ('BF16_dense','W8_dense','W8_screen'):
                v=e.allocation(RUNTIME,clock,scheme);self.assertLessEqual(v['area55_mm2'],v['target']['target_area55_mm2'])
                self.assertEqual(v['slices']%4,0)
        self.assertEqual(self.models['llama32_3b']['Q_per_KV'],3)
        self.assertEqual(self.models['deepseek_7b']['KV_waves_on8_groups'],4)

if __name__=='__main__':unittest.main()
