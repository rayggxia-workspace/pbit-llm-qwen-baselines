"""Small deterministic/statistical correctness tests; no model/benchmark run."""
import importlib.util
import json
import math
from pathlib import Path
import random
import tempfile
import unittest
from unittest import mock

import numpy as np

SPEC = importlib.util.spec_from_file_location("attention_e01_microbench", Path(__file__).with_name("microbench.py"))
mb = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mb)


def explicit_serial(logits, samples, burn, spacing, seed):
    """Independent, deliberately uncompressed microstep heat-bath oracle."""
    rng = random.Random(seed)
    reference = int(np.argmax(logits))
    sites = [i for i in range(len(logits)) if i != reference]
    state = reference
    output = []
    for step in range(len(sites) * (burn + spacing * samples)):
        site = rng.choice(sites)
        if state in (reference, site):
            probability = 1 / (1 + math.exp(logits[reference] - logits[site]))
            state = site if rng.random() < probability else reference
        if step + 1 > len(sites) * burn and (step + 1 - len(sites) * burn) % (len(sites) * spacing) == 0:
            output.append(state)
    return np.asarray(output)


class KernelTests(unittest.TestCase):
    def test_stable_reference_shift_and_extreme(self):
        logits = np.array([-1000., 0., 1., 5.])
        expected = np.exp(logits - 5) / np.exp(logits - 5).sum()
        np.testing.assert_allclose(mb.stable_probability(logits), expected, rtol=1e-14)
        np.testing.assert_allclose(mb.stable_probability(logits + 1e5), expected, rtol=1e-14)
        self.assertTrue(np.isfinite(mb.stable_probability([1e30, -1e30], np.float32)).all())

    def test_online_rescaling_matches_dense_with_late_maximum(self):
        rng = np.random.default_rng(12)
        logits = rng.normal(size=67).astype(np.float32)
        logits[-1] = 20
        values = rng.normal(size=(67, 9)).astype(np.float32)
        expected = mb.stable_probability(logits) @ values.astype(np.float64)
        for tile in (1, 8, 16, 64, 100):
            np.testing.assert_allclose(mb.online_tiled_pv(logits, values, tile), expected, rtol=2e-6, atol=2e-6)

    def test_exp2_log2e_conversion_and_fractional_approximation(self):
        logits = np.array([-20., -4.3, -1.75, -0.2, 0], dtype=np.float32)
        actual = mb.exp2_pwl_probability(logits, 64)
        expected = np.exp(logits.astype(np.float64))
        expected /= expected.sum()
        np.testing.assert_allclose(actual, expected, rtol=1e-4, atol=1e-7)
        # Missing log2(e) would yield this clearly different temperature.
        incorrect = 2. ** logits
        incorrect /= incorrect.sum()
        self.assertGreater(np.max(np.abs(actual - incorrect)), .02)
        self.assertLess(mb.probability_metrics(actual, expected)["abs_row_sum_minus_one"], 1e-6)

    def test_bf16_ties_even_negative_and_special_values(self):
        bits = np.array([0x3F808000, 0x3F818000, 0xBF808000, 0xBF818000,
                         0x00000000, 0x80000000, 0x7F800000, 0xFF800000, 0x7FC12345], dtype=np.uint32)
        expected_bits = np.array([0x3F800000, 0x3F820000, 0xBF800000, 0xBF820000,
                                  0x00000000, 0x80000000, 0x7F800000, 0xFF800000, 0x7FC12345], dtype=np.uint32)
        np.testing.assert_array_equal(mb.bf16_rne(bits.view(np.float32)).view(np.uint32), expected_bits)

    def test_systematic_count_constraints_and_one_phase(self):
        probability = np.array([.01, .23, .1, .66])
        indices, description = mb.sample_indices(probability, 37, 6, "digital_systematic_single_phase")
        counts = np.bincount(indices, minlength=4)
        target = probability * 37
        self.assertTrue(np.all((counts == np.floor(target)) | (counts == np.ceil(target))))
        self.assertTrue(np.all(np.diff(indices) >= 0))
        self.assertEqual(description["random_uniform_words"], 1)
        self.assertFalse(description["iid"])

    def test_indices_counts_matching_v_prefix_and_range_rejection(self):
        indices = np.array([3, 0, 3, 1, 3, 1])
        values = np.array([[1, 10], [2, 20], [3, 30], [4, 40]], dtype=np.float32)
        counts, result = mb.indices_to_pv(indices, values)
        np.testing.assert_array_equal(counts, [1, 2, 0, 3])
        np.testing.assert_allclose(result, values[indices].mean(axis=0), atol=1e-6)
        with self.assertRaises(ValueError):
            mb.indices_to_pv(np.array([4]), values)

    def test_compressed_serial_stationary_matches_explicit_microsteps(self):
        # Each chain has 30k samples; spacing 3 sweeps makes statistical error
        # much smaller than the tolerance. Different RNG consumption means
        # pathwise equality is neither expected nor asserted.
        logits = np.array([-.7, .4, 1.2, -.1])
        target = mb.stable_probability(logits)
        compressed, counters = mb.sample_indices(target, 30000, 11, "serial_random_scan_ising", logits, burn=100, spacing=3)
        explicit = explicit_serial(logits, 30000, 100, 3, 21)
        actual_a = np.bincount(compressed, minlength=4) / len(compressed)
        actual_b = np.bincount(explicit, minlength=4) / len(explicit)
        self.assertLess(np.max(np.abs(actual_a - target)), .015)
        self.assertLess(np.max(np.abs(actual_b - target)), .015)
        self.assertLess(np.max(np.abs(actual_a - actual_b)), .02)
        self.assertEqual(counters["attempted_updates"], 3 * (100 + 3 * 30000))
        self.assertLess(counters["state_flips"], counters["attempted_updates"])
        self.assertFalse(counters["iid"])
        self.assertFalse(counters["physical_device_model"])

    def test_short_horizon_is_not_iid_or_stationarity_claim(self):
        trace = {"logits": np.zeros((1, 8), dtype=np.float32), "values": np.arange(16, dtype=np.float32).reshape(1, 8, 2),
                 "metadata": [{"layer": 0, "head": 0}], "lengths": [8], "provenance": {"kind": "test_fixture"}}
        config = mb.normalize_config({"candidate_counts": [8], "sample_counts": [2], "real_row_indices": [0]})
        case = {"case_id": "test", "M": 8, "S": 2, "seed": 1, "profile": "uniform", "backend": "serial_random_scan_ising"}
        record, arrays = mb.evaluate_case(case, trace, config)
        self.assertFalse(record["sampler"]["iid"])
        self.assertFalse(record["stationarity_proven"])
        self.assertEqual(record["ess"]["category_indicator"]["status"], "insufficient_samples")
        self.assertGreaterEqual(record["contracts"]["full_probability"]["tv"], .75 - 1e-12)
        self.assertEqual(arrays["indices"].shape, (2,))

    def test_trace_metadata_shapes_and_prefix_integrity(self):
        logits = np.arange(24, dtype=np.float32).reshape(3, 8)
        values = np.arange(48, dtype=np.float32).reshape(3, 8, 2)
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temporary:
            path = Path(temporary) / "trace.npz"
            for metadata in (np.array([json.dumps({"layer": i}) for i in range(3)]),
                             np.array(json.dumps([{"layer": i} for i in range(3)]))):
                np.savez(path, logits=logits, values=values, row_metadata=metadata)
                trace = mb.load_trace(path)
                actual_x, actual_v, descriptor = mb.profile_inputs(trace, "real:2", 4, [0, 1, 2])
                np.testing.assert_array_equal(actual_x, logits[2, :4])
                np.testing.assert_array_equal(actual_v, values[2, :4])
                self.assertEqual(descriptor["source_row_metadata"], {"layer": 2})
                self.assertFalse(descriptor["representative_of_full_model"])
            with self.assertRaises(ValueError):
                mb.load_trace(None)

    def test_ess_observable_and_correlated_chain(self):
        rng = np.random.default_rng(6)
        iid = rng.normal(size=4096)
        correlated = np.zeros(4096)
        for i in range(1, len(correlated)):
            correlated[i] = .95 * correlated[i - 1] + iid[i]
        independent = mb.effective_sample_size(iid)
        dependent = mb.effective_sample_size(correlated)
        self.assertGreater(independent["ess"], 2500)
        self.assertLess(dependent["ess"], 500)
        self.assertEqual(mb.effective_sample_size(np.ones(4096))["status"], "unresolved_constant_observable")

    def test_matrix_is_explicit_and_pilot_is_twelve(self):
        config = mb.normalize_config({})
        pilot = mb.build_cases(config, "pilot")
        full = mb.build_cases(config, "full")
        self.assertEqual(len(pilot), 12)
        self.assertEqual(len(full), 5 * 3 * 4 + 5 * 3 * 3 * 3 * 3)
        self.assertEqual(set(case["backend"] for case in pilot), set(mb.NUMERICAL + mb.SAMPLERS))
        self.assertEqual({case["M"] for case in pilot}, {64, 512, 2048})
        self.assertNotIn("ideal_native_event", {case["backend"] for case in full})
        with self.assertRaises(ValueError):
            mb.normalize_config({"sample_counts": [1000000]})

    def test_timeout_is_persisted_and_blocks_full_without_overwrite(self):
        # A scheduler-independent journal/gate failure test. No numerical run
        # is executed: fake worker replies exercise persistence and recovery.
        class Reply:
            def get(self, timeout):
                raise mb.mp.TimeoutError()

        class Pool:
            def apply_async(self, function, args):
                return Reply()

            def terminate(self):
                pass

            def close(self):
                pass

            def join(self):
                pass

        class Context:
            def Pool(self, *args, **kwargs):
                return Pool()

        config = mb.normalize_config({"candidate_counts": [8], "sample_counts": [2], "real_row_indices": [0]})
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temporary:
            base = Path(temporary)
            trace = base / "trace.npz"
            np.savez(trace, logits=np.zeros((1, 8), dtype=np.float32), values=np.zeros((1, 8, 2), dtype=np.float32))
            with mock.patch.object(mb.mp, "get_context", return_value=Context()), mock.patch("builtins.print"):
                summary = mb.run(str(trace), str(base / "out"), "pilot", config)
            self.assertFalse(summary["gate_passed"])
            self.assertEqual(summary["timed_out_cases"], 12)
            journal = (base / "out/pilot/cases.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(journal), 12)
            self.assertTrue(all(json.loads(line)["status"] == "timed_out" for line in journal))
            with self.assertRaisesRegex(ValueError, "passing 12-case pilot"):
                mb.run(str(trace), str(base / "out"), "full", config)
            with self.assertRaisesRegex(ValueError, "refusing to overwrite"):
                mb.run(str(trace), str(base / "out"), "pilot", config)

    def test_pilot_gate_binds_both_source_files_and_driver_manifest(self):
        # Fake successful worker replies isolate gate behavior. The pilot
        # exercises no scientific numerical workload in this regression test.
        class Reply:
            def get(self, timeout):
                return {"status": "ok", "correctness_invariants_passed": True}, {"v_output": np.zeros(2)}

        class Pool:
            def apply_async(self, function, args):
                return Reply()

            def close(self):
                pass

            def join(self):
                pass

        class Context:
            def Pool(self, *args, **kwargs):
                return Pool()

        config = mb.normalize_config({"candidate_counts": [8], "sample_counts": [2], "real_row_indices": [0]})
        original_hash = mb.sha256
        manifest_digest = "a" * 64
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temporary:
            base = Path(temporary)
            trace = base / "trace.npz"
            np.savez(trace, logits=np.zeros((1, 8), dtype=np.float32), values=np.zeros((1, 8, 2), dtype=np.float32))
            with mock.patch.object(mb.mp, "get_context", return_value=Context()), mock.patch("builtins.print"):
                summary = mb.run(str(trace), str(base / "out"), "pilot", config, source_manifest_sha256=manifest_digest)
            self.assertTrue(summary["gate_passed"])
            context = json.loads((base / "out/pilot/run_context.json").read_text(encoding="utf-8"))
            self.assertEqual(context["execution_sources"]["microbench.py"], original_hash(mb.__file__))
            self.assertEqual(context["execution_sources"]["architecture_tlm/attention_reference_v3.py"],
                             original_hash(mb.REPO_ROOT / "architecture_tlm/attention_reference_v3.py"))
            self.assertEqual(context["execution_sources"]["source_manifest_sha256"], manifest_digest)
            for changed_path in (Path(mb.__file__), mb.REPO_ROOT / "architecture_tlm/attention_reference_v3.py"):
                def changed_hash(path):
                    return "b" * 64 if Path(path).resolve() == changed_path.resolve() else original_hash(path)
                with self.subTest(changed_source=changed_path.name), mock.patch.object(mb, "sha256", side_effect=changed_hash):
                    with self.assertRaisesRegex(ValueError, "passing 12-case pilot"):
                        mb.run(str(trace), str(base / "out"), "full", config, source_manifest_sha256=manifest_digest)
            with self.assertRaisesRegex(ValueError, "passing 12-case pilot"):
                mb.run(str(trace), str(base / "out"), "full", config, source_manifest_sha256="c" * 64)
            with self.assertRaisesRegex(ValueError, "64-character hexadecimal"):
                mb.execution_source_identity("invalid")


if __name__ == "__main__":
    unittest.main()
