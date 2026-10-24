"""CPU contract tests; no model weights, datasets, GPU or PPA required."""
import hashlib
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import torch
from torch import nn
from torch.nn import functional as F

from . import static_core
from .static_core import StaticFFN, encode_static
from qwen3.stochastic.vendor.stratified_core import StratifiedFFN, encode_input, stratified_counts, project_encoded


class TinyFFN(nn.Module):
    def __init__(self):
        super().__init__()
        self.gate_proj = nn.Linear(128, 128, bias=False)
        self.up_proj = nn.Linear(128, 128, bias=False)
        self.down_proj = nn.Linear(128, 128, bias=False)


def tables():
    return torch.tensor([[8., 2., .5, .125], [16., 4., 1., .25]])


class StaticEncodingTests(unittest.TestCase):
    def setUp(self):
        torch.manual_seed(17)

    def test_boundary_zero_endpoint_and_clipping(self):
        x = torch.zeros(64)
        x[:11] = torch.tensor([0., .125, -.125, .5, 2., 8., 9., -12.,
                              .125 * 255 / 256, .125 * 254 / 256, .25])
        e = encode_static(x, tables()[:1])
        self.assertEqual(e['bin_id'][:11].tolist(), [3, 3, 3, 2, 1, 0, 0, 0, 3, 3, 2])
        self.assertEqual(e['probability'][0].item(), 0.)
        self.assertEqual(e['probability'][8].item(), 255 / 256)
        self.assertFalse(e['full_one'][8])
        self.assertTrue(bool(e['full_one'][1:8].all()))
        self.assertEqual(e['decoded'][6:8].tolist(), [8., -8.])
        self.assertEqual(e['q'][1].item(), 255)
        self.assertEqual(e['probability'][1].item(), 1.)

    def test_group_and_batch_broadcast(self):
        x = torch.full((2, 3, 128), .2)
        e = encode_static(x, tables())
        self.assertEqual(e['scale'].shape, x.shape)
        self.assertTrue(bool((e['scale'][..., :64] == .5).all()))
        self.assertTrue(bool((e['scale'][..., 64:] == .25).all()))
        for batch in range(2):
            for token in range(3):
                single = encode_static(x[batch, token], tables())
                for key in e:
                    self.assertTrue(torch.equal(e[key][batch, token], single[key]))

    def test_fixed_encoding_does_not_reduce_values(self):
        x = torch.rand(128)
        with patch.object(torch.Tensor, 'amax', side_effect=AssertionError('online max')), \
                patch.object(torch.Tensor, 'max', side_effect=AssertionError('online max')):
            e = encode_static(x, tables())
        self.assertEqual(e['scale'].shape, x.shape)

    def test_invalid_tables(self):
        bad = [torch.ones(2, 4), tables().flip(-1), tables()[:1],
               tables().reshape(8), [[8., 2., .5, 0.], [16., 4., 1., .25]],
               [[8., 2., .5, -.125], [16., 4., 1., .25]],
               [[8., 2., .5, .12], [16., 4., 1., .25]],
               [[8. + 1e-9, 2., .5, .125], [16., 4., 1., .25]],
               [[float('inf'), 2., .5, .125], [16., 4., 1., .25]],
               [[float('nan'), 2., .5, .125], [16., 4., 1., .25]],
               tables().to(torch.complex64), torch.ones(2, 4, dtype=torch.bool),
               torch.tensor([[2. ** 128, 2., .5, .125], [16., 4., 1., .25]],
                            dtype=torch.float64),
               torch.tensor([[8., 2., .5, 2. ** -150], [16., 4., 1., .25]],
                            dtype=torch.float64)]
        for item in bad:
            with self.subTest(table=str(item)):
                with self.assertRaises(ValueError):
                    encode_static(torch.zeros(128), item)

    def test_invalid_activations(self):
        for x in (torch.zeros(63), torch.zeros(0), torch.tensor(1.),
                  torch.full((128,), float('nan'))):
            with self.assertRaises(ValueError):
                encode_static(x, tables())

    def test_subnormal_powers_do_not_nan_at_zero(self):
        table = torch.tensor([[2. ** -143, 2. ** -145, 2. ** -147, 2. ** -149]])
        x = torch.zeros(64)
        x[1] = 2. ** -149
        e = encode_static(x, table)
        self.assertTrue(bool(torch.isfinite(e['probability']).all()))
        self.assertEqual(e['probability'][0].item(), 0.)
        self.assertEqual(e['probability'][1].item(), 1.)

    def test_matches_dynamic_when_tables_match(self):
        x = torch.randn(2, 3, 128) * .3
        x[..., 0], x[..., 64] = 8., 16.
        dynamic = encode_input(x, 'pot4')
        static = encode_static(x, tables())
        for key in dynamic:
            self.assertTrue(torch.equal(dynamic[key], static[key]), key)

    def test_shared_stratified_counts_explicit_clock_oracle(self):
        # Values use all four bins, but equal q values in different bins must
        # see exactly the same random threshold in the same original group.
        x = torch.rand(2, 128) * 3
        e = encode_static(x, tables())
        q = (e['probability'] * 256).to(torch.int64).reshape(-1, 64)
        seed = 134
        offsets = torch.randint(8, (q.shape[0], 32),
                                generator=torch.Generator().manual_seed(seed))
        words = offsets + torch.arange(32).reshape(1, 32) * 8
        oracle = (words.unsqueeze(-1) < q.unsqueeze(1)).sum(1).reshape_as(x)
        actual = stratified_counts(e['probability'], 32, 32,
                                   torch.Generator().manual_seed(seed))
        self.assertTrue(torch.equal(actual, oracle))

    def test_full_coverage_equals_encoded_mean(self):
        x = torch.randn(2, 128) * 12
        weight = torch.randn(17, 128)
        e = encode_static(x, tables())
        actual = project_encoded(e, weight, 'sampled', 256,
                                 torch.Generator().manual_seed(1), 256)
        expected = project_encoded(e, weight, 'mean', 256)
        self.assertTrue(torch.equal(actual, expected))


