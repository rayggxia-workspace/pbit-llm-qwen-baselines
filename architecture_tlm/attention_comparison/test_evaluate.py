"""Small one-layer checks; no full24-layer local workload."""
import math
import unittest
from collections import defaultdict

from evaluate import BatchExternal, DEFAULT_BATCH, build, cases_from_config


def case(mode='digital_dense', context=128, samples=32, pending=32, summary='warm'):
    return dict(mode=mode, context=context, samples=samples, seed=0, period=100,
                summary=summary, max_pending=pending, selection='fixed_budget')


class ModuleTests(unittest.TestCase):
    def test_module_scope_projection_and_phase_closure(self):
        m = build(case(), layers=1)
        r = m.module_run()
        self.assertEqual(r['actions']['projection_weight_bytes'] * 24, 84 * 2**20)
        self.assertEqual(r['traffic']['external_projection_weights_read_burst_bytes'], 3670016)
        self.assertEqual(r['timing']['full_module_ms'], r['timing']['phase_sum_ms'])
        self.assertTrue(r['validation']['no_FFN_lm_head'])
        self.assertTrue(r['validation']['allocated_capacity_fits'])
        self.assertEqual({p['name'] for p in r['phases']},
                         {'QKV_projection', 'bias_RoPE', 'KV_append', 'Attention_core', 'Wo_projection'})
        self.assertEqual(len(m.weights.cache), 0)
        self.assertGreater(r['proxy']['energy_ledger_J']['ATT_PV_FP32_proxy'], 0)

    def test_missing_physical_PPA_and_mean_power(self):
        r = build(case(), layers=1).module_run()
        self.assertIsNone(r['physical_PPA']['energy_J'])
        self.assertIsNone(r['physical_PPA']['area_mm2'])
        self.assertFalse(r['physical_PPA']['complete'])
        self.assertIsNone(r['validation']['PPL'])
        self.assertAlmostEqual(r['proxy']['energy_J'], sum(r['proxy']['energy_ledger_J'].values()))
        self.assertAlmostEqual(r['proxy']['mean_power_W'], r['proxy']['energy_J'] / (r['timing']['full_module_ms'] / 1000))

    def test_small_ising_formula_and_large_capacity_charged(self):
        m = build(case('screen_ising'), layers=1)
        r = m.module_run()
        cap, samples, queries = 512, 32, 14
        expected = queries * (100 + math.ceil(cap * 17 / 8) / 16 + 500 + 2000 + samples * 100 + 20 + 1)
        self.assertAlmostEqual(r['macro']['active_ns'], expected)
        self.assertEqual(r['macro']['calls'], queries)
        self.assertGreater(r['allocation']['allocated_bytes'], 65536)
        self.assertEqual(r['actions'].get('ATT_PV_MAC', 0), 0)
        self.assertEqual(r['actions']['ATT_random_words'], 14 * 2)
        self.assertEqual(r['root_random']['local_instances'], 0)
        self.assertEqual(r['root_random']['shared_instances'], 0)
        self.assertEqual(r['macro']['numerical_source']['kind'], 'ideal_iid_oracle')
        self.assertEqual(len(r['workload']['ordered_local_sample_indices_sha256']), 64)
        self.assertAlmostEqual(r['known_SRAM_internal']['dynamic_J'], r['proxy']['energy_ledger_J']['ATT_scratch'])

    def test_warm_updates_new_K_without_cold_build(self):
        warm = build(case('screen_exact'), layers=1).module_run()
        cold = build(case('screen_exact', summary='cold'), layers=1).module_run()
        self.assertEqual(warm['actions']['ATT_summary_update_vector'], 128)
        self.assertEqual(warm['actions'].get('ATT_summary_build_vector', 0), 0)
        self.assertEqual(cold['traffic']['attention_summary_build_K_useful_bytes'], 128 * 2 * 64 * 2)
        self.assertEqual(warm['traffic']['attention_summary_read_useful_bytes'], 2 * 2 * 4 * 64 * 4)
        self.assertEqual(warm['case']['selection'], 'variable')
        self.assertEqual(warm['event_counts']['scratch_summary_old_sum_fill'], 1)
        self.assertEqual(warm['event_counts']['scratch_summary_update_writeback'], 1)

    def test_single_index_tail_word_cost_and_packing_capacity(self):
        r = build(case('screen_ising', samples=1), layers=1).module_run()
        self.assertAlmostEqual(r['known_SRAM_internal']['dynamic_J'], r['proxy']['energy_ledger_J']['ATT_scratch'])
        self.assertEqual(r['allocation']['output_packing_register_and_tail_bytes'], 28)

    def test_finite_burst_batches_share_link_not_divide_time(self):
        results = []
        for pending in (1, 32):
            cfg = dict(bandwidth_GBs=16, latency_ns=80, burst_bytes=64,
                       read_pJ_per_byte=64, write_pJ_per_byte=64)
            ext = BatchExternal(cfg, defaultdict(float), defaultdict(int), None, pending)
            results.append(ext.access(0, 2048, 'test', False, 65536))
        self.assertEqual(results[0], 32 * (4 + 80))
        self.assertEqual(results[1], 32 * 4 + 80)
        self.assertNotEqual(results[1], results[0] / 32)

    def test_QK_physical_group_union_not_logical_retention_multiplier(self):
        # Seven heads in KVgroup0 keep disjoint positions, group1 one position.
        m = build(case('screen_exact', context=512), layers=1)
        m.coord = dict(token=0, layer=0)
        rows = [dict(indices=[head], head=head) for head in range(7)]
        rows += [dict(indices=[0], head=head) for head in range(7, 14)]
        m.qk_tiles(0, 512, 0, rows, fused_pv=False)
        self.assertEqual(m.actions['ATT_QK_MAC'], 14 * 64)
        self.assertEqual(m.traffic['attention_K_useful_bytes'], 8 * 128)
        self.assertEqual(m.traffic['attention_K_physical_bytes'], 8 * 128)
        self.assertNotEqual(8 / (512 * 2), 14 / (512 * 14))

    def test_SRAM_word_energy_and_no_fake_capacity_bandwidth(self):
        m = build(case(), layers=1)
        end = m.scratch(0, read=1, write=17)
        self.assertEqual(end, 3 * 16 / 16)
        self.assertEqual(m.SRAM_read_words, 1)
        self.assertEqual(m.SRAM_write_words, 2)
        self.assertAlmostEqual(m.energy['ATT_scratch'], (10.0527 + 2 * 13.9599) * 1e-12)

    def test_batch_is_finite_and_expected(self):
        cases = cases_from_config(DEFAULT_BATCH)
        self.assertEqual(len(cases), 32)
        self.assertEqual(len({tuple(sorted(c.items())) for c in cases}), 32)


if __name__ == '__main__':
    unittest.main(verbosity=2)
