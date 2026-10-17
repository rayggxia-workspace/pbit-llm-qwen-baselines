"""Small addressed-traffic invariants, not a language-model quality test."""
import json
import math
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / 'runtime'
sys.path.insert(0, str(RUNTIME))
sys.path.insert(0, str(ROOT))

from attention_adapter import LlamaDigitalDecode
from pv_stream_v6 import context_samples


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def fixture(mode='pv', length=512):
    cfg = load(RUNTIME / 'configs/system_decode_default.json')
    cfg.update(context_tokens=length, decode_tokens=1)
    cfg['external_memory'].update(burst_bytes=64)
    cfg['attention_v3'] = load(RUNTIME / 'configs/attention_v3.json')
    cfg['attention_v3'].update(mode=mode, seed=17, kv_tile_tokens=64,
                               selector_bias=-100.0, summary_initialization='prefill_prebuilt',
                               record_transactions=True)
    cfg['pv_stream_v6'] = load(RUNTIME / 'configs/pv_stream_v6.json')
    cfg['rng_hierarchy'] = load(RUNTIME / 'configs/rng_hierarchy_v1.json')
    macro = load(RUNTIME / 'configs/screen_ising_v4.json')['ising']
    cfg['llama_attention'] = dict(selector='max4', prefill_prebuilt=True,
                                  ising_macro=macro, ising_capacity=length)
    shape = dict(hidden_size=64, intermediate_size=128, vocab_size=128,
                 num_hidden_layers=1, num_attention_heads=2, num_key_value_heads=2)
    evidence = load(RUNTIME / 'configs/evidence_contract.json')
    calibration = load(RUNTIME / 'results/sram_calibration_v1_20261016/calibration.json')
    plan = load(RUNTIME / 'configs/memory_schedule_v5_recommended.json')
    plan.update(unified_bytes=8 * 2**20, scratch_bytes=8 * 2**20,
                 weight_bytes=8 * 2**20)
    return cfg, shape, evidence, calibration, plan


def model(mode='pv', length=512):
    cfg, shape, evidence, calibration, plan = fixture(mode, length)
    return LlamaDigitalDecode(cfg, 'digital_bf16', evidence, shape, calibration, plan)


