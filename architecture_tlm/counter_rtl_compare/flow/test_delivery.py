import ast,json,tempfile,unittest,sys,hashlib
from pathlib import Path
import tkinter
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'sim'))
from generate import make
from wave import clip
from scalar_vcd import scalarize,verify_pt
ROOT=Path(__file__).resolve().parents[1]
class Tests(unittest.TestCase):
 def test_syntax(self):
  t=tkinter.Tcl()
  for p in ROOT.rglob('*.py'):ast.parse(p.read_text(encoding='utf-8-sig'),feature_version=(3,6))
  for p in (ROOT/'flow').glob('*.tcl'):self.assertEqual(int(t.call('info','complete',p.read_text(encoding='utf-8-sig'))),1,p)
 def test_no_weight_register(self):
  s=''.join(p.read_text() for p in (ROOT/'rtl').glob('*.sv'))
  self.assertNotIn('weights<=',s);self.assertIn('input wire [N*M*8-1:0] weights',s)
 def test_widths(self):
  for t,cw,sw in [(16,11,19),(32,12,20),(64,13,21)]:
   self.assertEqual((64*t).bit_length(),cw);self.assertEqual((64*t*128).bit_length()+1,sw)
   self.assertLess(64*t*128,2**(sw-1));self.assertGreaterEqual(64*t*128,2**(sw-2))
 def test_activity_profiles(self):
  with tempfile.TemporaryDirectory(dir=str(ROOT)) as d:
   for profile in ['mixed','sparse','dense','zero']:
    v=make(Path(d)/profile,64,2,32,17,4,profile)
    self.assertEqual(v['frames'],4)
    if profile=='zero':self.assertTrue(all(int(s,16)==0 for s in (Path(d)/profile/'gold.hex').read_text().splitlines()))
 def test_scalar_activity_and_rejection(self):
  with tempfile.TemporaryDirectory(dir=str(ROOT)) as d:
   p=Path(d);raw=p/'raw.vcd'
   header='$timescale 1ns $end\n$scope module tb_counter $end\n$scope module dut $end\n$var wire 1 ! clk $end\n$var wire 1 " out_valid $end\n$var wire 2 # result [1:0] $end\n$upscope $end\n$upscope $end\n$enddefinitions $end\n'
   raw.write_text(header+'#0\n0!\n0"\nb00 #\n#5\n1!\n#10\n0!\n1"\nb11 #\n#15\n1!\n#20\n0!\n')
   c=clip(raw,p/'window.vcd',5,20);self.assertEqual(c['xz_signals'],0)
   e=scalarize(p/'window.vcd',p/'scalar.vcd',2);self.assertTrue(e['all_bits_preserved'])
   self.assertEqual(len(e['expected_activity']),4)
   rows=['name\ttoggle_rate\tstatic_probability\tsource']
   for n,v in e['expected_activity'].items():rows.append('%s\t%.12f\t%.12f\tport'%(n,v['toggle_rate_per_ns'],v['static_probability']))
   (p/'actual.tsv').write_text('\n'.join(rows)+'\n');self.assertEqual(verify_pt(e,p/'actual.tsv')['status'],'PASS')
   (p/'bad.vcd').write_text((p/'window.vcd').read_text().replace('b11 #','bxx #'))
   with self.assertRaises(ValueError):scalarize(p/'bad.vcd',p/'badscalar.vcd',2)
 def test_same_synthesis_boundary(self):
  s=(ROOT/'flow/dc.tcl').read_text();self.assertIn('capture compile.rpt {compile}',s)
  self.assertNotIn('set_case_analysis',s);self.assertNotIn('dont_touch',s)
if __name__=='__main__':unittest.main()