class StaticFFNTests(unittest.TestCase):
    def setUp(self):
        torch.manual_seed(29)
        self.original = TinyFFN().eval()
        self.x = torch.randn(2, 3, 128)

    def test_none_tables_are_bitwise_original_all_modes(self):
        for mode in ('w8_only', 'mean', 'sampled'):
            with self.subTest(mode=mode):
                old = StratifiedFFN(self.original, policy='pot4', mode=mode,
                                    cycles=32, strata=32, seed=2, layer=3)
                new = StaticFFN(self.original, mode=mode, seed=2, layer=3)
                for _ in range(3):
                    self.assertTrue(torch.equal(old(self.x), new(self.x)))
                for name in ('gu_codes', 'gu_decoded', 'gu_tile_lsb',
                             'down_codes', 'down_decoded', 'down_tile_lsb',
                             'x_stats', 'z_stats', 'x_bins', 'z_bins'):
                    self.assertTrue(torch.equal(getattr(old, name), getattr(new, name)), name)
                self.assertTrue(torch.equal(old.rng_input.get_state(), new.rng_input.get_state()))
                self.assertTrue(torch.equal(old.rng_product.get_state(), new.rng_product.get_state()))

    def test_weight_identity_static_tables(self):
        old = StratifiedFFN(self.original, cycles=32, strata=32)
        new = StaticFFN(self.original, tables(), tables())
        for name in ('gu_codes', 'gu_decoded', 'gu_tile_lsb',
                     'down_codes', 'down_decoded', 'down_tile_lsb'):
            self.assertTrue(torch.equal(getattr(old, name), getattr(new, name)), name)

    def test_fixed_and_dynamic_signal_scope(self):
        for fixed_x, fixed_z in ((True, False), (False, True), (True, True)):
            m = StaticFFN(self.original, tables() if fixed_x else None,
                          tables() if fixed_z else None, mode='mean')
            enc = encode_static(self.x, tables()) if fixed_x else encode_input(self.x)
            g, u = F.linear(enc['decoded'], m.gu_decoded).chunk(2, -1)
            z = F.silu(g) * u
            enc_z = encode_static(z, tables()) if fixed_z else encode_input(z)
            expected = F.linear(enc_z['decoded'], m.down_decoded)
            self.assertTrue(torch.equal(m(self.x), expected))
            expected_dynamic = [n for n, fixed in (('x', fixed_x), ('z', fixed_z)) if not fixed]
            self.assertEqual(m.diagnostics()['online_absmax_signals'], expected_dynamic)

    def test_observer_preencoding_and_w8_bypass(self):
        m = StaticFFN(self.original, tables() / 1024., tables(), mode='w8_only', layer=7)
        seen = []
        m.observer = lambda layer, signal, value: seen.append((layer, signal, value.clone()))
        output = m(self.x)
        g, u = F.linear(self.x, m.gu_decoded).chunk(2, -1)
        z = F.silu(g) * u
        self.assertTrue(torch.equal(output, F.linear(z, m.down_decoded)))
        self.assertEqual([(item[0], item[1]) for item in seen], [(7, 'x'), (7, 'z')])
        self.assertTrue(torch.equal(seen[0][2], self.x))
        self.assertTrue(torch.equal(seen[1][2], z))
        self.assertEqual(m.diagnostics()['online_absmax_signals'], [])
        self.assertEqual(m.diagnostics()['x_clip_sse'], 0.)

    def test_scale_validation_only_at_construction(self):
        m = StaticFFN(self.original, tables(), tables())
        with patch.object(static_core, '_validated_scales',
                          side_effect=AssertionError('hot-path revalidation')):
            m(self.x)

    def test_scale_buffers_do_not_alias_caller(self):
        t = tables()
        m = StaticFFN(self.original, t, t)
        t.fill_(99.)
        self.assertTrue(torch.equal(m.x_scales, tables()))
        self.assertTrue(torch.equal(m.z_scales, tables()))
        self.assertNotEqual(m.x_scales.data_ptr(), m.z_scales.data_ptr())

    def test_clip_energy_and_sha(self):
        m = StaticFFN(self.original, tables(), tables(), mode='mean')
        x = torch.zeros(1, 128)
        x[0, :3] = torch.tensor([10., -12., 8.])
        m._stage(x, 'x', 'gu', m.rng_input)
        d = m.diagnostics()
        power = 100. + 144. + 64.
        self.assertEqual(d['x_clip_fraction'], 2 / 128)
        self.assertEqual(d['x_clip_sse'], 20.)
        self.assertEqual(d['x_clip_sse_over_power'], 20. / power)
        self.assertEqual(d['x_clipped_value_power_over_power'], 244. / power)
        self.assertEqual(d['x_max_overflow_ratio'], 1.5)
        self.assertEqual(d['x_max_overflow_excess'], .5)
        expected = hashlib.sha256(tables().numpy().astype('<f4').tobytes()).hexdigest()
        self.assertEqual(d['x_scales_sha256'], expected)
        self.assertEqual(d['scale_tables']['x']['exponent_spacing'], 2)
        self.assertFalse(d['diagnostic_reductions_drive_scales'])

    def test_zero_input_has_finite_diagnostics(self):
        m = StaticFFN(self.original, tables(), tables())
        self.assertTrue(torch.equal(m(torch.zeros_like(self.x)), torch.zeros_like(self.x)))
        for signal in ('x', 'z'):
            self.assertEqual(m.diagnostics()[signal + '_max_overflow_ratio'], 0.)
            self.assertEqual(m.diagnostics()[signal + '_clip_sse_over_power'], 0.)


if __name__ == '__main__':
    unittest.main(verbosity=2)
