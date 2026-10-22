"""Small CPU checks for article isolation and the exact causal teacher contract."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

import numpy as np

_path = Path(__file__).with_name("capture_teacher.py")
_spec = importlib.util.spec_from_file_location("gate_capture_teacher_under_test", _path)
capture = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(capture)


class DocumentTests(unittest.TestCase):
    def test_top_level_split_preserves_sections_and_deduplicates_body(self):
        text = "\n = Article one =\nbody one\n == Section ==\nmore\n = Duplicate title =\nbody  one\n == Section ==\nmore\n = Article two =\nbody two\n"
        docs = capture.parse_documents(text)
        self.assertEqual(len(docs), 3)
        self.assertIn("== Section ==", docs[0]["text"])
        self.assertEqual(docs[0]["content_sha256"], docs[1]["content_sha256"])
        self.assertNotEqual(docs[0]["content_sha256"], docs[2]["content_sha256"])
        self.assertEqual(docs[0]["text"], " = Article one =\nbody one\n == Section ==\nmore\n")
        spaced = capture.parse_documents(" = A = \n  body  \n = = Section = = \n more \n")
        self.assertEqual(len(spaced), 1)
        self.assertIn(" = = Section = = ", spaced[0]["text"])
        self.assertTrue(spaced[0]["text"].startswith(" = A = \n  body  \n"))

    def test_reproducible_disjoint_document_selection_and_length_filter(self):
        docs = capture.parse_documents("".join(f" = Article {i} =\nunique body {i}\n" for i in range(12)))
        def encode(text):
            article = int(text.split("Article ", 1)[1].split()[0])
            return [article * 100 + t for t in range(4 if article == 0 else 12)]
        options = dict(context=8, train_docs=3, val_docs=2, holdout_docs=2, seed=42)
        chosen, summary = capture.select_documents(docs, encode, **options)
        repeated, _ = capture.select_documents(docs, encode, **options)
        self.assertEqual(chosen, repeated)
        self.assertEqual([d["split"] for d in chosen], [0, 0, 0, 1, 1, 2, 2])
        self.assertEqual(len({d["content_sha256"] for d in chosen}), 7)
        self.assertTrue(all(len(d["token_ids"]) == 9 for d in chosen))
        self.assertTrue(all(d["source_document_index"] != 0 for d in chosen))
        self.assertEqual(summary["selected_articles"], 7)

    def test_duplicate_truncated_inputs_cannot_cross_splits(self):
        docs = capture.parse_documents("".join(f" = Article {i} =\nunique body {i}\n" for i in range(8)))
        def encode(text):
            article = int(text.split("Article ", 1)[1].split()[0])
            prefix = 30 if article in (3, 4) else article
            return [prefix * 100 + t for t in range(9)] + [article]
        chosen, summary = capture.select_documents(
            docs, encode, context=8, train_docs=3, val_docs=2, holdout_docs=2, seed=42)
        self.assertEqual(len({d["truncated_token_ids_sha256"] for d in chosen}), 7)
        self.assertEqual(summary["duplicate_truncated_inputs_skipped"], 1)

    def test_missing_articles_and_insufficient_unique_text_fail(self):
        with self.assertRaises(ValueError):
            capture.parse_documents("not an article")
        docs = capture.parse_documents(" = A =\nsame\n = B =\nsame\n = C =\nother\n")
        with self.assertRaises(ValueError):
            capture.select_documents(docs, lambda _: range(20), context=8,
                                     train_docs=1, val_docs=1, holdout_docs=1, seed=1)

    def test_phase_two_excludes_old_content_exact_article_and_truncated_tokens(self):
        docs = capture.parse_documents("".join(f" = Article {i} =\nunique body {i}\n" for i in range(20)))
        encoded = []
        def encode(text):
            article = int(text.split("Article ", 1)[1].split()[0])
            encoded.append(article)
            return [100 * article + token for token in range(12)]
        old, _ = capture.select_documents(docs, encode, context=8, train_docs=1,
                                          val_docs=1, holdout_docs=1, seed=42)
        excluded_document_sha256 = [old[0]["content_sha256"].upper(), old[1]["article_text_sha256"]]
        excluded_token_sha256 = [old[2]["truncated_token_ids_sha256"]]
        encoded.clear()
        options = dict(context=8, train_docs=3, val_docs=2, holdout_docs=2, seed=42,
                       exclude_document_sha256=excluded_document_sha256,
                       exclude_truncated_token_sha256=excluded_token_sha256)
        new, summary = capture.select_documents(docs, encode, **options)
        self.assertFalse({d["content_sha256"] for d in old} & {d["content_sha256"] for d in new})
        self.assertFalse({d["truncated_token_ids_sha256"] for d in old}
                         & {d["truncated_token_ids_sha256"] for d in new})
        self.assertNotIn(old[0]["source_document_index"], encoded)
        self.assertNotIn(old[1]["source_document_index"], encoded)
        self.assertEqual(summary["excluded_documents_skipped"], 2)
        self.assertEqual(summary["excluded_truncated_inputs_skipped"], 1)
        repeated, repeated_summary = capture.select_documents(docs, encode, **options)
        self.assertEqual(new, repeated)
        self.assertEqual(summary, repeated_summary)

    def test_exclusions_are_validated_and_insufficient_remaining_data_fails(self):
        docs = capture.parse_documents("".join(f" = Article {i} =\nunique body {i}\n" for i in range(3)))
        options = dict(context=8, train_docs=1, val_docs=1, holdout_docs=1, seed=42)
        def encode(text):
            article = int(text.split("Article ", 1)[1].split()[0])
            return [article * 100 + token for token in range(12)]
        with self.assertRaisesRegex(ValueError, "only 2 eligible"):
            capture.select_documents(docs, encode,
                                     exclude_document_sha256=[docs[0]["content_sha256"]], **options)
        for invalid in ("a" * 64, ["abc"], [None]):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                capture.select_documents(docs, encode,
                                         exclude_truncated_token_sha256=invalid, **options)


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        # Never use the shared server's global /tmp for test artifacts.
        self.temporary = tempfile.TemporaryDirectory(
            prefix="capture-test-", dir=Path(os.environ.get("GATE_OUTPUT_ROOT", str(_path.parent))).resolve())
        self.addCleanup(self.temporary.cleanup)
        self.output = Path(self.temporary.name)
        self.arrays = dict(
            x=np.arange(6 * 32 * 4, dtype=np.float32).reshape(6, 32, 4),
            mass=np.ones((6, 32), dtype=np.float32) / 32,
            block_v=np.zeros((6, 32, 64), dtype=np.float32),
            valid=np.ones((6, 32), dtype=np.bool_),
            forced=np.zeros((6, 32), dtype=np.bool_),
            counts=np.full((6, 32), 64, dtype=np.int16),
            teacher_output=np.zeros((6, 64), dtype=np.float32),
            document=np.array([0, 0, 1, 1, 2, 2], dtype=np.int64),
            layer=np.array([0, 12] * 3, dtype=np.int64),
            head=np.zeros(6, dtype=np.int64), position=np.full(6, 2047, dtype=np.int64),
            split=np.array([0, 0, 1, 1, 2, 2], dtype=np.int8),
        )

    def test_blind_and_training_files_preserve_schema_and_row_values(self):
        artifacts = capture.write_dataset_artifacts(self.output, self.arrays, emit_blind_split=True)
        self.assertEqual(set(artifacts), {"dataset", "training_dataset", "blind_holdout"})
        self.assertEqual(artifacts["training_dataset"]["split_values"], [0, 1])
        self.assertEqual(artifacts["blind_holdout"]["split_values"], [2])
        self.assertEqual(artifacts["training_dataset"]["groups"], 4)
        self.assertEqual(artifacts["blind_holdout"]["groups"], 2)
        for name, mask in (("dataset", np.ones(6, dtype=np.bool_)),
                           ("training_dataset", self.arrays["split"] != 2),
                           ("blind_holdout", self.arrays["split"] == 2)):
            path = self.output / (name + ".npz")
            self.assertEqual(artifacts[name]["sha256"], capture.digest(path))
            with np.load(path, allow_pickle=False) as saved:
                self.assertEqual(set(saved.files), set(self.arrays))
                for key, original in self.arrays.items():
                    np.testing.assert_array_equal(saved[key], original[mask])
                    self.assertEqual(saved[key].dtype, original.dtype)

    def test_legacy_mode_emits_only_full_dataset(self):
        artifacts = capture.write_dataset_artifacts(self.output, self.arrays)
        self.assertEqual(set(artifacts), {"dataset"})
        self.assertEqual([path.name for path in self.output.iterdir()], ["dataset.npz"])

    def test_blind_partition_rejects_crossed_documents_before_any_write(self):
        self.arrays["document"][-1] = 0
        with self.assertRaisesRegex(ValueError, "document crosses"):
            capture.write_dataset_artifacts(self.output, self.arrays, emit_blind_split=True)
        self.assertEqual(list(self.output.iterdir()), [])

    def test_preexisting_archive_is_never_overwritten(self):
        target = self.output / "blind_holdout.npz"
        target.write_bytes(b"original archive")
        with self.assertRaises(FileExistsError):
            capture.write_dataset_artifacts(self.output, self.arrays, emit_blind_split=True)
        self.assertEqual(target.read_bytes(), b"original archive")
        self.assertFalse((self.output / "dataset.npz").exists())


class TeacherTests(unittest.TestCase):
    def test_uniform_teacher_blocks_features_forced_and_value_sum(self):
        q = np.zeros(64, dtype=np.float32)
        k = np.arange(192 * 64, dtype=np.float32).reshape(192, 64)
        v = np.repeat(np.arange(192, dtype=np.float32)[:, None], 64, axis=1)
        row = capture.row_statistics(q, k, v, 149)
        self.assertEqual(row["x"].shape, (32, 4))
        np.testing.assert_array_equal(row["counts"][:4], [64, 64, 22, 0])
        np.testing.assert_allclose(row["mass"][:3], np.array([64, 64, 22]) / 150, atol=1e-7)
        np.testing.assert_array_equal(np.flatnonzero(row["valid"]), [0, 1, 2])
        np.testing.assert_array_equal(np.flatnonzero(row["forced"]), [0, 1, 2])
        np.testing.assert_allclose(row["teacher_output"], np.full(64, 74.5), atol=2e-5)
        np.testing.assert_array_equal(row["teacher_output"], row["block_v"].sum(axis=0))
        self.assertTrue(all(not value.dtype.hasobject for value in row.values()))

    def test_causal_future_invariance_and_subblock_means(self):
        rng = np.random.default_rng(5)
        q, k, v = rng.normal(size=64), rng.normal(size=(256, 64)), rng.normal(size=(256, 64))
        q, k, v = (t.astype(np.float32) for t in (q, k, v))
        first = capture.row_statistics(q, k, v, 127)
        k[128:], v[128:] = 1e6, -1e6
        second = capture.row_statistics(q, k, v, 127)
        for key in first:
            np.testing.assert_array_equal(first[key], second[key])
        for sub in range(4):
            expected = k[64 + sub * 16:64 + (sub + 1) * 16].mean(axis=0) @ q / 8
            self.assertAlmostEqual(float(first["x"][1, sub]), float(expected), places=6)
        scores = k[:128] @ q / 8
        p = np.exp(scores - scores.max()); p /= p.sum()
        np.testing.assert_allclose(first["teacher_output"], p @ v[:128], rtol=1e-5, atol=1e-6)
        self.assertAlmostEqual(float(first["mass"].sum()), 1.0, places=6)
        self.assertFalse(first["forced"][2:].any())

    def test_forced_last_two_blocks_and_invalid_shapes(self):
        q, k, v = np.ones(64), np.ones((2048, 64)), np.ones((2048, 64))
        row = capture.row_statistics(q, k, v, 2047)
        np.testing.assert_array_equal(np.flatnonzero(row["forced"]), [0, 30, 31])
        self.assertTrue(row["valid"].all())
        with self.assertRaises(ValueError):
            capture.row_statistics(q, k, v, 2048)
        with self.assertRaises(ValueError):
            capture.row_statistics(q, k[:, :32], v, 10)


if __name__ == "__main__":
    unittest.main()
