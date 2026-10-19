"""Stdlib provenance/guard regression tests; do not load Torch or model weights.

Run: python experiments/attention_e01/test_capture_contract.py
These tests do not establish GPU, Transformers-hook, numerical, or PPL validity.
"""

import copy
import json
import tempfile
from types import SimpleNamespace
import unittest
from pathlib import Path
from unittest import mock

import capture
import verify_inputs as verify


class InputContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="capture_contract_", dir=Path(__file__).resolve().parent)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.model = self.root / "model"
        self.model.mkdir()
        repo = Path(__file__).resolve().parents[2]
        (self.model / "config.json").write_bytes((repo / "config" / "qwen2.5-0.5b-config.json").read_bytes())
        (self.model / "tokenizer_config.json").write_text("{}", encoding="utf-8")
        (self.model / "tokenizer.json").write_text("{}", encoding="utf-8")
        (self.model / "model.safetensors").write_bytes(b"fixture, never load as model")
        self.text = self.root / "wiki.test.raw"
        self.text.write_text("verified corpus fixture\n", encoding="utf-8")
        # Fixtures cannot claim the real corpus/weight identity. Production
        # constants are overridden only inside this isolated test process.
        for name, value in (("WEIGHTS_SHA256", verify.sha256_file(self.model / "model.safetensors")),
                            ("TESTTEXT_SHA256", verify.sha256_file(self.text))):
            patcher = mock.patch.object(verify, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        paths = list(self.model.iterdir()) + [self.text]
        self.manifest = {
            "schema": verify.SCHEMA, "model_id": verify.MODEL_ID,
            "model_revision": verify.MODEL_REVISION,
            "provenance": {"reference": "test fixture only; no real model provenance"},
            "files": [{"role": "testtext" if path == self.text else verify.relevant_role(path),
                       "path": str(path), "sha256": verify.sha256_file(path),
                       "bytes": path.stat().st_size} for path in paths],
        }
        self.manifest_path = self.root / "expected.json"
        self.write_manifest()

    def write_manifest(self):
        self.manifest_path.write_text(json.dumps(self.manifest), encoding="utf-8")

    def run_verify(self):
        return verify.verify(str(self.model), str(self.text), str(self.manifest_path), str(self.root))

    def test_complete_coverage_and_recheck(self):
        report = self.run_verify()
        self.assertTrue(report["passed"])
        self.assertEqual(len(report["files"]), 5)
        report_path = self.root / "verified.json"
        report_path.write_text(json.dumps(report), encoding="utf-8")
        self.assertEqual(report, verify.recheck_report(report_path, self.model, self.text, self.root))

    def test_unlisted_model_shard_rejected(self):
        (self.model / "extra.safetensors").write_bytes(b"not in recorded manifest")
        with self.assertRaisesRegex(ValueError, "omits relevant"):
            self.run_verify()

    def test_missing_expected_hash_rejected(self):
        self.manifest["files"][0].pop("sha256")
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "expected SHA-256"):
            self.run_verify()

    def test_wrong_model_revision_rejected(self):
        self.manifest["model_revision"] = "0" * 40
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "original Qwen"):
            self.run_verify()

    def test_provenance_required(self):
        self.manifest["provenance"] = {}
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "independent recorded"):
            self.run_verify()

    def test_modified_test_bytes_rejected(self):
        self.text.write_text("different corpus, same file name\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "size mismatch|SHA-256 mismatch"):
            self.run_verify()

    def test_file_changed_after_verification_rejected(self):
        report = self.run_verify()
        report_path = self.root / "verified.json"
        report_path.write_text(json.dumps(report), encoding="utf-8")
        self.text.write_bytes(self.text.read_bytes().replace(b"verified", b"modified"))
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            verify.recheck_report(report_path, self.model, self.text, self.root)

    def test_config_geometry_rejected(self):
        config = copy.deepcopy(verify.EXPECTED_CONFIG)
        config["num_key_value_heads"] = 14
        with self.assertRaisesRegex(ValueError, "num_key_value_heads"):
            verify.validate_config(config)

    def test_config_bytes_are_independently_pinned(self):
        path = self.model / "config.json"
        path.write_bytes(path.read_bytes() + b"\n")
        for entry in self.manifest["files"]:
            if entry["path"] == str(path):
                entry["sha256"] = verify.sha256_file(path)
                entry["bytes"] = path.stat().st_size
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "original pinned"):
            self.run_verify()

    def test_self_generated_new_weight_manifest_does_not_change_reference(self):
        path = self.model / "model.safetensors"
        path.write_bytes(b"a different model with its own new expected hash")
        for entry in self.manifest["files"]:
            if entry["path"] == str(path):
                entry["sha256"] = verify.sha256_file(path)
                entry["bytes"] = path.stat().st_size
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "weights hash differs"):
            self.run_verify()

    def test_adapter_auto_loading_rejected(self):
        (self.model / "adapter_config.json").write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "adapter auto-loading"):
            self.run_verify()

    def test_parent_escape_rejected(self):
        with self.assertRaisesRegex(ValueError, "escapes"):
            verify.owned_path(self.root / ".." / "outside.json", self.root, exists=False)

    def test_relative_path_rejected(self):
        with self.assertRaisesRegex(ValueError, "absolute"):
            verify.owned_path("relative/file", self.root, exists=False)

    def test_symlink_escape_rejected(self):
        link = self.root / "escaped"
        try:
            link.symlink_to(self.root.parent, target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"symlink creation unavailable to this Windows user: {exc}")
        with self.assertRaisesRegex(ValueError, "escapes"):
            verify.owned_path(link, self.root)

    def test_role_mismatch_rejected(self):
        self.manifest["files"][-1]["role"] = "model"
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "path/role"):
            self.run_verify()

    def test_duplicate_manifest_entry_rejected(self):
        self.manifest["files"].append(self.manifest["files"][0])
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.run_verify()

    def test_verified_manifest_cannot_silently_change(self):
        report = self.run_verify()
        report_path = self.root / "verified.json"
        report_path.write_text(json.dumps(report), encoding="utf-8")
        self.manifest["provenance"]["reference"] = "changed source after verification"
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "inputs changed"):
            verify.recheck_report(report_path, self.model, self.text, self.root)


