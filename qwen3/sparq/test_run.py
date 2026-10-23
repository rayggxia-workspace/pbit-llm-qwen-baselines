"""Runner gates exercise resumable completeness, including an uneven tail."""
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import torch
from . import run


class RunnerTests(unittest.TestCase):
    def test_final_partial_ppl_shard_and_resume(self):
        calls=[]
        ids=torch.arange(4098)
        plan=run.full_window_plan(len(ids))
        def fake(model,tokens,**kwargs):
            start,count=kwargs['segment_start'],kwargs['segment_count']
            self.assertLessEqual(start+count,len(plan))
            calls.append((kwargs['mode'],start,count))
            return dict(records=[dict(r,nll_sum=float(r['scored_tokens'])) for r in plan[start:start+count]],elapsed_seconds=1.)
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory, patch.dict('os.environ',SLURM_JOB_ID='test'), patch.object(run,'evaluate_ppl',fake):
            out=run.Artifacts(directory,{'test':True})
            result=run.paired_ppl(None,ids,run.SparQConfig(),out,8,2)
            self.assertEqual(calls[-2:],[('dense',2,2),('sparq',2,2)])
            self.assertTrue(result['dense']['complete'])
            self.assertEqual(result['dense']['scored_tokens'],len(ids)-1)
            run.paired_ppl(None,ids,run.SparQConfig(),out,8,2)
            self.assertEqual(len(calls),4)

    def test_uneven_count(self):
        calls=[]
        ids=torch.arange(4097)
        plan=run.full_window_plan(len(ids))
        self.assertEqual(len(plan),4)
        def fake(model,tokens,**kw):
            calls.append(kw['segment_count'])
            rows=plan[kw['segment_start']:kw['segment_start']+kw['segment_count']]
            return dict(records=[dict(r,nll_sum=float(r['scored_tokens'])) for r in rows],elapsed_seconds=1.)
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory, patch.dict('os.environ',SLURM_JOB_ID='test'), patch.object(run,'evaluate_ppl',fake):
            run.paired_ppl(None,ids,run.SparQConfig(),run.Artifacts(directory,{}),8,3)
        self.assertEqual(calls,[3,3,1,1])

    def test_artifact_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory, patch.dict('os.environ',SLURM_JOB_ID='test'):
            a=run.Artifacts(directory,{'seed':0})
            a.put('part',{'complete':False})
            with self.assertRaises(ValueError):run.Artifacts(directory,{'seed':1})
            Path(directory,'part.json').write_text('{}')
            with self.assertRaises(ValueError):a.existing('part')


if __name__=='__main__':unittest.main()
