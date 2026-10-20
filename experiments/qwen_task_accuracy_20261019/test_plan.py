"""Cheap experiment-plan invariants; model-path tests live in test_cached_score."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from experiments.qwen_task_accuracy_20261019.run_tasks import configurations
from experiments.qwen_task_accuracy_20261019.task_data import TASKS


class PlanTests(unittest.TestCase):
    def test_samples_seeds_controls(self):
        rows=configurations()
        self.assertEqual(len(rows),13)
        self.assertEqual(len({r['name'] for r in rows}),13)
        self.assertEqual([(r['ffn'],r['mode']) for r in rows[:1]],[('none','sdpa')])
        for n in (64,128,512):
            self.assertEqual({r['seed'] for r in rows if r['mode']=='screen_ising' and r['samples']==n},{0,1,2})
        self.assertTrue(all(r['ffn']=='b4_t32' for r in rows[1:]))
        self.assertTrue(all(r['batch']==16 and r['burn']==16. and r['spacing']==4. for r in rows))
    def test_dataset_protocol(self):
        self.assertEqual({k:v[:2] for k,v in TASKS.items()},
                         {'piqa':('validation',1838),'arc_easy':('test',2376),'hellaswag':('validation',10042)})


if __name__=='__main__':
    unittest.main()
