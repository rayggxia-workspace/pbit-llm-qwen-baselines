"""CPU invariants/statistical checks; no checkpoint/data downloads."""
import unittest
from unittest.mock import patch

import torch
from torch import nn
from torch.nn import functional as F

from range_core import (MatrixSpec, RangeFFN, encode_input, make_matrix_spec,
                        project_counts, project_probability, shared_counts)


def original():
    torch.manual_seed(55)
    module = nn.Module()
    for name in ('gate_proj', 'up_proj', 'down_proj'):
        setattr(module, name, nn.Linear(64, 64, bias=False))
    return module


class Tests(unittest.TestCase):
    def test_dynamic_a8_endpoints_sign_and_zero(self):
        x = torch.zeros(2, 128)
        x[0, :4] = torch.tensor([-3., 3., -1., 1.])
        x[0, 64:68] = torch.tensor([8., -8., 4., -4.])
        p, decoded, scale = encode_input(x, None, 'dynamic64')
        self.assertTrue(bool((p >= 0).all() and (p <= 255/256).all()))
        torch.testing.assert_close(p * 256, (p * 256).round())
        torch.testing.assert_close(decoded[0, [0, 1, 64, 65]], x[0, [0, 1, 64, 65]])
        self.assertTrue(bool((decoded[1] == 0).all() and torch.isfinite(scale).all()))
        self.assertTrue(bool((scale > 0).all()))

    def test_weight_reference_unchanged_and_row64_a8(self):
        torch.manual_seed(99)
        w = torch.randn(128, 128) * torch.arange(1, 129)[:, None]
        old = make_matrix_spec(w, 'legacy')
        ideal = make_matrix_spec(w, 'row64_ideal')
        strict = make_matrix_spec(w, 'row64')
        torch.testing.assert_close(ideal.reference_decoded, old.reference_decoded, rtol=0, atol=0)
        torch.testing.assert_close(ideal.decoded, old.decoded, atol=2e-5, rtol=2e-6)
        torch.testing.assert_close(strict.probability * 256, (strict.probability * 256).round())
        self.assertLessEqual(strict.probability.max().item(), 255/256)
        self.assertGreaterEqual(ideal.probability.mean().item(), old.probability.mean().item())
        self.assertTrue(bool((ideal.probability.max(-1).values == 1).all()))
        torch.testing.assert_close(strict.decoded, strict.probability * strict.amplitude)
        zero = make_matrix_spec(torch.zeros(64, 64), 'row64')
        self.assertTrue(bool((zero.decoded == 0).all() and torch.isfinite(zero.probability).all()))

    def test_mean_projection_restores_different_scales(self):
        torch.manual_seed(32)
        x = torch.randn(2, 128)
        p, xq, scale = encode_input(x, None, 'dynamic64')
        spec = make_matrix_spec(torch.randn(64, 128), 'row64')
        actual = project_probability(p, x.sign(), scale, spec, 'mean', 128)
        torch.testing.assert_close(actual, F.linear(xq, spec.decoded))

    def test_counts_zero_one_and_signed_amplitude(self):
        p = torch.zeros(3, 64)
        p[:, :2] = 1
        sign = torch.ones_like(p)
        sign[:, 1] = -1
        scale = torch.ones_like(p) * 2
        wp = torch.zeros(2, 64)
        wp[:, :2] = 1
        amplitude = torch.ones(2, 64) * 3
        amplitude[1, 1] = -5
        spec = MatrixSpec(wp*amplitude, wp, amplitude, wp*amplitude, 'fixture')
        for kind in ('fixed', 'dual'):
            y = project_probability(p, sign, scale, spec, kind, 31,
                torch.Generator().manual_seed(1), torch.Generator().manual_seed(2))
            torch.testing.assert_close(y, torch.tensor([[0., 16.]]).expand(3, -1))

    def test_shared_a_covariance_and_dual_extra_variance(self):
        # Shared A threshold creates covariance; independent W adds only its
        # conditional variance. Signed cancellations must not erase that term.
        n, cycles = 16000, 64
        p = torch.zeros(n, 64)
        p[:, 0], p[:, 1] = .25, .5
        sign = torch.ones_like(p)
        scale = torch.ones_like(p)
        scale[:, 0], scale[:, 1] = 2., 3.
        wp = torch.zeros(1, 64)
        wp[0, 0], wp[0, 1] = .3, .7
        amp = torch.zeros(1, 64)
        amp[0, 0], amp[0, 1] = 4., -2.
        spec = MatrixSpec(wp*amp, wp, amp, wp*amp, 'fixture')
        counts = shared_counts(p, cycles, torch.Generator().manual_seed(33), 64)
        fixed = project_counts(counts, sign, scale, spec, 'fixed', cycles, None)[:, 0]
        dual = project_counts(counts, sign, scale, spec, 'dual', cycles,
                              torch.Generator().manual_seed(34))[:, 0]
        prob = torch.tensor([.25, .5], dtype=torch.float64)
        c = torch.tensor([8., -6.], dtype=torch.float64)
        r = torch.tensor([.3, .7], dtype=torch.float64)
        covariance = torch.minimum(prob[:, None], prob[None, :]) - prob[:, None]*prob[None, :]
        mean = (c*r*prob).sum().item()
        fixed_var = ((c*r) @ covariance @ (c*r) / cycles).item()
        extra = (c.square()*prob*r*(1-r)).sum().item()/cycles
        self.assertLess(abs(fixed.mean().item()-mean), .025)
        self.assertLess(abs(dual.mean().item()-mean), .025)
        self.assertLess(abs(fixed.var(unbiased=False).item()-fixed_var), .008)
        self.assertLess(abs(dual.var(unbiased=False).item()-(fixed_var+extra)), .02)

    def test_full_mean_ffn_and_scope_dispatch(self):
        m = RangeFFN(original(), {'x': [4.]}, [4.], activation_policy='dynamic64',
                     weight_policy='row64', kind='mean')
        x = torch.randn(2, 64)
        _, xq, _ = encode_input(x, m.scale_x, 'dynamic64')
        g, u = F.linear(xq, m.matrix_spec('gu').decoded).chunk(2, -1)
        z = F.silu(g)*u
        _, zq, _ = encode_input(z, m.scale_z, 'dynamic64')
        torch.testing.assert_close(m(x), F.linear(zq, m.matrix_spec('down').decoded))
        self.assertEqual(m.diagnostics()['calls'], 1)
        for scope, wanted in (('gu', ['dual', 'mean']), ('down', ['mean', 'dual']),
                               ('all', ['dual', 'dual'])):
            m = RangeFFN(original(), {'x': [4.]}, [4.], kind='dual', scope=scope)
            seen = []
            def fake(p, sign, scale, spec, kind, *args, **kwargs):
                seen.append(kind)
                return F.linear(sign*scale*p, spec.decoded)
            with patch('range_core.project_probability', fake):
                m(x)
            self.assertEqual(seen, wanted)

    def test_reproducibility_and_generators_not_consumed_by_mean(self):
        x = torch.randn(2, 64)
        a = RangeFFN(original(), {'x': [4.]}, [4.], kind='dual', seed=2)
        b = RangeFFN(original(), {'x': [4.]}, [4.], kind='dual', seed=2)
        torch.testing.assert_close(a(x), b(x), atol=0, rtol=0)
        m = RangeFFN(original(), {'x': [4.]}, [4.], kind='mean')
        state = m.rng_input.get_state().clone()
        m(x)
        self.assertTrue(torch.equal(state, m.rng_input.get_state()))


if __name__ == '__main__':
    torch.set_num_threads(4)
    unittest.main(verbosity=2)
