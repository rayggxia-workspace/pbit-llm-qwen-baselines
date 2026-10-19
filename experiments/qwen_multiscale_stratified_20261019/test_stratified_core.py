"""Joint stream law, range boundaries, frozen weights, and FFN regressions."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import torch
from torch import nn
from torch.nn import functional as F

import stratified_core as core
from stratified_core import (POLICY_BINS, StratifiedFFN, encode_input,
                             project_counts, stratified_counts)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] /
                       'qwen_fixedw_multiscale_20261019'))
from multiscale_core import MultiScaleFFN


def original(d=128, f=128):
    torch.manual_seed(55)
    module = nn.Module()
    module.gate_proj = nn.Linear(d, f, bias=False)
    module.up_proj = nn.Linear(d, f, bias=False)
    module.down_proj = nn.Linear(f, d, bias=False)
    return module


class Tests(unittest.TestCase):
    def test_iid_counts_are_bit_identical_to_original(self):
        p = torch.arange(256).repeat(2).reshape(4, 128).float() / 256
        g1 = torch.Generator().manual_seed(91)
        g2 = torch.Generator().manual_seed(91)
        a = stratified_counts(p, 127, 1, g1)
        b = core.shared_counts(p, 127, g2, 64)
        torch.testing.assert_close(a, b, rtol=0, atol=0)
        self.assertTrue(torch.equal(g1.get_state(), g2.get_state()))

    def test_fine_counts_equal_literal_common_random_words(self):
        # Different strata use explicitly different offsets; all lanes share
        # the word for their selected boundary stratum, across all scale bins.
        offsets = torch.tensor([[3, 0, 1, 2] * 16, [1, 2, 3, 0] * 16])
        offsets[0, -1] = 3  # Include R=255 so q=255 is visibly not a p1 bypass.
        q = torch.tensor([0, 1, 2, 3, 4, 5, 63, 64, 65, 127, 128, 255, 256] + [77] * 51)
        p = q.repeat(2, 1).float() / 256
        words = torch.arange(64)[None, :] * 4 + offsets
        expected = (words[:, :, None] < q[None, None, :]).sum(1).float()
        with patch.object(core.torch, 'randint', return_value=offsets) as rng:
            actual = stratified_counts(p, 64, 64)
        self.assertEqual(rng.call_args.args, (4, (2, 64)))
        torch.testing.assert_close(actual, expected, rtol=0, atol=0)
        self.assertTrue(bool((actual[:, 0] == 0).all()))
        self.assertTrue(bool((actual[:, 12] == 64).all()))
        self.assertFalse(bool((actual[:, 11] == 64).all()))

    def test_coarse_histogram_tree_equals_literal_common_random_words(self):
        # The binomial oracle is built from explicit per-clock words. It also
        # asserts every conditional parent count, catching incorrect ordering
        # of stratum roots/children or inter-stratum prefix accumulation.
        words = torch.tensor([[7, 59, 64, 112, 129, 190, 192, 255],
                              [0, 63, 76, 127, 128, 191, 221, 254]])
        hist = torch.zeros(2, 256)
        hist.scatter_add_(1, words, torch.ones_like(words, dtype=torch.float32))
        q = torch.tensor([0, 7, 8, 59, 60, 64, 65, 112, 113, 128,
                          129, 130, 190, 191, 192, 193, 255, 256] + [37] * 46)
        p = q.repeat(2, 1).float() / 256
        depth = [0]

        def split(counts, probabilities, generator=None):
            nodes = 4 * (2 ** depth[0])
            width = 256 // nodes
            parents = hist.reshape(2, nodes, width).sum(-1)
            torch.testing.assert_close(counts, parents, rtol=0, atol=0)
            torch.testing.assert_close(probabilities, torch.full_like(counts, .5))
            left = hist.reshape(2, nodes, 2, width // 2).sum(-1)[:, :, 0]
            depth[0] += 1
            return left

        with patch.object(core.torch, 'binomial', side_effect=split):
            actual = stratified_counts(p, 8, 4)
        expected = (words[:, :, None] < q[None, None, :]).sum(1).float()
        self.assertEqual(depth[0], 6)
        torch.testing.assert_close(actual, expected, rtol=0, atol=0)

    def test_different_strata_are_independent_same_stratum_shares_randomness(self):
        n = 24000
        q = torch.tensor([16, 32, 96] + [0] * 61)
        counts = stratified_counts(q.repeat(n, 1).float() / 256, 64, 4,
                                   torch.Generator().manual_seed(33))[:, :3]
        mean = counts.mean(0)
        torch.testing.assert_close(mean, torch.tensor([4., 8., 24.]), atol=.055, rtol=0)
        centered = counts - mean
        covariance = centered.T @ centered / n
        # Per boundary stratum there are 16 draws. q16/q32 share one stratum:
        # Cov=16*(min(.25,.5)-.25*.5)=2. q32/q96 are in distinct strata.
        self.assertAlmostEqual(covariance[0, 1].item(), 2., delta=.11)
        self.assertAlmostEqual(covariance[1, 2].item(), 0., delta=.11)
        self.assertAlmostEqual(covariance[1, 1].item(), 4., delta=.13)

    def test_fine_stratified_joint_law_and_variance_bound(self):
        n = 20000
        q = torch.tensor([1, 2, 5] + [0] * 61)
        p = q.repeat(n, 1).float() / 256
        c = stratified_counts(p, 64, 64, torch.Generator().manual_seed(92))[:, :3]
        residual = c - torch.tensor([0., 0., 1.])
        # Each boundary draw is uniform over four integer offsets. These are
        # .25/.5/.25 Bernoulli events; first two nested, third independent.
        torch.testing.assert_close(residual.mean(0), torch.tensor([.25, .5, .25]),
                                   atol=.012, rtol=0)
        centered = residual - residual.mean(0)
        covariance = centered.T @ centered / n
        self.assertAlmostEqual(covariance[0, 1].item(), .125, delta=.008)
        self.assertAlmostEqual(covariance[0, 2].item(), 0., delta=.008)
        self.assertTrue(bool((residual == 0).logical_or(residual == 1).all()))

    def test_full_256_strata_is_exact_and_does_not_consume_rng(self):
        p = torch.arange(256).repeat(2).reshape(2, 256).float() / 256
        rng = torch.Generator().manual_seed(8)
        state = rng.get_state().clone()
        c = stratified_counts(p, 512, 256, rng)
        torch.testing.assert_close(c, p * 512, rtol=0, atol=0)
        self.assertTrue(torch.equal(state, rng.get_state()))

    def test_strata_endpoints_and_same_probability_across_scale_bins(self):
        x = torch.zeros(256, 64)
        x[:, :4] = torch.tensor([1., .75, .1875, 255/256])
        e = encode_input(x, 'pot4')
        self.assertNotEqual(e['bin_id'][0, 1].item(), e['bin_id'][0, 2].item())
        for k in (1, 4, 16, 64):
            c = stratified_counts(e['probability'], 64, k,
                                  torch.Generator().manual_seed(19))
            torch.testing.assert_close(c[:, 1], c[:, 2], rtol=0, atol=0)
            self.assertTrue(bool((c[:, 0] == 64).all()))
            self.assertTrue(bool((c[:, 4:] == 0).all()))
            self.assertTrue(bool((c[:, 3] < 64).any()))
            self.assertFalse(bool(e['full_one'][:, 3].any()))

    def test_generalized_scale_bins_and_no_clipping(self):
        x = torch.zeros(1, 64)
        x[0, :8] = torch.tensor([1., -.25, .0625, -.015625,
                                 .00390625, -.0009765625, .000244140625, -.00006103515625])
        for bins in (1, 2, 3, 4, 6, 8):
            e = encode_input(x, 'pot' + str(bins))
            torch.testing.assert_close(e['bin_id'][0, :8],
                                       torch.arange(8).clamp_max(bins - 1), rtol=0, atol=0)
            self.assertTrue(bool((x.abs() <= e['scale']).all()))
            self.assertTrue(bool(torch.isfinite(e['scale']).all()))
            torch.testing.assert_close(e['probability'] * 256,
                                       (e['probability'] * 256).round(), rtol=0, atol=0)

    def test_all_bins_keep_identical_historical_w8(self):
        m = original()
        reference = MultiScaleFFN(m)
        for policy in POLICY_BINS:
            module = StratifiedFFN(m, policy, strata=16)
            for name in ('gu_codes', 'gu_decoded', 'gu_tile_lsb',
                         'down_codes', 'down_decoded', 'down_tile_lsb'):
                torch.testing.assert_close(getattr(module, name), getattr(reference, name),
                                           rtol=0, atol=0)
            self.assertFalse(module.diagnostics()['weight_stochastic'])

    def test_mean_ffn_is_exact_old_pot4_control_and_no_rng(self):
        m = original()
        x = torch.randn(2, 128)
        old = MultiScaleFFN(m, policy='pot4', mode='mean', seed=2, layer=3)
        new = StratifiedFFN(m, policy='pot4', mode='mean', seed=2, layer=3, strata=16)
        state_x, state_z = new.rng_input.get_state().clone(), new.rng_product.get_state().clone()
        torch.testing.assert_close(new(x), old(x), rtol=0, atol=0)
        self.assertTrue(torch.equal(state_x, new.rng_input.get_state()))
        self.assertTrue(torch.equal(state_z, new.rng_product.get_state()))
        d = new.diagnostics()
        self.assertEqual(d['strata'], 16)
        self.assertEqual(d['samples_per_stratum'], 8)
        self.assertEqual(d['stratum_width'], 16)

    def test_iid_ffn_is_exact_old_pot4_sampled_reference(self):
        m = original()
        x = torch.randn(3, 128).to(torch.bfloat16)
        old = MultiScaleFFN(m, policy='pot4', cycles=64, seed=2, layer=3)
        new = StratifiedFFN(m, policy='pot4', cycles=64, seed=2, layer=3, strata=1)
        torch.testing.assert_close(new(x), old(x), rtol=0, atol=0)
        self.assertTrue(torch.equal(old.rng_input.get_state(), new.rng_input.get_state()))
        self.assertTrue(torch.equal(old.rng_product.get_state(), new.rng_product.get_state()))

    def test_one_input_draw_shared_by_gate_up_independent_z_draw(self):
        module = StratifiedFFN(original(), policy='pot3', cycles=64, strata=4)
        x = torch.randn(2, 128)
        calls = []

        def sample(probability, cycles, strata, generator, group):
            calls.append((probability.clone(), generator))
            return probability * cycles

        with patch.object(core, 'stratified_counts', side_effect=sample):
            result = module(x)
        self.assertEqual(len(calls), 2)
        self.assertIs(calls[0][1], module.rng_input)
        self.assertIs(calls[1][1], module.rng_product)
        self.assertIsNot(calls[0][1], calls[1][1])
        e = encode_input(x, 'pot3')
        gu = project_counts(e['probability'] * 64, e['sign'], e['scale'], module.gu_decoded, 64)
        g, u = gu.chunk(2, -1)
        z = encode_input(F.silu(g) * u, 'pot3')
        expected = project_counts(z['probability'] * 64, z['sign'], z['scale'],
                                  module.down_decoded, 64)
        torch.testing.assert_close(result, expected, rtol=0, atol=0)

    def test_sampling_configuration_and_grid_validation(self):
        p = torch.zeros(1, 64)
        for cycles, strata in ((0, 1), (64, 0), (64, 3), (10, 4), (64, 128),
                                (True, 1), (64, True)):
            with self.assertRaises(ValueError):
                stratified_counts(p, cycles, strata)
            with self.assertRaises(ValueError):
                StratifiedFFN(original(), cycles=cycles, strata=strata)
        for invalid in (.1, -.1, 1.1, float('nan')):
            with self.assertRaises(ValueError):
                stratified_counts(torch.full((1, 64), invalid), 64, 4)
        with self.assertRaises(ValueError):
            stratified_counts(torch.zeros(63), 64, 4)


if __name__ == '__main__':
    torch.set_num_threads(4)
    unittest.main(verbosity=2)
