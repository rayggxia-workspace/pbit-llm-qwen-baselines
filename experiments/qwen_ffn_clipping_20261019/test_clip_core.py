"""CPU checks of endpoint semantics, range recovery and regression controls."""
import unittest

import torch
from torch import nn
from torch.nn import functional as F

from clip_core import (ClipFFN, MatrixSpec, RangeFFN, encode_clipped,
                       project_probability, round_up_pow2)


def original(width=64):
    generator = torch.Generator().manual_seed(55)
    module = nn.Module()
    for name in ('gate_proj', 'up_proj', 'down_proj'):
        layer = nn.Linear(width, width, bias=False)
        with torch.no_grad():
            layer.weight.copy_(torch.randn(width, width, generator=generator) / width ** .5)
        setattr(module, name, layer)
    return module


class Tests(unittest.TestCase):
    def test_true_one_and_255_over_256_are_distinct(self):
        value = torch.zeros(1, 64)
        value[0, :5] = torch.tensor([255/256, 1., 2., -1., -2.])
        p, decoded, scale = encode_clipped(value, 1.)
        torch.testing.assert_close(p[0, :5], torch.tensor([255/256, 1., 1., 1., 1.]), rtol=0, atol=0)
        torch.testing.assert_close(decoded[0, :5], torch.tensor([255/256, 1., 1., -1., -1.]), rtol=0, atol=0)
        legacy, _, _ = encode_clipped(value, scale, 'legacy')
        self.assertTrue(bool((legacy <= 255/256).all()))
        self.assertEqual(p[0, 5].item(), 0.)
        self.assertEqual(decoded[0, 5].item(), 0.)

    def test_pow2_rounds_up_and_preserves_exact_powers(self):
        value = torch.tensor([0., .25, .3, 1., 1.00001, 3., 4.])
        rounded = round_up_pow2(value)
        torch.testing.assert_close(rounded[1:], torch.tensor([.25, .5, 1., 2., 4., 4.]), rtol=0, atol=0)
        self.assertTrue(bool(torch.isfinite(rounded).all() and (rounded > 0).all()))
        self.assertTrue(bool((rounded >= value).all()))
        with self.assertRaises(ValueError):
            round_up_pow2(torch.tensor([-1.]))

    def test_cross_group_scales_and_signs_restore(self):
        value = torch.zeros(2, 128)
        value[:, :3] = torch.tensor([.5, -1., 3.])
        value[:, 64:67] = torch.tensor([8., -4., 32.])
        p, decoded, scale = encode_clipped(value, [.5, 8.])
        self.assertEqual(scale[0, 0].item(), .5)
        self.assertEqual(scale[0, 64].item(), 8.)
        probability = torch.ones(1, 128)
        weight = torch.ones(1, 128)
        spec = MatrixSpec(weight, probability, weight, weight, 'fixture')
        projected = project_probability(p, value.sign(), scale, spec, 'mean', 17)
        torch.testing.assert_close(projected, F.linear(decoded, weight))

    def test_dynamic_legacy_control_matches_values_and_rng_states(self):
        module = original()
        value = torch.randn(3, 64, generator=torch.Generator().manual_seed(19))
        for kind in ('fixed', 'dual', 'mean'):
            old = RangeFFN(module, {'x': [4.]}, [5.], activation_policy='dynamic64',
                           weight_policy='row64', kind=kind, cycles=31, seed=8, layer=3)
            new = ClipFFN(module, {'x': [4.]}, [5.], endpoint='legacy',
                          kind=kind, cycles=31, seed=8, layer=3)
            for _ in range(2):
                torch.testing.assert_close(new(value), old(value), rtol=0, atol=0)
            for name in ('input', 'product', 'weight_gu', 'weight_down'):
                self.assertTrue(torch.equal(getattr(new, 'rng_' + name).get_state(),
                                            getattr(old, 'rng_' + name).get_state()))

    def test_full_mean_ffn_matches_explicit_continuous_nonlinear_path(self):
        module = ClipFFN(original(128), {'x': [4., 5.]}, [7., 9.],
                         range_policy='fixed', fixed_x=[1., 2.], fixed_z=[.5, 1.],
                         x_factor=.75, z_factor=.5, pow2=True,
                         weight_pow2=True, kind='mean')
        value = torch.randn(2, 128, generator=torch.Generator().manual_seed(20))
        _, xq, _ = module.encode_stage(value, 'x')
        g, u = F.linear(xq, module.matrix_spec('gu').decoded).chunk(2, -1)
        z = F.silu(g) * u
        _, zq, _ = module.encode_stage(z, 'z')
        expected = F.linear(zq, module.matrix_spec('down').decoded)
        before = module.rng_input.get_state().clone()
        torch.testing.assert_close(module(value), expected, rtol=0, atol=0)
        self.assertTrue(torch.equal(before, module.rng_input.get_state()))
        stats = module.diagnostics()
        self.assertGreater(stats['x_clip_fraction'], 0.)
        self.assertGreater(stats['x_p_one_fraction'], 0.)
        self.assertGreater(stats['x_encoding_nmse'], 0.)

    def test_saturation_bias_is_not_reported_as_sampling_noise(self):
        value = torch.full((1, 64), 2.)
        p, decoded, scale = encode_clipped(value, .5)
        self.assertTrue(bool((p == 1).all()))
        torch.testing.assert_close(decoded, torch.full_like(value, .5))
        identity = torch.eye(64)
        spec = MatrixSpec(identity, identity, identity, identity, 'fixture')
        for seed in (0, 1):
            result = project_probability(p, value.sign(), scale, spec, 'dual', 11,
                torch.Generator().manual_seed(seed), torch.Generator().manual_seed(seed+3))
            torch.testing.assert_close(result, decoded, rtol=0, atol=0)
        self.assertEqual(((decoded-value).square().sum()/value.square().sum()).item(), .5625)

    def test_probability_one_shared_count_and_signed_weight(self):
        value = torch.zeros(2, 64)
        value[:, :2] = torch.tensor([3., -3.])
        p, _, scale = encode_clipped(value, 2.)
        wp = torch.zeros(2, 64)
        wp[:, :2] = 1.
        amplitude = torch.ones(2, 64) * 3.
        amplitude[1, 1] = -5.
        spec = MatrixSpec(wp*amplitude, wp, amplitude, wp*amplitude, 'fixture')
        for kind in ('fixed', 'dual'):
            result = project_probability(p, value.sign(), scale, spec, kind, 13,
                torch.Generator().manual_seed(1), torch.Generator().manual_seed(2))
            torch.testing.assert_close(result, torch.tensor([[0., 16.]]).expand(2, -1), rtol=0, atol=0)

    def test_weight_pot_keeps_same_original_w8_and_has_constant_one(self):
        module = original()
        with torch.no_grad():
            for projection in (module.gate_proj, module.up_proj, module.down_proj):
                projection.weight.fill_(2.)
        old = RangeFFN(module, {'x': [4.]}, [4.], weight_policy='row64')
        new = ClipFFN(module, {'x': [4.]}, [4.], weight_pow2=True)
        for name in ('gu', 'down'):
            old_spec, new_spec = old.matrix_spec(name), new.matrix_spec(name)
            torch.testing.assert_close(old_spec.reference_decoded, new_spec.reference_decoded, rtol=0, atol=0)
            torch.testing.assert_close(new_spec.decoded, new_spec.reference_decoded, rtol=0, atol=0)
            self.assertTrue(bool((new_spec.probability == 1).all()))
        self.assertEqual(new.diagnostics()['gu_weight_p_one_fraction'], 1.)

    def test_dynamic_factor_and_pow2_amplitudes(self):
        module = ClipFFN(original(128), {'x': [1., 1.]}, [1., 1.],
                         x_factor=.5, pow2=True, kind='mean')
        value = torch.zeros(1, 128)
        value[0, 0], value[0, 64] = 3., 9.
        p, decoded, scale = module.encode_stage(value, 'x')
        self.assertEqual(scale[0, 0].item(), 2.)
        self.assertEqual(scale[0, 64].item(), 8.)
        self.assertEqual(p[0, 0].item(), 1.)
        self.assertEqual(decoded[0, 64].item(), 8.)

    def test_invalid_parameters_and_scales_fail(self):
        for kwargs in ({'x_factor': 0}, {'z_factor': float('nan')},
                       {'range_policy': 'bad'}, {'endpoint': 'bad'}):
            with self.assertRaises(ValueError):
                ClipFFN(original(), {'x': [4.]}, [4.], **kwargs)
        for scale in (0., -1., float('inf')):
            with self.assertRaises(ValueError):
                encode_clipped(torch.zeros(1, 64), scale)


if __name__ == '__main__':
    torch.set_num_threads(4)
    unittest.main(verbosity=2)
