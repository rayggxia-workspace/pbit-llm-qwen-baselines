import json
import unittest
from pathlib import Path

from .model import Catalog, ThresholdBank, compare8, sigmoid_code


class Contracts(unittest.TestCase):
    def test_every_probability_has_exact_uniform_count(self):
        for q in range(257):
            self.assertEqual(sum(compare8(r, q) for r in range(256)), q)

    def test_signed_endpoints_and_monotonicity(self):
        q = [sigmoid_code(i) for i in range(-128, 128)]
        self.assertEqual((q[0], q[128], q[-1]), (0, 128, 256))
        self.assertEqual(q, sorted(q))

    def test_invalid_values_are_not_silently_quantized(self):
        for c in [-129, 128, 0.5, True]:
            with self.assertRaises(ValueError):
                sigmoid_code(c)
        for r, q in [(-1, 128), (256, 128), (0, 257), (True, 128)]:
            with self.assertRaises(ValueError):
                compare8(r, q)

    def test_matches_existing_sigmoid_table(self):
        from ..service import SigmoidTable
        ref = SigmoidTable(.125, -128, 127)
        self.assertEqual([sigmoid_code(c) for c in range(-128, 128)], list(ref.values.values()))

    def test_bank_requires_complete_configuration(self):
        bank = ThresholdBank(3, 2)
        with self.assertRaises(RuntimeError):
            bank.sample([0] * 3)
        self.assertEqual(bank.configure([-128, 0, 127])['load_cycles'], 2)
        self.assertEqual(bank.sample([0, 128, 255]), (0, 0, 1))
        self.assertEqual(bank.sample([0, 127, 255]), (0, 1, 1))

    def test_no_implicit_random_broadcast(self):
        bank = ThresholdBank(2, 1)
        bank.configure([0, 0])
        with self.assertRaises(ValueError):
            bank.sample([100])

    def test_q8_endpoint_loss_requires_explicit_acknowledgement(self):
        with self.assertRaises(ValueError):
            ThresholdBank(2, 1, 8)
        bank = ThresholdBank(2, 1, 8, clip_p1=True)
        info = bank.configure([127, 0])
        self.assertEqual(info['thresholds'], (255, 128))
        self.assertEqual(info['p1_clipped_nodes'], 1)
        self.assertEqual(bank.sample([255, 127]), (0, 1))

    def test_failed_configuration_preserves_previous_transaction(self):
        bank = ThresholdBank(2, 1)
        bank.configure([-128, 127])
        with self.assertRaises(ValueError):
            bank.configure([0, 128])
        self.assertEqual(bank.sample([0, 255]), (0, 1))


