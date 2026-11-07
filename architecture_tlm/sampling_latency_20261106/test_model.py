import json,unittest
from pathlib import Path
from .fastsim import stage,estimate
from .model import make_model
from architecture_tlm.unified_v6.shared_memory import AnalyticDRAM

class Sampling(unittest.TestCase):
    def test_current_layout_and_variable_frame_latency(self):
        for gu,wd in ((64,64),(8,32)):
            h,m=make_model(AnalyticDRAM(),gu_samples=gu,wd_samples=wd,
                mode='ising',ffn='sc',samples={},layers=36,include_lm=True)
            self.assertEqual(h.mem.capacity,1216*1024);self.assertEqual(m.mac_lanes,640)
            self.assertEqual(m.common_cores,12)
            h.execute([m.delay(660,'common_GU_core')]);self.assertEqual(h.now,(gu+2)*10)
            h.execute([m.delay(660,'common_Wd_core')]);self.assertEqual(h.now,(gu+wd+4)*10)
    def test_non_FFN_delay_is_not_rescaled(self):
        h,m=make_model(AnalyticDRAM(),gu_samples=8,wd_samples=32,
            mode='ising',ffn='sc',samples={},layers=36,include_lm=True)
        h.execute([m.delay(160,'unrelated_control')]);self.assertEqual(h.now,160)
    def test_invalid_sample_count(self):
        with self.assertRaises(ValueError):
            make_model(AnalyticDRAM(),gu_samples=0,mode='ising',ffn='sc',samples={},layers=36)
    def test_tile_coverage_and_bandwidth_lower_bound(self):
        r=stage(8,groups=16,blocks=8,batch=8,cores=4,slots=8,state_ports=2,bandwidth_GBs=100)
        self.assertEqual(r['frames'],128)
        self.assertGreaterEqual(r['elapsed_ns'],r['floors']['weight_ns'])
    def test_compute_bound_sampling_reduction(self):
        args=dict(groups=16,blocks=8,batch=8,cores=4,slots=8,state_ports=4,
            bandwidth_GBs=10000,state_service_ns=1,load_latency_ns=0)
        a=stage(64,**args);b=stage(8,**args)
        self.assertLess(b['elapsed_ns'],a['elapsed_ns']*.5)
    def test_bandwidth_dominance_and_state_backpressure(self):
        args=dict(groups=16,blocks=8,batch=8,cores=4,slots=8,state_ports=2,bandwidth_GBs=10)
        a=stage(64,**args);b=stage(8,**args)
        self.assertGreater(b['elapsed_ns']/a['elapsed_ns'],.95)
        c=stage(8,**dict(args,state_service_ns=5000))
        self.assertGreater(c['elapsed_ns'],b['elapsed_ns'])
    def test_reference_reproduction_and_lm_head_split(self):
        p=json.loads(Path(__file__).with_name('REFERENCE_PROFILE.json').read_bytes())
        a=estimate(p,64,64);b=estimate(p,8,32)
        self.assertAlmostEqual(a['including_lm_head_ms'],p['including_lm_head_ms'])
        self.assertAlmostEqual(b['excluding_lm_head_stage_ms']+b['lm_head_stage_ms'],b['including_lm_head_ms'])
        self.assertEqual(a['lm_head_stage_ms'],b['lm_head_stage_ms'])

if __name__=='__main__':unittest.main()
