"""Mechanism gates for resource configurations; no full-shape sweep."""
import copy
import unittest

from architecture_tlm.unified_v6.config import load, tiny
from architecture_tlm.unified_v6.model import FullDecode
from architecture_tlm.resource_optimization_v1.search import (
    ReceiptDecode, apply_candidate, digest, generate_candidates, validate_candidate)


class SearchContracts(unittest.TestCase):
    def setUp(self):
        self.candidates = {c['id']: c for c in generate_candidates()}

    def test_all_candidates_fit_every_production_mapping(self):
        for candidate in self.candidates.values():
            for method in ('bf16_exact', 'w8_exact', 'sc_exact', 'sc_screen_pv'):
                for context in (2048, 8192):
                    cfg = apply_candidate(candidate, method, context)
                    report = validate_candidate(candidate, cfg)
                    self.assertLessEqual(report['reserved_peak_bytes'], report['physical_capacity_bytes'])
        self.assertEqual(len(self.candidates), 16)

    def test_rejects_impossible_bank_fabric_and_unpaid_macro_roundup(self):
        cfg = apply_candidate(self.candidates['baseline_1m'])
        cfg['sram']['fabric_GBs'] = 32.
        with self.assertRaisesRegex(ValueError, 'bank bandwidth'):
            validate_candidate(self.candidates['baseline_1m'], cfg)
        cfg['sram']['fabric_GBs'] = 16.
        cfg['sram']['capacity_bytes'] += 1
        with self.assertRaisesRegex(ValueError, 'rounded physical'):
            validate_candidate(self.candidates['baseline_1m'], cfg)

    def test_rejects_slots_exceeding_capacity_and_sc_supply(self):
        cfg = apply_candidate(self.candidates['baseline_1m'], 'sc_exact')
        cfg['weight_chunk_bytes'] = 1024*1024
        with self.assertRaisesRegex(ValueError, 'capacity exceeded'):
            validate_candidate(self.candidates['baseline_1m'], cfg)
        cfg['weight_chunk_bytes'] = 16*1024
        with self.assertRaisesRegex(ValueError, 'cannot supply'):
            validate_candidate(self.candidates['baseline_1m'], cfg)

    def test_rejects_clock_algorithm_nonfinite_and_noninteger_changes(self):
        candidate = self.candidates['baseline_1m']
        for key, value in [('clock_hz', 80000000), ('clock_hz', float('nan'))]:
            cfg = apply_candidate(candidate)
            cfg['random'][key] = value
            with self.assertRaises(ValueError):
                validate_candidate(candidate, cfg)
        cfg = apply_candidate(candidate)
        cfg['ffn']['samples'] = 16
        with self.assertRaises(ValueError):
            validate_candidate(candidate, cfg)
        cfg = apply_candidate(candidate)
        cfg['macs_per_cycle'] = 512.0
        with self.assertRaises(ValueError):
            validate_candidate(candidate, cfg)

    def test_mapping_retains_identical_resource_contract(self):
        before = apply_candidate(self.candidates['baseline_1m'])
        after = apply_candidate(self.candidates['mapped_1m'])
        self.assertEqual(before['sram'], after['sram'])
        self.assertEqual(before['dram'], after['dram'])
        self.assertEqual(before['ffn'], after['ffn'])
        self.assertEqual(before['macs_per_cycle'], after['macs_per_cycle'])
        self.assertNotEqual(before['weight_chunk_bytes'], after['weight_chunk_bytes'])

    def test_capacity_alone_does_not_buy_free_time_or_change_flow(self):
        base, shape = tiny()
        cfg = apply_candidate(self.candidates['baseline_1m'], 'w8_exact', 65, 0, base)
        bigger = apply_candidate(self.candidates['capacity_8m'], 'w8_exact', 65, 0, base)
        before, after = FullDecode(cfg, shape).run(), FullDecode(bigger, shape).run()
        self.assertEqual(before['metrics']['TPOT_ms'], after['metrics']['TPOT_ms'])
        self.assertEqual(before['DRAM']['traffic'], after['DRAM']['traffic'])
        self.assertEqual(before['SRAM']['traffic'], after['SRAM']['traffic'])
        self.assertEqual(before['SRAM']['reserved_peak_bytes'], after['SRAM']['reserved_peak_bytes'])
        self.assertGreater(after['SRAM']['area_mm2'], before['SRAM']['area_mm2'])

    def test_apply_is_pure_and_only_resource_fields_are_editable(self):
        base, _ = load('qwen')
        old = digest(base)
        apply_candidate(self.candidates['wide_4m'], base_config=base)
        self.assertEqual(old, digest(base))
        invalid = copy.deepcopy(self.candidates['baseline_1m'])
        invalid['overrides']['ffn.samples'] = 16
        with self.assertRaisesRegex(ValueError, 'resource/mapping'):
            apply_candidate(invalid)

    def test_full_receipts_preserve_schedule_and_source_outputs(self):
        base, shape = tiny()
        cfg = apply_candidate(self.candidates['baseline_1m'], 'sc_screen_pv', 65, 0, base)
        plain = FullDecode(cfg, shape).run()
        instrumented = ReceiptDecode(cfg, shape)
        recorded = instrumented.run()
        self.assertEqual(plain, recorded)
        self.assertEqual(instrumented.route_rows, 2)
        self.assertEqual(instrumented.sample_rows, 2)
        self.assertEqual(len(recorded['row_receipts']), 2)


if __name__ == '__main__':
    unittest.main()
