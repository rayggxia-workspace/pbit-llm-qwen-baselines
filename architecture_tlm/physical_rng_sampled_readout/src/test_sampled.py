import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import execution,run_sampled,sampled_circuits as sc,sampled_metrics as sm
ROOT=Path(__file__).resolve().parent
def config():return json.loads((ROOT/'config.json').read_text(encoding='utf-8'))
def base():return json.loads((ROOT/'base_config.json').read_text(encoding='utf-8'))
def fake_rows(c,p,bad_read=False,bad_hold=False,transparent=False):
    rows=[]
    for j in range(round(p['stop_s']/p['strobe_s'])+1):
        t=j*p['strobe_s'];cycle=j//20;bit=cycle%2;q=1.2*bit;qb=1.2-q
        if bad_read and j==60:q=qb=.6
        if bad_hold and j==65:q,qb=qb,q
        rows.append(dict(time=t,out=.6,bit=.6 if j%20==19 else 1.2*bit,q=q,qb=qb,track=1.2 if transparent and j==60 else 0.))
    return rows
class SampledTests(unittest.TestCase):
    def test_transistor_channel_no_behavioral_latch_or_core_cap(self):
        c=config();sc.validate(c)
        text=sc.deck(Path('/readonly/model.lib'),base(),c,'noise',dict(q=sc.parameters(c,68003,True)))
        self.assertEqual(sum(line.startswith('X') for line in text.splitlines()),25)
        self.assertIn('XLFBN (x hold xi 0)',text);self.assertIn('XLFBP (x holdb xi vl)',text)
        self.assertIn('XLRST (x reset 0 0)',text)
        self.assertNotIn('Ccore ',text);self.assertNotIn('noiseoff',text);self.assertNotIn('bsource',text)
    def test_clock_geometry_nonoverlap_and_read_after_close(self):
        c=config();text=sc.clocks(c);rows=text.splitlines()
        def fields(line):return {k:float(v) for word in line.split() if '=' in word for k,v in [word.split('=')] if k not in ('type',)}
        a=fields(rows[0]);b=fields(rows[2])
        close=a['delay']+a['rise']+a['width']+a['fall']/2
        fb_on=b['delay']+b['rise']+b['width']+b['fall']/2
        self.assertAlmostEqual(close,c['period_s']-c['read_delay_s'],places=16)
        self.assertAlmostEqual(fb_on-close,c['dead_s'],places=16)
        self.assertGreater(c['read_delay_s'],c['dead_s']+c['clock_edge_s'])
    def test_parent_reference_and_disjoint_new_seeds(self):
        c=config();parent=json.loads((ROOT/'parent_reference.json').read_text())
        self.assertAlmostEqual(c['reference_V'],parent['reference_V'])
        self.assertFalse(set(c['validation_seeds'])&set(c['numeric_seeds']))
        self.assertFalse(set(c['validation_seeds'])&set(parent['validation_seeds']+parent['calibration_seeds']))
        q=sc.parameters(c,68003,True);self.assertEqual(q['samples'],20000)
        self.assertAlmostEqual(q['stop_s'],.0220001)
    def test_joint_Q_complement_validity(self):
        c=config();self.assertTrue(sm.valid(dict(q=0,qb=1.2),c))
        self.assertFalse(sm.valid(dict(q=1.2,qb=1.2),c));self.assertFalse(sm.valid(dict(q=.6,qb=.6),c))
    def sample(self,**kw):
        c=config();p=sc.parameters(c,1);p.update(start_s=2e-6,samples=4,stop_s=6.1e-6)
        with patch.object(sm.scan,'complete_psf'),patch.object(sm.parser,'checked_trace',return_value=iter(fake_rows(c,p,**kw))):
            return sm.trace(Path('fixture.tran'),c,p)
    def test_capture_mid_is_kept_when_real_Q_resolves(self):
        r=self.sample();self.assertEqual(r['actual_samples'],4);self.assertEqual(r['capture_MID'],4);self.assertEqual(r['invalid_Q'],0)
    def test_invalid_Q_is_counted_not_deleted(self):
        r=self.sample(bad_read=True);self.assertEqual(r['actual_samples'],4);self.assertEqual(r['invalid_Q'],1);self.assertEqual(r['Q_MID'],1)
    def test_hold_change_is_detected(self):self.assertGreater(self.sample(bad_hold=True)['hold_changed_saved_points'],0)
    def test_transparent_read_is_rejected(self):
        with self.assertRaises(ValueError):self.sample(transparent=True)
    def test_missing_timed_samples_is_rejected(self):
        c=config();p=sc.parameters(c,1);p.update(start_s=2e-6,samples=4,stop_s=6.1e-6)
        with patch.object(sm.scan,'complete_psf'),patch.object(sm.parser,'checked_trace',return_value=iter(fake_rows(c,p)[:100])):
            with self.assertRaises(ValueError):sm.trace(Path('fixture.tran'),c,p)
    def test_resource_budget_and_snapshot_no_overwrite(self):
        execution.check_resources(8,preview=True,threads=1,cpus=8)
        with self.assertRaises(ValueError):execution.check_resources(9,preview=True,threads=1,cpus=8)
        with tempfile.TemporaryDirectory(dir=str(ROOT)) as d:
            p=Path(d)/'source';run_sampled.snapshot(p)
            with self.assertRaises(FileExistsError):run_sampled.snapshot(p)
if __name__=='__main__':unittest.main()