class CaptureGuardsTests(unittest.TestCase):
    def test_no_allocation_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "allocated Slurm"):
            capture.require_gpu_allocation({})

    def test_gpu_hidden_cpu_job_rejected(self):
        for value in ("", "-1", "NoDevFiles", "none"):
            with self.subTest(value=value), self.assertRaisesRegex(RuntimeError, "CUDA_VISIBLE_DEVICES"):
                capture.require_gpu_allocation({"SLURM_JOB_ID": "1", "SLURM_JOB_NODELIST": "gpu-node",
                                                "CUDA_VISIBLE_DEVICES": value})

    def test_allocation_guard_accepts_allocated_device(self):
        capture.require_gpu_allocation({"SLURM_JOB_ID": "1", "SLURM_JOB_NODELIST": "gpu-node",
                                        "CUDA_VISIBLE_DEVICES": "0"})

    def test_selected_rows_unique_and_bounded(self):
        self.assertEqual(len(capture.parse_rows(capture.DEFAULT_ROWS)), 6)
        for value in ("0:14", "24:0", "-1:0", "0:0,0:0", "", "0"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                capture.parse_rows(value)

    def test_scoped_interceptor_restores_sdpa_and_hooks_after_failure(self):
        removed = []

        class Handle:
            def remove(self):
                removed.append(True)

        class Qwen2SdpaAttention:
            def register_forward_pre_hook(self, callback):
                return Handle()

            def register_forward_hook(self, callback):
                return Handle()

        original = object()
        functional = SimpleNamespace(scaled_dot_product_attention=original)
        fake_torch = SimpleNamespace(nn=SimpleNamespace(functional=functional))
        fake_model = SimpleNamespace(model=SimpleNamespace(layers=[
            SimpleNamespace(self_attn=Qwen2SdpaAttention()) for _ in range(24)]))
        with self.assertRaisesRegex(RuntimeError, "deliberate"), capture.intercept_sdpa(
                fake_model, fake_torch, [(0, 0)], 64):
            self.assertIsNot(functional.scaled_dot_product_attention, original)
            raise RuntimeError("deliberate failure during captured forward")
        self.assertIs(functional.scaled_dot_product_attention, original)
        self.assertEqual(len(removed), 48)


if __name__ == "__main__":
    unittest.main(verbosity=2)
