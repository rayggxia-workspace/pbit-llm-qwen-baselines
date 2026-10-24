import ast
import gzip
import hashlib
import json
import sys
import tarfile
import tempfile
import tkinter
import unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import package
from summarize import power_totals,check_time_unit,window_summary
from run import compress,archive


class DeliveryTests(unittest.TestCase):
 def test_syntax(self):
  t=tkinter.Tcl()
  for p in package.files():
   if p.suffix=='.py':ast.parse(p.read_text(encoding='utf-8-sig'),feature_version=(3,6))
   if p.suffix=='.tcl':self.assertEqual(int(t.call('info','complete',p.read_text())),1,p)

 def test_units(self):
  text='Dynamic Power Units = 1mW (derived from V,C,T units)\nLeakage Power Units = 1nW\nCell Internal Power = 2\nNet Switching Power = 3\nCell Leakage Power = 1000\nTotal Power = 5.001\n'
  v,s=power_totals(text);self.assertAlmostEqual(v[3],.005001)
  check_time_unit('Time Unit : 1e-09 Second\n')
  check_time_unit('Time_unit : 1e-09 Second\n')
  check_time_unit('Time_Unit : 1000ps\n')
  with self.assertRaises(ValueError):check_time_unit('Time_unit : 1e-12 Second\n')
  with self.assertRaises(ValueError):check_time_unit('Time Unit : 1ps\n')
  with self.assertRaises(ValueError):power_totals(text.replace('5.001','100'))

 def test_reconciliation_and_no_fake_frames(self):
  with tempfile.TemporaryDirectory(dir=str(ROOT.parent)) as d:
   p=Path(d)
   reports={'units.rpt':'Time Unit : 1ns\n',
    'power.rpt':'Dynamic Power Units = 1mW\nLeakage Power Units = 1nW\nCell Internal Power = 2\nNet Switching Power = 3\nCell Leakage Power = 1000\nTotal Power = 5.001\n',
    'inventory.tsv':'name\tref\tarea\tcategory\nq_drive/u0\tBUF\t10\tq_interface_buffers\n',
    'cells.rpt':'Cell Power Power Power Power\n------\nq_drive/u0\n2 3 1000 5.001 (100.0%)\nTotals (1 cells) 2 3 1000 5.001\n',
    'activity.rpt':'Total number of nets = 10\nNumber of annotated nets = 10\n'}
   for name in ('checks.rpt','ranges.rpt','model_checks.rpt','update.rpt','check_timing.rpt'):reports[name]=''
   for name,text in reports.items():(p/name).write_text(text)
   meta=dict(setup_slack_ns=1.,hold_slack_ns=.1,duration_ns=360.,frames=1,accepted_samples=32)
   r=window_summary(p,meta);self.assertAlmostEqual(r['pJ_per_frame'],1800.36)
   self.assertAlmostEqual(r['pJ_per_sample_vector'],1800.36/32)
   meta.update(frames=0,accepted_samples=0,hold_slack_ns=-.1)
   r=window_summary(p,meta);self.assertIsNone(r['pJ_per_frame']);self.assertIsNone(r['pJ_per_sample_vector'])
   self.assertIn('TIMING_VIOLATION',r['review_flags'])
   (p/'cells.rpt').write_text(reports['cells.rpt'].replace('Totals (1 cells)','Totals (2 cells)'))
   with self.assertRaises(ValueError):window_summary(p,meta)

 def test_snapshot(self):
  with tempfile.TemporaryDirectory(dir=str(ROOT.parent)) as d:
   src=Path(d)/'source';src.mkdir();(src/'test.sv').write_bytes(b'original\n')
   with patch.object(package,'ROOT',src):
    (src/'SOURCE_MANIFEST.json').write_text(json.dumps(package.manifest()))
    target=package.snapshot(Path(d)/'snapshot')
    with self.assertRaises(ValueError):package.snapshot(src/'nested')
    (src/'test.sv').write_bytes(b'changed\n')
    self.assertEqual((target/'test.sv').read_bytes(),b'original\n')
    with self.assertRaises(ValueError):package.verify()

 def test_compress_and_small_archive(self):
  with tempfile.TemporaryDirectory(dir=str(ROOT.parent)) as d:
   out=Path(d)/'job';out.mkdir();raw=out/'raw.vcd';raw.write_bytes(b'#0\n0!\n#10\n1!\n')
   original=raw.read_bytes();compress(raw)
   self.assertFalse(raw.exists())
   with gzip.open(str(out/'raw.vcd.gz'),'rb') as f:self.assertEqual(f.read(),original)
   (out/'failure.txt').write_text('test failure');(out/'mapped.v').write_text('netlist')
   archive(out)
   with tarfile.open(str(Path(d)/'job_reports.tar.gz')) as tar:
    self.assertIn('job/failure.txt',tar.getnames());self.assertNotIn('job/mapped.v',tar.getnames())
    self.assertNotIn('job/raw.vcd.gz',tar.getnames())

 def test_binding_auto_checks_function(self):
  t=tkinter.Tcl();t.eval('''
   proc get_lib_cells {args} {if {[lindex $args end] eq "*/*BUF*_9TSVT"} {return {lib/BUF_BAD_9TSVT lib/BUF_OK_9TSVT}};return [lindex $args end]}
   proc foreach_in_collection {var vals body} {upvar 1 $var x;foreach x $vals {uplevel 1 $body}}
   proc sizeof_collection {x} {llength $x}
   proc get_object_name {x} {return $x}
   proc get_lib_pins {args} {set c [lindex $args 1];if {[lindex $args end] eq "direction == in"} {return $c/A};return $c/Y}
   proc get_attribute {obj attr} {if {$attr eq "area"} {return 1};if {[string match *BAD* $obj]} {return {!A}};return A}
   proc save_text {path text} {set ::saved($path) $text}
  ''')
  t.eval((ROOT/'flow/generate_buffer_binding.tcl').read_text())
  t.setvar('env(BUF_REF)','AUTO');t.eval('generate_buffer_binding')
  self.assertEqual(t.getvar('env(BUF_REF)'),'BUF_OK_9TSVT')
  self.assertIn('.A(a),.Y(y)',t.getvar('saved(buffer_binding.v)'))
  t.setvar('env(BUF_REF)','BUF_BAD_9TSVT')
  with self.assertRaises(tkinter.TclError):t.eval('generate_buffer_binding')


if __name__=='__main__':unittest.main()
