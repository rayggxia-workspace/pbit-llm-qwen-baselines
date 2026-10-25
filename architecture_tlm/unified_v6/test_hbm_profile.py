import copy,json,tempfile,unittest
from pathlib import Path
from .config import load
from .memory_profiles import apply,HERE
class HBMContracts(unittest.TestCase):
 def test_unchanged_non_memory(self):
  c,_=load('qwen3_4b')
  with tempfile.NamedTemporaryFile() as exe:
   d=apply(c,'mature_ddr4',exe.name,'unused')
   for mode in ('narrow','wide','pipelined'):
    h=apply(c,'mature_hbm2_'+mode,exe.name,'unused')
    self.assertEqual({k:v for k,v in d.items() if k not in ('dram','memory_profile')},{k:v for k,v in h.items() if k not in ('dram','memory_profile')})
    self.assertTrue(h['dram']['timing_only'])
 def test_geometry_and_mapping(self):
  d=json.loads((HERE/'configs/dramsys/hbm2_8ch_16GiB_timing.json').read_text())['simulation']
  a=d['memspec']['memarchitecturespec'];bits=d['addressmapping']
  self.assertEqual(sorted(x for v in bits.values() for x in v),list(range(34)))
  self.assertEqual(a['nbrOfChannels'],8);self.assertEqual(a['nbrOfPseudoChannels'],2)
  self.assertEqual(a['burstLength']*a['width']//8,32)
  self.assertGreaterEqual(min(bits['CHANNEL_BIT']),8)
  self.assertFalse(d['simconfig']['PowerAnalysis'])
 def test_no_silent_fallback(self):
  c,_=load('qwen3_4b')
  with self.assertRaises(ValueError):apply(c,'mature_hbm2_wide','does-not-exist','unused')
if __name__=='__main__':unittest.main()