class AttentionAdapterTests(unittest.TestCase):
    def test_proportional_samples_and_mha_union(self):
        for length, expected in ((512, 32), (1024, 64), (2048, 128)):
            with self.subTest(length=length):
                m = model('pv', length)
                self.assertEqual(context_samples(length, m.pc), expected)
                end = m.attention(0, length, 0)
                self.assertGreater(end, 0)
                self.assertEqual(m.actions['ATT_V_sample_events'], m.qheads * expected)
                self.assertEqual(sum(row['sample_events'] for row in m.pv_tiles),
                                 m.qheads * expected)
                self.assertEqual(m.actions['ATT_V_group_union_rows'],
                                 m.actions['ATT_V_unique_head_indices'])
                self.assertEqual(m.actions['ATT_random_words'], m.qheads)
                self.assertNotIn('uniform_buffer', {e['name'] for e in m.attn_events})
                self.assertLess(m.traffic['attention_V_gather_physical_bytes'],
                                m.qheads * length * m.vecbytes)

    def test_screening_reads_only_selected_k_addresses(self):
        for mode in ('screen_exact', 'screen_pv', 'screen_ising'):
            with self.subTest(mode=mode):
                m = model(mode)
                issued = []
                original = m.ext.access
                def access(ready, size, kind, write, address=None):
                    issued.append((kind, address, size, write))
                    return original(ready, size, kind, write, address=address)
                m.ext.access = access
                m.attention(0, 512, 0)
                # Extreme negative bias keeps precisely first and last two blocks.
                expected_ids = set(range(64)) | set(range(384, 512))
                self.assertEqual(m.actions['ATT_selected_QK_tokens'], 2 * len(expected_ids))
                self.assertEqual(m.actions['ATT_QK_MAC'], 2 * len(expected_ids) * m.dim)
                kinds = {'ATT_K', 'ATT_KV_fused'}
                actual_k = set()
                allowed_k = {m.kv_address(0, i, h)
                             for h in range(m.kheads) for i in expected_ids}
                all_k = {m.kv_address(0, i, h)
                         for h in range(m.kheads) for i in range(512)}
                for kind, address, size, write in issued:
                    if kind in kinds and not write:
                        self.assertEqual(size, 64)
                        if address in all_k:
                            actual_k.add(address)
                            self.assertIn(address, allowed_k)
                self.assertEqual(actual_k, allowed_k)
                self.assertEqual(m.traffic['attention_summary_build_K_physical_bytes'], 0)
                self.assertGreater(m.traffic['attention_summary_read_physical_bytes'], 0)
                self.assertEqual(m.actions['ATT_summary_update_vector'], m.kheads * m.dim)
                if mode != 'screen_exact':
                    self.assertEqual(m.actions['ATT_V_sample_events'], 64)

    def test_ising_internal_rng_not_charged_twice_and_budget_exact(self):
        m = model('ising')
        end = m.attention(0, 512, 0)
        self.assertEqual(m.actions['ATT_random_words'], 0)
        self.assertEqual(m.actions['ATT_Ising_macro_calls'], 2)
        self.assertEqual(m.actions['ATT_Ising_macro_samples'], 64)
        self.assertEqual(m.actions['ATT_V_sample_events'], 64)
        self.assertAlmostEqual(m.energy['ATT_Ising_macro_active'], m.ising_macro.energy_J)
        self.assertFalse(m.ising_macro.finish(end)['internal_rng_separately_charged'])
        self.assertTrue(all(row['retained_internal_output_indices'] == 1 for row in m.ising_rows))
        self.assertGreater(m.work_mem.counters['read_words'], 0)
        self.assertGreater(m.work_mem.counters['write_words'], 0)

    def test_macro_never_silently_truncates_candidates(self):
        cfg, shape, evidence, calibration, plan = fixture('ising')
        cfg['llama_attention']['ising_capacity'] = 128
        m = LlamaDigitalDecode(cfg, 'digital_bf16', evidence, shape, calibration, plan)
        with self.assertRaisesRegex(ValueError, 'candidate count exceeds'):
            m.attention(0, 512, 0)

    def test_finite_scratch_capacity_is_enforced(self):
        m = model('screen_pv', 2048)
        m.work_mem.capacity = 32 * 1024
        with self.assertRaisesRegex(ValueError, 'finite banked SRAM'):
            m.attention(0, 2048, 0)

    def test_scatter_descriptor_limit_splits_without_dropping_rows(self):
        normal = model('pv')
        normal.attention(0, 512, 0)
        limited = model('pv')
        limited.pc['max_spans_per_descriptor'] = 1
        limited.attention(0, 512, 0)
        for kind in ('K', 'V_gather'):
            self.assertEqual(normal.traffic['attention_' + kind + '_physical_bytes'],
                             limited.traffic['attention_' + kind + '_physical_bytes'])
        self.assertGreater(limited.actions['ATT_SG_control_vector'], 0)
        dma = [e for e in limited.attn_events if e['name'].startswith('DRAM_scatter_')]
        self.assertTrue(all(e['ranges'] <= 1 for e in dma))

    def test_complete_small_decode_energy_closes(self):
        for mode in ('dense', 'pv', 'screen_exact', 'screen_pv', 'ising', 'screen_ising'):
            with self.subTest(mode=mode):
                m = model(mode)
                report = m.run()
                self.assertAlmostEqual(sum(report['energy_J'].values()) * 1000,
                                       report['metrics']['scenario_mJ_per_token'])
                self.assertTrue(all(value >= 0 and math.isfinite(value)
                                    for value in report['energy_J'].values()))
                self.assertEqual(report['llama_attention']['mode'], mode)
                self.assertEqual(report['quality_reference_ppl'], None)
                self.assertAlmostEqual(sum(m.pv_phases.values()), m.attn_elapsed)
                if mode in ('ising', 'screen_ising'):
                    self.assertEqual(report['ising_macro_v4']['calls'], 2)
                    self.assertEqual(report['ising_macro_v4']['capacity'], 512)


if __name__ == '__main__':
    unittest.main()
