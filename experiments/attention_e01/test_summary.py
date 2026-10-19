"""Small independent reporting fixtures; no NumPy, model or scientific run."""
import csv
import importlib.util
import json
import math
from pathlib import Path
import tempfile
import unittest


SPEC = importlib.util.spec_from_file_location("attention_e01_summary", Path(__file__).with_name("summarize.py"))
summary = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(summary)


CONFIG = {"candidate_counts": [64], "sample_counts": [32], "seeds": [0, 1, 2], "real_row_indices": [0]}


def ising_record(seed):
    # With one M/S and three profiles the 12 deterministic cases precede
    # samplers; uniform Ising seeds 0/1/2 have case IDs 14/17/20.
    return {"case_id": f"full_{14 + seed * 3:05d}", "profile": "uniform", "M": 64, "S": 32,
            "seed": seed, "backend": "serial_random_scan_ising", "status": "ok",
            "correctness_invariants_passed": True,
            "contracts": {"full_probability": {"tv": .5 + .1 * seed},
                          "category_indices": {"unique_V_rows": 10 + 2 * seed},
                          "final_v": {"nmse": (seed + 1) ** 2, "relative_l2_error": seed + 1}},
            "sampler": {"attempted_updates": 9072, "state_flips": 100 + 20 * seed},
            "backend_cpu_software_seconds": .01 * (seed + 1),
            "input": {"source_row": 0, "source_row_metadata": {"layer": 0, "head": 0}}}


def write_phase(root, records, phase="full", terminal=True, passed=False):
    directory = Path(root) / phase
    directory.mkdir(parents=True)
    context = {"schema": summary.SCHEMA, "phase": phase, "config": CONFIG,
               "context_sha256": "context_fixture", "git_commit": "fixture_only"}
    (directory / "run_context.json").write_text(json.dumps(context), encoding="utf-8")
    (directory / "cases.jsonl").write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")
    if terminal:
        (directory / "summary.json").write_text(json.dumps({"context_sha256": "context_fixture", "planned_cases": 39 if phase == "full" else 12,
            "recorded_cases": len(records), "completed_cases": sum(row["status"] == "ok" for row in records), "gate_passed": passed,
            "journal_sha256": summary.digest(directory / "cases.jsonl")}), encoding="utf-8")


def find_ising(report):
    return next(group for group in report["groups"] if group["profile"] == "uniform" and group["backend"] == "serial_random_scan_ising")


