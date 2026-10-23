import ast,json,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'flow'))
from scalar_vcd import scalarize,verify_pt
from vectors import make,advance

class FlowTests(unittest.TestCase):
    def test_python36(self):
        for p in ROOT.rglob('*.py'):
            if sys.version_info>=(3,8):ast.parse(p.read_text(encoding='utf-8'),feature_version=(3,6))
            else:ast.parse(p.read_text(encoding='utf-8'))
    def test_generator_endpoint_and_count(self):
        with tempfile.TemporaryDirectory(dir=str(ROOT/'sim')) as d:
            x=make(d,n=4,m=2,t=32,k=32,seed=17)
            self.assertEqual([w['accepted_samples'] for w in x['windows'] if w['mode']=='active'],[32]*6)
            self.assertEqual(x['accepted'],192)
    def test_full_range_map(self):
        for seed in [1,17,74565]:
            s=seed
            for _ in range(100):
                a=s
                for _ in range(16):a=(a>>1)^((0x80200003) if a&1 else 0)
                self.assertEqual(advance(s),a);s=a
    def test_scalar_vectors_and_alias(self):
        with tempfile.TemporaryDirectory(dir=str(ROOT/'sim')) as d:
            d=Path(d);src=d/'a.vcd';src.write_text('''$timescale 1ns $end
$scope module tb $end
$scope module full $end
$scope module dut $end
$var wire 2 ! products [1:0] $end
$var wire 2 ! alias [1:0] $end
$var wire 1 " clk $end
$upscope $end
$upscope $end
$upscope $end
$enddefinitions $end
#0
b00 !
0"
#5
b10 !
1"
#10
''')
            r=scalarize(src,d/'b.vcd',prefix='tb/full/dut',wanted=['clk','products[0]','products[1]'])
            self.assertEqual(r['scalar_ids'],3);self.assertEqual(r['expected_activity']['products[1]']['static_probability'],.5)
            f=d/'pt.tsv';f.write_text('name\ttoggle_rate\tstatic_probability\nclk\t0.1\t0.5\nproducts[0]\t0\t0\nproducts[1]\t0.1\t0.5\n')
            self.assertEqual(verify_pt(r,f)['checked_bits'],3)
            f.write_text('name\ttoggle_rate\tstatic_probability\n')
            with self.assertRaises(ValueError):verify_pt(r,f)
    def test_explicit_buffer_and_boundary(self):
        self.assertIn('set_dont_touch $buffers true',(ROOT/'flow/dc.tcl').read_text())
        self.assertIn('PWR-981',(ROOT/'flow/pt.tcl').read_text())
        s=(ROOT/'rtl/cim_sng.sv').read_text()
        self.assertNotIn('reg [N*8',s)

if __name__=='__main__':unittest.main(verbosity=2)
