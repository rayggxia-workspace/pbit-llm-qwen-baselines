"""Adversarial tests for per-bin integer equivalence, with no physical claims."""

import importlib.util
from pathlib import Path
import unittest


# Explicit sibling loading permits safe-path (-P) execution after relocation.
_spec = importlib.util.spec_from_file_location("ffn_counter_diagnostic", Path(__file__).with_name("counter.py"))
counter = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(counter)


class CounterTests(unittest.TestCase):
    def assert_equal(self, weights, signs, bins, samples, ones=None, expected=None):
        a = counter.accumulate_a(weights, signs, bins, samples, ones)
        b = counter.accumulate_b(weights, signs, bins, samples, ones)
        self.assertEqual(a, b)
        self.assertEqual(a, counter.dot_reference(weights, signs, bins, samples, ones))
        if expected is not None:
            self.assertEqual(a, expected)

    def test_every_w8_code_and_both_input_signs(self):
        for weight in range(-128, 128):
            for sign in (0, 1):
                with self.subTest(weight=weight, sign=sign):
                    self.assert_equal([[weight]], [sign], [2], [[1]],
                                      expected=((0, 0, weight * (1 - 2 * sign), 0),))

    def test_distinct_bin_identity_and_input_permutation(self):
        weights = [[-128, -1, 64, 127], [1, 2, -3, -4]]
        signs, bins = [1, 0, 1, 0], [0, 1, 2, 3]
        samples, ones = [[1, 1, 1, 0], [0, 1, 0, 1]], [0, 0, 1, 0]
        expected = ((128, -2, -128, 127), (1 * -1, 4, 6, -4))
        self.assert_equal(weights, signs, bins, samples, ones, expected)
        order = [2, 0, 3, 1]
        self.assert_equal([[row[i] for i in order] for row in weights],
                          [signs[i] for i in order], [bins[i] for i in order],
                          [[row[i] for i in order] for row in samples],
                          [ones[i] for i in order], expected)

    def test_true_one_positive_128_and_sample_sum_boundary(self):
        self.assert_equal([[-128] * 64], [1] * 64, [0] * 64, [[0] * 64], [1] * 64,
                          ((8192, 0, 0, 0),))
        self.assertEqual(counter.required_widths(64, 32)["sample_sum_bits"], 15)
        with self.assertRaises(OverflowError):
            counter.accumulate_b([[-128] * 64], [1] * 64, [0] * 64,
                                 [[1] * 64], sum_bits=14)

    def test_exact_extrema_and_storage_widths_all_t(self):
        for t, count_bits, sum_bits in ((16, 11, 19), (32, 12, 20), (64, 13, 21)):
            with self.subTest(t=t):
                widths = counter.required_widths(64, t)
                self.assertEqual(widths["count_bits"], count_bits)
                self.assertEqual(widths["sum_bits"], sum_bits)
                sample = [[1] * 64 for _ in range(t)]
                for sign in (0, 1):
                    self.assert_equal([[-128] * 64], [sign] * 64, [3] * 64, sample,
                                      expected=((0, 0, 0, -128 * 64 * t * (1 - 2 * sign)),))
                with self.assertRaises(OverflowError):
                    counter.accumulate_a([[-128] * 64], [0] * 64, [0] * 64,
                                         sample, count_bits=count_bits - 1)
                with self.assertRaises(OverflowError):
                    counter.accumulate_b([[-128] * 64], [1] * 64, [0] * 64,
                                         sample, sum_bits=sum_bits - 1)
        widths = counter.required_widths(64, 32)
        self.assertEqual(widths["a_counter_state_bits"], 49152)
        self.assertEqual(widths["b_accumulator_state_bits"], 5120)

    def test_insufficient_width_rejected_even_if_final_result_cancels(self):
        # +128 precedes -128 on successive samples: final zero cannot mask overflow.
        with self.assertRaises(OverflowError):
            counter.accumulate_b([[-128, -128]], [1, 0], [0, 0], [[1, 0], [0, 1]], sum_bits=8)
        self.assert_equal([[-128, -128]], [1, 0], [0, 0], [[1, 0], [0, 1]],
                          expected=((0, 0, 0, 0),))

    def test_frame_concatenation_without_reset_is_additive(self):
        weights, signs, bins = [[-128, 37, -5]], [1, 0, 1], [0, 2, 2]
        left, right = [[1, 0, 1], [0, 1, 0]], [[1, 1, 0]]
        for implementation in (counter.accumulate_a, counter.accumulate_b):
            first = implementation(weights, signs, bins, left)
            second = implementation(weights, signs, bins, right)
            whole = implementation(weights, signs, bins, left + right)
            self.assertEqual(whole, tuple(tuple(x + y for x, y in zip(a, b))
                                          for a, b in zip(first, second)))

    def test_zero_bits_and_fresh_frame_have_no_residual_state(self):
        self.assert_equal([[-128]], [1], [0], [[1]], expected=((128, 0, 0, 0),))
        self.assert_equal([[-128]], [1], [0], [[0]], expected=((0, 0, 0, 0),))

    def test_invalid_shapes_domains_and_widths_rejected(self):
        invalid = [([[128]], [0], [0], [[1]], None),
                   ([[-129]], [0], [0], [[1]], None),
                   ([[1]], [2], [0], [[1]], None),
                   ([[1]], [0], [4], [[1]], None),
                   ([[1]], [0], [0], [[2]], None),
                   ([[1]], [0], [0], [[1]], [2]),
                   ([[1, 2]], [0], [0], [[1]], None),
                   ([[1]], [0], [0], [], None),
                   ([[1]], [0], [], [[1]], None)]
        for implementation in (counter.accumulate_a, counter.accumulate_b, counter.dot_reference):
            for args in invalid:
                with self.subTest(implementation=implementation.__name__, args=args):
                    with self.assertRaises(ValueError):
                        implementation(*args)
        for width in (0, -1, 1.5, True):
            with self.assertRaises(ValueError):
                counter.accumulate_a([[1]], [0], [0], [[1]], count_bits=width)
            with self.assertRaises(ValueError):
                counter.accumulate_b([[1]], [0], [0], [[1]], sum_bits=width)

    def test_fixed_seed_diagnostic(self):
        result = counter.diagnose()
        self.assertTrue(result["passed"])
        self.assertEqual(result["seed"], 20261023)
        self.assertEqual(result["case_count"], 66)
        self.assertEqual(result["bin_outputs_checked"], 888)


if __name__ == "__main__":
    unittest.main(verbosity=2)
