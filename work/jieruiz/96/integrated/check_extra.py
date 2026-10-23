"""Supplemental whole-schedule checks, distinct from the 11 module tests."""
import sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT))
from architecture_tlm.unified_v6.config import tiny
from architecture_tlm.unified_v6.model import FullDecode
from architecture_tlm.unified_v6.rng_integrated import IntegratedRandomService
from architecture_tlm.unified_v6.core import Scheduler,Ledger
class Extra(unittest.TestCase):
 def cfg(self):
  c,m=tiny();c['random'].update(backend='integrated_service',seed_word_interval_cycles=2,seed_startup_cycles=3);c['attention']['mode']='screen_pv';return c,m
 def test_stream_is_32_not_64_cycles(self):
  c,m=self.cfg();rng=IntegratedRandomService(c['random'],Scheduler(),Ledger(),10.,ffn='sc',mode='exact',group=2,context=129,candidates=192,seed=0)
  ready=rng.prepare_ffn(0,('x',0),False);done=rng.stream_ffn(ready+10,32,32,1)
  self.assertEqual(done-ready,340)
 def test_slow_seed_bus_changes_whole_decode(self):
  c,m=self.cfg();fast=FullDecode(c,m).run();c['random']['seed_word_interval_cycles']=10000;slow=FullDecode(c,m).run()
  self.assertGreater(slow['metrics']['elapsed_ns'],fast['metrics']['elapsed_ns'])
 def test_no_unconditional_clocked_random_hardware_in_control(self):
  c,m=self.cfg();c['ffn']['mode']='bf16';c['attention']['mode']='exact';r=FullDecode(c,m).run()
  self.assertIsNone(r['random_interface']['network']);self.assertEqual(r['random_interface']['calibrated_endpoint_two_state_energy_J'],0)
if __name__=='__main__':unittest.main(verbosity=2)
