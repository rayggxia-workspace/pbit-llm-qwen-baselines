import unittest
from unittest.mock import patch
import torch
from torch import nn
from torch.nn import functional as F
from core import encode_fixed
from run_sz import SzFFN, suite


def module(variant='sz_group', backend='gaussian', cycles=256):
    original = nn.Module()
    for name in ('gate_proj', 'up_proj', 'down_proj'):
        setattr(original, name, nn.Linear(64, 64, bias=False))
    torch.manual_seed(42)
    with torch.no_grad():
        for p in original.parameters():
            p.copy_(torch.randn_like(p) * .1)
    return SzFFN(original, dict(x=[4.], g=[4.], u=[4.]), 'dual_exact',
                 cycles=cycles, variant=variant, backend=backend, sz=[2.])


class Tests(unittest.TestCase):
    def test_suite_is_unique_and_covers_requested_lengths(self):
        configs = suite()
        self.assertEqual(len(configs), 32)
        self.assertEqual(len({tuple(c.values()) for c in configs}), 32)
        self.assertEqual({c['cycles'] for c in configs}, {256, 1024, 4096})

    def test_sz_no_sampling_limit_matches_direct_quantized_swiglu(self):
        # Removes sampling alone to catch a missing scale factor or sign error.
        m = module()
        x = torch.randn(4, 64) * .2
        _, xq = encode_fixed(x, m.scale_x, 12)
        g, u = F.linear(xq, m.gu_decoded).chunk(2, -1)
        z = F.silu(g) * u
        _, zq = encode_fixed(z, m.scale_z, 12)
        expected = F.linear(zq, m.down_decoded)
        def projection(counts, sign, scale, name, generator, stochastic_weight):
            return F.linear(sign*scale*counts/m.cycles, getattr(m, name+'_decoded'))
        with patch('run_sz.sample_counts', lambda p,t,r: p*t), patch.object(m, '_count_projection', projection):
            actual = m(x)
        torch.testing.assert_close(actual, expected, atol=2e-7, rtol=2e-5)

    def test_matched_gu_preserves_old_product_mean_before_reencoding(self):
        g = torch.randn(2000)
        u = torch.randn(2000)
        pg, gq = encode_fixed(g, torch.tensor(4.), 12)
        pu, uq = encode_fixed(u, torch.tensor(8.), 12)
        old = gq.sign()*uq.sign()*32*pg*torch.sigmoid(gq)*pu
        torch.testing.assert_close(old, F.silu(gq)*uq)

    def test_exact_conditional_binomial_small_event_moments(self):
        m = module(backend='binomial')
        with torch.no_grad():
            m.down_codes.zero_()
            m.down_codes[0, 0] = 32
            m.down_tile_scales.fill_(.25)
        n = 20000
        counts = torch.zeros(n, 64)
        counts[:, 0] = 2
        out = m._count_projection(counts, torch.ones_like(counts), torch.ones(64),
                                  'down', torch.Generator().manual_seed(9), True)[:, 0]
        p = 32/127
        amplitude = 127*.25/256
        mean, variance = 2*p*amplitude, 2*p*(1-p)*amplitude**2
        self.assertLess(abs(out.mean().item()-mean), .003)
        self.assertLess(abs(out.var().item()-variance), .0003)
        self.assertTrue(bool((out >= 0).all()))


if __name__ == '__main__':
    torch.set_num_threads(4)
    unittest.main(verbosity=2)
