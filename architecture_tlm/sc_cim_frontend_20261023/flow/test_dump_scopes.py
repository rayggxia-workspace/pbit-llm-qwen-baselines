import tempfile
import unittest
from pathlib import Path
from dump_scopes import generate,normalize_header
from scalar_vcd import scalarize,verify_pt


class DumpTests(unittest.TestCase):
    def test_constant_requires_literal_and_matching_wave(self):
        with tempfile.TemporaryDirectory(dir=str(Path(__file__).resolve().parents[2])) as d:
            p=Path(d)
            (p/'net').write_text("module cim_probe_mapped; assign ext_ready = 1'b0; endmodule")
            (p/'tsv').write_text('name\ttoggle_rate\tstatic_probability\n'+'ext_ready\tNA\tNA\n')
            expected=dict(duration_ns=10,expected_activity={'ext_ready':dict(toggle_count=0,static_probability=0,toggle_rate_per_ns=0)})
            self.assertEqual(verify_pt(expected,p/'tsv',p/'net')['status'],'PASS')
            expected['expected_activity']['ext_ready']['toggle_count']=1
            with self.assertRaisesRegex(ValueError,'unavailable'):verify_pt(expected,p/'tsv',p/'net')
            expected['expected_activity']['ext_ready']['toggle_count']=0
            (p/'net').write_text("module cim_probe_mapped; assign ext_ready = dynamic_signal; endmodule")
            with self.assertRaisesRegex(ValueError,'unavailable'):verify_pt(expected,p/'tsv',p/'net')

    def test_design_ancestors_only(self):
        with tempfile.TemporaryDirectory(dir=str(Path(__file__).resolve().parents[2])) as d:
            p=Path(d);(p/'i').write_text('name\tref\nsub/u0\tBUF_9TSVT\nsub/deeper/u1\tDFF_9TSVT\n')
            self.assertEqual(generate(p/'i',p/'o','full'),['','sub','sub/deeper'])
            self.assertNotIn('u0',(p/'o').read_text())
            self.assertIn('$dumpvars(1,tb.full.dut.sub.deeper);',(p/'o').read_text())

    def test_normalization_retains_x_gate(self):
        with tempfile.TemporaryDirectory(dir=str(Path(__file__).resolve().parents[2])) as d:
            p=Path(d)
            header='$timescale 1ns $end\n$scope module tb $end\n$scope module full.dut $end\n$var wire 1 ! clk $end\n$upscope $end\n$upscope $end\n$enddefinitions $end\n'
            for bit in ['0','x']:
                (p/'raw').write_text(header+'#0\n'+bit+'!\n#10\n1!\n')
                self.assertEqual(normalize_header(p/'raw',p/'norm','full'),1)
                if bit=='x':
                    with self.assertRaisesRegex(ValueError,'X/Z'):
                        scalarize(p/'norm',p/'scalar',prefix='tb/full/dut',wanted=['clk'])
                else:
                    result=scalarize(p/'norm',p/'scalar',prefix='tb/full/dut',wanted=['clk'])
                    self.assertEqual(result['expected_activity']['clk']['toggle_count'],1)
