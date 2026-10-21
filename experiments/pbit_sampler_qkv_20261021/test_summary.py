import unittest
from summarize import gather,crossing,summarize_rows


def records(method='winner0',omit=None):
    return [dict(method=method,seed=seed,curves=[dict(burn=32,samples=s,
        normalized_error_per_repeat=[error]*8,logical_updates_per_repeat=[32+s]*8,
        pbit_draws_per_repeat=[(32+s)*512]*8,extra_fair_bits_per_repeat=[s*2.]*8,
        rank_calls_per_repeat=[s]*8) for s,error in ((64,.02),(128,.01),(256,.003))]) for seed in range(3) if seed!=omit]


class SummaryChecks(unittest.TestCase):
    def test_all_seeds_and_duplicate_guard(self):
        with self.assertRaises(ValueError):gather(records(omit=1))
        with self.assertRaises(ValueError):gather(records()+records()[:1])

    def test_burn_and_cost_in_grid_crossing(self):
        curves=gather(records())['winner0'];hit=crossing(curves,'winner0',128)
        self.assertEqual(hit['samples'],256)
        self.assertEqual(hit['logical_updates_mean'],288)
        self.assertEqual(hit['pbit_draws_mean'],288*512)
        self.assertIsNone(crossing(curves,'winner0',512))

    def test_missing_is_censored_and_wave_cost(self):
        curves=gather(records())
        rows=[dict(row=dict(context=2048,pool='screen512'),candidates=512,curves=curves)]
        summary=summarize_rows(rows)
        s=next(g for g in summary if g['target_iid_samples']==128)
        self.assertEqual(s['median_64pbit_service_wave_lower_bound'],288*8)
        s=next(g for g in summary if g['target_iid_samples']==512)
        self.assertEqual(s['mean_gate_reached'],0)
        self.assertIsNone(s['median_observed_updates'])

    def test_iid_does_not_use_lucky_shorter_budget(self):
        curves=[dict(burn=0,samples=s,normalized_mse=.00001,mc_normal_95_high=.00001) for s in (64,128,512)]
        self.assertEqual(crossing(curves,'iid',128)['samples'],128)


if __name__=='__main__':unittest.main()
