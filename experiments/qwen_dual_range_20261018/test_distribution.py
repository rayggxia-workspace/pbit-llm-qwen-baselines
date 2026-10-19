"""CPU endpoint and clipping checks; no model/data/GPU required."""
import unittest

import torch

from analyze_distribution import Accumulator, activation_measure, probability_measure


class Tests(unittest.TestCase):
    def test_activation_bin_endpoints_and_quantiles(self):
        q = torch.tensor([0, 1, 3, 4, 15, 16, 63, 64, 127, 128, 255.])
        p = q/256
        measured = activation_measure(q, p, q, torch.tensor(256.))
        acc = Accumulator(*measured)
        acc.add(*measured)
        result = acc.export()
        self.assertEqual([b['count'] for b in result['bins']], [1, 2, 2, 2, 2, 2])
        self.assertEqual(result['magnitude_code_quantiles']['50'], 16)
        self.assertEqual(result['magnitude_code_quantiles']['100'], 255)
        self.assertAlmostEqual(result['mean_magnitude_code'], q.mean().item(), places=5)
        self.assertEqual(result['encoding_nmse'], 0.)
        self.assertEqual(result['clipping_fraction'], 0.)

    def test_weight_probability_boundaries_legacy_not_a8(self):
        p = torch.tensor([0., 1/127, 1/64, 1/16, 1/4, 1/2, 1.])
        measured = probability_measure(p)
        acc = Accumulator(*measured)
        acc.add(*measured)
        result = acc.export(False)
        self.assertEqual([b['count'] for b in result['bins']], [1, 2, 1, 1, 1, 1])
        self.assertAlmostEqual(result['mean_probability'], p.double().mean().item())

    def test_clipping_energy_and_sign(self):
        value = torch.tensor([-4., -1., 0., 1., 4.])
        scale = torch.tensor(256/255)  # Maximum represented magnitude is one.
        decoded = value.clamp(-1, 1)
        p = decoded.abs()/scale
        measured = activation_measure(value, p, decoded, scale)
        acc = Accumulator(*measured)
        acc.add(*measured)
        result = acc.export()
        self.assertAlmostEqual(result['clipping_fraction'], 2/5)
        self.assertAlmostEqual(result['clipped_value_energy_fraction'], 32/34)
        self.assertAlmostEqual(result['clipping_sse_over_signal_energy'], 18/34)
        self.assertAlmostEqual(result['encoding_nmse'], 18/34)

    def test_aggregate_is_count_weighted(self):
        acc = None
        for n, q in ((3, 0), (1, 128)):
            value = torch.full((n,), float(q))
            measured = activation_measure(value, value/256, value, torch.tensor(256.))
            if acc is None:
                acc = Accumulator(*measured)
            acc.add(*measured)
        result = acc.export()
        self.assertEqual(result['values'], 4)
        self.assertEqual(result['zero_code_fraction'], .75)
        self.assertEqual(result['mean_probability'], .125)


if __name__ == '__main__':
    unittest.main()
