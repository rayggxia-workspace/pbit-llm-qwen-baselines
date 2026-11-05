"""No-license tests. All generated files stay under explicit --tmp-root."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest

from parse_results import EvidenceError, parse_stage
from run_case import (archive_reports, digest, load_cases, run_process, save,
                      snapshot, source_inventory, verify_functional)

TMP_ROOT = None


class FlowTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='flow-test-',dir=str(TMP_ROOT))
        self.root=Path(self.temp.name)
        self.stage=self.root/'stage';self.stage.mkdir()
        self.log=self.root/'tool.log';self.log.write_text('Tool mock log\n',encoding='utf-8')
        reports={
            'STAGE_COMPLETE':'dc\n',
            'pvt.txt':'corner=ss\nvoltage_V=1.08\ntemperature_C=125\nlibrary=test_ss\ncondition=ss_v1p08_125c\ntime_unit=ns\ncapacitance_unit=pF\n',
            'setup_slack_ns.txt':'2.5\n','hold_slack_ns.txt':'.15\n',
            'setup.rpt':'slack (MET) 2.5\n','hold.rpt':'slack (MET) .15\n',
            'constraints.rpt':'No violations.\n','check_design.rpt':'Design checked.\n',
            'check_timing.rpt':"Information: Checking 'no_input_delay'.\nInformation: Checking 'no_clock'.\nInformation: Checking 'unconstrained_endpoints'.\ncheck_timing succeeded.\nRETURN: 1\n",
            'mapping_audit.txt':'mapped_leaf_cells=10\nunmapped_leaf_cells=0\nnonlibrary_leaf_cells=0\narea_library_units=100.0\n',
            'area.rpt':'Total cell area: 100.0\n',
        }
        for name,text in reports.items():(self.stage/name).write_text(text,encoding='utf-8')

    def tearDown(self):self.temp.cleanup()

    def parsed(self):return parse_stage(self.stage,self.log,'ss','dc')

    def replace(self,name,old,new):
        path=self.stage/name;path.write_text(path.read_text().replace(old,new),encoding='utf-8')

    def test_met_without_power(self):
        r=self.parsed();self.assertEqual(r['status'],'met');self.assertIsNone(r['power_W'])

    def test_negative_setup_is_not_met(self):
        (self.stage/'setup_slack_ns.txt').write_text('-2.5')
        self.assertEqual(self.parsed()['status'],'not_met')

    def test_negative_hold_is_not_met(self):
        (self.stage/'hold_slack_ns.txt').write_text('-0.01')
        self.assertEqual(self.parsed()['status'],'not_met')

    def test_drc_violation_is_not_met(self):
        (self.stage/'constraints.rpt').write_text('max_transition (VIOLATED)')
        self.assertEqual(self.parsed()['status'],'not_met')

    def test_missing_slack_fails(self):
        (self.stage/'setup_slack_ns.txt').unlink()
        with self.assertRaises(EvidenceError):self.parsed()

    def test_nan_slack_fails(self):
        (self.stage/'setup_slack_ns.txt').write_text('NaN')
        with self.assertRaises(EvidenceError):self.parsed()

    def test_bad_pvt_fails(self):
        self.replace('pvt.txt','voltage_V=1.08','voltage_V=1.2')
        with self.assertRaises(EvidenceError):self.parsed()

    def test_unknown_units_fail(self):
        self.replace('pvt.txt','time_unit=ns','time_unit=ps')
        with self.assertRaises(EvidenceError):self.parsed()

    def test_unmapped_fails(self):
        self.replace('mapping_audit.txt','unmapped_leaf_cells=0','unmapped_leaf_cells=1')
        with self.assertRaises(EvidenceError):self.parsed()

    def test_unconstrained_fails(self):
        with (self.stage/'check_timing.rpt').open('a') as s:s.write('Warning: 2 unconstrained endpoints\n')
        with self.assertRaises(EvidenceError):self.parsed()

    def test_missing_check_coverage_fails(self):
        self.replace('check_timing.rpt',"Information: Checking 'unconstrained_endpoints'.",'')
        with self.assertRaises(EvidenceError):self.parsed()

    def test_error_in_log_fails(self):
        self.log.write_text('Error: Unresolved reference\n')
        with self.assertRaises(EvidenceError):self.parsed()

    def test_area_mismatch_fails(self):
        self.replace('area.rpt','100.0','120.0')
        with self.assertRaises(EvidenceError):self.parsed()

    def test_completed_marker_required(self):
        (self.stage/'STAGE_COMPLETE').unlink()
        with self.assertRaises(EvidenceError):self.parsed()

    def make_source(self):
        p=self.root/'package';p.mkdir()
        for name in ('rtl','tests','flow'):(p/name).mkdir()
        (p/'rtl/top.sv').write_text('module TOP(input clk, rst_n); endmodule\n')
        (p/'tests/run_all.py').write_text('# fixture only\n')
        (p/'flow/example.py').write_text('# fixture only\n')
        save(p/'cases.json',dict(schema_version=1,cases=[dict(id='one',top='TOP',smoke=True)]))
        return p

    def test_snapshot_and_duplicate_destination(self):
        p=self.make_source();target=self.root/'frozen'
        original=snapshot(p,target)
        self.assertEqual(source_inventory(target),original)
        with self.assertRaises(FileExistsError):snapshot(p,target)

    def test_private_source_is_rejected(self):
        p=self.make_source();(p/'flow/user.db').write_text('not a library')
        with self.assertRaises(EvidenceError):source_inventory(p)

    def test_cases_identifiers_and_smoke(self):
        p=self.make_source();self.assertEqual(load_cases(p)[0]['id'],'one')
        save(p/'cases.json',dict(schema_version=1,cases=[dict(id='x;touch bad',top='TOP',smoke=True)]))
        with self.assertRaises(EvidenceError):load_cases(p)

    def test_functional_sha_gate(self):
        p=self.make_source();inventory=source_inventory(p)
        summary=self.root/'summary.json'
        save(summary,dict(status='passed',case_id='one',source_sha256=inventory))
        self.assertEqual(verify_functional(summary,'one',inventory)['status'],'passed')
        inventory['rtl/top.sv']='0'*64
        with self.assertRaises(EvidenceError):verify_functional(summary,'one',inventory)

    def test_process_success_receipt(self):
        receipt=self.root/'process.json'
        r=run_process([sys.executable,'-c','print(123)'],self.root,os.environ.copy(),10,self.log,receipt)
        self.assertEqual(r['returncode'],0);self.assertEqual(r['log_sha256'],digest(self.log))

    def test_timeout_receipt(self):
        receipt=self.root/'timeout.json'
        with self.assertRaises(EvidenceError):
            run_process([sys.executable,'-c','import time;time.sleep(10)'],self.root,os.environ.copy(),.1,self.log,receipt)
        self.assertEqual(json.loads(receipt.read_text())['status'],'timeout')

    def test_archive_excludes_library_and_netlist(self):
        run=self.root/'run';run.mkdir();(run/'receipts').mkdir();(run/'work/dc').mkdir(parents=True)
        for name in ('mapped.v','library_private.rpt','secret.db','setup.rpt'):
            (run/'work/dc'/name).write_text('synthetic fixture\n')
        save(run/'RESULT.json',dict(status='failed'))
        archive_reports(run)
        with tarfile.open(run/'reports.tar.gz') as t:
            names=t.getnames()
        self.assertIn('work/dc/setup.rpt',names)
        for name in ('mapped.v','library_private.rpt','secret.db'):
            self.assertFalse(any(x.endswith(name) for x in names))

    def prepare_submission_fixture(self):
        p=self.make_source()
        for source in Path(__file__).resolve().parent.iterdir():
            if source.is_file():shutil.copyfile(source,p/'flow'/source.name)
        environment=self.root/'user_env.sh';environment.write_text('# synthetic fixture only\n')
        args=[sys.executable,'-B',str(p/'flow/submit.py'),'--suite','smoke','--env',str(environment),
              '--corner','ss','--output-root',str(self.root/'prepared')]
        run=subprocess.run(args,capture_output=True,text=True,timeout=15)
        self.assertEqual(run.returncode,0,run.stderr)
        info=json.loads(run.stdout)
        return p,environment,Path(info['submission'])

    def test_slurm_prepare_only_is_frozen(self):
        _,_,submission=self.prepare_submission_fixture()
        receipt=json.loads((submission/'SUBMISSION.json').read_text())
        self.assertEqual(receipt['status'],'prepared_only')
        self.assertTrue(receipt['jobs_not_started'])
        manifest=json.loads((submission/'SOURCE_MANIFEST.json').read_text())
        self.assertEqual(source_inventory(submission/'source'),manifest['source_sha256'])
        self.assertNotIn(b'\r',(submission/'job.sh').read_bytes())

    def test_array_environment_change_has_failure_receipt(self):
        _,environment,submission=self.prepare_submission_fixture()
        environment.write_text('# changed after snapshot\n')
        env=os.environ.copy();env['SLURM_ARRAY_TASK_ID']='0'
        run=subprocess.run([sys.executable,'-B',str(submission/'source/flow/array_entry.py'),
                            '--plan',str(submission/'PLAN.json')],env=env,capture_output=True,text=True,timeout=15)
        self.assertEqual(run.returncode,2,run.stderr)
        receipts=list(submission.glob('ARRAY_RECEIPT_*.json'))
        self.assertEqual(len(receipts),1)
        data=json.loads(receipts[0].read_text())
        self.assertEqual(data['status'],'failed');self.assertIn('Environment setup changed',data['error'])


class TclTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import tkinter
            cls.tcl=tkinter.Tcl();cls.TclError=tkinter.TclError
        except (ImportError,RuntimeError) as exc:
            raise unittest.SkipTest('Tcl interpreter unavailable: '+str(exc))
        cls.flow=Path(__file__).resolve().parent
        cls.tcl.call('source',str(cls.flow/'library_conditions.tcl'))

    def test_all_tcl_syntactically_complete(self):
        for path in self.flow.glob('*.tcl'):
            with self.subTest(path=path.name):
                self.assertEqual(int(self.tcl.call('info','complete',path.read_text(encoding='utf-8'))),1)

    def test_no_synchronous_reset_exception(self):
        text=(self.flow/'common.tcl').read_text()
        import re
        self.assertFalse(re.search(r'^\s*(set_false_path|set_multicycle_path|set_case_analysis)\b',text,re.M))

    def test_pvt_table(self):
        text='Operating Conditions:\nName Process Temp Voltage Tree Type\nss_v1p08_125c 1.0 125 1.08 balanced_case\n\nWire Load Models: none\n'
        result=self.tcl.call('oc_from_report',text,'test','fixture')
        self.assertEqual(float(self.tcl.call('dict','get',result,'voltage')),1.08)

    def test_pvt_named_block(self):
        text='Operating Conditions:\nOperating Condition Name: tt_v1p2_25c\nProcess: 1\nTemperature: 25\nVoltage: 1.2\n\nWire Load Models: none\n'
        result=self.tcl.call('oc_from_report',text,'test','fixture')
        self.assertEqual(float(self.tcl.call('dict','get',result,'temperature')),25)

    def test_missing_pvt_fails(self):
        with self.assertRaises(self.TclError):self.tcl.call('oc_from_report','nothing','test','fixture')

    def test_ambiguous_pvt_fails(self):
        text='Operating Conditions:\nName Process Temp Voltage\nss 1 125 1.08\ntt 1 25 1.2\n'
        with self.assertRaises(self.TclError):self.tcl.call('oc_from_report',text,'test','fixture')


def main():
    global TMP_ROOT
    p=argparse.ArgumentParser();p.add_argument('--tmp-root',required=True)
    args,remaining=p.parse_known_args()
    TMP_ROOT=Path(args.tmp_root).expanduser().resolve();TMP_ROOT.mkdir(parents=True,exist_ok=True)
    program=unittest.main(argv=[sys.argv[0]]+remaining,exit=False,verbosity=2)
    return 0 if program.result.wasSuccessful() else 1


if __name__=='__main__':raise SystemExit(main())
