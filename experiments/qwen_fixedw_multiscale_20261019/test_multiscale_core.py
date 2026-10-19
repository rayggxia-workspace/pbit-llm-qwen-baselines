"""CPU boundary, exact-reduction, frozen-W, and shared-stream invariants."""
import unittest
from unittest.mock import patch

import torch
from torch import nn
from torch.nn import functional as F

import multiscale_core as core
from multiscale_core import (MultiScaleFFN, encode_input, project_counts,
                             project_encoded, quantize_int8, shared_counts)
from range_core import RangeFFN, encode_input as encode_old


def original(d=128, f=128):
    torch.manual_seed(55)
    module = nn.Module()
    module.gate_proj = nn.Linear(d, f, bias=False)
    module.up_proj = nn.Linear(d, f, bias=False)
    module.down_proj = nn.Linear(f, d, bias=False)
    return module


class Tests(unittest.TestCase):
    def test_scale_bin_boundaries_sign_zero_and_p1(self):
        x = torch.zeros(1, 64)
        x[0, :10] = torch.tensor([8., -2., .5, -.125, .0625, 1.999,
                                  .499, .124, 0., 7.96875])
        e = encode_input(x, 'pot4')
        torch.testing.assert_close(e['bin_id'][0, :10],
                                   torch.tensor([0, 1, 2, 3, 3, 1, 2, 3, 3, 0]))
        torch.testing.assert_close(e['scale'][0, :5], torch.tensor([8., 2., .5, .125, .125]))
        self.assertTrue(bool(e['full_one'][0, :4].all()))
        self.assertEqual(e['probability'][0, 8].item(), 0.)
        self.assertEqual(e['probability'][0, 9].item(), 255/256)
        self.assertFalse(e['full_one'][0, 9].item())
        torch.testing.assert_close(e['decoded'][0, :5], x[0, :5])
        self.assertTrue(bool((x.abs() <= e['scale']).all()))
        self.assertTrue(bool((e['probability'] * 256 == (e['probability'] * 256).round()).all()))

    def test_ceil_power_of_two_uses_correct_side_of_boundary(self):
        # log2(1+ulp) can round close to a boundary; frexp preserves the side.
        x = torch.ones(2, 64)
        x[0, 0] = torch.nextafter(torch.tensor(1.), torch.tensor(2.))
        x[1, 0] = 1.
        e = encode_input(x, 'pot1')
        self.assertEqual(e['scale'][0, 0].item(), 2.)
        self.assertEqual(e['scale'][1, 0].item(), 1.)
        self.assertFalse(e['full_one'][0, 0].item())
        self.assertTrue(e['full_one'][1, 0].item())

    def test_zero_groups_and_multiple_shapes(self):
        for policy in ('dynamic64', 'pot1', 'pot4', 'pot8'):
            e = encode_input(torch.zeros(2, 3, 128), policy)
            self.assertTrue(bool(torch.isfinite(e['scale']).all()))
            self.assertTrue(bool((e['scale'] > 0).all()))
            self.assertTrue(bool((e['decoded'] == 0).all()))
            self.assertFalse(bool(e['full_one'].any()))
        with self.assertRaises(ValueError):
            encode_input(torch.zeros(63), 'pot4')
        with self.assertRaises(ValueError):
            encode_input(torch.zeros(64), 'pot2')

    def test_dynamic64_encoding_is_strict_historical_reference(self):
        torch.manual_seed(2)
        x = torch.randn(2, 3, 128)
        p, decoded, scale = encode_old(x, None, 'dynamic64')
        e = encode_input(x, 'dynamic64')
        for actual, expected in ((e['probability'], p), (e['decoded'], decoded),
                                 (e['scale'], scale)):
            torch.testing.assert_close(actual, expected, rtol=0, atol=0)
        self.assertFalse(bool(e['full_one'].any()))

    def test_all_policies_keep_strict_identical_historical_w8(self):
        m = original()
        for policy in ('dynamic64', 'pot1', 'pot4', 'pot8'):
            module = MultiScaleFFN(m, policy)
            for name, w in (('gu', torch.cat((m.gate_proj.weight, m.up_proj.weight), 0)),
                            ('down', m.down_proj.weight)):
                codes, decoded, lsb = quantize_int8(w)
                for field, expected in (('codes', codes), ('decoded', decoded), ('tile_lsb', lsb)):
                    torch.testing.assert_close(getattr(module, name + '_' + field), expected,
                                               rtol=0, atol=0)
            before = module.gu_decoded.clone(), module.down_decoded.clone()
            module(torch.randn(1, 128))
            torch.testing.assert_close(module.gu_decoded, before[0], rtol=0, atol=0)
            torch.testing.assert_close(module.down_decoded, before[1], rtol=0, atol=0)
            self.assertFalse(module.diagnostics()['weight_probability_reencoded'])

    def test_literal_shared_r8_stream_equals_counts_with_cross_tile_scales(self):
        torch.manual_seed(4)
        x = torch.randn(2, 128) * torch.tensor([1.] * 64 + [8.] * 64)
        e = encode_input(x, 'pot4')
        w = torch.randn(128, 128)
        w[64:, :] *= 7.
        w[:, 64:] *= .125
        codes, decoded, lsb = quantize_int8(w)
        random_words = torch.tensor([[0, 1, 63, 64, 127, 128, 254, 255],
                                     [255, 210, 180, 140, 100, 60, 20, 0]])
        # Each group has its own word; all 64 lanes, across scale bins, share it.
        streams = (random_words[None, :, :, None] <
                   (e['probability'] * 256).reshape(2, 2, 1, 64)).float()
        counts = streams.sum(2).reshape_as(x)
        result = project_counts(counts, e['sign'], e['scale'], decoded, 8)
        literal = torch.zeros(2, 128)
        for cycle in range(8):
            event = streams[:, :, cycle, :].reshape_as(x)
            literal += F.linear(e['sign'] * e['scale'] * event, decoded) / 8
        torch.testing.assert_close(result, literal, rtol=3e-6, atol=1e-5)
        # Independent check restores both the selected input-bin scale and W
        # tile LSB; merging counts across these scales would fail this fixture.
        tiled = torch.zeros_like(result)
        for group in range(2):
            start = group * 64
            selected = e['sign'][:, start:start+64] * e['scale'][:, start:start+64]
            integers = counts[:, start:start+64]
            for row_group in range(2):
                out_start = row_group * 64
                tiled[:, out_start:out_start+64] += F.linear(
                    selected * integers,
                    codes[out_start:out_start+64, start:start+64].float()) * lsb[row_group, group] / 8
        torch.testing.assert_close(result, tiled, rtol=3e-6, atol=1e-5)

    def test_same_probability_has_same_shared_count_across_bins(self):
        # .75 and .1875 select different scales but both encode probability .75.
        x = torch.zeros(128, 64)
        x[:, :3] = torch.tensor([1., .75, .1875])
        e = encode_input(x, 'pot4')
        self.assertNotEqual(e['bin_id'][0, 1].item(), e['bin_id'][0, 2].item())
        counts = shared_counts(e['probability'], 127, torch.Generator().manual_seed(33), 64)
        torch.testing.assert_close(counts[:, 1], counts[:, 2], rtol=0, atol=0)
        self.assertTrue(bool((counts[:, 0] == 127).all()))
        self.assertTrue(bool((counts[:, 3:] == 0).all()))

    def test_sampled_projection_calls_one_joint_sampler_for_all_bins(self):
        x = torch.randn(2, 128)
        e = encode_input(x, 'pot8')
        w = torch.randn(64, 128)
        counts = torch.floor(e['probability'] * 17)
        with patch.object(core, 'shared_counts', return_value=counts) as sampler:
            actual = project_encoded(e, w, 'sampled', 17, None)
        sampler.assert_called_once()
        self.assertEqual(sampler.call_args.args[3], 64)
        torch.testing.assert_close(actual, F.linear(e['sign'] * e['scale'] * counts, w) / 17)

    def test_full_mean_ffn_matches_encoded_control_and_keeps_rng_state(self):
        module = MultiScaleFFN(original(), policy='pot4', mode='mean', seed=2, layer=3)
        x = torch.randn(2, 128)
        state_x, state_z = module.rng_input.get_state().clone(), module.rng_product.get_state().clone()
        xq = encode_input(x, 'pot4')['decoded']
        g, u = F.linear(xq, module.gu_decoded).chunk(2, -1)
        zq = encode_input(F.silu(g)*u, 'pot4')['decoded']
        expected = F.linear(zq, module.down_decoded)
        torch.testing.assert_close(module(x), expected, rtol=0, atol=0)
        self.assertTrue(torch.equal(state_x, module.rng_input.get_state()))
        self.assertTrue(torch.equal(state_z, module.rng_product.get_state()))
        diag = module.diagnostics()
        self.assertEqual(diag['calls'], 1)
        for name in ('x', 'z'):
            self.assertEqual(diag[name+'_values'], 256)
            self.assertAlmostEqual(sum(diag[name+'_bin_occupancy']), 1.)
            self.assertEqual(diag[name+'_clip_fraction'], 0.)

    def test_w8_only_has_no_a_encoding_and_exact_w8_swiglu(self):
        module = MultiScaleFFN(original(), mode='w8_only')
        x = torch.randn(2, 128).to(torch.bfloat16)
        g, u = F.linear(x.float(), module.gu_decoded).chunk(2, -1)
        expected = F.linear(F.silu(g)*u, module.down_decoded).to(x.dtype)
        with patch.object(core, 'encode_input', side_effect=AssertionError('must not encode')):
            torch.testing.assert_close(module(x), expected, rtol=0, atol=0)
        d = module.diagnostics()
        self.assertFalse(d['activation_encoding_applied'])
        self.assertEqual(sum(d['x_bin_counts']), 0)
        self.assertEqual(d['x_mean_probability'], 0.)
        self.assertEqual(d['z_encoding_nmse'], 0.)

    def test_dynamic64_fixed_ffn_matches_prior_range_reference(self):
        m = original()
        x = torch.randn(3, 128)
        old = RangeFFN(m, {'x': [1.]}, [1.], activation_policy='dynamic64',
                       weight_policy='legacy', kind='fixed', cycles=128, seed=2, layer=3)
        new = MultiScaleFFN(m, policy='dynamic64', cycles=128, seed=2, layer=3)
        torch.testing.assert_close(new(x), old(x), rtol=0, atol=0)

    def test_seed_reproducibility_and_independent_stage_generators(self):
        x = torch.randn(2, 128)
        a = MultiScaleFFN(original(), cycles=64, seed=7, layer=2)
        b = MultiScaleFFN(original(), cycles=64, seed=7, layer=2)
        self.assertEqual(a.rng_input.initial_seed(), 707015)
        self.assertEqual(a.rng_product.initial_seed(), 707016)
        self.assertIsNot(a.rng_input, a.rng_product)
        torch.testing.assert_close(a(x), b(x), rtol=0, atol=0)
        with self.assertRaises(ValueError):
            MultiScaleFFN(original(), cycles=0)


if __name__ == '__main__':
    torch.set_num_threads(4)
    unittest.main(verbosity=2)
