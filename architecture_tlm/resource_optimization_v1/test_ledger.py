"""Arithmetic and adversarial checks; no model inference or new TLM runs."""

import copy
import json
from pathlib import Path
import unittest

from .ledger import lower_bounds, resource_ledger


TLM = Path(__file__).resolve().parents[1]
LEGACY = TLM / 'unified_v6/results/qwen_20261022_v2/qwen'
INTEGRATED = TLM / 'unified_v6/results/integrated_rng_20261022_v3/qwen'


def archived(mode='sc', context=2048, integrated=False):
    if integrated:
        path = INTEGRATED / ('qwen_L%d_seed0_%s_exact_integrated_service.json' % (context, mode))
    else:
        path = LEGACY / ('qwen_L%d_seed0_%s_exact.json' % (context, mode))
    return json.loads(path.read_text(encoding='utf-8'))


def component(ledger, name):
    return next(c for c in ledger['components'] if c['module'] == name)


class InventoryTests(unittest.TestCase):
    def test_known_worksets_and_separate_local_state(self):
        r = archived()
        out = resource_ledger(r['config'], r['model'], r)
        work = out['working_set_bytes']
        self.assertEqual(work['ffn_W8_one_layer'], 13074432)
        self.assertEqual(work['ffn_W8_all_layers'], 313786368)
        self.assertEqual(work['BF16_KV_all_layers_at_context'], 24 * 1024**2)
        tile = component(out, 'SC_tiles_and_local_counters')
        self.assertEqual(tile['required_counter_bits_per_tile'], 6 * 1024 * 8)
        self.assertEqual(tile['required_counter_bits_total'], 48 * 1024 * 8)
        self.assertIsNone(tile['physical_state_bits'])
        self.assertEqual(tile['alternative']['required_bytes_per_tile'], 640)
        self.assertEqual(tile['alternative']['status'], 'proposed_not_implemented')
        hold = component(out, 'SC_weight_retention_and_feed')
        self.assertEqual(hold['required_visible_weight_bytes'], 32768)
        self.assertEqual(hold['macro_output_bits_per_beat'], 2048)
        self.assertIsNone(hold['physical_retention_bits'])

    def test_physical_macro_rounding_does_not_multiply_ports(self):
        r = archived()
        # Synthetic inventory fixture with one extra addressable byte. Actual
        # TLM instantiates a complete second row of sixteen 64 KiB macros.
        r['config']['sram']['capacity_bytes'] += 1
        r['SRAM'].update(configured_bytes=1024**2 + 1, physical_bytes=2 * 1024**2,
                         macros=32, area_mm2=32 * r['SRAM']['calibrated_macro']['area_mm2'])
        out = resource_ledger(r['config'], r['model'], r)
        mem = component(out, 'SRAM_macros')
        self.assertEqual(mem['physical_instances'], 32)
        self.assertEqual(mem['macros_per_bank'], 2)
        self.assertEqual(out['SRAM_allocation']['unaddressable_physical_padding_bytes'], 1024**2 - 1)
        self.assertAlmostEqual(out['SRAM_bandwidth']['aggregate_bank_peak_GBs'], 20.48)
        self.assertAlmostEqual(mem['area_mm2'], 9.9892259208)

    def test_unknown_whole_chip_ppa_stays_null_despite_large_proxy_price(self):
        r = archived()
        r['metrics']['priced_subtotal_mJ_per_token'] = 123456789
        out = resource_ledger(r['config'], r['model'], r)
        self.assertIsNone(out['full_physical_area_mm2'])
        self.assertIsNone(out['full_physical_energy_J'])
        self.assertIsNone(out['area_anchor_A0_mm2'])
        self.assertFalse(out['ranking_eligible'])

    def test_digital_path_does_not_claim_active_sc_state(self):
        r = archived('w8')
        out = resource_ledger(r['config'], r['model'], r)
        self.assertEqual(component(out, 'SC_tiles_and_local_counters')['required_counter_bits_total'], 0)
        self.assertFalse(component(out, 'SC_weight_retention_and_feed')['active_for_path'])

    def test_integrated_rng_anchor_is_explicitly_partial(self):
        r = archived(integrated=True)
        out = resource_ledger(r['config'], r['model'], r)
        rng = component(out, 'random_service')
        self.assertEqual(rng['configured_native_endpoints'], 1)
        self.assertGreater(rng['calibrated_endpoint_area_mm2'], 0)
        self.assertIsNone(rng['area_mm2'])
        self.assertIsNone(rng['energy_J'])
        self.assertEqual(rng['random_stream_SRAM_bytes'], 0)

    def test_counter_width_changes_at_power_boundary(self):
        r = archived()
        r['config']['ffn']['samples'] = 64
        r['FFN_activity']['SC_counter_peak_bits'] = 8 * 64 * 8 * 2 * 4 * 13
        out = resource_ledger(r['config'], r['model'], r)
        self.assertEqual(component(out, 'SC_tiles_and_local_counters')['counter_bits_per_value'], 13)

    def test_integrated_digital_path_has_known_zero_native_endpoints(self):
        r = archived('bf16', integrated=True)
        out = resource_ledger(r['config'], r['model'], r)
        self.assertEqual(component(out, 'random_service')['configured_native_endpoints'], 0)

    def test_rejects_stale_shape_config_and_inconsistent_storage(self):
        r = archived()
        changed = copy.deepcopy(r['config'])
        changed['sram']['capacity_bytes'] *= 2
        with self.assertRaisesRegex(ValueError, 'configuration differs'):
            resource_ledger(changed, r['model'], r)
        changed_shape = copy.deepcopy(r['model'])
        changed_shape['num_hidden_layers'] = 32
        with self.assertRaisesRegex(ValueError, 'shape differs'):
            lower_bounds(r['config'], changed_shape, r)
        r['SRAM']['macros'] += 1
        with self.assertRaisesRegex(ValueError, 'mismatch'):
            resource_ledger(r['config'], r['model'], r)

    def test_rejects_overlap_and_unattainable_macro_clock(self):
        r = archived()
        r['SRAM']['layout']['weight_pong']['address'] = 0
        with self.assertRaisesRegex(ValueError, 'overlapping'):
            resource_ledger(r['config'], r['model'], r)
        r = archived()
        r['config']['sram']['clock_hz'] = 200000000
        with self.assertRaisesRegex(ValueError, 'period violates'):
            resource_ledger(r['config'], r['model'], r)

    def test_input_dictionaries_are_never_mutated(self):
        r = archived()
        original = copy.deepcopy(r)
        out = resource_ledger(r['config'], r['model'], r)
        lower_bounds(r['config'], r['model'], r)
        out['components'][0]['macro']['area_mm2'] = 0
        self.assertEqual(r, original)


