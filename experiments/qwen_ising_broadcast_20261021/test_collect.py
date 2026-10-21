import json,tempfile,unittest
from pathlib import Path
from collect import collect,digest


class CollectorContracts(unittest.TestCase):
    def setup_files(self,r):
        # Explicit personal checkout dir; no shared-host default temp directory.
        (r/'ppl').mkdir()
        ref=dict(perplexity=10.,nll_sum=1.,scored_tokens=128,token_ids_sha256_le_int64='same')
        (r/'bf16_reference.json').write_text(json.dumps(ref))
        cfg=dict(name='a_s0',backend='a',seed=0)
        (r/'suite.json').write_text(json.dumps(dict(cases=[cfg],args=dict(commit='a'*40))))
        return ref,cfg

    def test_pending_is_not_a_score(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as d:
            r=Path(d);self.setup_files(r);s=collect(r)
            self.assertEqual(s['pending'],1);self.assertFalse(s['groups'])

    def test_failure_is_not_an_average(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as d:
            r=Path(d);ref,c=self.setup_files(r)
            (r/'ppl/a_s0.json').write_text(json.dumps(dict(configuration=c,status='sampler_cap_failed',perplexity=None)))
            s=collect(r);self.assertIsNone(s['groups'][0]['ppl_mean']);self.assertEqual(s['groups'][0]['failed_seeds'],1)

    def test_mixed_targets_are_rejected(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as d:
            r=Path(d);ref,c=self.setup_files(r)
            (r/'ppl/a_s0.json').write_text(json.dumps(dict(ref,configuration=c,status='completed',scored_tokens=127,
                bf16_reference_sha256=digest(r/'bf16_reference.json'))))
            with self.assertRaises(ValueError):collect(r)

if __name__=='__main__':unittest.main()
