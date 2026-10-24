import ast,json,tempfile,unittest,sys,hashlib
from pathlib import Path
import tkinter
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import package
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'sim'))
from generate import make
from wave import clip
from scalar_vcd import scalarize,verify_pt
from summarize import power_totals,check_time_unit,window_summary
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
   header='$timescale 1ns $end\n$scope module tb_counter $end\n$scope module dut $end\n$var wire 1 ! clk $end\n$var wire 1 " out_valid $end\n$var wire 2 # result [1:0] $end\n$var wire 1 ! clock_alias $end\n$upscope $end\n$upscope $end\n$enddefinitions $end\n'
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
 def test_power_units_and_energy(self):
  text='Dynamic Power Units = 1mW\nLeakage Power Units = 1nW\nCell Internal Power = 2\nNet Switching Power = 3\nCell Leakage Power = 1000\nTotal Power = 5.001\n'
  values,scales=power_totals(text)
  self.assertAlmostEqual(values[3],.005001)
  self.assertEqual(scales,[.001,.001,1e-9,.001])
  with self.assertRaises(ValueError):power_totals(text.replace('5.001','9.0'))
  check_time_unit('Time Units = 1ns\n')
  check_time_unit('Time Unit : 1e-09 Second\n')
  with self.assertRaises(ValueError):check_time_unit('Time Unit : 1ps\n')
 def test_window_summary(self):
  with tempfile.TemporaryDirectory(dir=str(ROOT)) as d:
   p=Path(d)
   reports={'units.rpt':'Time Unit : 1ns\n',
    'power.rpt':'Dynamic Power Units = 1mW\nLeakage Power Units = 1nW\nCell Internal Power = 2\nNet Switching Power = 3\nCell Leakage Power = 1000\nTotal Power = 5.001\n',
    'inventory.tsv':'name\tref\tarea\tcategory\nu0\tDFF\t10\tstate\n',
    'cells.rpt':'Cell Power Power Power Power\n------\nu0 2 3 1000 5.001 (100.0%)\nTotals (1 cells) 2 3 1000 5.001\n',
    'activity.rpt':'Total number of nets = 10\nNumber of annotated nets = 10\n'}
   for name in ('checks.rpt','ranges.rpt','model_checks.rpt','update.rpt','check_timing.rpt'):reports[name]=''
   for name,text in reports.items():(p/name).write_text(text)
   meta=dict(setup_slack_ns=1.,hold_slack_ns=.1,duration_ns=360.,frames=1,bin_outputs=4)
   r=window_summary(p,meta)
   self.assertAlmostEqual(r['pJ_per_frame'],1800.36)
   self.assertEqual(r['area_um2'],10.)
   self.assertEqual(r['status'],'CALCULATED_PRELAYOUT')
   meta['hold_slack_ns']=-.1;meta['frames']=0;meta['bin_outputs']=0
   r=window_summary(p,meta)
   self.assertIsNone(r['pJ_per_frame']);self.assertIn('TIMING_VIOLATION',r['review_flags'])
   (p/'cells.rpt').write_text(reports['cells.rpt'].replace('Totals (1 cells)','Totals (2 cells)'))
   with self.assertRaises(ValueError):window_summary(p,meta)
 def test_snapshot_hash_and_isolation(self):
  with tempfile.TemporaryDirectory(dir=str(ROOT.parent)) as d:
   p=Path(d);src=p/'src';src.mkdir();payload=b'original\n'
   (src/'rtl.sv').write_bytes(payload)
   (src/'package_manifest.json').write_text(json.dumps(dict(files={'rtl.sv':dict(bytes=len(payload),sha256=hashlib.sha256(payload).hexdigest())})))
   with patch.object(package,'ROOT',src):
    dst=package.snapshot(p/'snapshot')
    self.assertEqual((dst/'rtl.sv').read_bytes(),payload)
    with self.assertRaises(ValueError):package.snapshot(src/'nested')
    (src/'rtl.sv').write_text('changed')
    self.assertEqual((dst/'rtl.sv').read_bytes(),payload)
    with self.assertRaises(ValueError):package.verify()
if __name__=='__main__':unittest.main()
