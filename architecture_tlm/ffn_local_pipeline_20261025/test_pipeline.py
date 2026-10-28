"""Independent small-shape contracts for Issue186 local weight pipeline.

Set PBIT_TLM_CHECKOUT to the checkout under audit. No external simulator,
weights, GPU, or full Qwen run is needed. These are schedule contracts, not
bit-exact model quality or physical SRAM/DRAM timing validation.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import unittest

CHECKOUT = os.environ.get('PBIT_TLM_CHECKOUT')
if not CHECKOUT:
    CHECKOUT=str(Path(__file__).resolve().parents[2])
sys.path.insert(0, str(Path(CHECKOUT).resolve()))

from architecture_tlm.unified_v6.test_ffn_locality import case
from architecture_tlm.unified_v6.model import FullDecode
from architecture_tlm.ffn_local_pipeline_20261025.model import LocalPipelineFFN


EPS = 1e-5


def simulate(*, overlap=True, bypass=False, tile=64, engines=2, retain=2,
             old=False, mutate=None):
    cfg, model = case(tile=tile, engines=engines, retain=retain,
                      source_groups=tile // 64)
    cfg['trace_event_limit'] = 200000
    cfg['local_pipeline'] = dict(overlap=overlap, weight_bypass=bypass)
    if mutate:
        mutate(cfg, model)
    obj = FullDecode(cfg, model)
    if not old:
        obj.ffn_latest = LocalPipelineFFN(obj)
    result = obj.run()
    if result['trace_truncated']:
        raise AssertionError('Audit requires the complete small-shape event trace')
    return obj, result


def records(result):
    audit = result['FFN_contract']['local_pipeline']
    if audit['records_truncated']:
        raise AssertionError('Audit requires all ticket records')
    return audit['records']


def logical_projection(result):
    return [(r['name'], tuple(r['job'])) for r in records(result)]


class PipelineAudit(unittest.TestCase):
    def assert_finite_dependencies(self, obj, result):
        rr = records(result)
        self.assertTrue(rr)
        self.assertTrue(all(t is None for t in obj.ffn_latest.bank_tickets))
        state = result['FFN_contract']['local_pipeline']
        self.assertEqual(state['counts']['issued'], len(rr))
        self.assertEqual(state['counts']['programmed'], len(rr))
        self.assertEqual(state['counts']['retired'], len(rr))
        self.assertLessEqual(state['counts']['max_live_banks'], 2)
        prior_bank = {}
        for i, r in enumerate(rr):
            self.assertLessEqual(r['bytes'], state['bank_capacity_bytes'])
            self.assertLessEqual(r['coefficient_bytes'], state['coefficient_bank_bytes'])
            self.assertLessEqual(r['issue_ns'], r['weight_dma_done_ns'] + EPS)
            self.assertLessEqual(r['weight_dma_done_ns'], r['coefficient_dma_done_ns'] + EPS)
            self.assertLessEqual(r['weight_dma_done_ns'], r['program_start_ns'] + EPS)
            self.assertLessEqual(r['program_done_ns'], r['ready_ns'] + EPS)
            self.assertLessEqual(r['coefficient_dma_done_ns'], r['ready_ns'] + EPS)
            self.assertLessEqual(r['ready_ns'], r['compute_start_ns'] + EPS)
            self.assertLessEqual(r['compute_start_ns'], r['compute_done_ns'] + EPS)
            self.assertLessEqual(r['compute_done_ns'], r['retire_ns'] + EPS)
            if i:
                self.assertLessEqual(rr[i-1]['retire_ns'], r['compute_start_ns'] + EPS,
                                     'A second result may not overwrite live counters')
            if r['bank'] in prior_bank:
                previous = prior_bank[r['bank']]
                self.assertEqual(previous['generation'] + 1, r['generation'])
                self.assertLessEqual(previous['retire_ns'], r['issue_ns'] + EPS,
                                     'Bank reused before coefficients and restore were released')
            prior_bank[r['bank']] = r
        self.assertLessEqual(max(r['retire_ns'] for r in rr), result['metrics']['elapsed_ns'] + EPS)

    def assert_no_resource_overlap(self, result):
        by_resource = {}
        for event in result['events']:
            self.assertGreaterEqual(event['start_ns'] + EPS, event['ready_ns'])
            self.assertGreaterEqual(event['end_ns'] + EPS, event['start_ns'])
            for resource in event['resources']:
                by_resource.setdefault(resource, []).append(event)
        for resource, events in by_resource.items():
            events.sort(key=lambda e: (e['start_ns'], e['end_ns']))
            for left, right in zip(events, events[1:]):
                self.assertLessEqual(left['end_ns'], right['start_ns'] + EPS,
                                     (resource, left['stage'], right['stage']))
        self.assertAlmostEqual(sum(result['phase_ns'].values()),
                               result['metrics']['elapsed_ns'], delta=EPS)

    def test_bank_lifecycle_and_single_compute_pipeline(self):
        obj, result = simulate()
        self.assert_finite_dependencies(obj, result)
        self.assert_no_resource_overlap(result)

    def test_partial_and_code_boundaries_are_not_overtaken(self):
        obj, result = simulate(retain=2)
        rr = records(result)
        checked = 0
        for previous, current in zip(rr, rr[1:]):
            if previous['name'] != current['name']:
                continue
            p, c = previous['job'], current['job']
            same_output_window = p[0] == c[0] and p[2] == c[2]
            if same_output_window:
                continue
            checked += 1
            self.assertLessEqual(previous['retire_ns'], current['program_start_ns'] + EPS)
            # The previous output's last K group must be committed first.
            writes = [e for e in result['events']
                      if e['stage'] == 'sram_SC_wide_partial' and e.get('write')
                      and abs(e['end_ns'] - previous['retire_ns']) < EPS]
            self.assertEqual(len(writes), 1)
            # A noninitial retention window reloads its existing partial before
            # programming/consuming its new weight tile.
            if c[0] > 0:
                reads = [e for e in result['events']
                         if e['stage'] == 'sram_SC_wide_partial' and not e.get('write')
                         and e['start_ns'] + EPS >= previous['retire_ns']
                         and e['end_ns'] <= current['program_start_ns'] + EPS]
                self.assertEqual(len(reads), 1)
            if p[0] != c[0]:
                windows = [e for e in result['events']
                           if e['stage'] == 'sram_locality_code_window'
                           and e['start_ns'] + EPS >= previous['retire_ns']
                           and e['end_ns'] <= current['program_start_ns'] + EPS]
                self.assertEqual(len(windows), 1)
        self.assertGreater(checked, 0)

    def test_overlap_occurs_only_between_independent_weight_banks(self):
        def fast_memory(cfg, model):
            cfg['dram'].update(bandwidth_GBs=128., latency_ns=0., max_pending=512)
        _, result = simulate(mutate=fast_memory)
        rr = records(result)
        overlaps = []
        for previous, current in zip(rr, rr[1:]):
            lo = max(previous['compute_start_ns'], current['program_start_ns'])
            hi = min(previous['compute_done_ns'], current['program_done_ns'])
            if hi > lo + EPS:
                overlaps.append((previous, current))
                self.assertNotEqual(previous['bank'], current['bank'])
                self.assertEqual(previous['name'], current['name'])
                self.assertEqual(previous['job'][0], current['job'][0])
                self.assertEqual(previous['job'][2], current['job'][2])
        self.assertTrue(overlaps, 'Fixture must exercise real compute/program overlap')
        self.assertGreater(result['FFN_contract']['local_pipeline']['counts']['program_compute_overlap_ns'], 0)

    def test_disabled_overlap_preserves_jobs_and_frame_order(self):
        _, serial = simulate(overlap=False)
        _, piped = simulate(overlap=True)
        self.assertEqual(logical_projection(serial), logical_projection(piped))
        for key in ('logical_job_order_sha256', 'logical_frame_order_sha256'):
            self.assertEqual(serial['FFN_contract']['local_pipeline'][key],
                             piped['FFN_contract']['local_pipeline'][key])
        for previous, current in zip(records(serial), records(serial)[1:]):
            self.assertLessEqual(previous['retire_ns'], current['program_start_ns'] + EPS)

    def test_logical_hash_is_independent_of_timing_and_storage_path(self):
        _, shared = simulate()
        def slow(cfg, model):
            cfg['dram'].update(bandwidth_GBs=.5, latency_ns=3000., max_pending=4)
            cfg['sram']['fabric_GBs'] = 1.
        obj, direct = simulate(bypass=True, mutate=slow)
        self.assertEqual(logical_projection(shared), logical_projection(direct))
        for key in ('logical_job_order_sha256', 'logical_frame_order_sha256'):
            self.assertEqual(shared['FFN_contract']['local_pipeline'][key],
                             direct['FFN_contract']['local_pipeline'][key])
        self.assert_finite_dependencies(obj, direct)
        self.assert_no_resource_overlap(direct)

    def test_math_work_and_external_bytes_match_old_locality(self):
        _, old = simulate(old=True)
        _, new = simulate()
        # Exclude new response-buffer actions: coefficients now have explicit
        # response accounting. Arithmetic and actual external traffic remain.
        keys = ('SC_W8_magnitude_AND', 'SC_product_sign_XOR',
                'SC_weighted_bitplane_compress_bit_work', 'SC_signed_temporal_accumulate',
                'SC_bucket_route', 'SC_coefficient16_restore', 'SC_bucket_shift_reduce',
                'SC_cross_tile_add64', 'locality_R8_word_demand',
                'locality_endpoint_update', 'AND_threeway_comparison', 'AND_two_input_gate')
        for key in keys:
            self.assertEqual(old['actions'].get(key, 0), new['actions'].get(key, 0), key)
        for key in ('weights_logical_bytes', 'weights_physical_bytes',
                    'weight_scales_logical_bytes', 'weight_scales_physical_bytes'):
            self.assertEqual(old['DRAM']['traffic'][key], new['DRAM']['traffic'][key], key)
        self.assertEqual(old['FFN_activity'], new['FFN_activity'])
        self.assertEqual(old['attention_activity'], new['attention_activity'])
        self.assertEqual(old['row_receipts'], new['row_receipts'])
        for key in ('partial_read_bytes', 'partial_write_bytes'):
            self.assertEqual(old['FFN_contract']['locality_counts'][key],
                             new['FFN_contract']['locality_counts'][key])

    def test_bypass_removes_only_sc_shared_weight_and_scale_moves(self):
        _, shared = simulate(bypass=False)
        obj, direct = simulate(bypass=True)
        self.assertEqual(shared['DRAM']['traffic'], direct['DRAM']['traffic'])
        counts = direct['FFN_contract']['local_pipeline']['counts']
        logical_saved = counts['weight_load_bytes'] + counts['coefficient_load_bytes']
        for direction in ('read', 'write'):
            actual = (shared['SRAM']['traffic'][direction + '_logical_bytes'] -
                      direct['SRAM']['traffic'][direction + '_logical_bytes'])
            self.assertEqual(actual, logical_saved)
        self.assertEqual(direct['actions']['SC_shared_SRAM_bypass_weight_byte'],
                         counts['weight_load_bytes'])
        self.assert_finite_dependencies(obj, direct)

    def test_slow_memory_causes_backpressure_without_more_work(self):
        _, fast = simulate()
        def slow(cfg, model):
            cfg['dram'].update(bandwidth_GBs=.25, latency_ns=10000., max_pending=2)
        obj, result = simulate(mutate=slow)
        self.assertGreater(result['metrics']['elapsed_ns'], fast['metrics']['elapsed_ns'])
        self.assertGreater(result['FFN_contract']['local_pipeline']['counts']['exposed_supply_wait_ns'],
                           fast['FFN_contract']['local_pipeline']['counts']['exposed_supply_wait_ns'])
        self.assertEqual(logical_projection(result), logical_projection(fast))
        self.assertEqual(result['actions']['SC_W8_magnitude_AND'], fast['actions']['SC_W8_magnitude_AND'])
        self.assert_finite_dependencies(obj, result)
        self.assert_no_resource_overlap(result)

    def test_128_quadrants_tail_and_window_drain(self):
        def tail(cfg, model):
            model['intermediate_size'] = 640
        obj, result = simulate(tile=128, engines=3, retain=2, mutate=tail)
        rr = records(result)
        self.assertTrue(any(r['bytes'] < obj.ffn_latest.bank_capacity for r in rr))
        self.assert_finite_dependencies(obj, result)
        self.assert_no_resource_overlap(result)
        for name, info in obj.matrix_info.items():
            if not name.endswith(('/gu', '/down')):
                continue
            chosen = [r for r in rr if r['name'] == name]
            self.assertEqual(sum(r['bytes'] for r in chosen), info['bytes'])
            self.assertEqual(sum(r['coefficient_bytes'] for r in chosen), info['scale_bytes'])
            cursor = 0
            for r in chosen:
                self.assertEqual(r['job'][6], cursor)
                cursor += r['bytes']

    def test_no_free_duplicate_compute_or_counter_array(self):
        _, old = simulate(old=True)
        _, new = simulate()
        a, b = old['FFN_contract']['local_state'], new['FFN_contract']['local_state']
        self.assertEqual(b['weight_hold_bytes'], 2 * a['weight_hold_bytes'])
        self.assertEqual(b['tile_coefficient_and_exponent_bits'],
                         2 * a['tile_coefficient_and_exponent_bits'])
        for key in ('temporal_counter_bits', 'reduction_pipeline_bits',
                    'resident_output_partial_bits', 'local_input_code_window_bits',
                    'input_context_bank_bits', 'nonlinear_context_bank_bits'):
            self.assertEqual(a[key], b[key], key)
        self.assertIsNone(new['metrics']['full_physical_area_mm2'])
        self.assertIsNone(new['metrics']['full_physical_energy_J'])
        self.assertFalse(new['FFN_contract']['local_pipeline']['actual_endpoint_executed'])

    def test_shared_receiver_rejects_rate_mismatch_without_throttling(self):
        def slow_receiver(cfg, model):
            cfg['ffn']['local_weight_load_bytes_per_cycle'] = 1
        # Shared SRAM currently drains a descriptor at its own rate; without
        # a throttling backend or explicit full response FIFO, a slower local
        # receiver must not silently become an ideal stream.
        with self.assertRaisesRegex(ValueError, 'receiver|throttl'):
            simulate(bypass=False, mutate=slow_receiver)

    def test_direct_response_buffer_can_feed_a_slow_local_receiver(self):
        def slow_receiver(cfg, model):
            cfg['ffn']['local_weight_load_bytes_per_cycle'] = 1
        _, fast = simulate(bypass=True)
        obj, slow = simulate(bypass=True, mutate=slow_receiver)
        self.assertGreater(slow['metrics']['elapsed_ns'], fast['metrics']['elapsed_ns'])
        self.assertEqual(logical_projection(slow), logical_projection(fast))
        self.assert_finite_dependencies(obj, slow)
        self.assert_no_resource_overlap(slow)


if __name__ == '__main__':
    unittest.main(verbosity=2)