class SummaryTests(unittest.TestCase):
    def test_three_seed_mean_and_sample_std_from_independent_values(self):
        rows = [ising_record(seed) for seed in (0, 1, 2)]
        result = summary.aggregate_records(rows, summary.expected_cases(CONFIG, "full"))
        group = find_ising(result)
        self.assertEqual(group["status"], "complete")
        self.assertEqual(group["valid_seeds"], [0, 1, 2])
        self.assertAlmostEqual(group["statistics"]["tv_half_l1"]["mean"], .6)
        self.assertAlmostEqual(group["statistics"]["tv_half_l1"]["std_ddof1"], .1)
        self.assertAlmostEqual(group["statistics"]["nmse"]["mean"], 14 / 3)
        self.assertAlmostEqual(group["statistics"]["nmse"]["std_ddof1"], math.sqrt(49 / 3))
        self.assertEqual(group["statistics"]["relative_l2_error"]["mean"], 2)
        self.assertEqual(group["statistics"]["unique_V_rows"]["mean"], 12)
        self.assertEqual(group["statistics"]["state_flips"]["std_ddof1"], 20)
        self.assertEqual(result["status"], "partial")  # Other matrix rows absent.

    def test_failed_row_excluded_but_reported_with_missing_valid_seed(self):
        rows = [ising_record(seed) for seed in (0, 1, 2)]
        rows[1]["status"] = "timed_out"
        rows[1]["correctness_invariants_passed"] = False
        rows[1]["contracts"]["final_v"]["nmse"] = 1e20  # Must never enter mean.
        result = summary.aggregate_records(rows, summary.expected_cases(CONFIG, "full"))
        group = find_ising(result)
        self.assertEqual(group["status"], "failed")
        self.assertEqual(group["missing_valid_seeds"], [1])
        self.assertEqual(group["statistics"]["nmse"]["mean"], 5)
        self.assertEqual(result["failed_records"], 1)
        self.assertEqual(result["failures"][0]["status"], "timed_out")

    def test_missing_seed_and_duplicate_seed_are_not_complete(self):
        expected = summary.expected_cases(CONFIG, "full")
        result = summary.aggregate_records([ising_record(0), ising_record(2)], expected)
        group = find_ising(result)
        self.assertEqual(group["status"], "partial")
        self.assertEqual(group["missing_valid_seeds"], [1])
        duplicate = summary.aggregate_records([ising_record(0), ising_record(0), ising_record(2)], expected)
        self.assertEqual(find_ising(duplicate)["valid_seeds"], [2])
        self.assertEqual(duplicate["failed_records"], 2)

    def test_numeric_no_S_record_has_no_artificial_seed_std(self):
        row = {"case_id": "full_00000", "profile": "uniform", "M": 64, "backend": "stable_fp32", "status": "ok",
               "correctness_invariants_passed": True,
               "contracts": {"full_probability": {"tv": 1e-8}, "final_v": {"nmse": 1e-12, "relative_l2_error": 1e-6}}}
        result = summary.aggregate_records([row], summary.expected_cases(CONFIG, "full"))
        group = next(group for group in result["groups"] if group["backend"] == "stable_fp32" and group["profile"] == "uniform")
        self.assertIsNone(group["S"])
        self.assertEqual(group["valid_seeds"], [])
        self.assertIsNone(group["statistics"]["nmse"]["std_ddof1"])

    def test_paired_differences_require_all_three_complete_seed_sets(self):
        groups = []
        for backend, values in (("digital_iid_inverse_cdf", [1., 3., 5.]),
                                ("digital_systematic_single_phase", [.5, 1., 1.5]),
                                ("serial_random_scan_ising", [2., 4., 6.])):
            groups.append({"profile": "real:0", "M": 64, "S": 32, "backend": backend,
                           "status": "complete", "valid_seeds": [0, 1, 2],
                           "statistics": {"nmse": summary.sample_statistics(values), "relative_l2_error": summary.sample_statistics([1, 2, 3])},
                           "valid_seed_nmse": {str(seed): value for seed, value in enumerate(values)}})
        result = summary.same_s_comparisons(groups)[0]
        self.assertTrue(result["complete_three_backend_seed_sets"])
        self.assertEqual(result["paired_nmse_ising_minus_iid"]["mean"], 1)
        self.assertEqual(result["paired_nmse_ising_minus_iid"]["std_ddof1"], 0)
        groups[0]["valid_seeds"] = [0, 2]
        groups[0]["status"] = "partial"
        incomplete = summary.same_s_comparisons(groups)[0]
        self.assertFalse(incomplete["complete_three_backend_seed_sets"])
        self.assertIsNone(incomplete["paired_nmse_ising_minus_iid"])

    def test_actual_journal_output_hashes_and_input_preservation(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temporary:
            base = Path(temporary)
            write_phase(base / "run", [ising_record(0), ising_record(1), ising_record(2)])
            original = {path: summary.digest(path) for path in (base / "run/full").iterdir()}
            report = summary.write_report(base / "run", base / "report")
            self.assertEqual(report["status"], "partial")
            self.assertEqual(report["phases"]["full"]["expected_cases"], 39)
            self.assertEqual(report["phases"]["full"]["observed_records"], 3)
            self.assertEqual(original, {path: summary.digest(path) for path in original})
            with (base / "report/aggregate.csv").open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            group = next(row for row in rows if row["backend"] == "serial_random_scan_ising" and row["profile"] == "uniform")
            self.assertAlmostEqual(float(group["nmse_mean"]), 14 / 3)
            self.assertIn("CPU 软件", (base / "report/RESULTS_ZH.md").read_text(encoding="utf-8"))
            self.assertTrue((base / "report/REPORT.json").is_file())
            with self.assertRaisesRegex(ValueError, "new directory"):
                summary.write_report(base / "run", base / "report")
            with self.assertRaisesRegex(ValueError, "outside raw phase"):
                summary.write_report(base / "run", base / "run/full/report")

    def test_truncated_journal_and_missing_terminal_summary_are_explicit(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temporary:
            base = Path(temporary)
            write_phase(base, [ising_record(0)], terminal=False)
            with (base / "full/cases.jsonl").open("a", encoding="utf-8") as handle:
                handle.write('{"case_id": "interrupted"')
            phase = summary.read_phase(base, "full")
            self.assertEqual(phase["status"], "failed")
            self.assertEqual(len(phase["malformed_lines"]), 1)
            self.assertIn("missing_terminal_summary", phase["integrity_issues"])
            self.assertEqual(phase["valid_records"], 1)

    def test_default_matrix_count_is_465_not_planning_623(self):
        self.assertEqual(len(summary.expected_cases({}, "full")), 465)
        self.assertEqual(len(summary.expected_cases({}, "pilot")), 12)

    def test_complete_matrix_and_terminal_hash_mismatch(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temporary:
            base = Path(temporary)
            for phase in ("pilot", "full"):
                records = []
                for case_id, wanted in summary.expected_cases(CONFIG, phase).items():
                    record = {**wanted, "case_id": case_id, "status": "ok", "correctness_invariants_passed": True,
                              "contracts": {"full_probability": {"tv": 0}, "category_indices": {"unique_V_rows": 1},
                                            "final_v": {"nmse": 0, "relative_l2_error": 0}},
                              "sampler": {"attempted_updates": 100, "state_flips": 10}}
                    records.append(record)
                write_phase(base, records, phase, passed=True)
            report = summary.collect_report(base)
            self.assertEqual(report["status"], "complete")
            self.assertEqual(report["phases"]["full"]["valid_records"], 39)
            with (base / "full/cases.jsonl").open("a", encoding="utf-8") as handle:
                handle.write("\n")  # Valid JSONL whitespace, but changed immutable bytes.
            changed = summary.collect_report(base)
            self.assertEqual(changed["status"], "failed")
            self.assertIn("summary_journal_sha256_mismatch", changed["phases"]["full"]["integrity_issues"])


if __name__ == "__main__":
    unittest.main()
