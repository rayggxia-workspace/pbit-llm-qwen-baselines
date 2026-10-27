"""Host-only flow tests. Fake files are NOT technology or gate simulations."""
import importlib.util,json,subprocess,sys,tempfile,unittest
from pathlib import Path
P=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location("driver",P/"run_case.py");d=importlib.util.module_from_spec(sp);sp.loader.exec_module(d)
class Flow(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory(prefix="cv2-flow-test-");self.p=Path(self.t.name)
  for name in ("a.sv","tb.sv","lib.db","cells.v","icg.sv"):(self.p/name).write_text("test fixture only\n")
  self.c=dict(id="case",top="top",tb_top="tb",rtl_files=["a.sv"],tb_files=["tb.sv"])
  self.l=dict(target_db="lib.db",reference_cell="INV1",verilog_models=["cells.v"],corner="ss",voltage_v=1.08,temperature_c=125)
 def tearDown(self):self.t.cleanup()
 def norm(self):return d.normalize(self.c,self.l,self.p,self.p)
 def test_defaults(self):
  c,l=self.norm();self.assertEqual(c["period_ns"],10);self.assertEqual(c["uncertainty_ns"],.5)
 def test_500(self):
  self.c["frequency_mhz"]=500;c,_=self.norm();self.assertEqual(c["period_ns"],2);self.assertEqual(c["uncertainty_ns"],.1)
 def test_reject_mode1(self):
  self.c["gate_mode"]=1
  with self.assertRaises(ValueError):self.norm()
 def test_reject_missing_icg(self):
  self.c["gate_mode"]=2
  with self.assertRaises((ValueError,KeyError)):self.norm()
 def test_icg(self):
  self.c["gate_mode"]=2;self.l.update(icg_cell="CLKG1",icg_wrapper="icg.sv",icg_enable_pin="EN",icg_test_enable_pin="TE");c,_=self.norm()
  self.assertIn("PB_ICG_TECH_MAPPED",c["defines"]);self.assertIn(self.p/"icg.sv",c["rtl_files"])
 def test_bad_frequency(self):
  self.c["frequency_mhz"]=0
  with self.assertRaises(ValueError):self.norm()
 def test_no_source(self):
  self.c["rtl_files"]=["missing.sv"]
  with self.assertRaises(ValueError):self.norm()
 def test_define(self):
  self.c["defines"]=["OK;bad"]
  with self.assertRaises(ValueError):self.norm()
 def test_tcl_safe(self):
  with self.assertRaises(ValueError):d.tcl("a} [bad]")
 def test_constraints(self):
  c,l=self.norm();s=d.configuration(c,l);self.assertIn("set ::CV2_PERIOD_NS {10.0}",s)
  common=(P/"common.tcl").read_text();self.assertNotIn("set_false_path",common);self.assertNotIn("set_multicycle_path",common)
 def test_power_mixed_units(self):
  a=d.power_parse("Cell Internal Power = 1.2 mW\nNet Switching Power = 3 uW\nCell Leakage Power = 20 nW\nTotal Power = 1.20302 mW")
  self.assertAlmostEqual(a["total_w"],.00120302);self.assertAlmostEqual(a["leakage_w"],2e-8)
 def test_power_header_units(self):
  a=d.power_parse("Dynamic Power Units = 1 W\nLeakage Power Units = 1 uW\nCell Internal Power = .002\nNet Switching Power = .0001\nCell Leakage Power = 20\nTotal Power = .00212")
  self.assertAlmostEqual(a["leakage_w"],20e-6);self.assertTrue(a["power_sum_consistent"])
 def test_power_bad_total(self):
  a=d.power_parse("Cell Internal Power = 1 mW\nNet Switching Power = 1 mW\nCell Leakage Power = 0 W\nTotal Power = 100 mW")
  self.assertFalse(a["power_sum_consistent"])
 def test_activity(self):
  a=d.activity_parse("Total number of nets = 100\nNumber of annotated nets = 90 (90%)\nTotal number of leaf cells = 20\nNumber of fully annotated leaf cells = 20")
  self.assertEqual(a["net_coverage_percent"],90);self.assertEqual(a["leaf_coverage_percent"],100)
 def test_unknown_power(self):self.assertIsNone(d.power_parse("unrecognized")["total_w"])
 def test_sta(self):
  self.assertEqual(d.collect_sta(self.p)["status"],"unknown")
  (self.p/"setup_slack_ns.txt").write_text("-0.01");(self.p/"hold_slack_ns.txt").write_text("0.1")
  self.assertEqual(d.collect_sta(self.p)["status"],"not_met")
 def test_no_gating_paths(self):
  (self.p/"setup_slack_ns.txt").write_text("1");(self.p/"hold_slack_ns.txt").write_text("1")
  self.assertEqual(d.collect_sta(self.p,2)["status"],"review_required")
 def test_gating_slack(self):
  for name in ("setup","hold"):(self.p/(name+"_slack_ns.txt")).write_text("1")
  for name in ("gate_setup","gate_hold"):
   (self.p/(name+"_slack_ns.txt")).write_text("1");(self.p/(name+".rpt")).write_text("clock gating-check end-point")
  self.assertEqual(d.collect_sta(self.p,2)["status"],"met")
  (self.p/"gate_hold_slack_ns.txt").write_text("-1")
  self.assertEqual(d.collect_sta(self.p,2)["status"],"not_met")
 def test_area_evidence(self):
  self.l["area_scale_um2"]=1
  with self.assertRaises(ValueError):self.norm()
 def test_reuse_provenance(self):
  c,l=self.norm();folder=self.p/"synth";folder.mkdir();(folder/"mapped.v").write_text("module top;endmodule")
  serial={k:[str(x) for x in v] if isinstance(v,list) else v for k,v in c.items()}
  old=dict(status="completed_provisional",case=serial,source_sha256={str(x):d.digest(x) for x in c["rtl_files"]+[l["target_db"]]+l["verilog_models"]},netlist_sha256=d.digest(folder/"mapped.v"))
  (self.p/"RESULT.json").write_text(json.dumps(old))
  d.validate_reuse(folder,c,l)
  (folder/"mapped.v").write_text("different")
  with self.assertRaises(ValueError):d.validate_reuse(folder,c,l)
 def test_cli_preflight(self):
  c,l=self.norm()
  c["rtl_files"]=[str(x) for x in c["rtl_files"]];c["tb_files"]=[str(x) for x in c["tb_files"]]
  l["target_db"]=str(l["target_db"]);l["verilog_models"]=[str(x) for x in l["verilog_models"]]
  (self.p/"case.json").write_text(json.dumps(c));(self.p/"library.json").write_text(json.dumps(l))
  cmd=[sys.executable,str(P/"run_case.py"),"--case",str(self.p/"case.json"),"--library",str(self.p/"library.json"),"--output",str(self.p/"out")]
  r=subprocess.run(cmd,capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr)
  value=json.loads((self.p/"out/RESULT.json").read_text());self.assertEqual(value["status"],"preflight_passed")
  self.assertFalse((self.p/"out/synth").exists())
 def test_tcl_complete(self):
  try:import tkinter
  except ImportError:self.skipTest("Tk/Tcl runtime unavailable")
  try:tcl=tkinter.Tcl()
  except tkinter.TclError:self.skipTest("Tcl runtime unavailable")
  for f in P.glob("*.tcl"):self.assertEqual(int(tcl.call("info","complete",f.read_text(encoding="utf-8"))),1,f.name)
 def fixture(self):
  (self.p/"vectors.txt").write_text("1\n0 0 0\n")
  (self.p/"expected.json").write_text("[]")
  (self.p/"validator.py").write_text("print('mock')")
  cfg=dict(top="top",period_ns=10,vector_sha256=d.digest(self.p/"vectors.txt"),expected_sha256=d.digest(self.p/"expected.json"),start_ns=10,end_ns=20,frames=2,accepted_samples=2)
  (self.p/"FIXTURE.json").write_text(json.dumps(cfg))
  self.c.update(fixture_manifest="FIXTURE.json",validator_script="validator.py")
  return cfg
 def test_fixture_valid(self):
  self.fixture();c,_=self.norm();f=d.validate_fixture(c)
  self.assertEqual(len(c["data_files"]),2);self.assertEqual(f["frames"],2)
 def test_fixture_changed(self):
  self.fixture();(self.p/"vectors.txt").write_text("changed");c,_=self.norm()
  with self.assertRaises(ValueError):d.validate_fixture(c)
 def test_fixture_frequency_mismatch(self):
  self.fixture();self.c["frequency_mhz"]=500;c,_=self.norm()
  with self.assertRaises(ValueError):d.validate_fixture(c)
 def test_fixture_no_validator(self):
  self.fixture();del self.c["validator_script"];c,_=self.norm()
  with self.assertRaises(ValueError):d.validate_fixture(c)
 def test_fixture_window_counts(self):
  f=self.fixture();w=dict(start_ns=10.,end_ns=20.,operations=2,accepted_samples=2)
  d.validate_window_fixture(w,f);w["operations"]=3
  with self.assertRaises(ValueError):d.validate_window_fixture(w,f)
 def test_fixture_window_time(self):
  f=self.fixture();w=dict(start_ns=0.,end_ns=20.,operations=2,accepted_samples=2)
  with self.assertRaises(ValueError):d.validate_window_fixture(w,f)
 def counter_cases(self,extra):
  output=self.p/"cases"
  cmd=[sys.executable,str(P/"make_counter_cases.py"),"--output",str(output),"--bins","4","--pipeline","1","--modes","continuous"]+extra
  result=subprocess.run(cmd,capture_output=True,text=True)
  self.assertEqual(result.returncode,0,result.stderr)
  return json.loads(next(output.glob("*.json")).read_text(encoding="utf-8"))
 def test_counter_threshold_profile_default(self):
  c=self.counter_cases([])
  self.assertEqual(c["threshold_profile"],"swept");self.assertEqual(c["threshold_seed"],193)
  self.assertIn("+THRESHOLD_PROFILE=swept",c["plusargs"]);self.assertIn("+THRESHOLD_SEED=193",c["plusargs"])
 def test_counter_threshold_profile_uniform(self):
  c=self.counter_cases(["--threshold-profile","uniform","--threshold-seed","42","--p8","64"])
  self.assertEqual(c["threshold_profile"],"uniform");self.assertEqual(c["center_p8"],64)
  self.assertIn("+THRESHOLD_PROFILE=uniform",c["plusargs"]);self.assertIn("+THRESHOLD_SEED=42",c["plusargs"]);self.assertIn("+P8=64",c["plusargs"])
 def test_hash(self):self.assertEqual(len(d.digest(self.p/"a.sv")),64)
if __name__=="__main__":unittest.main()
