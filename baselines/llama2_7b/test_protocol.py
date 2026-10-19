"""CPU contract tests: token coverage, shifted indexing and artifact identity."""

from __future__ import annotations

import json
import math
import tempfile
import unittest
from pathlib import Path

from protocol import EXPECTED_SHAPE, sha256, verify_identity, windows, write_json


class SlidingWindowTest(unittest.TestCase):
    def test_all_targets_exactly_once_for_short_and_partial_windows(self):
        for n in (2, 3, 5, 6, 7, 8, 9, 10, 17, 33, 2048, 2049, 2560, 4096, 4100):
            for w, stride in ((5, 1), (5, 3), (8, 7), (2048, 512), (4096, 512)):
                items = list(windows(n, w, stride))
                targets = [p for item in items for p in range(item.score_start, item.end)]
                self.assertEqual(targets, list(range(1, n)), (n, w, stride))
                self.assertEqual(sum(x.count for x in items), n - 1)
                self.assertTrue(all(0 <= x.logits_start < x.end - x.begin - 1 for x in items))

    def test_reference_mask_and_shift_match_global_target_positions(self):
        # A tiny causal scorer returns vocabulary probabilities based on the
        # previous token. It exposes off-by-one label shifts independently of
        # the window implementation; all windows must have the same token NLL.
        tokens = [0, 1, 2, 0, 2, 1, 1, 0, 2, 0, 1, 2, 1, 0, 0, 2, 1]
        transition = [[0.1, 0.7, 0.2], [0.2, 0.3, 0.5], [0.6, 0.1, 0.3]]
        expected = math.fsum(-math.log(transition[tokens[p - 1]][tokens[p]])
                             for p in range(1, len(tokens)))
        for width, stride in ((4, 1), (6, 3), (10, 5), (30, 7)):
            losses = []
            for item in windows(len(tokens), width, stride):
                batch = tokens[item.begin:item.end]
                local_logits = range(item.logits_start, len(batch) - 1)
                for local in local_logits:
                    losses.append(-math.log(transition[batch[local]][batch[local + 1]]))
            self.assertEqual(len(losses), len(tokens) - 1)
            self.assertAlmostEqual(math.fsum(losses), expected, places=13)

    def test_no_added_bos_or_lost_boundary_target(self):
        items = list(windows(15, 8, 3))
        self.assertEqual([x.record() for x in items], [
            {"begin": 0, "end": 8, "score_start": 1, "count": 7, "logits_start": 0},
            {"begin": 3, "end": 11, "score_start": 8, "count": 3, "logits_start": 4},
            {"begin": 6, "end": 14, "score_start": 11, "count": 3, "logits_start": 4},
            {"begin": 9, "end": 15, "score_start": 14, "count": 1, "logits_start": 4},
        ])

    def test_reject_nonoverlap_and_invalid_inputs(self):
        for args in ((1, 8, 2), (9, 1, 1), (9, 8, 0), (9, 8, 8), (9, 8, 9)):
            with self.assertRaises(ValueError):
                list(windows(*args))


class IdentityTest(unittest.TestCase):
    def setUp(self):
        # Explicit verified personal checkout directory, never shared /tmp.
        self.test_parent = Path(__file__).resolve().parent / ".test_tmp"
        self.test_parent.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="identity-", dir=self.test_parent)
        self.root = Path(self.temp.name)
        self.model = self.root / "model"
        self.model.mkdir()
        write_json(self.model / "config.json", EXPECTED_SHAPE)
        for name in ("tokenizer.json", "tokenizer.model", "tokenizer_config.json", "model.safetensors"):
            (self.model / name).write_bytes(b"fixture bytes only; not a real model\n")
        self.manifest = {
            "repository": "meta-llama/Llama-2-7b-hf", "revision": "a" * 40,
            "model_shape": dict(EXPECTED_SHAPE),
            "files": {p.name: {"bytes": p.stat().st_size, "sha256": sha256(p)}
                      for p in self.model.iterdir()},
        }
        self.path = self.root / "identity.json"

    def tearDown(self):
        self.temp.cleanup()
        if self.test_parent.exists() and not any(self.test_parent.iterdir()):
            self.test_parent.rmdir()

    def save(self):
        self.path.write_text(json.dumps(self.manifest), encoding="utf-8", newline="\n")

    def test_verified_fixture_and_changed_bytes_fail_closed(self):
        self.save()
        self.assertTrue(verify_identity(self.model, self.path)["use_safetensors"])
        (self.model / "tokenizer.model").write_bytes(b"modified")
        with self.assertRaisesRegex(ValueError, "mismatch"):
            verify_identity(self.model, self.path)

    def test_extra_loader_metadata_must_be_verified(self):
        self.save()
        (self.model / "generation_config.json").write_bytes(b"{}")
        with self.assertRaisesRegex(ValueError, "not identity-verified"):
            verify_identity(self.model, self.path)

    def test_unverified_shadow_checkpoint_is_rejected(self):
        self.save()
        (self.model / "model-00001-of-00002.safetensors").write_bytes(b"unverified shadow")
        with self.assertRaisesRegex(ValueError, "checkpoint file is not identity-verified"):
            verify_identity(self.model, self.path)

    def test_unsafe_path_and_wrong_model_revision_fail(self):
        self.manifest["files"]["../escape"] = {"sha256": "0" * 64, "bytes": 0}
        self.save()
        with self.assertRaisesRegex(ValueError, "escapes"):
            verify_identity(self.model, self.path)
        del self.manifest["files"]["../escape"]
        self.manifest["revision"] = "main"
        self.save()
        with self.assertRaisesRegex(ValueError, "40-hex"):
            verify_identity(self.model, self.path)

    def test_missing_weight_shard_fails(self):
        (self.model / "model.safetensors").unlink()
        del self.manifest["files"]["model.safetensors"]
        index = self.model / "model.safetensors.index.json"
        write_json(index, {"weight_map": {"weight": "model-00001-of-00002.safetensors"}})
        self.manifest["files"][index.name] = {"sha256": sha256(index), "bytes": index.stat().st_size}
        self.save()
        with self.assertRaisesRegex(ValueError, "Unverified weight shards"):
            verify_identity(self.model, self.path)


if __name__ == "__main__":
    unittest.main()
