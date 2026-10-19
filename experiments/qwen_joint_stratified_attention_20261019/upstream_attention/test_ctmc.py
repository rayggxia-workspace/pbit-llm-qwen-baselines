"""Small-state finite-time tests: stationary probabilities alone cannot detect IID."""
import math
import unittest

try:
    import torch
except ImportError:
    torch = None

if torch is not None:
    if __package__:
        from .ctmc import CTMCEventLimitError, ct_mc_indices
    else:
        from ctmc import CTMCEventLimitError, ct_mc_indices


@unittest.skipIf(torch is None, "torch is not installed in this Python environment")
class TestCTMC(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old_threads = torch.get_num_threads()
        torch.set_num_threads(2)

    @classmethod
    def tearDownClass(cls):
        torch.set_num_threads(cls.old_threads)

    @staticmethod
    def rng(seed):
        return torch.Generator(device="cpu").manual_seed(seed)

    def test_binary_short_time_is_not_iid(self):
        rows = 8192
        indices, stats = ct_mc_indices(
            torch.zeros(rows, 2), 1, 0.0, 0.05, generator=self.rng(1)
        )
        # Independent two-state generator: Q=[[-.5,.5],[.5,-.5]], p(0)=[1,0].
        expected = (1.0 - math.exp(-0.05)) / 2.0
        observed = (indices[:, 0] == 1).float().mean().item()
        tolerance = 5 * math.sqrt(expected * (1 - expected) / rows) + 0.001
        self.assertAlmostEqual(observed, expected, delta=tolerance)
        self.assertLess(observed, 0.1)  # A target-Softmax IID replacement gives 0.5.
        self.assertFalse(stats["iid_fallback"])

    def test_three_state_transient_matches_generator_exponential(self):
        rows, time = 8192, 0.7
        logits = torch.tensor([0.9, -0.3, 0.4], dtype=torch.float64)
        rate = torch.sigmoid(logits[1:] - logits[0])
        q = torch.zeros(3, 3, dtype=torch.float64)
        q[0, 1:] = rate
        q[1:, 0] = 1 - rate
        q.diagonal().copy_(-q.sum(-1))
        expected = torch.matrix_exp(time * q)[0]
        indices, _ = ct_mc_indices(
            logits.expand(rows, -1), 1, 0.0, time, generator=self.rng(22)
        )
        observed = torch.bincount(indices[:, 0], minlength=3).double() / rows
        self.assertTrue(torch.all((observed - expected).abs() < 0.018))

    def test_long_burn_matches_stationary_distribution(self):
        rows = 8192
        logits = torch.tensor([0.9, -0.3, 0.4])
        indices, _ = ct_mc_indices(
            logits.expand(rows, -1), 1, 16.0, 4.0, generator=self.rng(8)
        )
        observed = torch.bincount(indices[:, 0], minlength=3).float() / rows
        self.assertTrue(torch.all((observed - logits.softmax(-1)).abs() < 0.018))

    def test_close_samples_keep_markov_correlation(self):
        indices, stats = ct_mc_indices(
            torch.zeros(2048, 2), 16, 16.0, 0.05, generator=self.rng(18)
        )
        expected_repeat = (1 + math.exp(-0.05)) / 2
        observed = (indices[:, 1:] == indices[:, :-1]).float().mean().item()
        self.assertAlmostEqual(observed, expected_repeat, delta=0.014)
        self.assertGreater(observed, 0.94)
        self.assertAlmostEqual(observed, stats["adjacent_repeat_fraction"])

    def test_masked_padding_and_nonzero_reference_index(self):
        logits = torch.tensor([
            [0.0, -torch.inf, -1.0, -torch.inf],
            [-torch.inf, 2.0, -torch.inf, 1.0],
            [-torch.inf, -torch.inf, 5.0, -torch.inf],
        ])
        indices, stats = ct_mc_indices(logits, 128, 16, 4, generator=self.rng(5))
        self.assertEqual(indices.dtype, torch.long)
        self.assertEqual(tuple(indices.shape), (3, 128))
        self.assertTrue(torch.isfinite(logits).gather(1, indices).all())
        self.assertTrue((indices[2] == 2).all())
        self.assertEqual(stats["valid_categories"], 5)
        self.assertEqual(stats["padding_categories"], 7)
        self.assertEqual(stats["dropped_events"], 0)

    def test_one_category_needs_no_events(self):
        indices, stats = ct_mc_indices(torch.tensor([[3.0]]), 1024, 16, 4, max_events=1)
        self.assertTrue((indices == 0).all())
        self.assertEqual(stats["event_columns_generated"], 0)
        self.assertEqual(stats["zero_birth_rows"], 1)

    def test_underflowed_birth_rates_return_reference(self):
        indices, stats = ct_mc_indices(torch.tensor([[0.0, -1000.0]]), 64, 16, 4)
        self.assertTrue((indices == 0).all())
        self.assertEqual(stats["birth_sum_max"], 0.0)

    def test_budget_sweep_shares_exact_sample_prefix(self):
        logits = torch.tensor([
            [0.3, -0.2, 1.0, -torch.inf],
            [0.0, 0.0, 0.0, -1.0],
            [-torch.inf, 2.0, -torch.inf, 1.0],
        ])
        longest, long_stats = ct_mc_indices(logits, 1024, 16, 4, generator=self.rng(73))
        self.assertGreater(long_stats["coverage_appends"], 0)
        for samples in (32, 64, 128, 256, 512, 1024):
            with self.subTest(samples=samples):
                indices, stats = ct_mc_indices(logits, samples, 16, 4, generator=self.rng(73))
                self.assertTrue(torch.equal(indices, longest[:, :samples]))
                self.assertEqual(stats["dropped_rows"], 0)
                self.assertFalse(stats["event_cap_reached"])

    def test_reproducibility_and_generator_state_advances(self):
        logits = torch.zeros(4, 5)
        first_generator = self.rng(7)
        first, _ = ct_mc_indices(logits, 32, 16, 4, generator=first_generator)
        same, _ = ct_mc_indices(logits, 32, 16, 4, generator=self.rng(7))
        continued, _ = ct_mc_indices(logits, 32, 16, 4, generator=first_generator)
        self.assertTrue(torch.equal(first, same))
        self.assertFalse(torch.equal(first, continued))

    def test_event_cap_fails_without_truncation_or_fallback(self):
        with self.assertRaises(CTMCEventLimitError) as caught:
            ct_mc_indices(torch.zeros(1, 2), 1, 1000000, 1, generator=self.rng(3), max_events=1)
        stats = caught.exception.stats
        self.assertTrue(stats["event_cap_reached"])
        self.assertEqual(stats["event_columns_generated"], 1)
        self.assertEqual(stats["uncovered_rows"], 1)
        self.assertEqual(stats["dropped_events"], 0)
        self.assertFalse(stats["iid_fallback"])

    def test_invalid_inputs_are_rejected(self):
        for logits in (
            torch.full((1, 2), -torch.inf), torch.tensor([[torch.nan, 0.0]]),
            torch.tensor([[torch.inf, 0.0]]), torch.zeros(2),
            torch.empty(0, 2), torch.zeros(1, 2, dtype=torch.long),
        ):
            with self.subTest(logits=logits):
                with self.assertRaises(ValueError):
                    ct_mc_indices(logits, 4, 0, 1)
        for args in ((0, 0, 1), (True, 0, 1), (4, -1, 1), (4, 0, 0),
                     (4, float("nan"), 1), (4, 0, float("inf"))):
            with self.subTest(args=args):
                with self.assertRaises(ValueError):
                    ct_mc_indices(torch.zeros(1, 2), *args)


if __name__ == "__main__":
    unittest.main()