class Costs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = Catalog()

    def test_frozen_source_coverage(self):
        source = json.loads((Path(__file__).parent / 'evidence/38427136_SUMMARY.json').read_text(encoding='utf-8'))
        self.assertEqual(self.c.data['designs'], source['designs'])
        self.assertEqual(len(self.c.data['designs']), 10)
        self.assertEqual(self.c.data['source']['windows'], 150)
        for d in self.c.data['designs']:
            self.assertGreaterEqual(d['setup_slack_ns'], 0)
            self.assertGreaterEqual(d['hold_slack_ns'], 0)
            self.assertEqual(set(d['modes']), {'idle', 'fixed50', 'random', 'sweep', 'cadence64'})

    def test_single_full_call_reproduces_measured_energy(self):
        for corner in ['ss', 'tt']:
            r = self.c.estimate_window(nodes=1, corner=corner)
            p = self.c.component('pbit_sample8_reg', corner)
            self.assertAlmostEqual(r['pJ_per_output_bit'], p['power_W'] * 1e4, places=12)
            self.assertAlmostEqual(r['raw_cell_area_um2'], 405.36, places=8)

    def test_replication_and_single_area_scaling(self):
        r = self.c.estimate_window(nodes=128)
        self.assertAlmostEqual(r['equivalent55_cell_area_mm2'], .0420277248)
        self.assertAlmostEqual(r['average_power_W'], 128 * 15.026666666666666e-6)
        self.assertNotIn('PRNG', r)
        self.assertTrue(any('PRNG' in v for v in r['excludes']))

    def test_field_reuse_requires_retention_contract(self):
        with self.assertRaises(ValueError):
            self.c.estimate_window(samples_per_configuration=64)
        r = self.c.estimate_window(samples_per_configuration=64, inputs_held=True)
        self.assertEqual(r['input_retention'], 'external_existing_required')
        self.assertEqual(r['sample_cycles'], 64)
        self.assertEqual(r['threshold_storage_bits'], 0)

    def test_shared_bank_does_not_claim_full_rate_during_load(self):
        r = self.c.estimate_window('shared_lut_cached', nodes=128, lut_lanes=1)
        self.assertEqual(r['load_cycles'], 128)
        self.assertEqual(r['latency_first_output_cycles'], 129)
        self.assertEqual(r['outputs'], 128)
        self.assertAlmostEqual(r['effective_per_node_Msample_s'], 100 / 129)
        self.assertIn('no_array_PPA', r['evidence'])

    def test_shared_more_luts_reduce_load_time_but_increase_area(self):
        a = self.c.estimate_window('shared_lut_cached', lut_lanes=1, samples_per_configuration=64)
        b = self.c.estimate_window('shared_lut_cached', lut_lanes=8, samples_per_configuration=64)
        self.assertLess(a['equivalent55_cell_area_mm2'], b['equivalent55_cell_area_mm2'])
        self.assertGreater(a['total_cycles'], b['total_cycles'])
        self.assertEqual(b['threshold_storage_bits'], 128 * 9)

    def test_shared_q8_is_not_falsely_discounted_from_unmeasured_bank(self):
        with self.assertRaises(ValueError):
            self.c.estimate_window('shared_lut_cached', storage_bits=8)
        a = self.c.estimate_window('shared_lut_cached')
        b = self.c.estimate_window('shared_lut_cached', storage_bits=8, clip_p1=True)
        self.assertEqual(a['total_window_J'], b['total_window_J'])
        self.assertEqual(a['equivalent55_cell_area_mm2'], b['equivalent55_cell_area_mm2'])
        self.assertEqual(b['threshold_storage_bits'], 1024)
        self.assertEqual(b['p1_max_absolute_probability_error_from_clipping'], 1 / 256)

    def test_baseline_and_increment_energy_close(self):
        r = self.c.estimate_window('shared_lut_cached', samples_per_configuration=64)
        self.assertAlmostEqual(r['total_window_J'], r['baseline_clock_and_leakage_J'] + sum(r['incremental_operation_J'].values()))
        self.assertEqual(r['clock_policy'], 'free_running_CE_no_ICG')

    def test_mapping_residuals_are_not_full_lut_double_charge(self):
        full = self.c.estimate_window(nodes=128)
        shared = self.c.estimate_window('shared_lut_cached', nodes=128, lut_lanes=128)
        # The only area difference at equal LUT counts is the extra q-cache proxy.
        self.assertAlmostEqual(shared['raw_cell_area_um2'] - full['raw_cell_area_um2'], 128 * (464.04 - 343.8))

    def test_unknown_frequency_requires_explicit_opt_in(self):
        with self.assertRaises(ValueError):
            self.c.component('pbit_sample8_reg', clock_mhz=500)
        r = self.c.component('pbit_sample8_reg', clock_mhz=500, allow_above_reference=True)
        self.assertEqual(r['frequency_evidence'], 'dynamic_only_frequency_projection')

    def test_frequency_projection_preserves_leakage(self):
        a = self.c.component('pbit_sample8_reg', clock_mhz=100)
        b = self.c.component('pbit_sample8_reg', clock_mhz=50)
        self.assertGreater(b['power_W'], a['power_W'] / 2)

    def test_bad_dimensions(self):
        for kw in [{'nodes': 0}, {'samples_per_configuration': 0}, {'clock_mhz': 0}, {'nodes': True},
                   {'implementation': 'shared_lut_cached', 'nodes': 4, 'lut_lanes': 8}]:
            with self.assertRaises(ValueError):
                self.c.estimate_window(**kw)


if __name__ == '__main__':
    unittest.main()
