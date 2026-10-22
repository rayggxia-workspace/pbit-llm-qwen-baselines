"""Small independent integer/temporal checks; no full projection timing runs."""

import copy
import os
from pathlib import Path
import unittest

from .dependencies import load
from .fixtures import (REPRESENTATION, acceptance_counts, build_fixture,
                       count_packet, digest, scale_word, temporal_direct_bins,
                       w8_dot, w8_partial, word)


class FixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cache = os.environ.get('FFN_DATAFLOW_DEPS')
        if not cache:
            raise RuntimeError('set FFN_DATAFLOW_DEPS to the verified dependency cache')
        cls.restore = load(Path(cache)).restore

    def tiny(self, **kwargs):
        values = dict(seed=0, groups=1, tiles=1, rows_per_tile=2, samples=32)
        values.update(kwargs)
        return build_fixture(self.restore, **values)

    def encoded(self, *, sign=0, q=0, true_one=0):
        return dict(q=[q] * 64, bins=[0] * 64,
                    input_sign=[sign] * 64, true_one=[true_one] * 64, top_exp=0)

    def test_three_seeds_reproduce_and_keep_stratified_shared_inputs(self):
        hashes = []
        for seed in (0, 1, 2):
            a, b = self.tiny(seed=seed), self.tiny(seed=seed)
            self.assertEqual(a, b)
            hashes.append(a['hashes']['inputs'])
            self.assertEqual(a['rows'], 2)
            self.assertEqual(a['representation'], REPRESENTATION)
            thresholds = a['inputs'][0]['thresholds']
            self.assertEqual([t // 8 for t in thresholds], list(range(32)))
            for packet in a['packets'][0]:
                self.assertEqual(packet['top_exp'], a['inputs'][0]['encoded']['top_exp'])
                self.assertEqual(packet['weight_scale_word'], a['inputs'][0]['scale_words'][0])
        self.assertEqual(len(set(hashes)), 3)

    def test_compressed_counters_match_independent_temporal_dot_all_supported_T(self):
        for samples in (16, 32, 64):
            for representation in (REPRESENTATION, 'product_sign_magnitude'):
                fixture = self.tiny(samples=samples, representation=representation)
                g = fixture['inputs'][0]
                for row, packet in enumerate(fixture['packets'][0]):
                    expected = temporal_direct_bins(g['weights'][row], g['encoded'], g['thresholds'])
                    self.assertEqual(packet['signed_bins'], expected)
                    temporal_bits = [[int(t < q) for q in g['encoded']['q']] for t in g['thresholds']]
                    raw = self.restore.accumulate_counts(g['weights'][row], g['encoded']['input_sign'],
                        g['encoded']['bins'], temporal_bits, representation=representation,
                        count_width=fixture['count_width'], true_one=g['encoded']['true_one'])
                    self.assertEqual(packet['counts'], [[list(rail) for rail in b] for b in raw])

    def test_minus128_and_negative_input_preserve_rail_semantics(self):
        weights = [-128] + [0] * 63
        thresholds = [255] * 32
        for sign in (0, 1):
            enc = self.encoded(sign=sign, true_one=1)
            packet = count_packet(self.restore, weights, enc, thresholds, word(1))
            expected = 128 if sign else -128
            self.assertEqual(packet['signed_bins'], [expected * 32, 0, 0, 0])
            self.assertEqual(packet['sc_word'], word(expected))
            magnitude = count_packet(self.restore, weights, enc, thresholds, word(1),
                                      representation='product_sign_magnitude')
            self.assertEqual(magnitude['sc_word'], packet['sc_word'])
            wrong = self.restore.normalize_counts(magnitude['counts'], representation=REPRESENTATION,
                                                   count_width=12, samples=32)
            self.assertEqual(wrong[0], -packet['signed_bins'][0])

    def test_true_one_overrides_q_and_max_threshold(self):
        enc = self.encoded(q=0)
        enc['true_one'][0] = 1
        weights = [1] * 64
        frame = [255] * 32
        self.assertEqual(acceptance_counts(enc, frame), [32] + [0] * 63)
        packet = count_packet(self.restore, weights, enc, frame, word(1))
        self.assertEqual(packet['signed_bins'], [32, 0, 0, 0])
        self.assertEqual(packet['sc_word'], word(1))

    def test_positive_endpoint_uses_twelve_bit_counts_and_signed_twenty(self):
        enc = self.encoded(sign=1, true_one=1)
        packet = count_packet(self.restore, [-128] * 64, enc, list(range(32)), word(1))
        self.assertEqual(packet['count_width'], 12)
        self.assertEqual(packet['counts'][0][1][7], 2048)
        self.assertEqual(packet['signed_bins'][0], 262144)
        with self.assertRaisesRegex(ValueError, 'positive W=-128'):
            self.restore.normalize_counts(packet['counts'], representation=REPRESENTATION,
                count_width=12, samples=32, accumulator_width=19)

    def test_all_w8_codes_and_both_signs_match_direct_dot(self):
        for sign in (0, 1):
            enc = self.encoded(sign=sign, true_one=1)
            enc['bins'] = [i % 4 for i in range(64)]
            for start in (-128, -64, 0, 64):
                weights = list(range(start, start + 64))
                packet = count_packet(self.restore, weights, enc, list(range(32)), word(1))
                self.assertEqual(packet['signed_bins'],
                                 temporal_direct_bins(weights, enc, list(range(32))))

    def test_original_subnormal_restore_order_is_preserved(self):
        original = self.restore.restore_bins([3, 0, 0, 0], top_exp=-145,
                                             weight_scale_word=word(1.5), samples=32)
        self.assertEqual(original, 0x00000003)
        oracle = self.restore._oracle()
        first_convert = oracle.R.pack(3, -145, 23)[0]
        old_order = oracle.mul(oracle.mul(first_convert, word(1.5)), word(1 / 32))
        self.assertEqual(old_order, 0x00000002)
        tiny_words = [1, 0x80000001] + [0] * 62
        enc = self.restore.encode(tiny_words, frac=23)
        self.assertEqual(enc['top_exp'], -149)
        self.assertEqual(enc['input_sign'][:2], (0, 1))

    def test_digital_dot_is_ordered_fp32_not_a_host_float_sum(self):
        words = [word(2**24), word(1), word(-(2**24))] + [0] * 61
        weights = [1, 1, 1] + [0] * 61
        dot = w8_dot(self.restore, words, weights)
        self.assertEqual(dot, word(0))
        self.assertEqual(w8_partial(self.restore, words, weights, word(2)), word(0))
        # Exact-real or binary64 accumulation would retain the +1 term.
        self.assertEqual(sum((2**24, 1, -(2**24))), 1)

    def test_digital_scale_stage_is_separate_and_shared_with_fixture(self):
        fixture = self.tiny(tiles=2)
        group = fixture['inputs'][0]
        for row in range(fixture['rows']):
            scale = group['scale_words'][row // fixture['rows_per_tile']]
            self.assertEqual(fixture['w8_partials'][0][row],
                             scale_word(self.restore, fixture['w8_unscaled'][0][row], scale))
            self.assertEqual(fixture['w8_partials'][0][row],
                             w8_partial(self.restore, group['words'], group['weights'][row], scale))

    def test_expected_sc_cross_k_matches_temporal_reference(self):
        fixture = self.tiny(groups=3, tiles=2, rows_per_tile=2)
        expected = [0] * fixture['rows']
        for k, group in enumerate(fixture['inputs']):
            for row, weights in enumerate(group['weights']):
                bins = temporal_direct_bins(weights, group['encoded'], group['thresholds'])
                partial = self.restore.restore_bins(bins, top_exp=group['encoded']['top_exp'],
                    weight_scale_word=group['scale_words'][row // 2], samples=32)
                self.assertEqual(partial, fixture['sc_partials'][k][row])
                expected[row] = self.restore.add_words(expected[row], partial)
        self.assertEqual(expected, fixture['expected_sc'])

    def test_hashes_detect_operand_and_order_changes(self):
        fixture = self.tiny(groups=2)
        self.assertEqual(fixture['hashes']['inputs'], digest(fixture['inputs']))
        saved = fixture.pop('fixture_sha256')
        self.assertEqual(saved, digest(fixture))
        fixture['inputs'][0]['thresholds'][0] ^= 1
        self.assertNotEqual(fixture['hashes']['inputs'], digest(fixture['inputs']))
        self.assertNotEqual(saved, digest(fixture))

    def test_packet_construction_preserves_inputs(self):
        fixture = self.tiny()
        group = fixture['inputs'][0]
        before = copy.deepcopy(group)
        count_packet(self.restore, group['weights'][0], group['encoded'], group['thresholds'],
                     group['scale_words'][0])
        self.assertEqual(group, before)

    def test_invalid_shapes_codes_and_cached_frame_are_rejected(self):
        for kwargs in (dict(seed=-1), dict(groups=0), dict(rows_per_tile=65), dict(samples=31)):
            with self.assertRaises(ValueError):
                self.tiny(**kwargs)
        enc = self.encoded()
        with self.assertRaisesRegex(ValueError, 'signed-W8'):
            count_packet(self.restore, [128] * 64, enc, [0] * 32, word(1))
        with self.assertRaisesRegex(ValueError, 'cached multiplicities'):
            count_packet(self.restore, [1] * 64, enc, [0] * 32, word(1), multiplicities=[32] * 64)
        with self.assertRaisesRegex(ValueError, 'finite raw FP32'):
            w8_dot(self.restore, [0x7f800000] + [0] * 63, [1] * 64)
        with self.assertRaisesRegex(ValueError, 'positive finite'):
            w8_partial(self.restore, [0] * 64, [1] * 64, word(-1))


if __name__ == '__main__':
    unittest.main()
