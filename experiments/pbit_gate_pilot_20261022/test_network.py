"""Small CPU correctness checks; synthetic fixtures are not model-quality results."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

import numpy as np
import torch

try:
    from .network import PBitNetwork, budget_penalty, effective_probability, export_model, import_model
    from .train import calibrate_model, calibrate_scalar, fit_normalization, probability_from_scores, validate_dataset
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from network import PBitNetwork, budget_penalty, effective_probability, export_model, import_model
    from train import calibrate_model, calibrate_scalar, fit_normalization, probability_from_scores, validate_dataset


class TestPBitNetwork(unittest.TestCase):
    def setUp(self):
        torch.manual_seed(21)
        torch.set_num_threads(1)

    def test_parameter_count_and_state_probabilities(self):
        model = PBitNetwork()
        self.assertEqual(sum(p.numel() for p in model.parameters()), 49)
        self.assertEqual(tuple(model.states.shape), (256, 8))
        self.assertEqual(torch.unique(model.states, dim=0).shape[0], 256)
        distribution = model.hidden_distribution(torch.randn(7, 4))
        torch.testing.assert_close(distribution.sum(-1), torch.ones(7))
        self.assertTrue(torch.all(distribution >= 0))

    def test_real_two_stage_samples_match_exact_marginal(self):
        model = PBitNetwork()
        x = torch.randn(5, 4)
        generator = torch.Generator().manual_seed(100)
        with torch.no_grad():
            expected = model(x)
            observed = model.sample(x, draws=60000, generator=generator).mean(0)
        torch.testing.assert_close(observed, expected, atol=0.01, rtol=0)

    def test_gradients_are_finite_and_nonzero(self):
        model = PBitNetwork()
        x = torch.randn(9, 4)
        loss = torch.nn.functional.binary_cross_entropy(model(x), torch.linspace(0.1, 0.9, 9))
        loss.backward()
        for parameter in model.parameters():
            self.assertTrue(torch.isfinite(parameter.grad).all())
            self.assertGreater(float(parameter.grad.abs().sum()), 0)

    def test_export_roundtrip(self):
        model = PBitNetwork()
        artifact = export_model(model, [0] * 4, [1] * 4)
        restored = import_model(json.loads(json.dumps(artifact)))
        x = torch.randn(3, 32, 4)
        self.assertTrue(torch.equal(model(x), restored(x)))

    def test_group_budget_and_forced_mask(self):
        q = torch.tensor([[0.1, 0.2, 0.4], [0.1, 0.8, 0.6]])
        valid = torch.tensor([[True, True, False], [True, True, True]])
        forced = torch.tensor([[True, False, False], [True, False, False]])
        effective = effective_probability(q, valid, forced)
        torch.testing.assert_close(effective, torch.tensor([[1.0, 0.2, 0.0], [1.0, 0.8, 0.6]]))
        torch.testing.assert_close(budget_penalty(effective, 1.8), torch.tensor(0.0), atol=1e-12, rtol=0)
        self.assertGreater(float(((effective.sum(1) - 1.8) ** 2).mean()), 0)
        with self.assertRaises(ValueError):
            budget_penalty(q.flatten(), 1.8)

    def test_calibration_changes_actual_output_bias(self):
        model = PBitNetwork()
        x = torch.randn(6, 32, 4)
        valid = torch.ones(6, 32, dtype=torch.bool)
        forced = torch.zeros_like(valid)
        forced[:, [0, 30, 31]] = True
        result = calibrate_model(model, x, valid, forced, 8)
        self.assertAlmostEqual(result["train_mean_blocks"], 8, places=5)
        self.assertAlmostEqual(float(model.bias.detach()), result["after"], places=7)

    def test_teacher_mass_is_not_the_selection_probability(self):
        mass = np.full((5, 32), 1 / 32)
        valid = np.ones_like(mass, dtype=bool)
        forced = np.zeros_like(valid)
        forced[:, [0, 30, 31]] = True
        bias = calibrate_scalar(np.log(mass + 1e-12), valid, forced, 8)
        labels = probability_from_scores(np.log(mass + 1e-12), valid, forced, bias)
        self.assertAlmostEqual(labels.sum(1).mean(), 8, places=10)
        self.assertFalse(np.allclose(labels[~forced], mass[~forced]))

    def fixture(self):
        rng = np.random.default_rng(42)
        mass = np.full((6, 32), 1 / 32, dtype=np.float32)
        block_v = rng.normal(size=(6, 32, 64)).astype(np.float32) / 32
        forced = np.zeros((6, 32), dtype=bool)
        forced[:, [0, 30, 31]] = True
        return {"x": rng.normal(size=(6, 32, 4)).astype(np.float32), "mass": mass,
                "block_v": block_v, "teacher_output": block_v.sum(1),
                "valid": np.ones((6, 32), dtype=bool), "forced": forced,
                "counts": np.full((6, 32), 64, dtype=np.int16), "layer": np.zeros(6, dtype=np.int16),
                "head": np.zeros(6, dtype=np.int16), "document": np.arange(6),
                "split": np.array([0, 0, 1, 1, 2, 2]), "position": np.full(6, 2047)}

    def test_document_isolation_and_train_only_normalization(self):
        data = self.fixture()
        self.assertEqual(validate_dataset(data)["train"]["groups"], 2)
        mean, std = fit_normalization(data["x"], data["valid"], data["forced"], data["split"] == 0)
        altered = data["x"].copy()
        altered[data["split"] != 0] += 10000
        mean2, std2 = fit_normalization(altered, data["valid"], data["forced"], data["split"] == 0)
        np.testing.assert_array_equal(mean, mean2)
        np.testing.assert_array_equal(std, std2)
        data["document"][2] = data["document"][0]
        with self.assertRaisesRegex(ValueError, "document"):
            validate_dataset(data)


if __name__ == "__main__":
    unittest.main()
