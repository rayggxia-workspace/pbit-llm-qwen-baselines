import ast
import csv
import gzip
import hashlib
import json
import os
import tarfile
from pathlib import Path
import sys
import tempfile
import tkinter
import unittest
from unittest.mock import patch

from xz_audit import audit, decisions, prepare_activity, save
from scalar_vcd import scalarize
from resume_power import checked_inputs, FROZEN, ROOT
import resume_power
from wave import clip

HEADER = '''$timescale 1ns $end
$scope module tb_counter $end
$scope module dut $end
$var wire 1 ! clk $end
$var wire 1 " out_valid $end
$var wire 2 # result [1:0] $end
$scope module add $end
$var wire 2 % B [1:0] $end
$upscope $end
$scope module U0 $end
$var reg 1 & notifier $end
$upscope $end
$upscope $end
$upscope $end
$enddefinitions $end
'''
EVENTS = '#0\n0!\n0"\nb00 #\nbz1 %\nx&\n#5\n1!\n#10\n0!\n1"\nb11 #\nbz0 %\n#15\n1!\n#20\n0!\n#25\n1!\n'


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=str(ROOT.parent))
        self.addCleanup(self.temp.cleanup)
        self.p = Path(self.temp.name)
        self.raw = self.p/'raw.vcd'; self.raw.write_text(HEADER+EVENTS)

    def classify(self, audit_data, change=None):
        names = sorted({a['name'][len('tb_counter/dut/'):] for r in audit_data['unknown_bits'] for a in r['aliases']})
        path = self.p/'proof.tsv'
        rows = ['name\tclassification\treason\tevidence']
        for n in names:
            state = 'MODEL_INTERNAL' if 'notifier' in n else 'DISCONNECTED'
            if change and n in change:
                state = change[n]
            rows.append(n+'\t'+state+'\tunit_test_only\tmock')
        path.write_text('\n'.join(rows)+'\n')
        return path

    def test_raw_unknown_bits_preserved_in_audit(self):
        meta = audit(self.raw)
        self.assertEqual(meta['unknown_bit_count'], 2)
        byname = {r['aliases'][0]['name']:r for r in meta['unknown_bits']}
        self.assertEqual(byname['tb_counter/dut/add/B[1]']['kinds'], ['z'])
        self.assertEqual(byname['tb_counter/dut/U0/notifier']['kinds'], ['x'])
        self.assertEqual(byname['tb_counter/dut/add/B[1]']['last_tick'], 10)

    def test_only_proven_bits_removed_not_replaced(self):
        meta = audit(self.raw)
        excluded, blocked = decisions(meta, self.classify(meta))
        self.assertFalse(blocked)
        result = scalarize(self.raw, self.p/'scalar.vcd', 2, excluded)
        text = (self.p/'scalar.vcd').read_text()
        self.assertNotIn('notifier', text)
        self.assertNotIn('B [1]', text)
        self.assertIn('B [0]', text)
        self.assertEqual(result['excluded_nonfunctional_bits'], 2)
        self.assertFalse(result['all_bits_preserved'])
        self.assertEqual(result['expected_activity']['result[1]']['toggle_count'], 1)

    def test_unknown_without_proof_still_fails(self):
        with self.assertRaises(ValueError):
            scalarize(self.raw, self.p/'scalar.vcd', 2)

    def test_required_or_unresolved_unknown_blocks(self):
        meta = audit(self.raw)
        for status in ['REQUIRED', 'UNRESOLVED']:
            excluded, blocked = decisions(meta, self.classify(meta, {'add/B[1]':status}))
            self.assertEqual(len(blocked), 1)
            self.assertEqual(len(excluded), 1)

    def test_alias_cannot_hide_connected_pin(self):
        text = HEADER.replace('$scope module U0 $end', '$var wire 2 % input_alias [1:0] $end\n$scope module U0 $end')
        self.raw.write_text(text+EVENTS)
        meta = audit(self.raw)
        excluded, blocked = decisions(meta, self.classify(meta, {'input_alias[1]':'REQUIRED'}))
        self.assertEqual(len(blocked), 1)
        self.assertNotIn(('%', 0), excluded)

    def test_missing_or_duplicate_proof_rejected(self):
        meta = audit(self.raw); proof = self.classify(meta)
        lines = proof.read_text().splitlines()
        proof.write_text('\n'.join(lines[:-1])+'\n')
        with self.assertRaises(ValueError):
            decisions(meta, proof)
        proof.write_text('\n'.join(lines+[lines[-1]])+'\n')
        with self.assertRaises(ValueError):
            decisions(meta, proof)

    def test_fatal_probe_keeps_raw_diagnostics(self):
        def fail(*args):
            raise RuntimeError('simulated PT failure')
        with self.assertRaises(RuntimeError):
            prepare_activity(self.raw, self.p, 5, 20, 2, self.p/'dc', fail)
        self.assertTrue((self.p/'XZ_AUDIT.json').is_file())
        self.assertIn('add/B[1]', (self.p/'xz_requests.txt').read_text())

    def test_clean_does_not_need_probe(self):
        self.raw.write_text((HEADER+EVENTS).replace('bz1 %','b01 %').replace('bz0 %','b00 %').replace('x&','0&'))
        def fail(*args):
            self.fail('No connectivity probe needed')
        stats = prepare_activity(self.raw, self.p, 5, 20, 2, self.p/'dc', fail)
        self.assertEqual(stats['excluded_nonfunctional_bits'], 0)

    def test_gzip_clip_and_boundary(self):
        with gzip.open(str(self.p/'raw.vcd.gz'), 'wt') as f:
            f.write(HEADER+EVENTS)
        meta = clip(self.p/'raw.vcd.gz', self.p/'window.vcd', 5, 20)
        self.assertEqual(meta['duration_ns'], 15)
        self.assertEqual(meta['xz_signals'], 2)
        result = audit(self.p/'window.vcd')
        self.assertEqual(result['duration_ticks'], 15)

    def test_no_dut_alias_escaping(self):
        self.raw.write_text((HEADER+EVENTS).replace('module dut','module unexpected'))
        with self.assertRaises(ValueError):
            audit(self.raw)

    def test_zero_duration_x_is_not_waived(self):
        self.raw.write_text((HEADER+EVENTS).replace('b11 #', 'bxx #\nb11 #'))
        meta = audit(self.raw)
        self.assertEqual(meta['unknown_bit_count'], 4)
        excluded, blocked = decisions(meta, self.classify(meta, {'result[1]':'REQUIRED', 'result[0]':'REQUIRED'}))
        self.assertEqual(len(blocked), 2)

    def test_reuse_source_mismatch(self):
        manifest = dict(release='counter_ppa_v2',
            package_manifest_sha256='0debbfacb696238041830ebfe80aa0838db932e02558dcff641195f323818958',
            sources={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in FROZEN})
        manifest['sources']['sim/tb.sv'] = '0'*64
        save(self.p/'EXECUTION.json', manifest)
        with self.assertRaisesRegex(ValueError, 'Frozen RTL/TB'):
            checked_inputs(self.p)

    def make_old(self):
        old = self.p/'old'; (old/'dc').mkdir(parents=True)
        (old/'gate/functional').mkdir(parents=True)
        case = old/'gate/mixed_s17'; case.mkdir()
        lib = self.p/'library.db'; lib.write_bytes(b'mock library - not real EDA')
        manifest = dict(release='counter_ppa_v2',
            package_manifest_sha256='0debbfacb696238041830ebfe80aa0838db932e02558dcff641195f323818958',
            sources={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in FROZEN},
            library=dict(path=str(lib),sha256=hashlib.sha256(lib.read_bytes()).hexdigest()),
            arch=0, m=1, t=32, pipe=1, period_ns=10, power_frames=4, corner='ss', profiles=['mixed'], seeds=[17])
        save(old/'EXECUTION.json', manifest)
        save(old/'COMMANDS.json', [dict(command=['dc_shell'],rc=0),dict(command=['vcs'],rc=0)])
        for name in ['mapped.v','mapped.sdc','SYNTH_COMPLETE']:
            (old/'dc'/name).write_text('mock\n')
        (old/'gate/functional/FUNCTION_PASS').write_text('pass')
        (old/'gate/functional/command2.log').write_text('COUNTER_PASS frames=23\n')
        (case/'FUNCTION_PASS').write_text('pass')
        (case/'command3.log').write_text('WINDOW_BEGIN time_ns=40.000\n'
            'WINDOW_END time_ns=1480.000 frames=4 active_cycles=144\nIDLE_END time_ns=2120.000\nCOUNTER_PASS\n')
        header = HEADER.replace('$var wire 2 # result [1:0]', '$var wire 80 # result [79:0]')
        (case/'raw.vcd').write_text(header+'#0\n0!\n0"\nb0 #\nbz1 %\nx&\n#40\n1!\n'
            '#1480\n0!\n#2120\n1!\n')
        return old, lib

    def test_resume_blocked_archive_and_old_immutable(self):
        old, lib = self.make_old(); dest = self.p/'new'
        before = {str(p):p.read_bytes() for p in old.rglob('*') if p.is_file()}
        def tool(cmd, cwd, **kwargs):
            self.assertEqual(cmd[0], 'pt_shell')
            work = Path(cwd)
            names = (work/'xz_requests.txt').read_text().splitlines()
            (work/'xz_classification.tsv').write_text('name\tclassification\treason\tevidence\n'+
                ''.join(n+'\tREQUIRED\tconnected\tU/D\n' for n in names))
            (work/'XZ_PROBE_COMPLETE').write_text('mock')
            return type('Result', (), dict(returncode=0))()
        with patch.object(sys, 'argv', ['resume_power.py','--old',str(old),'--out',str(dest)]), \
             patch.dict(os.environ, {'STD_DB':str(lib)}), patch.object(resume_power.subprocess, 'run', tool):
            with self.assertRaisesRegex(RuntimeError, 'functional or unresolved'):
                resume_power.main()
        self.assertFalse((dest/'FLOW_COMPLETE').exists())
        with tarfile.open(str(dest)+'_reports.tar.gz') as tar:
            self.assertTrue(any(n.endswith('/XZ_POLICY.json') for n in tar.getnames()))
            self.assertTrue(any(n.endswith('/failure.txt') for n in tar.getnames()))
        self.assertEqual(before, {str(p):p.read_bytes() for p in old.rglob('*') if p.is_file()})

    def test_resume_success_without_dc_vcs(self):
        old, lib = self.make_old(); dest = self.p/'new'
        calls = []
        def tool(cmd, cwd, **kwargs):
            self.assertEqual(cmd[0], 'pt_shell'); calls.append(cmd[-1]); work=Path(cwd)
            if cmd[-1].endswith('xz_probe.tcl'):
                records = json.loads((work/'XZ_AUDIT.json').read_text())
                proof = self.classify(records)
                (work/'xz_classification.tsv').write_bytes(proof.read_bytes())
                (work/'XZ_PROBE_COMPLETE').write_text('mock')
            else:
                self.assertTrue(cmd[-1].endswith('pt.tcl'))
                reports={'units.rpt':'Time Unit : 1ns\n',
                    'power.rpt':'Dynamic Power Units = 1mW\nLeakage Power Units = 1nW\nCell Internal Power = 2\nNet Switching Power = 3\nCell Leakage Power = 1000\nTotal Power = 5.001\n',
                    'inventory.tsv':'name\tref\tarea\tcategory\nu0\tDFF\t10\tstate\n',
                    'cells.rpt':'Cell Power Power Power Power\n------\nu0 2 3 1000 5.001 (100.0%)\nTotals (1 cells) 2 3 1000 5.001\n',
                    'activity.rpt':'Total number of nets = 10\nNumber of annotated nets = 10\n',
                    'setup_slack_ns.txt':'1','hold_slack_ns.txt':'.1','POWER_CALCULATED':'mock'}
                for name in ('checks.rpt','ranges.rpt','model_checks.rpt','update.rpt','check_timing.rpt'):
                    reports[name]=''
                stats=json.loads((work/'ACTIVITY_EXPECTED.json').read_text())
                reports['output_activity.tsv']='name\ttoggle_rate\tstatic_probability\n'+''.join(
                    '{}\t{:.15f}\t{:.15f}\n'.format(n,v['toggle_rate_per_ns'],v['static_probability'])
                    for n,v in stats['expected_activity'].items())
                for name,text in reports.items():
                    (work/name).write_text(text)
            return type('Result', (), dict(returncode=0))()
        with patch.object(sys, 'argv', ['resume_power.py','--old',str(old),'--out',str(dest)]), \
             patch.dict(os.environ, {'STD_DB':str(lib)}), patch.object(resume_power.subprocess, 'run', tool):
            resume_power.main()
        summary=json.loads((dest/'SUMMARY.json').read_text())
        self.assertEqual(len(summary['windows']),2)
        self.assertAlmostEqual(summary['windows'][0]['pJ_per_frame'],1800.36)
        self.assertIsNone(summary['windows'][1]['pJ_per_frame'])
        self.assertEqual(len(calls),4)
        self.assertTrue((dest/'FLOW_COMPLETE').is_file())

    def test_syntax_python36_and_tcl(self):
        tcl = tkinter.Tcl()
        for p in (ROOT/'flow').glob('*.py'):
            ast.parse(p.read_text(encoding='utf-8-sig'), feature_version=(3,6))
        for p in (ROOT/'flow').glob('*.tcl'):
            self.assertEqual(int(tcl.call('info', 'complete', p.read_text())), 1, str(p))

    def test_tcl_literal_patterns_and_classifier(self):
        tcl = tkinter.Tcl()
        text = (ROOT/'flow/xz_probe.tcl').read_text()
        procs = text[text.index('proc literal_pattern'):text.index('proc main')]
        tcl.eval(procs)
        for name in ['add/B[1]', 'a?b*', 'a\\b', 'GEN[3]/sum']:
            pattern = tcl.call('literal_pattern', name)
            self.assertEqual(int(tcl.call('string', 'match', pattern, name)), 1)
        tcl.eval('''
        array set leaf_ref {U0 DFFX1_9TSVT}
        proc get_ports {args} {if {[lindex $args end] eq "result"} {return result}; return {}}
        proc get_pins {args} {if {[lindex $args end] eq "U0/D"} {return U0/D}; return {}}
        proc sizeof_collection {x} {llength $x}
        proc get_cells {args} {return U0}
        proc get_object_name {x} {return $x}
        proc get_nets {args} {
          set p [lindex $args end]
          if {$p eq "dangling" || $p eq "connected"} {return $p}; return {}
        }
        proc foreach_in_collection {v col body} {upvar 1 $v x; foreach x $col {uplevel 1 $body}}
        proc all_connected {args} {if {[lindex $args end] eq "connected"} {return U0/D}; return {}}
        ''')
        for name, expected in [('U0/notifier','MODEL_INTERNAL'),('dangling','DISCONNECTED'),
                               ('connected','REQUIRED'),('U0/D','REQUIRED'),
                               ('result','REQUIRED'),('absent','UNRESOLVED')]:
            answer = tcl.call('classify_xz', name)
            self.assertEqual(answer[0], expected, (name, answer))


if __name__ == '__main__':
    unittest.main()
