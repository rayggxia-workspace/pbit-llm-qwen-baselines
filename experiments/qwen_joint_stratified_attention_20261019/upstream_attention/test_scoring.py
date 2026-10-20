"""CPU scoring checks: targets, first query, stage execution, no CUDA/weights."""
import importlib.util
import math
import struct
import unittest

from experiments.attention_joint_ising.scoring import (full_window_plan, ids_sha256,
    plan_batches, plan_metadata, suffix_offsets, suffix_plan, summarize_records, target_positions)


class PlanTests(unittest.TestCase):
    def test_historical_suffix_manifest(self):
        offsets = suffix_offsets(299078)
        self.assertEqual(len(offsets), 32)
        self.assertEqual(offsets[:4], [0, 9577, 19155, 28732])
        self.assertEqual(offsets[-1], 296902)
        rows = suffix_plan(299078)
        self.assertEqual(rows[0]['prefill_tokens'], 2047)
        self.assertEqual(rows[0]['first_target'], 2048)
        self.assertEqual(rows[0]['last_target_exclusive'], 2176)
        self.assertEqual(sum(row['scored_tokens'] for row in rows), 4096)

    def test_all_WT2_targets_once(self):
        rows = full_window_plan(299078)
        positions = [x for row in rows for x in target_positions(row)]
        self.assertEqual(positions, list(range(1, 299078)))
        self.assertEqual(rows[0]['prefill_tokens'], 0)
        self.assertEqual(rows[1]['prefill_tokens'], 1023)
        self.assertEqual(rows[1]['first_target'], 2048)
        self.assertTrue(plan_metadata(rows, 299078, 'full')['every_full_corpus_target_once'])

    def test_full_short_and_partial_window(self):
        for count in (2, 7, 8, 9, 18, 31):
            rows = full_window_plan(count, 8, 4)
            self.assertEqual([x for row in rows for x in target_positions(row)], list(range(1, count)))

    def test_no_padding_or_reordering_batches(self):
        rows = full_window_plan(31, 8, 4)
        batches = list(plan_batches(rows, 3))
        self.assertEqual([r for batch in batches for r in batch], rows)
        for batch in batches:
            self.assertLessEqual(len(batch), 3)
            self.assertEqual(len({(r['prefill_tokens'], r['scored_tokens']) for r in batch}), 1)

    def test_invalid_or_overlapping_plans_rejected(self):
        for args in ((10, 8, 4, 2), (20, 8, 8, 3)):
            with self.assertRaises(ValueError):
                suffix_plan(*args)
        with self.assertRaises(ValueError):
            full_window_plan(10, 8, 9)

    def test_weighted_NLL_not_mean_perplexity(self):
        result = summarize_records([dict(scored_tokens=1, nll_sum=1), dict(scored_tokens=3, nll_sum=9)])
        self.assertEqual(result['mean_nll'], 2.5)
        self.assertAlmostEqual(result['perplexity'], math.exp(2.5))

    def test_little_endian_hash_contract(self):
        import hashlib
        self.assertEqual(ids_sha256([1, 3]), hashlib.sha256(struct.pack('<qq', 1, 3)).hexdigest())

    def test_lazy_import_no_transformers_requirement(self):
        from experiments.attention_joint_ising.evaluate import _case
        self.assertEqual(_case({})['protocol'], 'suffix')

    def test_wrapper_sdpa_mode_is_explicit_and_unknown_modes_rejected(self):
        from experiments.attention_joint_ising.evaluate import _case
        self.assertEqual(_case({'mode': 'digital_sdpa'})['mode'], 'digital_sdpa')
        with self.assertRaisesRegex(ValueError, 'unknown mode'):
            _case({'mode': 'unverified_digital_backend'})


@unittest.skipUnless(importlib.util.find_spec('torch'), 'Torch unavailable; pure plan checks still run')
class TinyCachedModelTests(unittest.TestCase):
    def make_model(self):
        import torch
        from types import SimpleNamespace
        class Attention(torch.nn.Module):
            def forward(self, hidden_states):
                return hidden_states
        Qwen2MLP = type('Qwen2MLP', (torch.nn.Linear,), {})
        class Layer(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self.self_attn = Attention()
                self.mlp = Qwen2MLP(4, 4)
        class Backbone(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self.layers = torch.nn.ModuleList([Layer() for _ in range(24)])
            def forward(self, input_ids, past_key_values=None, use_cache=True):
                hidden = torch.nn.functional.one_hot(input_ids % 4, 4).float()
                for layer in self.layers:
                    hidden = layer.self_attn(hidden)
                return SimpleNamespace(last_hidden_state=hidden, past_key_values=object())
        class Model(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self.model = Backbone()
                self.lm_head = torch.nn.Linear(4, 4)
        return Model().eval()

    def test_suffix_all_scored_queries_execute_24_layers(self):
        import torch
        from experiments.attention_joint_ising.evaluate import evaluate_case
        r = evaluate_case(self.make_model(), torch.arange(64) % 4,
            dict(mode='sdpa', context=8, decode=2, examples=3, batch=2), None)
        self.assertEqual(r['scored_tokens'], 6)
        self.assertEqual(r['execution_audit']['decode_calls_per_layer'], [4] * 24)
        self.assertEqual(r['execution_audit']['scored_query_tokens'], 6)

    def test_full_first_window_is_not_ignored(self):
        import torch
        from experiments.attention_joint_ising.evaluate import evaluate_case
        r = evaluate_case(self.make_model(), torch.arange(18) % 4,
            dict(mode='sdpa', protocol='full', context=8, stride=4, batch=2), None)
        self.assertEqual(r['scored_tokens'], 17)
        self.assertEqual(r['execution_audit']['scored_query_tokens'], 17)
        self.assertEqual(r['examples'][0]['first_target_token'], 1)
        self.assertEqual(r['examples'][-1]['last_target_token'], 17)


if __name__ == '__main__':
    unittest.main(verbosity=2)
