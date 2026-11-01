import unittest
from .shared_memory import SharedMemory,AnalyticDRAM
from .shared_decode import SharedDecode
from .shared_audit import SharedAudit
class AuditTests(unittest.TestCase):
    def run_model(self,audited):
        h=SharedMemory(AnalyticDRAM(latency_ns=100),credit=256,response_bytes=32768,issue_per_cycle=24,return_banks=512)
        m=SharedDecode(h,layers=1,context=128,hidden=128,ffn_size=128,q_heads=4,kv_heads=1,vocab=64,gu=2,nl=2,include_lm=False,weight_layout='tile_packed')
        audit=SharedAudit(m).install() if audited else None
        r=m.run();return r,h.report(),audit.report() if audit else None
    def test_observer_has_no_timing_or_activity_effect(self):
        a,ma,_=self.run_model(False);b,mb,_=self.run_model(True)
        self.assertEqual(a,b);self.assertEqual(ma,mb)
    def test_phase_and_driver_accounting(self):
        r,m,a=self.run_model(True)
        self.assertEqual(len(a['phases']),len(r['phases']))
        for p,ref in zip(a['phases'],r['phases']):
            self.assertEqual(p['elapsed_ns'],ref['duration_ns'])
            for actor,states in p['actors'].items():
                self.assertLessEqual(sum(states.values()),p['elapsed_ns']+1e-5)
                self.assertTrue(all(v>=0 for v in states.values()))
            for k in ['with_outstanding_ns','no_DDR_demand_ns','queued_and_credit_full_ns','queued_and_response_reserved_full_ns']:
                self.assertLessEqual(p['metrics'].get(k,0),p['elapsed_ns']+1e-5)
        q=next(p for p in a['phases'] if p['stage']=='QKV')
        self.assertIn('wait_weight_ready',q['actors']['digital:QKV'])
        self.assertGreater(q['metrics']['request_RTT_sum_ns'],0)
    def test_global_bytes_and_readiness_conserve(self):
        r,m,a=self.run_model(True)
        self.assertEqual(sum(p['metrics'].get('issued_bytes',0) for p in a['phases']),sum(v['issued_bytes'] for v in m['by_kind'].values()))
        self.assertEqual(sum(p['sram_delta'].get('read_words',0) for p in a['phases']),m['SRAM']['counts']['read_words'])
        self.assertEqual(sum(p['metrics'].get('request_count',0) for p in a['phases'])*64,sum(v['issued_bytes'] for v in m['by_kind'].values()))
if __name__=='__main__':unittest.main()
