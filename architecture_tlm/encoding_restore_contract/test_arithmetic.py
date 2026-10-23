"""Numerical gates for explicit counter conventions and literal RTL restoration."""

import importlib.util
from pathlib import Path
import random
import struct
import unittest

from .arithmetic import (ArithmeticContractError, COUNT_REPRESENTATIONS,
                         accumulate_counts, add_words, encode, normalize_counts, restore_bins)


ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "historical_encoding_restore_scoreboard", ROOT / "architecture_tlm/digital_ppa_v1/sim/validate.py")
HISTORICAL = importlib.util.module_from_spec(spec)
spec.loader.exec_module(HISTORICAL)


def fp32_word(value):
    return struct.unpack("<I", struct.pack("<f", value))[0]


def fp32(value):
    return struct.unpack("<f", struct.pack("<f", value))[0]


def raw_counts():
    return [[[0] * 8 for _ in range(2)] for _ in range(4)]


class EncodingRestoreArithmeticTests(unittest.TestCase):
    def test_existing_finite_encoder_vectors_all_three_seeds(self):
        for kind, frac in ((4, 7), (5, 23)):
            for seed in (20261022, 7, 1234567):
                vectors, expected = HISTORICAL.vectors(kind, seed)
                actual = []
                for valid, _, _, data, *_ in vectors:
                    if valid:
                        words = [(data >> (i * (frac + 9))) & ((1 << (frac + 9)) - 1) for i in range(64)]
                        actual.append(encode(words, frac=frac)["packed"])
                self.assertEqual(actual, expected, (kind, seed))

    def test_existing_literal_restore_vectors_all_three_seeds(self):
        for seed in (20261022, 7, 1234567):
            vectors, expected = HISTORICAL.vectors(6, seed)
            actual = []
            for valid, _, _, data, _, scale, _, exp, _ in vectors:
                if not valid:
                    continue
                counts = [[[(data >> (((b * 2 + rail) * 8 + p) * 12)) & 4095 for p in range(8)]
                           for rail in range(2)] for b in range(4)]
                integers = normalize_counts(counts, representation="input_sign_twos_complement",
                                            count_width=12, samples=32)
                actual.append(restore_bins(integers, top_exp=exp - 65536 if exp & 32768 else exp,
                                           weight_scale_word=scale, samples=32))
            self.assertEqual(actual, expected, seed)

    def test_encoder_bin_boundary_true_one_and_rne_ties(self):
        # With top=1, the last-bin quantization grid is 1/16384. Halfway
        # values .5,1.5,2.5 grid steps round to the even codes 0,2,2.
        values = [1.0, .25, .0625, .015625, 1 / 32768, 3 / 32768, 5 / 32768] + [0.0] * 57
        for frac in (7, 23):
            words = [fp32_word(v) >> (16 if frac == 7 else 0) for v in values]
            result = encode(words, frac=frac)
            self.assertEqual(result["top_exp"], 0)
            self.assertEqual(result["bins"][:7], (0, 1, 2, 3, 3, 3, 3))
            self.assertEqual(result["q"][:7], (255, 255, 255, 255, 0, 2, 2))
            self.assertEqual(result["true_one"][:7], (1, 1, 1, 1, 0, 0, 0))

    def test_encoder_zero_subnormal_and_max_finite_without_host_float_limits(self):
        for frac, expected_min_exp in ((7, -133), (23, -149)):
            sign_mask = 1 << (frac + 8)
            zero = encode([sign_mask] + [0] * 63, frac=frac)
            self.assertEqual(zero["top_exp"], 0)
            self.assertEqual(zero["input_sign"][0], 1)
            self.assertEqual(zero["q"], (0,) * 64)
            self.assertEqual(zero["true_one"], (0,) * 64)
            self.assertEqual(zero["bins"], (3,) * 64)
            tiny = encode([1] + [0] * 63, frac=frac)
            self.assertEqual(tiny["top_exp"], expected_min_exp)
            self.assertEqual((tiny["bins"][0], tiny["q"][0], tiny["true_one"][0]), (0, 255, 1))
            largest = (254 << frac) | ((1 << frac) - 1)
            maximum = encode([largest, 1] + [0] * 62, frac=frac)
            self.assertEqual(maximum["top_exp"], 128)
            self.assertEqual(maximum["q"][0], 255)
            self.assertEqual(maximum["true_one"][0], 0)
            self.assertEqual(maximum["q"][1], 0)

    def test_encoder_rejects_nonfinite_shape_and_word_errors(self):
        for frac in (7, 23):
            for nonfinite in ((255 << frac), (255 << frac) | 1,
                              (1 << (frac + 8)) | (255 << frac)):
                with self.assertRaisesRegex(ArithmeticContractError, "finite encoder"):
                    encode([nonfinite] + [0] * 63, frac=frac)
        for values in ([0] * 63, [0] * 65, [False] * 64, [-1] + [0] * 63,
                       [65536] + [0] * 63, [0.0] * 64, "0" * 64):
            with self.subTest(values=str(values)[:60]), self.assertRaises(ArithmeticContractError):
                encode(values)
        with self.assertRaises(ArithmeticContractError):
            encode([0] * 64, frac=8)

    def test_all_256_weights_both_input_signs_and_sample_lengths(self):
        for t in (16, 32, 64):
            width = t.bit_length()
            for w in range(-128, 128):
                for sign in (0, 1):
                    expected = (-1 if sign else 1) * w * t
                    for representation in COUNT_REPRESENTATIONS:
                        # Force true-one while all raw sample bits are zero.
                        counts = accumulate_counts([w], [sign], [2], [[0]] * t,
                                                   representation=representation,
                                                   count_width=width, true_one=[1])
                        actual = normalize_counts(counts, representation=representation,
                                                  count_width=width, samples=t, inputs=1)
                        self.assertEqual(actual, (0, 0, expected, 0), (w, sign, t, representation))

    def test_real_encoded_shared_threshold_frame_matches_direct_dot(self):
        for seed in (7, 23, 20261023):
            rng = random.Random(seed)
            values = [((-1) ** i) * 2.0 ** (i % 9 - 8) * (1 + (i % 3) / 4) for i in range(64)]
            fields = encode([fp32_word(v) for v in values], frac=23)
            weights = [rng.randrange(-128, 128) for _ in range(64)]
            weights[0] = -128
            for t in (16, 32, 64):
                thresholds = [i * (256 // t) + rng.randrange(256 // t) for i in range(t)]
                frame = [[threshold < q for q in fields["q"]] for threshold in thresholds]
                width = (64 * t).bit_length()
                expected = [0] * 4
                # Independent dot order: count each lane's accepted bits first,
                # then contract fixed weights, signs and bins without bit planes.
                for i, w in enumerate(weights):
                    active = sum(bool(fields["true_one"][i]) or threshold < fields["q"][i]
                                 for threshold in thresholds)
                    expected[fields["bins"][i]] += (-1 if fields["input_sign"][i] else 1) * w * active
                for representation in COUNT_REPRESENTATIONS:
                    counts = accumulate_counts(weights, fields["input_sign"], fields["bins"], frame,
                                               representation=representation, count_width=width,
                                               true_one=fields["true_one"])
                    actual = normalize_counts(counts, representation=representation, count_width=width, samples=t)
                    self.assertEqual(actual, tuple(expected), (seed, t, representation))

    def test_count_label_is_semantic_not_an_alias_or_fabricated_bus(self):
        counts = raw_counts()
        counts[0][0][7] = 32
        twos = normalize_counts(counts, representation="input_sign_twos_complement", count_width=12, samples=32)
        magnitude = normalize_counts(counts, representation="product_sign_magnitude", count_width=12, samples=32)
        self.assertEqual(twos, (-4096, 0, 0, 0))
        self.assertEqual(magnitude, (4096, 0, 0, 0))
        for representation in (None, "bitplane", "magnitude", "", 0):
            with self.assertRaisesRegex(ArithmeticContractError, "explicit supported"):
                normalize_counts(counts, representation=representation, count_width=12, samples=32)
        with self.assertRaises(TypeError):
            normalize_counts(counts, count_width=12, samples=32)

    def test_t16_t32_t64_complete_positive_endpoint_widths(self):
        for t, count_width, signed_width in ((16, 11, 19), (32, 12, 20), (64, 13, 21)):
            counts = accumulate_counts([-128] * 64, [1] * 64, [0] * 64, [[1] * 64] * t,
                                       representation="input_sign_twos_complement", count_width=count_width)
            actual = normalize_counts(counts, representation="input_sign_twos_complement",
                                      count_width=count_width, samples=t, accumulator_width=signed_width)
            self.assertEqual(actual, (8192 * t, 0, 0, 0))
            self.assertEqual(restore_bins(actual, top_exp=0, weight_scale_word=0x3f800000,
                                          samples=t, accumulator_width=signed_width), fp32_word(8192.0))
            with self.assertRaisesRegex(ArithmeticContractError, "full-frame endpoint"):
                normalize_counts(counts, representation="input_sign_twos_complement",
                                 count_width=count_width - 1, samples=t)
            with self.assertRaisesRegex(ArithmeticContractError, "positive W=-128"):
                normalize_counts(counts, representation="input_sign_twos_complement", count_width=count_width,
                                 samples=t, accumulator_width=signed_width - 1)

    def test_counter_rejects_shape_type_range_and_width_errors(self):
        for counts in (raw_counts()[:3], [raw_counts()], [0] * 64,
                       [[[0] * 7 for _ in range(2)] for _ in range(4)]):
            with self.assertRaises(ArithmeticContractError):
                normalize_counts(counts, representation=COUNT_REPRESENTATIONS[0], count_width=12, samples=32)
        for value in (-1, 2049, 4096, 1.0, True):
            counts = raw_counts()
            counts[2][1][4] = value
            with self.subTest(value=value), self.assertRaises(ArithmeticContractError):
                normalize_counts(counts, representation=COUNT_REPRESENTATIONS[0], count_width=12, samples=32)
        for width in (0, 11, 12.0, True):
            with self.subTest(width=width), self.assertRaises(ArithmeticContractError):
                normalize_counts(raw_counts(), representation=COUNT_REPRESENTATIONS[0], count_width=width, samples=32)

    def test_sample_frame_rejects_bad_w8_metadata_and_coverage(self):
        base = dict(weights=[-128], input_sign=[1], bins=[0], sample_bits=[[1]] * 32,
                    representation=COUNT_REPRESENTATIONS[0], count_width=6)
        for change in (dict(weights=[-129]), dict(weights=[128]), dict(weights=[True]),
                       dict(input_sign=[-1]), dict(input_sign=[]), dict(bins=[4]),
                       dict(sample_bits=[[1]] * 31), dict(sample_bits=[[1, 1]] * 32),
                       dict(sample_bits=[[2]] * 32), dict(true_one=[2]), dict(count_width=5)):
            with self.subTest(change=change), self.assertRaises(ArithmeticContractError):
                accumulate_counts(**(base | change))

    def test_restore_subnormal_ties_scale_and_literal_rounding_difference(self):
        # First conversion: 3*2^-150 -> 2 min-subnormal units (ties-even).
        # Multiplying by 1.5 then gives 3 units. Moving /T to the later multiply
        # as cycle_v1's historical host-float expression does gives 2 units.
        result = restore_bins((3, 0, 0, 0), top_exp=-145, weight_scale_word=0x3fc00000, samples=32)
        legacy_expression = fp32(fp32(3 * 2.0**-145) * 1.5 / 32)
        self.assertEqual(result, 3)
        self.assertEqual(fp32_word(legacy_expression), 2)
        self.assertEqual(restore_bins((1, 0, 0, 0), top_exp=-145,
                                      weight_scale_word=0x3f800000, samples=32), 0)
        self.assertEqual(restore_bins((32, 0, 0, 0), top_exp=0,
                                      weight_scale_word=1, samples=32), 1)

    def test_restore_overflow_nan_and_infinity_follow_each_original_operation(self):
        cases = [((32, 0, 0, 0), 128, 0x3f800000, 0x7f800000),
                 ((-32, 0, 0, 0), 128, 0x3f800000, 0xff800000),
                 ((32, -128, 0, 0), 128, 0x3f800000, 0x7fc00000),
                 ((32, 0, 0, 0), 0, 0x7fa12345, 0x7fc00000),
                 ((32, 0, 0, 0), 0, 0x7f800000, 0x7fc00000),
                 ((32, 0, 0, 0), 128, 0, 0x7fc00000),
                 ((32, 0, 0, 0), 0, 0xc0000000, 0xc0000000)]
        for bins, exponent, scale, expected in cases:
            with self.subTest(bins=bins, exponent=exponent, scale=hex(scale)):
                self.assertEqual(restore_bins(bins, top_exp=exponent, weight_scale_word=scale, samples=32), expected)

    def test_restore_rejects_unqualified_exponents_and_malformed_state(self):
        base = dict(bin_sums=(0, 0, 0, 0), top_exp=0, weight_scale_word=0x3f800000, samples=32)
        for change in (dict(bin_sums=(0, 0, 0)), dict(bin_sums=(0.0, 0, 0, 0)),
                       dict(bin_sums=(524288, 0, 0, 0)), dict(top_exp=-150),
                       dict(top_exp=129), dict(top_exp=0.0), dict(weight_scale_word=-1),
                       dict(weight_scale_word=1 << 32), dict(weight_scale_word=1.0),
                       dict(samples=8), dict(samples=32.0), dict(inputs=0),
                       dict(inputs=65), dict(accumulator_width=19)):
            with self.subTest(change=change), self.assertRaises(ArithmeticContractError):
                restore_bins(**(base | change))

    def test_separate_cross_block_addition_rne_specials_and_word_validation(self):
        self.assertEqual(add_words(0x3f800000, 0x33800000), 0x3f800000)
        self.assertEqual(add_words(0x3f800001, 0x33800000), 0x3f800002)
        self.assertEqual(add_words(0x3f800000, 0xbf800000), 0)
        self.assertEqual(add_words(0x80000000, 0x80000000), 0x80000000)
        self.assertEqual(add_words(0x7f800000, 0xff800000), 0x7fc00000)
        for invalid in (-1, 1 << 32, 1.0, True):
            with self.assertRaises(ArithmeticContractError):
                add_words(invalid, 0)
            with self.assertRaises(ArithmeticContractError):
                add_words(0, invalid)


if __name__ == "__main__":
    unittest.main()
