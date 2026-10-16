"""Architectural invariants for the fixed-resource scheduling experiment."""
import copy
import math
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from system_decode import load
from run_mapping_optimization import checked_run, verify_same_work, bounds


class MappingTests(unittest.TestCase):
    def setUp(self):
        self.cfg, self.evidence, self.shape = load()
        self.shape.update(hidden_size=64, intermediate_size=128, num_hidden_layers=1,
                          num_attention_heads=2, num_key_value_heads=1, vocab_size=256)
        self.cfg.update(context_tokens=129, decode_tokens=2)
        self.plan = dict(chunk_bytes=65536, pin=True, attention_tokens=64,
                         early_sc_weights=True)

    def test_same_work_and_capacity_both_routes(self):
        areas = []
        for variant in ('digital_int8_ffn', 'fixed_sc_exact'):
            before = checked_run(self.cfg, variant, self.evidence, self.shape)
            after = checked_run(self.cfg, variant, self.evidence, self.shape, self.plan)
            checks = verify_same_work(before, after)
            self.assertTrue(all(checks.values()))
            self.assertLessEqual(after['mapping_checks']['peak_weight_SRAM_bytes'], 16*2**20)
            areas.append(after['metrics']['parameterized_area_mm2'])
        self.assertEqual(areas[0], areas[1])

    def test_unused_arrays_and_sources_charged_to_digital(self):
        r = checked_run(self.cfg, 'digital_int8_ffn', self.evidence, self.shape)
        self.assertGreater(r['energy_J']['SC_idle'], 0)
        self.assertGreater(r['energy_J']['RNG_sources'], 0)
        self.assertEqual(r['resource_matching']['physical_SC_engines'], 8)

    def test_attention_buffer_limit(self):
        plan = dict(self.plan, attention_tokens=65536)
        with self.assertRaisesRegex(AssertionError, 'buffer overflow'):
            checked_run(self.cfg, 'digital_int8_ffn', self.evidence, self.shape, plan)

    def test_weight_buffer_limit(self):
        plan = dict(self.plan, chunk_bytes=16*2**20)
        with self.assertRaises(AssertionError):
            checked_run(self.cfg, 'digital_int8_ffn', self.evidence, self.shape, plan)

    def test_bounds_below_actual_cost(self):
        for variant in ('digital_int8_ffn', 'fixed_sc_exact'):
            r = checked_run(self.cfg, variant, self.evidence, self.shape, self.plan)
            b = bounds(r, self.cfg, self.evidence, self.shape, variant)
            self.assertLessEqual(b['resource_lower_bound_ms'], r['metrics']['mean_TPOT_ms']+1e-9)
            self.assertLessEqual(b['conditional_simplified_energy_lower_bound_mJ_per_token'],
                                 r['metrics']['scenario_mJ_per_token']+1e-9)


if __name__ == '__main__':
    unittest.main()
