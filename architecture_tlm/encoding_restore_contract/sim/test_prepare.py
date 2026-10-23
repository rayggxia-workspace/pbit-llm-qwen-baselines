"""Checks for staged RTL inputs; these do not claim RTL simulation."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("ready_valid_inputs", HERE / "validate_ready_valid.py")
RV = importlib.util.module_from_spec(spec)
spec.loader.exec_module(RV)


class PreparedInputsTests(unittest.TestCase):
    def test_previous_encoder_and_t32_vectors_preserved(self):
        prior = json.loads((HERE.parent / "results/rtl_2773/VALIDATION.json").read_text(encoding="utf-8"))
        for row in prior["results"]:
            with self.subTest(kind=row["kind"], seed=row["seed"]):
                actual = hashlib.sha256(RV.vector_text(row["kind"], row["seed"], 32).encode("ascii")).hexdigest()
                self.assertEqual(actual, row["vector_sha256"])

    def test_count_width_and_end_field_preserve_maximum(self):
        for samples, width in ((16, 11), (32, 12), (64, 13)):
            with self.subTest(samples=samples):
                rows = RV.vectors(2, 7, samples)
                self.assertEqual(len(rows), 96)
                for packed, _, _, _ in rows:
                    self.assertLess(packed, 1 << (64 * width))
                    for i in range(64):
                        self.assertLessEqual((packed >> (width * i)) & ((1 << width) - 1), 64 * samples)
                self.assertEqual(rows[1][0] >> (63 * width), 64 * samples)
                self.assertEqual(rows[1][0].bit_length(), 64 * width)

    def test_sign_extrema_and_literal_rounding_across_samples(self):
        for samples in (16, 32, 64):
            rows = RV.vectors(2, 7, samples)
            with self.subTest(samples=samples):
                self.assertEqual(rows[2][3], RV.AR.fbits(-8192.0))
                self.assertEqual(rows[3][3], RV.AR.fbits(8128.0))
                self.assertEqual(rows[4][3], RV.AR.fbits(8192.0))
                self.assertEqual(rows[5][3], RV.AR.fbits(-8128.0))
                self.assertEqual(rows[18][3], 0x00000003)

    def test_matrix_and_prepared_hashes(self):
        cases = RV.cases()
        self.assertEqual(len(cases), 15)
        self.assertEqual(len({c["top"] for c in cases}), 15)
        self.assertEqual({(c["samples"], c["count_width"]) for c in cases if c["kind"] == 2},
                         {(16, 11), (32, 12), (64, 13)})
        with tempfile.TemporaryDirectory(prefix="prepare_check_", dir=HERE) as directory:
            root = Path(directory).resolve()
            self.assertTrue(root.is_relative_to(HERE))
            prepared = RV.prepare_inputs(root, cases, [7])
            for item in prepared:
                self.assertEqual(RV.sha256(root / item["fixed_top"]["path"]), item["fixed_top"]["sha256"])
                for vector in item["vectors"]:
                    self.assertEqual(RV.sha256(root / vector["path"]), vector["sha256"])
            self.assertEqual(len(list(root.glob("*.hex"))), 5)
            self.assertEqual(len(list(root.glob("*.sv"))), 15)

    def test_invalid_geometry_rejected_before_generation(self):
        for sample in (0, 1, 24, 128):
            with self.assertRaises(ValueError):
                RV.vectors(2, 7, sample)
        for samples, depths in (((16, 16), (3,)), ((32,), (0,)), ((32,), (3, 3))):
            with self.assertRaises(ValueError):
                RV.cases(samples, depths)


if __name__ == "__main__":
    unittest.main()
