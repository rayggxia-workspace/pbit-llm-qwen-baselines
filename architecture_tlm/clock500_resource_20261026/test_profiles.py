import unittest,sys
from pathlib import Path
from .profiles import configuration
from architecture_tlm.unified_v6.ffn_latest import batch_cycles
class Profiles(unittest.TestCase):
 def test_domains_and_capacity(self):
  c,m=configuration(dict(expanded_compute=True,expanded_sram=True),sys.executable,Path('dram-test-only'))
  self.assertEqual(c['core_hz'],500000000)
  self.assertEqual(c['random']['clock_hz'],c['core_hz'])
  self.assertEqual(c['sram']['clock_hz'],80000000)
  self.assertEqual(c['sram']['banks'],512)
  self.assertEqual(c['sram']['macro_depth'],256)
  self.assertEqual(c['sram']['capacity_bytes'],8*1024**2)
  self.assertEqual(c['dram']['descriptor_span_ns'],2)
  self.assertEqual(c['dram']['frontend_response_capacity_bytes'],32768)
  self.assertEqual(c['digital_weight_chunk_bytes'],65536)
  self.assertEqual(c['ffn']['local_weight_bytes'],131072)
  self.assertGreaterEqual(c['weight_chunk_bytes'],131072)
  self.assertEqual(c['ffn']['nonlinear_samples'],128)
  self.assertEqual(m['num_hidden_layers'],36)
 def test_per_wave_cycles(self):
  # Quadrupled outputs and postprocess lanes preserve per-full-wave cycle budget.
  for bins in (4,7):
   self.assertEqual(batch_cycles(512*bins,64,3),batch_cycles(2048*bins,256,3))
  self.assertEqual(batch_cycles(512,16,6),batch_cycles(2048,64,6))
  self.assertEqual(batch_cycles(512,32,2),batch_cycles(2048,128,2))
 def test_memory_unchanged_by_core_frequency(self):
  a,_=configuration(dict(core_hz=100000000),sys.executable,Path('a'))
  b,_=configuration(dict(core_hz=500000000),sys.executable,Path('b'))
  self.assertEqual(a['sram'],b['sram'])
  for key in ('configuration','host_request_bytes','max_pending','controller_admission_limit'):
   self.assertEqual(a['dram'][key],b['dram'][key])
 def test_rng_reference_energy(self):
  # At 500M the reference energy/edge stays at its measured 100M value.
  c,_=configuration({},sys.executable,Path('a'))
  self.assertEqual(c['random']['energy_reference_hz'],100000000)
if __name__=='__main__':unittest.main()
