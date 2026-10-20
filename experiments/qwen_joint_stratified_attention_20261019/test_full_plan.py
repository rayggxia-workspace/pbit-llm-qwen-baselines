"""Pure protocol admission/coverage checks; no model or Torch dependency."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from experiments.qwen_joint_stratified_attention_20261019.run_full import cases, validate_case
from experiments.qwen_joint_stratified_attention_20261019.upstream_attention.scoring import (
    full_window_plan, plan_metadata)


class FullPlanTest(unittest.TestCase):
    def test_matched_grid_and_every_target_coverage(self):
        grid = cases('full')
        self.assertEqual(len(grid), 22)
        self.assertEqual(sum(row['ffn'] == 'none' and row['mode'] == 'sdpa' for row in grid), 1)
        self.assertEqual(sum(row['mode'] == 'screen_ising' for row in grid), 12)
        self.assertTrue(all(row['protocol'] == 'full' and row['batch'] == 32 for row in grid))
        metadata = plan_metadata(full_window_plan(299078, 2048, 1024), 299078, 'full')
        self.assertEqual(metadata['scored_tokens'], 299077)
        self.assertTrue(metadata['every_full_corpus_target_once'])

    def test_protocol_and_phase_rejected(self):
        with self.assertRaises(ValueError):
            cases('suffix')
        cfg = dict(cases('full')[0], protocol='suffix')
        with self.assertRaises(ValueError):
            validate_case(cfg, 'full')
        with self.assertRaises(ValueError):
            validate_case(cases('full')[0], 'unknown')
        self.assertEqual([row['batch'] for row in cases('memory')], [16, 32])
        self.assertEqual([row['context'] for row in cases('memory')], [2048, 1024])
        self.assertNotIn('torch', sys.modules)


if __name__ == '__main__':
    unittest.main()
