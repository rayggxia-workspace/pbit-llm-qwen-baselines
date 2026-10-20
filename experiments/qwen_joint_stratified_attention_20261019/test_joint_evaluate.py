"""CPU integration tests: real adapters, 24 layers and 64-wide FFN tiles.

These are synthetic integration checks, not model PPL or hardware results.
"""
import copy
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import torch
from torch import nn
from torch.nn import functional as F
from experiments.qwen_joint_stratified_attention_20261019 import joint_evaluate as joint
from experiments.qwen_joint_stratified_attention_20261019.upstream_attention.attention import (
    JointAttentionController, _repeat_kv, _rope)


class Qwen2MLP(nn.Module):
    def __init__(self):
        super().__init__()
        self.gate_proj = nn.Linear(64, 64, bias=False)
        self.up_proj = nn.Linear(64, 64, bias=False)
        self.down_proj = nn.Linear(64, 64, bias=False)

    def forward(self, x):
        return self.down_proj(F.silu(self.gate_proj(x)) * self.up_proj(x))


class Cache:
    def __init__(self):
        self.data = {}

    def update(self, k, v, layer, kwargs):
        if layer in self.data:
            old_k, old_v = self.data[layer]
            k, v = torch.cat((old_k, k), -2), torch.cat((old_v, v), -2)
        self.data[layer] = k, v
        return k, v

    def length(self):
        return self.data[0][0].shape[-2] if self.data else 0


class Attention(nn.Module):
    def __init__(self, index):
        super().__init__()
        self.layer_idx, self.num_heads, self.num_key_value_heads = index, 4, 2
        self.num_key_value_groups, self.head_dim, self.hidden_size = 2, 16, 64
        self.q_proj, self.o_proj = nn.Linear(64, 64), nn.Linear(64, 64)
        self.k_proj, self.v_proj = nn.Linear(64, 32), nn.Linear(64, 32)

    def rotary_emb(self, v, position_ids):
        phase = position_ids[..., None].float() * torch.arange(1, 9).float()[None, None] * .001
        phase = torch.cat((phase, phase), -1)
        return phase.cos(), phase.sin()

    def forward(self, hidden_states, attention_mask=None, position_ids=None,
                past_key_value=None, output_attentions=False, use_cache=False,
                cache_position=None, position_embeddings=None):
        b, n, _ = hidden_states.shape
        q = self.q_proj(hidden_states).view(b, n, 4, 16).transpose(1, 2)
        k = self.k_proj(hidden_states).view(b, n, 2, 16).transpose(1, 2)
        v = self.v_proj(hidden_states).view(b, n, 2, 16).transpose(1, 2)
        cos, sin = self.rotary_emb(v, position_ids) if position_embeddings is None else position_embeddings
        q, k = _rope(q, k, cos, sin)
        if past_key_value is not None:
            k, v = past_key_value.update(k, v, self.layer_idx, {})
        out = F.scaled_dot_product_attention(q, _repeat_kv(k, 2), _repeat_kv(v, 2),
                                            dropout_p=0., is_causal=n > 1)
        return self.o_proj(out.transpose(1, 2).contiguous().reshape(b, n, 64)), None, past_key_value


class Layer(nn.Module):
    def __init__(self, index):
        super().__init__()
        self.self_attn, self.mlp = Attention(index), Qwen2MLP()

    def forward(self, x, **kwargs):
        x = x + .05 * self.self_attn(x, **kwargs)[0]
        return x + .05 * self.mlp(x)


class Backbone(nn.Module):
    def __init__(self):
        super().__init__()
        self.embed_tokens = nn.Embedding(32, 64)
        self.layers = nn.ModuleList([Layer(i) for i in range(24)])

    def forward(self, input_ids, past_key_values=None, use_cache=True):
        cache = Cache() if past_key_values is None else past_key_values
        start = cache.length()
        positions = torch.arange(start, start + input_ids.shape[1])[None].expand(input_ids.shape[0], -1)
        x = self.embed_tokens(input_ids)
        for layer in self.layers:
            x = layer(x, position_ids=positions, past_key_value=cache, use_cache=use_cache)
        return SimpleNamespace(last_hidden_state=x, past_key_values=cache)


