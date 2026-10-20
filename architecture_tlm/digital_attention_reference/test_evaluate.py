"""Checks on scope, work conservation, capacity, and honest incomplete PPA."""
import unittest

from evaluate import evaluate, load, macro, validate


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.cfg = load()

    def test_qwen_2k_work_and_scope(self):
        r = evaluate(self.cfg, 2048)
        self.assertEqual(r['work']['core_MAC'], 88080384)
        self.assertEqual(r['work']['projection_MAC'], 44040192)
        self.assertEqual(r['work']['full_Attention_MAC'], 132120576)
        self.assertEqual(r['work']['full_Attention_MAC'], r['work']['core_MAC'] + r['work']['projection_MAC'])
        self.assertEqual(r['work']['reciprocal_ops'], 336)
        self.assertEqual(r['work']['exp_ops'], 24 * 14 * (2048 + 32))

    def test_gqa_traffic_shared_once_not_fourteen_times(self):
        r = evaluate(self.cfg, 2048)
        self.assertEqual(r['traffic_bytes']['KV_read'], 24 * 2**20)
        self.assertEqual(r['traffic_bytes']['projection_weight_read'], 84 * 2**20)
        self.assertEqual(r['traffic_bytes']['KV_append_write'], 12 * 1024)
        self.assertEqual(r['traffic_bytes']['probability_DRAM'], 0)

    def test_per_group_working_set_and_phase_reuse(self):
        r = evaluate(self.cfg, 2048)
        self.assertEqual(r['allocation']['peak_live_bytes'], 45496)
        self.assertEqual(r['allocation']['allocated_bytes'], 65536)
        self.assertAlmostEqual(r['allocation']['SRAM_only_area_mm2'], .03322622205 * 16)
        self.assertEqual(r['allocation']['full_KV_residency_counterfactual']['F_macros'], 384)
        self.assertFalse(r['allocation']['full_KV_residency_counterfactual']['allocated'])

    def test_capacity_failure_is_not_silent_spill(self):
        self.cfg['memory']['lanes'] = 8
        with self.assertRaisesRegex(ValueError, 'working set'):
            evaluate(self.cfg, 2048)

    def test_f_macro_rejected_at_100MHz_SS(self):
        self.cfg['memory']['sram_macro_id'] = 'F'
        spec, _ = macro(self.cfg)
        with self.assertRaisesRegex(ValueError, 'cycle'):
            validate(self.cfg, spec)

    def test_no_free_resident_weight_assumption(self):
        self.cfg['memory']['weights_resident'] = True
        with self.assertRaisesRegex(ValueError, 'resident'):
            evaluate(self.cfg, 2048)

    def test_context_scaling_only_affects_core_not_projection(self):
        a, b = (evaluate(self.cfg, length) for length in (512, 2048))
        self.assertEqual(b['work']['core_MAC'], 4 * a['work']['core_MAC'])
        self.assertEqual(b['traffic_bytes']['KV_read'], 4 * a['traffic_bytes']['KV_read'])
        self.assertEqual(b['work']['projection_MAC'], a['work']['projection_MAC'])
        self.assertEqual(b['allocation']['peak_live_bytes'], a['allocation']['peak_live_bytes'])

    def test_unknown_PPA_cannot_become_full_totals(self):
        r = evaluate(self.cfg, 2048)
        self.assertFalse(r['totals']['complete'])
        for key in ('full_energy_J', 'full_area_mm2', 'full_power_W'):
            self.assertIsNone(r['totals'][key])
        self.assertIsNone(r['timing']['achieved_latency_ns'])
        self.assertIn('PV_MAC', r['missing_PPA_coefficients'])
        self.assertIn('FP32', r['precision']['probability_sum_PV_accumulator'])

    def test_padding_is_separate_from_universal_work_floor(self):
        r = evaluate(self.cfg, 2048)
        self.assertGreater(r['timing']['serialized_compute_only_padded_ns'],
                           r['timing']['serialized_compute_only_no_padding_ns'])
        self.assertEqual(r['work']['full_Attention_MAC'], 132120576)

    def test_known_streaming_internal_energy_has_both_passes(self):
        r = evaluate(self.cfg, 2048)
        counts = 108 * 2**20 // 16
        self.assertEqual(r['known_SRAM_internal_subset']['read_words'], counts)
        self.assertEqual(r['known_SRAM_internal_subset']['write_words'], counts)
        self.assertAlmostEqual(r['known_SRAM_internal_subset']['read_J'], counts * 10.0527e-12)
        self.assertAlmostEqual(r['known_SRAM_internal_subset']['write_J'], counts * 13.9599e-12)
        self.assertAlmostEqual(r['timing']['resource_lower_bounds_ns']['known_SRAM_streaming_at_port_fabric_cap'] / 1e6, 14.155776)
        self.assertAlmostEqual(sum(r['known_SRAM_internal_subset']['component_internal_J'].values()),
                               r['known_SRAM_internal_subset']['read_J'] + r['known_SRAM_internal_subset']['write_J'])


if __name__ == '__main__':
    unittest.main()
