"""CPU-only gates for complete freezing, blind isolation and immutable inputs."""
import copy
from contextlib import nullcontext, redirect_stdout
import io
import importlib.util
import itertools
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

import numpy as np

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("gate_blind_evaluate_test", HERE / "blind_evaluate.py")
blind = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(blind)


class BlindTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="blind-test-", dir=Path(os.environ.get("GATE_OUTPUT_ROOT", HERE)))
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.primary = self.root / "primary"
        self.config = dict(layers=[0, 12, 23], train_seeds=[0, 1, 2],
                           kinds=["pbit_4_8_1", "linear_pbit", "deterministic_4_8_1"],
                           preprocess_modes=["query_relative", "global"],
                           max4_temperatures=[0.125, 0.25, 0.5, 1., 2.],
                           val_budget_ratio_max=1.02, device="cuda", eval_seeds=[101, 202, 303],
                           eval_draws=32, epsilon=1e-12, direct_epochs=300)
        self.make_search(self.primary, self.config)

    def write(self, path, value):
        blind.write_json(path, value)

    def make_search(self, root, config, primary=None):
        (root / "search").mkdir(parents=True)
        (root / "capture").mkdir()
        self.write(root / "runtime_config.json", config)
        config_sha = blind.digest(root / "runtime_config.json")
        datasets = dict(training_dataset=dict(path=str(root / "capture/training_dataset.npz"), sha256="1" * 64,
                                              groups=6, split_values=[0, 1], arrays={}),
                        blind_holdout=dict(path=str(root / "capture/blind_holdout.npz"), sha256="2" * 64,
                                           groups=3, split_values=[2], arrays={}))
        capture = dict(status="completed", config_sha256=config_sha, datasets=datasets)
        if primary:
            capture = blind.read_json(primary / "capture/capture.json")[0]
            datasets = capture["datasets"]
        self.write(root / "capture/capture.json", capture)
        binding = dict(resolved_config=config, config_sha256=config_sha, dataset_sha256="1" * 64,
                       dataset_path=datasets["training_dataset"]["path"],
                       source_sha256={name: blind.digest(HERE / name) for name in ("optimize.py", "network.py", "train.py")},
                       code_commit="a" * 40, blind_dataset_loaded=False, split_ids=[0, 1])
        self.write(root / "search/DATA_BINDING.json", binding)
        summary = dict(candidates=[], baselines=[], selected_by_layer={}, selected_by_family={}, blind_dataset_loaded=False)
        for layer in config["layers"]:
            for temperature in config["max4_temperatures"]:
                identity = f"layer{layer}_max4_temp{temperature:g}"
                payload = dict(format="gate_phase2_v1", kind="max4_standardized_sigmoid", layer=layer,
                               temperature=temperature, bias=0., normalization={"mode": "max4_query_free"})
                filename = identity + "_model.json"
                if primary and (primary / "search" / filename).is_file():
                    (root / "search" / filename).write_bytes((primary / "search" / filename).read_bytes())
                else:
                    self.write(root / "search" / filename, payload)
                val = dict(expected_selected_blocks=8., expected_missed_mass=0.1 + temperature * .01,
                           sampled_subset_pv_nmse_mean=.2)
                summary["baselines"].append(dict(id=identity, kind=payload["kind"], layer=layer,
                    temperature=temperature, val=val, model_file=filename, model_sha256=blind.digest(root / "search" / filename)))
            for kind, mode, seed in itertools.product(config["kinds"], config["preprocess_modes"], config["train_seeds"]):
                identity = f"layer{layer}_{kind}_{mode}_seed{seed}"
                payload = dict(format="gate_phase2_v1", kind=kind, layer=layer, preprocess=mode, seed=seed,
                               normalization={"mode": mode}, parameters={"bias": 0.},
                               checkpoint={"epoch": config["direct_epochs"]})
                filename = identity + "_model.json"
                self.write(root / "search" / filename, payload)
                val = dict(expected_selected_blocks=8., expected_missed_mass=(.05 if primary else .12) + seed * .001,
                           sampled_subset_pv_nmse_mean=.1)
                summary["candidates"].append(dict(id=identity, kind=kind, layer=layer, preprocess=mode, seed=seed,
                    val=val, val_budget_pass=True, selection={"budget_eligible": True},
                    model_file=filename, model_sha256=blind.digest(root / "search" / filename)))
            entries = [row for row in summary["candidates"] + summary["baselines"] if row["layer"] == layer]
            selected = min(entries, key=lambda row: row["val"]["expected_missed_mass"])
            summary["selected_by_layer"][str(layer)] = {key: selected[key] for key in ("id", "model_file", "model_sha256")}
            families = {}
            for kind, mode in itertools.product(config["kinds"], config["preprocess_modes"]):
                selected = next(row for row in entries if row["kind"] == kind and row.get("preprocess") == mode)
                families[kind + "/" + mode] = {key: selected[key] for key in ("id", "model_file", "model_sha256")}
            summary["selected_by_family"][str(layer)] = families
        self.write(root / "search/SCAN_SUMMARY.json", summary)
        return summary

    def test_freeze_never_opens_npz_and_retains_all_configurations(self):
        original_open = Path.open
        def json_only(path, *args, **kwargs):
            if Path(path).suffix == ".npz":
                raise AssertionError("freeze opened a dataset")
            return original_open(path, *args, **kwargs)
        output = self.root / "frozen"
        with mock.patch.object(Path, "open", json_only), mock.patch.object(np, "load", side_effect=AssertionError("blind load")):
            frozen = blind.freeze(self.primary, output)
        self.assertEqual(frozen["record_count"], 69)
        self.assertEqual(sum(row["role"] == "candidate" for row in frozen["records"]), 54)
        self.assertFalse(frozen["blind_dataset_opened"])
        loaded, payloads = blind.load_frozen(output / "FREEZE.json")
        self.assertEqual(len(payloads), 69)
        self.assertEqual(loaded["selected_by_layer"], frozen["selected_by_layer"])
        self.assertFalse((self.primary / "capture/blind_holdout.npz").exists())

    def test_missing_candidate_and_changed_model_reject_before_output(self):
        summary_path = self.primary / "search/SCAN_SUMMARY.json"
        summary = blind.read_json(summary_path)[0]
        omitted = summary["candidates"].pop()
        blind.write_json(summary_path, summary, replace=True)
        with self.assertRaisesRegex(ValueError, "incomplete or duplicated"):
            blind.freeze(self.primary, self.root / "missing")
        self.assertFalse((self.root / "missing").exists())
        summary["candidates"].append(omitted)
        blind.write_json(summary_path, summary, replace=True)
        (self.primary / "search" / omitted["model_file"]).write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "model SHA mismatch"):
            blind.freeze(self.primary, self.root / "changed")

    def test_refinement_freezes_78_and_selects_only_from_validation(self):
        refine = self.root / "refinement"
        config = dict(self.config, kinds=["pbit_4_8_1"], preprocess_modes=["query_relative"], direct_epochs=6000)
        self.make_search(refine, config, self.primary)
        frozen = blind.freeze(self.primary, self.root / "frozen", refine)
        self.assertEqual(frozen["record_count"], 78)
        self.assertEqual(frozen["candidate_count"], 63)
        self.assertTrue(all(row["id"].startswith("refine1__") for row in frozen["selected_by_layer"].values()))
        self.assertTrue(frozen["search_sources"]["refine1"]["capture_training_config_differ"])
        self.assertTrue(all(not row["id"].startswith("refine1__") for row in
                            frozen["search_sources"]["primary"]["selected_by_layer"].values()))
        _, payloads = blind.load_frozen(self.root / "frozen/FREEZE.json")
        self.assertEqual(len(payloads), 78)

    def test_changed_duplicate_control_rejects_additional_search(self):
        refine = self.root / "refinement"
        config = dict(self.config, kinds=["pbit_4_8_1"], preprocess_modes=["query_relative"], direct_epochs=6000)
        summary = self.make_search(refine, config, self.primary)
        row = summary["baselines"][0]
        path = refine / "search" / row["model_file"]
        path.write_text("{}", encoding="utf-8")
        row["model_sha256"] = blind.digest(path)
        blind.write_json(refine / "search/SCAN_SUMMARY.json", summary, replace=True)
        with self.assertRaisesRegex(ValueError, "duplicate baseline differs"):
            blind.freeze(self.primary, self.root / "frozen", refine)
        self.assertFalse((self.root / "frozen").exists())

    def test_all_ninety_models_include_low_temperature_and_train_threshold(self):
        refine = self.root / "refinement"
        config = dict(self.config, kinds=["pbit_4_8_1"], preprocess_modes=["query_relative"], direct_epochs=6000)
        self.make_search(refine, config, self.primary)
        extension = self.root / "baseline_extension"
        extension_config = dict(self.config, kinds=[], preprocess_modes=[],
                                max4_temperatures=[.015625, .03125, .0625, 1.0])
        summary = self.make_search(extension, extension_config, self.primary)
        for layer in (0, 12, 23):
            identity = f"layer{layer}_max4_train_threshold"
            payload = dict(format="gate_phase2_v1", kind="max4_train_threshold", layer=layer,
                           threshold=0., tie_probability=.5, normalization={"mode": "max4_query_free"})
            filename = identity + "_model.json"
            self.write(extension / "search" / filename, payload)
            summary["baselines"].append(dict(id=identity, kind="max4_train_threshold", layer=layer,
                temperature=None, model_file=filename, model_sha256=blind.digest(extension / "search" / filename),
                val=dict(expected_selected_blocks=8., expected_missed_mass=.01, sampled_subset_pv_nmse_mean=.1)))
        blind.write_json(extension / "search/SCAN_SUMMARY.json", summary, replace=True)
        frozen = blind.freeze(self.primary, self.root / "frozen", refine, extension)
        self.assertEqual(frozen["record_count"], 90)
        self.assertEqual(frozen["temperature_control_count"], 24)
        self.assertEqual(frozen["hard_threshold_control_count"], 3)
        self.assertTrue(all(row["id"].startswith("baseline1__") for row in frozen["selected_by_layer"].values()))
        _, payloads = blind.load_frozen(self.root / "frozen/FREEZE.json")
        self.assertEqual(len(payloads), 90)

    def test_only_optimize_source_can_differ_from_training(self):
        path = self.primary / "search/DATA_BINDING.json"
        binding = blind.read_json(path)[0]
        binding["source_sha256"]["network.py"] = "3" * 64
        blind.write_json(path, binding, replace=True)
        with self.assertRaisesRegex(ValueError, "only the authorized optimize.py"):
            blind.freeze(self.primary, self.root / "wrong_network")
        binding["source_sha256"]["network.py"] = blind.digest(HERE / "network.py")
        binding["source_sha256"]["optimize.py"] = "3" * 64
        blind.write_json(path, binding, replace=True)
        frozen = blind.freeze(self.primary, self.root / "allowed_dispatch")
        self.assertEqual(frozen["search_sources"]["primary"]["training_source_sha256"]["optimize.py"], "3" * 64)
        self.assertEqual(frozen["evaluation_source_sha256"]["optimize.py"], blind.digest(HERE / "optimize.py"))
        self.assertEqual(frozen["operator_compatibility"]["changed_by_source"], {"primary": ["optimize.py"]})

    def test_frozen_parameter_or_config_tampering_is_detected(self):
        output = self.root / "frozen"
        frozen = blind.freeze(self.primary, output)
        path = Path(frozen["records"][0]["frozen_model_file"])
        original = path.read_bytes()
        path.write_bytes(b"{}")
        with self.assertRaisesRegex(ValueError, "frozen artifact changed"):
            blind.load_frozen(output / "FREEZE.json")
        path.write_bytes(original)
        changed = copy.deepcopy(frozen)
        changed["config"]["eval_draws"] = 999
        blind.write_json(output / "FREEZE.json", changed, replace=True)
        with self.assertRaisesRegex(ValueError, "frozen artifact changed"):
            blind.load_frozen(output / "FREEZE.json")

    def test_unknown_split_rejected_before_loading_teacher_arrays(self):
        class Archive:
            files = ["split", "x"]
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def __getitem__(self, key):
                if key != "split": raise AssertionError("loaded teacher before split guard")
                return np.array([2, 1], dtype=np.int8)
        with mock.patch.object(blind, "digest", return_value="2" * 64), mock.patch.object(np, "load", return_value=Archive()):
            with self.assertRaisesRegex(ValueError, "only nonempty split2"):
                blind.load_blind_dataset(self.root / "blind.npz", "2" * 64)

    def prepare_blind_data(self):
        data = dict(x=np.zeros((3, 32, 4), dtype=np.float32), mass=np.full((3, 32), 1 / 32, dtype=np.float32),
            block_v=np.zeros((3, 32, 64), dtype=np.float32), teacher_output=np.zeros((3, 64), dtype=np.float32),
            valid=np.ones((3, 32), dtype=np.bool_), forced=np.zeros((3, 32), dtype=np.bool_),
            counts=np.full((3, 32), 64, dtype=np.int16), split=np.full(3, 2, dtype=np.int8),
            layer=np.array([0, 12, 23], dtype=np.int64), document=np.zeros(3, dtype=np.int64),
            head=np.zeros(3, dtype=np.int64), position=np.full(3, 2047, dtype=np.int64))
        data["forced"][:, [0, 30, 31]] = True
        path = self.primary / "capture/blind_holdout.npz"
        np.savez_compressed(path, **data)
        capture_path = self.primary / "capture/capture.json"
        capture = blind.read_json(capture_path)[0]
        capture["datasets"]["blind_holdout"].update(sha256=blind.digest(path),
            arrays={key: dict(shape=list(value.shape), dtype=str(value.dtype)) for key, value in data.items()})
        blind.write_json(capture_path, capture, replace=True)
        return data

    def test_evaluate_is_started_before_blind_read_and_reports_every_payload(self):
        self.prepare_blind_data()
        frozen = blind.freeze(self.primary, self.root / "frozen")
        output, calls = self.root / "evaluation", []
        fake_torch = SimpleNamespace(__version__="mock", set_num_threads=lambda _: None,
            inference_mode=nullcontext, cuda=SimpleNamespace(is_available=lambda: True,
            device_count=lambda: 1, get_device_name=lambda _: "mock allocation"))
        def evaluate_payload(payload, data, split, config):
            self.assertEqual(split, 2)
            self.assertEqual(set(data["split"].tolist()), {2})
            calls.append((payload["kind"], payload["layer"]))
            return {"groups": len(data["split"]), "sampling_contract": "mock CPU API routing test"}
        fake_operator = SimpleNamespace(torch=fake_torch, validate_dataset=lambda _: None,
            subset=lambda data, mask: {key: value[mask] for key, value in data.items()}, evaluate_payload=evaluate_payload)
        original_load = np.load
        def checked_load(path, **kwargs):
            self.assertTrue((output / "EVAL_STARTED.json").is_file())
            self.assertEqual(Path(path).name, "blind_holdout.npz")
            return original_load(path, **kwargs)
        with mock.patch.object(blind, "allocation_context", return_value={"scope": "mock CPU routing"}), \
             mock.patch.object(blind.importlib, "import_module", return_value=fake_operator), \
             mock.patch.object(np, "load", checked_load), \
             mock.patch.object(blind, "verify_evaluation_sources", wraps=blind.verify_evaluation_sources) as verify, \
             redirect_stdout(io.StringIO()):
            result = blind.evaluate(self.root / "frozen/FREEZE.json", output)
            self.assertEqual(verify.call_count, 2)
        self.assertEqual(len(calls), 69)
        self.assertEqual(result["selected_by_layer"], frozen["selected_by_layer"])
        self.assertEqual(result["status"], "completed")
        self.assertTrue((output / "RESULT_MANIFEST.json").is_file())
        self.assertEqual(len(list((output / "records").iterdir())), 69)

    def test_real_hard_threshold_dispatch_cpu_smoke(self):
        try:
            import torch
        except ImportError:
            self.skipTest("torch absent locally; required in server CPU integration preflight")
        package_root = str(HERE.parents[1])
        import sys
        with mock.patch.object(sys, "path", [package_root] + sys.path):
            operator = __import__("experiments.pbit_gate_pilot_20261022.optimize", fromlist=["evaluate_payload"])
        torch.set_num_threads(1)
        data = self.prepare_blind_data()
        data = operator.subset(data, data["layer"] == 0)
        payload = dict(format="gate_phase2_v1", kind="max4_train_threshold", layer=0,
                       threshold=0., tie_probability=.25, normalization={"mode": "max4_query_free", "std_floor": .01})
        config = dict(self.config, device="cpu", eval_draws=4)
        result = operator.evaluate_payload(payload, data, 2, config)
        self.assertEqual(result["groups"], 1)
        self.assertAlmostEqual(result["expected_selected_blocks"], 3 + 29 * .25, places=6)
        self.assertEqual(set(result["by_position"]), {"2047"})

    def test_evaluation_failure_keeps_partial_and_failure_manifest(self):
        self.prepare_blind_data()
        blind.freeze(self.primary, self.root / "frozen")
        output, calls = self.root / "failed_evaluation", []
        def failing(payload, data, split, config):
            calls.append(payload)
            if len(calls) == 2:
                raise RuntimeError("injected evaluation failure")
            return {"groups": len(data["split"])}
        fake = SimpleNamespace(torch=SimpleNamespace(__version__="mock", set_num_threads=lambda _: None,
            inference_mode=nullcontext, cuda=SimpleNamespace(is_available=lambda: True,
                device_count=lambda: 1, get_device_name=lambda _: "mock")),
            validate_dataset=lambda _: None, subset=lambda data, mask: {key: value[mask] for key, value in data.items()},
            evaluate_payload=failing)
        with mock.patch.object(blind, "allocation_context", return_value={}), \
             mock.patch.object(blind.importlib, "import_module", return_value=fake), redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(RuntimeError, "injected evaluation failure"):
                blind.evaluate(self.root / "frozen/FREEZE.json", output)
        self.assertEqual(blind.read_json(output / "PARTIAL.json")[0]["completed_records"], 1)
        self.assertEqual(blind.read_json(output / "FAILURE.json")[0]["status"], "failed")
        self.assertTrue((output / "RESULT_MANIFEST.json").is_file())
        self.assertEqual(len(list((output / "records").iterdir())), 1)

    def test_evaluate_requires_allocation_and_preserves_existing_output(self):
        output = self.root / "frozen"
        blind.freeze(self.primary, output)
        with mock.patch.dict(os.environ, {"SLURM_JOB_ID": "", "CUDA_VISIBLE_DEVICES": ""}):
            with self.assertRaises(RuntimeError):
                blind.evaluate(output / "FREEZE.json", self.root / "evaluation")
        existing = self.root / "existing"
        existing.mkdir()
        with self.assertRaises(FileExistsError):
            blind.evaluate(output / "FREEZE.json", existing)
        self.assertFalse((self.root / "evaluation").exists())


if __name__ == "__main__":
    unittest.main()