class LowerBoundTests(unittest.TestCase):
    def traffic_fixture(self, dram_bytes=4096):
        r = archived('w8')
        r['DRAM']['traffic'] = {'weights_physical_bytes': dram_bytes}
        r['SRAM']['traffic'] = {'read_physical_bytes': 0, 'write_physical_bytes': 0}
        r['events'] = []
        r['event_count'] = 100
        r['trace_truncated'] = True
        r['resource_busy_ns'] = {}
        r['metrics']['elapsed_ns'] = 1e6
        return r

    def test_archived_fixed_traffic_and_busy_are_distinct(self):
        r = archived('w8')
        out = lower_bounds(r['config'], r['model'], r)
        self.assertEqual(out['physical_bytes']['SRAM'], 1405768576)
        self.assertEqual(out['resource_traffic_lower_bounds_ns']['sram_fabric'], 87860536)
        self.assertEqual(out['fixed_service_lower_bound_ns'], max(r['resource_busy_ns'].values()))
        self.assertGreater(sum(r['resource_busy_ns'].values()), out['conditional_lower_bound_ns'])
        self.assertIsNone(out['legacy_link']['exact_trace_window_service_ns'])
        pure = lower_bounds(r['config'], r['model'], r, include_fixed_service=False)
        self.assertEqual(pure['conditional_lower_bound_ns'], pure['fixed_traffic_lower_bound_ns'])

    def test_weight_only_window_math_matches_plan(self):
        r = self.traffic_fixture(674136064)
        r['metrics']['elapsed_ns'] = 1e9
        out = lower_bounds(r['config'], r['model'], r)
        self.assertEqual(out['resource_traffic_lower_bounds_ns']['dram_data_link'], 42133504)
        self.assertEqual(out['legacy_link']['aggregate_service_lower_bound_ns'], 68466944)
        self.assertAlmostEqual(out['legacy_link']['full_window_effective_GBs'], 2048 / 208)

    def test_descriptor_fragmentation_is_not_aggregate_window_count(self):
        r = self.traffic_fixture()
        out = lower_bounds(r['config'], r['model'], r,
                           dram_descriptor_physical_bytes=[64] * 64)
        self.assertEqual(out['legacy_link']['aggregate_min_windows'], 2)
        self.assertEqual(out['legacy_link']['aggregate_service_lower_bound_ns'], 416)
        self.assertEqual(out['legacy_link']['exact_window_count'], 64)
        self.assertEqual(out['legacy_link']['exact_descriptor_service_ns'], 5376)
        self.assertEqual(out['conditional_lower_bound_ns'], 5376)

    def test_empty_descriptors_pay_no_latency(self):
        r = self.traffic_fixture(0)
        out = lower_bounds(r['config'], r['model'], r,
                           dram_descriptor_physical_bytes=[0, 0])
        self.assertEqual(out['legacy_link']['exact_descriptor_service_ns'], 0)
        self.assertIsNone(out['elapsed_over_conditional_lower_bound'])

    def test_only_complete_trace_establishes_exact_window_service(self):
        r = self.traffic_fixture(128)
        r.update(events=[dict(stage='dram_weights', resources=['dram_dma'], bytes=64)] * 2,
                 event_count=2, trace_truncated=False)
        out = lower_bounds(r['config'], r['model'], r)
        self.assertEqual(out['legacy_link']['exact_trace_window_service_ns'], 168)
        r['trace_truncated'] = True
        out = lower_bounds(r['config'], r['model'], r)
        self.assertIsNone(out['legacy_link']['exact_trace_window_service_ns'])

    def test_rejects_incomplete_descriptor_list_and_false_complete_trace(self):
        r = self.traffic_fixture()
        with self.assertRaisesRegex(ValueError, 'match full'):
            lower_bounds(r['config'], r['model'], r, dram_descriptor_physical_bytes=[64])
        r.update(events=[], event_count=0, trace_truncated=False)
        with self.assertRaisesRegex(ValueError, 'complete Link trace'):
            lower_bounds(r['config'], r['model'], r)

    def test_invalid_rates_bytes_and_impossible_busy_are_rejected(self):
        for bad in (0, -1, float('nan'), float('inf')):
            r = self.traffic_fixture()
            r['config']['dram']['bandwidth_GBs'] = bad
            with self.assertRaises(ValueError):
                lower_bounds(r['config'], r['model'], r)
        r = self.traffic_fixture(65)
        with self.assertRaisesRegex(ValueError, 'burst aligned'):
            lower_bounds(r['config'], r['model'], r)
        r = self.traffic_fixture()
        r['resource_busy_ns'] = {'vector': 1e10}
        with self.assertRaisesRegex(ValueError, 'exceeds recorded'):
            lower_bounds(r['config'], r['model'], r)

    def test_nonlinear_waits_and_parallel_banks_do_not_add_to_bound(self):
        r = self.traffic_fixture(0)
        r['resource_busy_ns'] = {'vector': 10, 'sram_bank:0': 20, 'sram_bank:1': 20}
        r['wait_ns'] = {'vector': 1000000}
        r['stage_busy_ns'] = {'restore': 100, 'other': 200}
        out = lower_bounds(r['config'], r['model'], r)
        self.assertEqual(out['conditional_lower_bound_ns'], 20)

    def test_nonlegacy_backend_never_inherits_window_drain_latency(self):
        r = self.traffic_fixture()
        r['config']['dram']['backend'] = 'persistent_link'
        out = lower_bounds(r['config'], r['model'], r)
        self.assertIsNone(out['legacy_link']['aggregate_service_lower_bound_ns'])
        self.assertEqual(out['conditional_lower_bound_ns'], 256)
        with self.assertRaisesRegex(ValueError, 'only to legacy Link'):
            lower_bounds(r['config'], r['model'], r, dram_descriptor_physical_bytes=[4096])

    def test_per_token_division_does_not_change_run_bound(self):
        r = self.traffic_fixture()
        r['config']['decode_tokens'] = 4
        out = lower_bounds(r['config'], r['model'], r)
        self.assertEqual(out['conditional_lower_bound_ns'], 416)
        self.assertEqual(out['conditional_lower_bound_ms_per_token'], 416 / 4 / 1e6)


if __name__ == '__main__':
    unittest.main()
