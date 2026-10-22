"""Small CPU checks for article isolation and the exact causal teacher contract."""
import importlib.util
from pathlib import Path
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
