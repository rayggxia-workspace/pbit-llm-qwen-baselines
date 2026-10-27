import copy
import math
import unittest
from unittest.mock import patch

import torch
from torch import nn

from .pot64 import FORMAT, choose_exponents, quantize, export_weights
from qwen3.training.stochastic_nonlinear.core import (
    Config, TrainableFFN, NoiseKey, noise_context)
from qwen3.training.stochastic_nonlinear.checkpoint import ffn_state, load_ffn_state
from qwen3.and_direct.core import coefficient_table, COEFFICIENT_BITS


def original():
    module = nn.Module()
    for name in ('gate_proj', 'up_proj', 'down_proj'):
        setattr(module, name, nn.Linear(64, 64, bias=False))
    return module


def tables():
    return dict(x=[[4., 1., .25, .0625]], g=[4.], u=[4.])


class TestPoT64(unittest.TestCase):
    def setUp(self):
        torch.manual_seed(910)
        torch.set_num_threads(1)
        torch.backends.cuda.matmul.allow_tf32 = False

    def test_scalar_oracle_all_supported_widths_and_tile_layout(self):
        weight = torch.randn(128, 128)
        weight[:64, :64] *= .01
        weight[64:, 64:] *= 9
        for bits in (4, 6, 8, 9):
            codes, decoded, step = quantize(weight, bits)
            limit = 2**(bits-1)-1
            for row in range(2):
                for col in range(2):
                    tile = weight[row*64:(row+1)*64, col*64:(col+1)*64]
                    maximum = float(tile.abs().max())
                    exponent = math.ceil(math.log2(maximum/limit))
                    expected_step = 2.**exponent
                    self.assertEqual(float(step[row, col]), expected_step)
                    # Python's round is nearest-even; selected samples are independent of torch.round.
                    for rr, cc in ((0, 0), (13, 31), (63, 63)):
                        q = max(-limit, min(limit, round(float(tile[rr, cc])/expected_step)))
                        self.assertEqual(int(codes[row*64+rr, col*64+cc]), q)
                        self.assertEqual(float(decoded[row*64+rr, col*64+cc]), q*expected_step)
            self.assertTrue(bool((torch.frexp(step)[0] == .5).all()))

    def test_exponent_boundary_exact_and_one_float_above(self):
        for exponent in (-20, -10, 0, 10):
            boundary = torch.tensor(127.*2.**exponent)
            w = torch.zeros(64, 64); w[0, 0] = boundary
            self.assertEqual(int(choose_exponents(w)[0, 0]), exponent)
            w[0, 0] = torch.nextafter(boundary, torch.tensor(float('inf')))
            self.assertEqual(int(choose_exponents(w)[0, 0]), exponent+1)

    def test_zero_and_mixed_signs_round_to_even(self):
        q, decoded, step = quantize(torch.zeros(64, 64))
        self.assertEqual(float(step[0, 0]), 2.**-24)
        self.assertEqual(int(q.abs().sum()), 0)
        w = torch.zeros(64, 64); w[0, :6] = torch.tensor([.5, 1.5, 2.5, -.5, -1.5, -2.5])
        q, _, _ = quantize(w, exponents=torch.zeros(1, 1, dtype=torch.int8))
        self.assertEqual(q[0, :6].tolist(), [0, 2, 2, 0, -2, -2])

    def test_invalid_shapes_values_and_exponents(self):
        with self.assertRaises(ValueError): quantize(torch.zeros(65, 64))
        w = torch.zeros(64, 64); w[0, 0] = float('nan')
        with self.assertRaises(ValueError): quantize(w)
        with self.assertRaises(ValueError): quantize(torch.zeros(64, 64), exponents=[[.5]])
        with self.assertRaises(ValueError): quantize(torch.zeros(64, 64), exponents=[[121]])

    def test_frozen_quantizer_saturates_without_choosing_new_step(self):
        exponent = torch.tensor([[-10]], dtype=torch.int8)
        w = torch.full((64, 64), 2.)
        with patch('qwen3.weight_quantization.pot64.choose_exponents', side_effect=AssertionError('online max')):
            q, _, step = quantize(w, exponents=exponent)
        self.assertEqual(int(q.max()), 127)
        self.assertEqual(float(step[0, 0]), 2.**-10)

    def test_training_keeps_exponents_frozen_through_update_and_eval(self):
        module = TrainableFFN(original(), tables(), 0, Config(nonlinear_samples=32))
        before = {k: v.clone() for k, v in module.named_buffers() if k.endswith('weight_exponents')}
        opt = torch.optim.SGD(module.parameters(), lr=.01)
        x = torch.randn(3, 64)
        with patch('qwen3.weight_quantization.pot64.choose_exponents', side_effect=AssertionError('online max')):
            with noise_context(module, NoiseKey(4)):
                module(x).square().mean().backward()
            opt.step()
            with noise_context(module.eval(), NoiseKey(5)):
                self.assertTrue(bool(torch.isfinite(module(x)).all()))
        for k, v in before.items(): self.assertTrue(torch.equal(v, dict(module.named_buffers())[k]))

    def test_all_three_projections_use_the_stored_exponents(self):
        t = tables(); t['weight_exponents'] = dict(gu=[[-8], [-9]], down=[[-10]])
        module = TrainableFFN(original(), t, 0)
        self.assertEqual(module.gu_weight_exponents.tolist(), [[-8], [-9]])
        self.assertEqual(module.down_weight_exponents.tolist(), [[-10]])
        with noise_context(module, NoiseKey(3)):
            module(torch.randn(2, 64)).square().sum().backward()
        self.assertTrue(all(p.grad is not None for p in module.parameters()))

    def test_export_and_frozen_inference_replay_equal(self):
        module = TrainableFFN(original(), tables(), 0)
        with torch.no_grad():
            for p in module.parameters(): p.add_(torch.randn_like(p)*.02)
        exported = export_weights(module)
        self.assertEqual(exported['format'], FORMAT)
        self.assertEqual(exported['gu_codes'].dtype, torch.int8)
        other = copy.deepcopy(module)
        for name, projections in (('gu', ('gate_proj','up_proj')), ('down', ('down_proj',))):
            expanded = exported[name+'_exponents'].int().repeat_interleave(64, 0).repeat_interleave(64, 1)
            weight = torch.ldexp(exported[name+'_codes'].float(), expanded)
            chunks = weight.chunk(len(projections), 0)
            with torch.no_grad():
                for projection, chunk in zip(projections, chunks): getattr(other, projection).weight.copy_(chunk)
        x = torch.randn(2, 64)
        with noise_context(module, NoiseKey(11)), noise_context(other, NoiseKey(11)):
            self.assertTrue(torch.equal(module(x), other(x)))

    def test_restore_coefficients_are_exact_shifts(self):
        lsb = torch.tensor([[2.**-10, 2.**-12]])
        g, u = torch.tensor([4., 8.]), torch.tensor([8., 4.])
        coeff, exponent, real = coefficient_table(lsb, g, u)
        self.assertTrue(bool(((coeff & (coeff-1)) == 0).all()))
        reconstructed = torch.ldexp(coeff.double(), exponent[:, None]-COEFFICIENT_BITS)
        self.assertTrue(torch.equal(reconstructed, real))
        with self.assertRaises(ValueError): coefficient_table(torch.tensor([[.003]]), torch.tensor([4.]), torch.tensor([4.]))

    def test_checkpoint_rejects_changed_exponent_before_mutation(self):
        module = TrainableFFN(original(), tables(), 0)
        saved = ffn_state(module)
        saved['']['gu_weight_exponents'][0, 0] += 1
        before = module.gu_weight_exponents.clone()
        with self.assertRaises(ValueError): load_ffn_state(module, saved)
        self.assertTrue(torch.equal(before, module.gu_weight_exponents))

    def test_legacy_scale_format_not_accepted(self):
        with self.assertRaises(ValueError): Config(weight_format='maxabs-over-127')

    def test_w9_training_and_export_use_eight_magnitude_bits(self):
        module = TrainableFFN(original(), tables(), 0,
                              Config(weight_bits=9, nonlinear_samples=32))
        with noise_context(module, NoiseKey(13)):
            module(torch.randn(3, 64)).square().mean().backward()
        self.assertTrue(all(p.grad is not None and bool(torch.isfinite(p.grad).all())
                            for p in module.parameters()))
        exported = export_weights(module)
        self.assertEqual(exported['total_weight_bits'], 9)
        self.assertEqual(exported['gu_codes'].dtype, torch.int16)
        self.assertLessEqual(int(exported['gu_codes'].abs().max()), 255)


if __name__ == '__main__':
    unittest.main()