class Model(nn.Module):
    def __init__(self):
        super().__init__()
        self.config = SimpleNamespace(num_hidden_layers=24)
        self.model = Backbone()
        self.lm_head = nn.Linear(64, 32, bias=False)


class JointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old_threads = torch.get_num_threads()
        torch.set_num_threads(1)

    @classmethod
    def tearDownClass(cls):
        torch.set_num_threads(cls.old_threads)

    def setUp(self):
        torch.manual_seed(5)
        self.model = Model().eval()
        self.ids = torch.arange(24, dtype=torch.long) % 32
        self.calibration = dict(parameter=torch.zeros(24, 4), temperature=torch.ones(24, 4))
        self.case = dict(ffn='none', mode='sdpa', context=8, decode=2, examples=2,
                         batch=2, samples=4, burn=.2, spacing=.3,
                         budget_blocks=3, capture_scored_logits_sha256=True)

    def run_case(self, **kwargs):
        case = dict(self.case, **kwargs)
        return joint.evaluate_case(self.model, self.ids, case, self.calibration)

    def test_all_three_ffns_on_both_phases_and_all_24_layers(self):
        for ffn in joint.FFN_CONFIGS:
            with self.subTest(ffn=ffn):
                self.setUp()
                result = self.run_case(ffn=ffn, mode='screen_ising')
                audit = result['execution_audit']
                self.assertEqual(result['scored_tokens'], 4)
                self.assertEqual(audit['decode_calls_per_layer'], [2] * 24)
                self.assertEqual(audit['prefill_calls_per_layer'], [1] * 24)
                self.assertEqual(audit['ffn_decode_calls_per_layer'], [2] * 24)
                self.assertEqual(audit['ffn_prefill_calls_per_layer'], [1] * 24)
                self.assertEqual(audit['ffn_decode_tokens_per_layer'], [4] * 24)
                self.assertEqual(audit['ffn_prefill_tokens_per_layer'], [14] * 24)
                self.assertTrue(all(x['calls'] == 3 for x in result['ffn_stats'].values()))
                self.assertTrue(all(x['sampler_calls'] == 2 for x in result['sampling_stats']['layers'].values()))
                self.assertNotIn('and FFN; original', result['sampling_stats']['scope'])
                self.assertTrue(all(not hasattr(x.self_attn, '_joint_attention_owner') for x in self.model.model.layers))

    def test_original_sdpa_and_wrapper_bit_equal_with_same_ffn(self):
        for ffn in ('none', 'b4_t32'):
            with self.subTest(ffn=ffn):
                a, b = copy.deepcopy(self.model), copy.deepcopy(self.model)
                plain = joint.evaluate_case(a, self.ids, dict(self.case, ffn=ffn), self.calibration)
                wrapped = joint.evaluate_case(b, self.ids, dict(self.case, ffn=ffn, mode='digital_sdpa'), self.calibration)
                self.assertEqual(plain['scored_logits_sha256'], wrapped['scored_logits_sha256'])
                self.assertEqual(plain['nll_sum'], wrapped['nll_sum'])

    def test_full_all_targets_including_first_window_and_no_capture(self):
        result = self.run_case(ffn='b2_t32', mode='screen_iid', protocol='full',
                               stride=4, capture_scored_logits_sha256=False)
        self.assertEqual(result['scored_tokens'], 23)
        self.assertTrue(result['scoring_plan']['every_full_corpus_target_once'])
        self.assertEqual(result['execution_audit']['ffn_decode_tokens_per_layer'], [23] * 24)
        self.assertEqual(result['sampling_stats']['layers']['0']['query_rows'], 23 * 4)
        self.assertIsNone(result['scored_logits_sha256'])

    def test_screen_exact_has_no_pv_sampling_and_none_keeps_ffn(self):
        result = self.run_case(mode='screen_exact')
        self.assertIsNone(result['ffn_stats'])
        self.assertEqual(result['sampling_stats']['layers']['0']['sampler_calls'], 0)
        self.assertEqual(result['sampling_stats']['totals']['sample_events'], 0)
        self.assertTrue(all(type(x.mlp).__name__ == 'Qwen2MLP' for x in self.model.model.layers))

    def test_streams_seeded_independently_with_historical_formulas(self):
        case = joint._case(dict(self.case, ffn='b4_t16', seed=2))
        controller = JointAttentionController(mode='screen_ising', seed=2, calibration=self.calibration)
        controller.install(self.model)
        self.addCleanup(controller.close)
        joint._install_ffn(self.model, case)
        mlp = self.model.model.layers[7].mlp
        self.assertEqual(mlp.rng_input.initial_seed(), 700001 + 2000 + 49)
        self.assertEqual(mlp.rng_product.initial_seed(), 700002 + 2000 + 49)
        self.assertEqual(controller._generator(7, torch.device('cpu'), 'selector').initial_seed(), 22107)
        self.assertEqual(controller._generator(7, torch.device('cpu'), 'sampler').initial_seed(), 25107)
        self.assertIsNot(mlp.rng_input, mlp.rng_product)

    def test_guard_ignores_stats_but_catches_weight_buffer_writes(self):
        joint._install_ffn(self.model, joint._case(dict(self.case, ffn='b2_t32')))
        guard = joint.ModelGuard(self.model, 'b2_t32')
        self.model.model.layers[0].mlp.x_stats.add_(1)
        self.model.model.layers[0].mlp.calls += 1
        guard.verify()
        self.model.model.layers[0].mlp.gu_decoded.add_(1)
        with self.assertRaisesRegex(RuntimeError, 'weight-buffer'):
            guard.verify()

    def test_guard_detects_parameter_and_object_changes(self):
        guard = joint.ModelGuard(self.model, 'none')
        with torch.no_grad():
            self.model.lm_head.weight.add_(1)
        with self.assertRaisesRegex(RuntimeError, 'parameter'):
            guard.verify()
        self.setUp()
        guard = joint.ModelGuard(self.model, 'none')
        self.model.model.layers[0].mlp = Qwen2MLP()
        with self.assertRaisesRegex(RuntimeError, 'FFN objects'):
            guard.verify()

    def test_attention_restored_and_hooks_removed_on_failure(self):
        originals = [x.self_attn.forward for x in self.model.model.layers]
        with patch.object(self.model.lm_head, 'forward', side_effect=RuntimeError('intentional')):
            with self.assertRaisesRegex(RuntimeError, 'intentional'):
                self.run_case(ffn='b4_t16', mode='screen_ising')
        self.assertEqual(originals, [x.self_attn.forward for x in self.model.model.layers])
        self.assertTrue(all(not x.mlp._forward_pre_hooks for x in self.model.model.layers))
        self.assertTrue(all(not x.self_attn._forward_pre_hooks for x in self.model.model.layers))

    def test_invalid_case_or_reused_model_rejected(self):
        for update in ({'ffn': 'unknown'}, {'mode': 'digital_exact'}, {'capture_scored_logits_sha256': 1}):
            with self.subTest(update=update), self.assertRaises(ValueError):
                self.run_case(**update)
        self.run_case(ffn='b2_t32')
        with self.assertRaisesRegex(ValueError, 'fresh'):
            self.run_case(ffn='b2_t32')

    def test_prefill_is_not_silently_replaced_by_decode(self):
        layers = self.model.model.layers
        audit = joint.ExecutionAudit(layers)
        self.addCleanup(audit.close)
        audit.begin('decode')
        with self.assertRaisesRegex(RuntimeError, 'single-token'):
            layers[0].mlp(torch.zeros(1, 2, 64))


if __name__ == '__main__':
    unittest.main()
