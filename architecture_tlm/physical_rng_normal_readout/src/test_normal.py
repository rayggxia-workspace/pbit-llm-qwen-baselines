import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import normal_circuits as nc
import normal_metrics as nm
import execution,engine,run_normal

ROOT=Path(__file__).resolve().parent
def config():return json.loads((ROOT/'config.json').read_text())
def base():return json.loads((ROOT/'base_config.json').read_text())

class NormalTests(unittest.TestCase):
    def test_12MOS_unstarved_and_original_zero_cap_core(self):
        c=config();nc.validate(c)
        for v in c['candidates']:
            s=nc.deck(Path('/read_only/model.lib'),base(),c,v,'noise',.6,parameters=nc.q(c,64007,long=True))
            self.assertEqual(sum(line.startswith('X') for line in s.splitlines()),12)
            self.assertNotIn('Ccore ',s);self.assertNotIn('noiseoff',s)
            self.assertIn('XB1N (inv sense 0 0)',s);self.assertIn('XB1P (inv sense vdc vdc)',s)
            self.assertIn('noisescale=1',s);self.assertIn('noisefmax=100000000',s)
            self.assertIn('w=1u l=1u',s)
    def test_bias_gate_rejects_weak_or_unsaturated_input(self):
        points={n:dict(vgs=.55,vth=.35,vds=.3,vdsat=.1,gmoverid=15.) for n in ['XIP','XIN','XTAIL','XLP','XLM']}
        self.assertTrue(nm.bias_checks(points,config())['passed'])
        points['XIP']['vgs']=.36
        self.assertFalse(nm.bias_checks(points,config())['passed'])
        points['XIP']['vgs']=.55;points['XIN']['gmoverid']=28.
        self.assertFalse(nm.bias_checks(points,config())['passed'])
        points['XIN']['gmoverid']=15.;points['XTAIL']['vds']=.05
        self.assertFalse(nm.bias_checks(points,config())['passed'])
    def test_validation_count_and_seed_separation(self):
        c=config();q=nc.q(c,c['validation_seeds'][0],long=True)
        self.assertEqual(round((q['stop_s']-q['discard_s'])/c['sample_interval_s']),20000)
        self.assertFalse(set(c['validation_seeds'])&set(c['calibration_seeds']))
        self.assertFalse(set(c['numeric_seeds'])&set(c['calibration_seeds']))
        c['noisefmin_Hz']=10
        with self.assertRaises(ValueError):nc.q(c,1)
    def test_numeric_screen_uses_rail_scaled_distributions(self):
        c=config();rows=[]
        for tag in ['base','fine','wide']:
            for seed in c['numeric_seeds']:
                m=dict(p1=.5,midrail_fraction=0.,core_distribution=dict(cdf=[.1,.8,1.],std_V=.01),
                    comparator_distribution=dict(cdf=[.5,.5,1.],std_V=.6),dense_acf={'1':dict(correlation=.005)})
                rows.append(dict(setting=dict(tag=tag,q=dict(seed=seed)),metrics=m))
        self.assertEqual(nm.numerical_screen(rows,c)['status'],'SHORT_SCREEN_PASS')
        for r in rows:
            if r['setting']['tag']=='wide':r['metrics']['p1']=.7
        self.assertEqual(nm.numerical_screen(rows,c)['status'],'SHORT_SCREEN_REVIEW_REQUIRED')
    def test_resource_bounds(self):
        execution.check_resources(8,preview=True,threads=1,cpus=8)
        with self.assertRaises(ValueError):execution.check_resources(9,preview=True,threads=1,cpus=8)
        with self.assertRaises(ValueError):execution.check_resources(8,threads=1,cpus=8,environ={})
    def test_source_snapshot_uses_exact_readonly_bytes_and_no_overwrite(self):
        with tempfile.TemporaryDirectory(dir=str(ROOT)) as t:
            out=Path(t)/'source'
            run_normal.snapshot(out)
            self.assertEqual((out/'config.json').read_bytes(),(ROOT/'config.json').read_bytes())
            with self.assertRaises(FileExistsError):run_normal.snapshot(out)
    def test_step_target_is_not_a_claim_of_independent_rate(self):
        c=config();v=c['candidates'][0]
        s=nc.deck(Path('/pdk/model.lib'),base(),c,v,'step',.6,overdrive=.001,loaded=True)
        self.assertIn('val0=0.599',s);self.assertIn('strobeperiod=5e-10',s)
        self.assertIn('XN (out gn 0 0)',s)
    def test_midrail_is_not_silently_deleted(self):
        import long_metrics as m
        self.assertEqual(m.logic_level(.6,1.2,config()),'MID')
        self.assertEqual(m.logic_level(0,1.2,config()),'LOW')
        self.assertEqual(m.logic_level(1.2,1.2,config()),'HIGH')

if __name__=='__main__':unittest.main()
