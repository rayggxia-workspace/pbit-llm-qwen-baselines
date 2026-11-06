"""Conservation, shared-resource and short-tail feedback checks."""
import json
import math
from pathlib import Path
import unittest


class BF16Contract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from .model import make_model
        from architecture_tlm.unified_v6.shared_memory import AnalyticDRAM
        cls.profile = json.loads(Path(__file__).with_name('PROFILE.json').read_bytes())
        cls.hub, cls.model = make_model(AnalyticDRAM(latency_ns=30, bandwidth_GBs=136.4606),
                                     cls.profile, layers=36, include_lm=True)

    def test_area_and_fit(self):
        p = self.profile
        self.assertLess(abs(p['area_gap_percent']), .4)
        self.assertEqual(p['lanes'], 1888)
        self.assertLessEqual(p['output_tile'] * p['K_tile'] * 2, 65536)
        self.assertEqual(p['FMA_pool_shared_by'], ['QKV', 'O', 'g', 'u', 'down', 'lm_head'])

    def test_full_weight_and_output_coverage(self):
        m = self.model
        d, f, q, kv = 2560, 9728, 4096, 1024
        for name, outputs, inputs in [('g', f, d), ('u', f, d), ('down', d, f),
                ('QKV', q + 2 * kv, d), ('O', d, q), ('lm_head', 151936, d)]:
            tasks = m.matrix_tasks(0, name, outputs, inputs, 2)
            self.assertEqual(sum(t[1] for t in tasks), outputs * inputs)
            self.assertEqual(sum(sum(n for _, n in t[0]) for t in tasks), 2 * outputs * inputs)
            self.assertEqual(sum(t[3] for t in tasks if t[4]), outputs)
            self.assertTrue(all(sum(n for _, n in t[0]) <= 65536 for t in tasks))

    def test_feedback_tail_is_not_work_div_lanes(self):
        from architecture_tlm.digital_fair_20261105.model import fma_cycles
        # One output has only one of four feedback contexts available.
        self.assertEqual(fma_cycles(1, 128, 1888, 32), 17)
        self.assertGreater(fma_cycles(1, 128, 1888, 32), math.ceil(128 / 1888) + 4)
        self.assertEqual(fma_cycles(236, 128, 1888, 32), 20)

    def test_finite_weight_leases_and_short_matrix(self):
        h, m = self.hub, self.model
        prior = m.actions['digital_BF16_MAC']
        # Cross-operator prefetch uses different physical pools; neither live
        # lease can be overwritten. Include both K and output tails.
        # Keep the DMA64B alignment required by the real model shapes.
        m.phase('g_prefetch', [m.prefetch_matrix(0, 'g', 256, 288, 2)], 0)
        m.phase('g_with_u_prefetch', [m.digital_matrix(0, 'g', 256, 288, 2),
                                   m.prefetch_matrix(0, 'u', 256, 288, 2)], 0)
        m.phase('u', [m.digital_matrix(0, 'u', 256, 288, 2)], 0)
        self.assertEqual(m.actions['digital_BF16_MAC'] - prior, 2 * 256 * 288)
        self.assertFalse(m.prefetched)
        self.assertFalse(m.slot_leases)
        self.assertFalse(h.mem.queue)
        self.assertEqual(h.report()['final_pending'], 0)
        self.assertTrue(all(x <= y for x, y in zip(h.mem.bank_allocated, h.mem.bank_depths)))
        self.assertTrue(all(abs(r['time_ledger_residual_ns']) <= 1e-6 for r in m.matrix_audit))


if __name__ == '__main__':
    unittest.main()
