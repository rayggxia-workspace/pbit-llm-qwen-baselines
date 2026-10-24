import json
from pathlib import Path
import tempfile
import unittest
from report_helpers import library_units, totals
from run import stage
from wave import clip
from collect import collect
from analyze import summarize


class Tests(unittest.TestCase):
    def test_summary_and_bad_coverage(self):
        with tempfile.TemporaryDirectory(dir=str(Path.cwd())) as d:
            w = Path(d)
            (w/'configuration.json').write_text(json.dumps(dict(kind=0, corner='ss', voltage_V=1.08, temperature_C=125)))
            p, s = w/'power/test', w/'gate/test'
            p.mkdir(parents=True)
            s.mkdir(parents=True)
            (s/'workload.json').write_text(json.dumps(dict(mode='stream', seed=17, outputs=10, inputs=10)))
            (s/'wave_audit.json').write_text(json.dumps(dict(xz_signals=0, duration_ns=100)))
            files = {'POWER_CALCULATED':'yes', 'units.rpt':'Time_unit : 1e-09 Second\nCapacitive_load_unit : 1e-12 Farad\n',
                'inventory.tsv':'name\tref\tarea\tcategory\ncore/U1\tINVX1_9TSVT\t1.5\tcore_logic\n',
                'cells.rpt':'Cell Power Power Power Power\n-----\ncore/U1 1 2 1000 3.001 (100.0%)\nTotals (1 cells) 1 2 1000 3.001\n',
                'power.rpt':'Dynamic Power Units = 1mW\nLeakage Power Units = 1nW\nCell Internal Power = 1\nNet Switching Power = 2\nCell Leakage Power = 1000\nTotal Power = 3.001\n',
                'activity.rpt':'Total number of nets = 10\nNumber of annotated nets = 10\n',
                'setup_slack_ns.txt':'0.2', 'hold_slack_ns.txt':'-0.1'}
            for name in ('checks.rpt', 'model_checks.rpt', 'update.rpt', 'check_timing.rpt'):
                files[name] = ''
            for name, value in files.items():
                (p/name).write_text(value)
            r = summarize(w)[0]
            self.assertAlmostEqual(r['pJ_per_completed_output'], 30.01)
            self.assertEqual(r['status'], 'CALCULATED_PROVISIONAL')
            self.assertIn('TIMING_VIOLATION', r['review_flags'])
            (p/'activity.rpt').write_text('Total number of nets = 10\nNumber of annotated nets = 0\n')
            with self.assertRaises(ValueError):
                summarize(w)

    def test_units(self):
        u = library_units('Time_unit : 1e-09 Second\nCapacitive_load_unit : 1e-12 Farad\n')
        self.assertEqual(u['time_s'], 1e-9)
        with self.assertRaises(ValueError):
            library_units('Time_unit : 1ps\nCapacitive_load_unit : 1pf\n')

    def test_power_units(self):
        p, _ = totals('Dynamic Power Units = 1mW\nLeakage Power Units = 1nW\n'
                      'Cell Internal Power = 1\nNet Switching Power = 2\n'
                      'Cell Leakage Power = 1000\nTotal Power = 3.001\n')
        self.assertAlmostEqual(p[3], .003001)

    def test_checkpoint(self):
        with tempfile.TemporaryDirectory(dir=str(Path.cwd())) as d:
            p = Path(d)/'stage'
            stage(p, ['ok'], lambda: (p/'ok').write_text('ok'))
            stage(p, ['ok'], lambda: self.fail('Must reuse'))
            (p/'ok').write_text('changed')
            with self.assertRaises(ValueError):
                stage(p, ['ok'], lambda: None)

    def test_wave(self):
        with tempfile.TemporaryDirectory(dir=str(Path.cwd())) as d:
            p = Path(d)
            h = '$timescale 1ps $end\n$scope module tb_ppa $end\n$scope module dut $end\n$var wire 1 ! clk $end\n$upscope $end\n$upscope $end\n$enddefinitions $end\n'
            (p/'in.vcd').write_text(h+'#0\nx!\n#1000\n0!\n#5000\n1!\n#10000\n0!\n#15000\n1!\n')
            audit = clip(p/'in.vcd', p/'out.vcd', 2, 12)
            self.assertEqual(audit['xz_signals'], 0)
            self.assertEqual(audit['duration_ns'], 10)
            self.assertEqual(clip(p/'in.vcd', p/'bad.vcd', .5, 12)['xz_signals'], 1)
            with self.assertRaises(ValueError):
                clip(p/'in.vcd', p/'short.vcd', 2, 20)

    def test_collect_failure(self):
        with tempfile.TemporaryDirectory(dir=str(Path.cwd())) as d:
            p = Path(d)/'123_0'
            (p/'dc').mkdir(parents=True)
            (p/'dc/failure.txt').write_text('deliberate failure')
            collect(p)
            collect(p)
            index = json.loads((p/'RESULT_INDEX.json').read_text())
            self.assertFalse(index['stage_status']['flow_complete'])
            self.assertNotIn('RESULT_INDEX.json', index)
            self.assertTrue((p.parent/'123_0_reports.tar.gz').is_file())


if __name__ == '__main__':
    unittest.main()
