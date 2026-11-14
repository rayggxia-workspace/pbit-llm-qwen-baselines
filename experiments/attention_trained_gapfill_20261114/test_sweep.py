import unittest
import torch
from .methods import CASES, configuration, Patch
from experiments.sparq_ising_20261028.vendor.plans import full_window_plan, plan_batches


class SweepTests(unittest.TestCase):
    def test_matrix_and_complete_targets(self):
        self.assertEqual(len(CASES), 6)
        self.assertEqual(len({(c['name'], c['seed']) for c in CASES}), 6)
        self.assertEqual({(c["k"], c["samples"]) for c in CASES[1:]},
                         {(64,64),(64,128),(128,16),(256,16),(256,128)})
        self.assertEqual({c["seed"] for c in CASES}, {0})
        self.assertEqual({c["overlay"] for c in CASES[1:]}, {"k_wh128"})
        for c in CASES[1:]:
            cfg = configuration(c)
            self.assertEqual((cfg.burn, cfg.local, cfg.r), (0, 32, 32))
            self.assertEqual(cfg.samples, c['samples'] or 64)
        plan = full_window_plan(299078)
        self.assertEqual(len(plan), 292)
        self.assertEqual(sum(x['scored_tokens'] for x in plan), 299077)
        self.assertEqual(plan[0]['prefill_tokens'], 0)
        batches = [b for start in range(0, len(plan), 32)
                   for b in plan_batches(plan[start:start+32], 32)]
        self.assertEqual(sum(len(b) for b in batches), 292)

    def test_numeric_contract_independent_of_budget(self):
        z = torch.tensor([[12., 10., 6., -100.]])
        for c in [c for c in CASES if c['samples']]:
            from experiments.attention_gap_accuracy_20261102.methods import load_table
            patch = Patch(c)
            patch.table = load_table()
            got = patch.probabilities(z, 'winner')
            self.assertEqual(got[0, 0].tolist(), [0.5, 30/256, 0., 0.])
            self.assertEqual(got[0, 25].tolist(), [1., 0., 0., 0.])
            self.assertEqual(patch.report()['samples'], c['samples'])


if __name__ == '__main__':
    unittest.main()
