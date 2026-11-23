"""Independent small exact oracles; no GPU or trained weights required."""
import unittest
from fractions import Fraction
from itertools import product
import numpy as np


class MathChecks(unittest.TestCase):
    def test_power_of_two_gate_preserves_nonzero_small_thresholds(self):
        for q, k in product([0, 1, 3, 13, 128, 255, 256], [0, 1, 2, 4, 6]):
            hits = sum(lo < q and hi == 0 for lo, hi in product(range(256), range(1 << k)))
            self.assertEqual(Fraction(hits, 256 * (1 << k)), Fraction(q, 256 * (1 << k)))
            self.assertEqual(Fraction(hits, 256 * (1 << k)) * (1 << k), Fraction(q, 256))

    def test_normalized_categorical_and_bernoulli_unbiased(self):
        mass = [1, 0, 3, 2]
        sign = [1, 1, -1, 1]
        w = [3, 7, -2, 5]
        cdf = np.cumsum(mass)
        got = [0] * 4
        for ticket in range(sum(mass)):
            got[int(np.searchsorted(cdf, ticket, side='right'))] += 1
        self.assertEqual(got, mass)
        exact = sum(m * s * v for m, s, v in zip(mass, sign, w))
        categorical = sum(Fraction(sum(mass), sum(mass)) * sign[i] * w[i]
                          for i in np.searchsorted(cdf, np.arange(sum(mass)), side='right'))
        bernoulli = sum(Fraction(m, sum(mass)) * sum(mass) * s * v
                        for m, s, v in zip(mass, sign, w))
        self.assertEqual(categorical, exact)
        self.assertEqual(bernoulli, exact)

    def test_counted_selected_rows_equal_event_replay(self):
        bits = np.array([[1, 0, 1, 0], [0, 0, 1, 0], [1, 0, 0, 0]])
        w = np.array([[2, 99, -3, 88], [7, -11, 5, 13]])
        counts = bits.sum(0)
        selected = np.flatnonzero(counts)
        self.assertEqual(selected.tolist(), [0, 2])
        np.testing.assert_array_equal(w[:, selected] @ counts[selected], (w @ bits.T).sum(1))

    def test_record_fields_do_not_overlap(self):
        for index, count, shift, negative in product([0, 63, 64, 2559], [1, 64, 1024], [0, 2, 4, 6], [0, 1]):
            word = index | count << 12 | shift << 23 | negative << 26
            self.assertEqual((word & 4095, (word >> 12) & 2047, (word >> 23) & 7, (word >> 26) & 1),
                             (index, count, shift, negative))


if __name__ == '__main__':
    unittest.main()
