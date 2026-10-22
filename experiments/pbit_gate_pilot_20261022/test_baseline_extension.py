"""TRAIN-fitted hard max4 cutoff checks; synthetic data only."""
from __future__ import annotations

import unittest

import numpy as np

try:
    from .baseline_extension import fit_threshold
    from .optimize import predict_payload, sample_payload
    from .train import max4_logits, probability_from_scores
    from . import test_network as old_tests
except ImportError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from baseline_extension import fit_threshold
    from optimize import predict_payload, sample_payload
    from train import max4_logits, probability_from_scores
    import test_network as old_tests


class TestHardMax4(unittest.TestCase):
    def fixture(self):
        return {key: value[:4].copy() for key, value in old_tests.TestPBitNetwork().fixture().items()}

    def test_exact_train_budget_and_variable_query_counts(self):
        data = self.fixture()
        payload = fit_threshold(data, 8)
        q = predict_payload(payload, data)
        self.assertAlmostEqual(float(q[data["split"] == 0].sum(1).mean()), 8, places=12)
        self.assertGreater(np.ptp(q[data["split"] == 0].sum(1)), 0)
        self.assertTrue(np.all(q[data["forced"]] == 1))

    def test_cutoff_ties_are_calibrated_probabilities(self):
        data = self.fixture()
        data["x"].fill(0)
        payload = fit_threshold(data, 8)
        self.assertEqual(payload["threshold"], 0)
        self.assertAlmostEqual(payload["tie_probability"], 5 / 29)
        q = predict_payload(payload, data)
        np.testing.assert_allclose(q.sum(1), 8, atol=1e-12, rtol=0)
        samples = sample_payload(payload, data, seed=42, draws=20000)
        self.assertAlmostEqual(float(samples.sum(-1).mean()), 8, delta=0.05)
        self.assertGreater(np.ptp(samples.sum(-1)), 0)

    def test_validation_changes_do_not_refit_cutoff(self):
        data = self.fixture()
        fitted = fit_threshold(data)
        data["x"][data["split"] == 1] = 0
        self.assertEqual(fitted, fit_threshold(data))
        q = predict_payload(fitted, data)
        self.assertNotAlmostEqual(float(q[data["split"] == 1].sum(1).mean()), 8)

    def test_legacy_sigmoid_prediction_is_unchanged(self):
        data = self.fixture()
        payload = {"kind": "max4_standardized_sigmoid", "temperature": 0.25, "bias": -1.5}
        expected = probability_from_scores(max4_logits(data["x"], data["valid"], data["forced"]) / 0.25,
                                           data["valid"], data["forced"], -1.5)
        np.testing.assert_array_equal(predict_payload(payload, data), expected)


if __name__ == "__main__":
    unittest.main()
