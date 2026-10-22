"""Phase-two budget/gradient/sampling/isolation checks, on synthetic inputs only."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import numpy as np
import torch

try:
    from .optimize import (DeterministicNetwork, apply_preprocess, constrained_objective,
        fit_preprocess, gate_basis, load_model, load_trainval_dataset, make_model,
        model_payload, predict_payload, sample_payload, solve_bias)
    from . import test_network as old_tests
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from optimize import (DeterministicNetwork, apply_preprocess, constrained_objective,
        fit_preprocess, gate_basis, load_model, load_trainval_dataset, make_model,
        model_payload, predict_payload, sample_payload, solve_bias)
    import test_network as old_tests


def temporary_root():
    root = Path(os.environ.get("GATE_OUTPUT", Path(__file__).resolve().parent / "_test_tmp"))
    root.mkdir(parents=True, exist_ok=True)
    return root


class TestConstrainedOptimization(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(1)
        torch.manual_seed(7)
        self.x = torch.randn(24, 4, dtype=torch.float64)
        self.mass = torch.rand(24, dtype=torch.float64) * 0.12
        self.groups = 3
        self.forced_mean = 1.0
        self.forced_mass_mean = 0.15
        self.target = 4.0

    def objective(self, model):
        basis = gate_basis(model, self.x, self.mass, self.groups)
        solve_bias(model, basis, self.forced_mean, self.target, steps=70)
        return constrained_objective(model, basis, self.forced_mean,
            self.forced_mass_mean, self.target)

    def test_implicit_gradient_matches_constrained_finite_difference(self):
        for kind in ("pbit_4_8_1", "linear_pbit", "deterministic_4_8_1"):
            model = make_model(kind, initialization="random").double()
            shadow, info = self.objective(model)
            self.assertFalse(info["rejected"])
            shadow.backward()
            parameter = model.weight if kind == "linear_pbit" else model.hidden_weight
            index = (1,) if parameter.ndim == 1 else (1, 2)
            actual = float(parameter.grad[index])
            original = float(parameter.detach()[index])
            epsilon = 1e-5
            values = []
            for change in (-epsilon, epsilon):
                with torch.no_grad():
                    parameter[index] = original + change
                _, changed = self.objective(model)
                values.append(changed["loss"])
            numerical = (values[1] - values[0]) / (2 * epsilon)
            self.assertAlmostEqual(actual, numerical, delta=max(2e-7, abs(numerical) * 2e-4), msg=kind)

    def test_exact_budget_and_256_atom_aggregation(self):
        model = make_model("pbit_4_8_1").double()
        basis = gate_basis(model, self.x, self.mass, self.groups)
        self.assertEqual(tuple(basis["a"].shape), (256,))
        solve_bias(model, basis, self.forced_mean, self.target, steps=70)
        q = model(self.x)
        self.assertAlmostEqual(float(q.sum().detach()) / self.groups + self.forced_mean, self.target, places=11)
        _, info = constrained_objective(model, basis, self.forced_mean, self.forced_mass_mean, self.target)
        self.assertLess(abs(info["F"]), 1e-11)

    def test_warmup_implicit_gradient(self):
        model = make_model("pbit_4_8_1", initialization="random").double()
        targets = torch.linspace(0.05, 0.8, len(self.x), dtype=self.x.dtype)
        def objective():
            basis = gate_basis(model, self.x, self.mass, self.groups)
            solve_bias(model, basis, self.forced_mean, self.target, steps=70)
            return constrained_objective(model, basis, self.forced_mean,
                self.forced_mass_mean, self.target, warmup_targets=targets)
        shadow, _ = objective()
        shadow.backward()
        actual = float(model.output_weight.grad[2])
        original = float(model.output_weight.detach()[2])
        values = []
        for change in (-1e-5, 1e-5):
            with torch.no_grad():
                model.output_weight[2] = original + change
            _, info = objective()
            values.append(info["loss"])
        numerical = (values[1] - values[0]) / 2e-5
        self.assertAlmostEqual(actual, numerical, delta=2e-7)

    def test_small_root_derivative_rejects_step(self):
        model = make_model("linear_pbit").double()
        with torch.no_grad():
            model.bias.fill_(100)
        basis = gate_basis(model, self.x, self.mass, self.groups)
        objective, info = constrained_objective(model, basis, self.forced_mean,
                                               self.forced_mass_mean, self.target)
        self.assertIsNone(objective)
        self.assertTrue(info["rejected"])

    def trainval_fixture(self):
        data = old_tests.TestPBitNetwork().fixture()
        return {key: value[:4] for key, value in data.items()}

    def test_reject_blind_before_loading_features(self):
        class ForbiddenArchive:
            files = ["split", "x"]
            def __enter__(self):
                return self
            def __exit__(self, *unused):
                return False
            def __getitem__(self, key):
                if key != "split":
                    raise AssertionError("feature arrays must not be loaded")
                return np.array([0, 1, 2])
        with mock.patch("numpy.load", return_value=ForbiddenArchive()):
            with self.assertRaisesRegex(ValueError, "TRAIN/VAL ONLY"):
                load_trainval_dataset("unused.npz")
        with tempfile.TemporaryDirectory(dir=temporary_root()) as directory:
            path = Path(directory) / "data.npz"
            np.savez(path, **self.trainval_fixture())
            loaded = load_trainval_dataset(path)
            self.assertEqual(set(loaded["split"].tolist()), {0, 1})

    def test_preprocess_fit_is_train_only_and_query_relative_declared(self):
        data = self.trainval_fixture()
        original = fit_preprocess(data, "global")
        changed = {key: value.copy() for key, value in data.items()}
        changed["x"][changed["split"] == 1] += 1000
        self.assertEqual(original, fit_preprocess(changed, "global"))
        normalization = fit_preprocess(data, "query_relative", 12)
        values = apply_preprocess(data["x"], data["valid"], data["forced"], normalization)
        self.assertLessEqual(float(np.abs(values).max()), 12)
        self.assertFalse(normalization["train_feature_standardization"])

    def test_payload_reload_and_true_sampled_marginal(self):
        data = self.trainval_fixture()
        normalization = fit_preprocess(data, "query_relative")
        for kind in ("pbit_4_8_1", "deterministic_4_8_1", "linear_pbit"):
            model = make_model(kind)
            payload = json.loads(json.dumps(model_payload(model, normalization)))
            reloaded = load_model(payload)
            self.assertEqual(sum(p.numel() for p in reloaded.parameters()), 5 if kind == "linear_pbit" else 49)
            q = predict_payload(payload, data)
            samples = sample_payload(payload, data, seed=123, draws=16000)
            np.testing.assert_allclose(samples.mean(0), q, atol=0.025, rtol=0)
            self.assertTrue(np.all(samples[:, data["forced"]] == 1))


if __name__ == "__main__":
    unittest.main()
