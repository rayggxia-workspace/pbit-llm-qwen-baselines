"""CPU-only policy, GQA, summary and model-patch regression tests."""
import math
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from experiments.attention_joint_ising import attention as module
from experiments.attention_joint_ising.attention import JointAttentionController, budget_blocks

torch = module.torch


class PolicyTests(unittest.TestCase):
    def test_quota_keeps_forced_then_raw_then_score_with_stable_ties(self):
        self.assertEqual(budget_blocks([1.] * 12, {4, 8}, 8), [0, 1, 2, 3, 4, 8, 10, 11])
        self.assertEqual(budget_blocks(list(range(12)), set(range(12)), 8), [0, 5, 6, 7, 8, 9, 10, 11])

    def test_short_context_and_insufficient_mandatory_budget(self):
        self.assertEqual(budget_blocks([1, 2], set(), 8), [0, 1])
        with self.assertRaises(ValueError):
            budget_blocks([1] * 10, set(), 2)

    def test_input_rejection(self):
        for args in ({'mode': 'screen_sampled'}, {'samples': 0}, {'burn': -1},
                     {'spacing': 0}, {'budget_blocks': 2}, {'target_fraction': 0},
                     {'selection': 'topk'}):
            with self.assertRaises(ValueError):
                JointAttentionController(**args)


if torch is not None:
    class Qwen2MLP(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.weight = torch.nn.Parameter(torch.ones(1))

    class FakeAttention(torch.nn.Module):
        def __init__(self, index):
            super().__init__()
            self.layer_idx, self.num_heads, self.num_key_value_heads = index, 4, 2
            self.num_key_value_groups, self.head_dim, self.hidden_size = 2, 2, 8
            self.q_proj = torch.nn.Linear(8, 8)
            self.k_proj, self.v_proj = torch.nn.Linear(8, 4), torch.nn.Linear(8, 4)
            self.o_proj = torch.nn.Linear(8, 8)
            self.original_calls = 0

        def rotary_emb(self, v, position_ids):
            return torch.ones((v.shape[0], v.shape[-2], 2)), torch.zeros((v.shape[0], v.shape[-2], 2))

        def forward(self, hidden_states, **kwargs):
            self.original_calls += 1
            return hidden_states + 123, None, kwargs.get('past_key_value')

    class FakeModel(torch.nn.Module):
        def __init__(self, layers=24):
            super().__init__()
            self.config = SimpleNamespace(num_hidden_layers=layers)
            self.model = torch.nn.Module()
            self.model.layers = torch.nn.ModuleList()
            for i in range(layers):
                layer = torch.nn.Module()
                layer.self_attn, layer.mlp = FakeAttention(i), Qwen2MLP()
                self.model.layers.append(layer)

    class FakeCache:
        def __init__(self):
            self.data, self.kwargs = {}, {}

        def update(self, k, v, index, kwargs):
            self.kwargs[index] = kwargs
            if index in self.data:
                old_k, old_v = self.data[index]
                k, v = torch.cat((old_k, k), -2), torch.cat((old_v, v), -2)
            self.data[index] = k, v
            return k, v


    def reference_qwen_sdpa(a, hidden_states, cache, cos, sin, cache_position):
        """Independent transcription of pinned Qwen2SdpaAttention:578-637.

        Uses original dtype, nontrivial RoPE, real projection modules and an
        independent cache. This is a wrapper regression, not a GPU/PPL claim.
        """
        b, n, _ = hidden_states.shape
        query = a.q_proj(hidden_states).view(b, n, a.num_heads, a.head_dim).transpose(1, 2)
        key = a.k_proj(hidden_states).view(b, n, a.num_key_value_heads, a.head_dim).transpose(1, 2)
        value = a.v_proj(hidden_states).view(b, n, a.num_key_value_heads, a.head_dim).transpose(1, 2)
        def rotate(x):
            first, second = x[..., :x.shape[-1] // 2], x[..., x.shape[-1] // 2:]
            return torch.cat((-second, first), dim=-1)
        cos1, sin1 = cos.unsqueeze(1), sin.unsqueeze(1)
        query, key = query * cos1 + rotate(query) * sin1, key * cos1 + rotate(key) * sin1
        key, value = cache.update(key, value, a.layer_idx, {'sin': sin, 'cos': cos, 'cache_position': cache_position})
        def repeat(x):
            batch, heads, length, dim = x.shape
            return x[:, :, None, :, :].expand(batch, heads, a.num_key_value_groups, length, dim).reshape(batch, a.num_heads, length, dim)
        out = torch.nn.functional.scaled_dot_product_attention(query, repeat(key), repeat(value),
            attn_mask=None, dropout_p=0.0, is_causal=False)
        return a.o_proj(out.transpose(1, 2).contiguous().view(b, n, a.hidden_size))


@unittest.skipIf(torch is None, 'Torch is not installed in this Python runtime')
class AttentionTests(unittest.TestCase):
    def setUp(self):
        torch.manual_seed(10)
        self.model = FakeModel().eval()

    def controller(self, **kwargs):
        c = JointAttentionController(**kwargs).install(self.model)
        self.addCleanup(c.close)
        return c

    def test_torch_quota_matches_scalar_v4_oracle(self):
        scores = torch.randint(0, 4, (2, 4, 12)).float()
        raw = torch.rand(2, 4, 12) > .5
        forced = torch.tensor([True] + [False] * 9 + [True, True])
        result = module._fixed_mask(scores, raw, forced, 8)
        for b in range(2):
            for h in range(4):
                expected = budget_blocks(scores[b, h].tolist(), raw[b, h].nonzero().flatten().tolist(), 8)
                self.assertEqual(result[b, h].nonzero().flatten().tolist(), expected)

    def test_prefill_delegation_all_24_layers_and_no_parameter_changes(self):
        before = {k: v.clone() for k, v in self.model.state_dict().items()}
        parameter_ids = [id(p) for p in self.model.parameters()]
        originals = [layer.self_attn.forward for layer in self.model.model.layers]
        c = self.controller(mode='digital_exact')
        for layer in self.model.model.layers:
            x = torch.randn(1, 3, 8)
            out, _, _ = layer.self_attn(x)
            self.assertTrue(torch.equal(out, x + 123))
            layer.self_attn(x[:, :1])
        stats = c.stats()
        self.assertEqual(stats['installed_layers'], 24)
        self.assertTrue(all(s['prefill_calls'] == s['decode_calls'] == 1 for s in stats['layers'].values()))
        self.assertEqual(parameter_ids, [id(p) for p in self.model.parameters()])
        for name, value in self.model.state_dict().items():
            self.assertTrue(torch.equal(value, before[name]))
        c.close()
        self.assertEqual(originals, [layer.self_attn.forward for layer in self.model.model.layers])

    def test_dense_gqa_matches_repeat_kv_reference(self):
        c = self.controller(mode='digital_exact')
        a = self.model.model.layers[0].self_attn
        q, k, v = torch.randn(2, 4, 1, 2), torch.randn(2, 2, 13, 2), torch.randn(2, 2, 13, 2)
        out = c._core(a, q, k, v)
        p = (q @ k.repeat_interleave(2, 1).transpose(-1, -2) / math.sqrt(2)).softmax(-1)
        self.assertTrue(torch.allclose(out, p @ v.repeat_interleave(2, 1), atol=2e-6))

    def test_sample_gqa_local_to_global_address_and_no_target_softmax(self):
        c = self.controller(mode='screen_ising', samples=2)
        a = self.model.model.layers[0].self_attn
        mask = torch.tensor([[[False, True, True], [True, False, True], [False, True, True], [True, False, True]]])
        k = torch.randn(1, 2, 130, 2)
        v = torch.arange(130).reshape(1, 1, 130, 1).expand(1, 2, 130, 2).clone().float()
        v[:, 1] += 1000
        q = torch.randn(1, 4, 1, 2)
        local = torch.tensor([[0, 65], [0, 65], [0, 65], [0, 65]])
        with patch.object(c, '_select', return_value=(mask, mask)), patch.object(c, '_sample_indices', return_value=(local, {})):
            with patch.object(torch.Tensor, 'softmax', side_effect=AssertionError('target softmax forbidden')):
                out = c._core(a, q, k, v)
        expected = torch.tensor([96.5, 64.5, 1096.5, 1064.5]).reshape(1, 4, 1, 1).expand_as(out)
        self.assertTrue(torch.equal(out, expected))

    def test_incremental_summary_equals_rebuild_at_subblock_and_block_boundaries(self):
        c = self.controller(mode='screen_exact')
        a = self.model.model.layers[0].self_attn
        full = torch.randn(1, 2, 66, 2)
        for length in range(1, 67):
            got = c._summaries(a, full[:, :, :length]).clone()
            packed = torch.nn.functional.pad(full[:, :, :length], (0, 0, 0, (-length) % 64))
            expected = packed.reshape(1, 2, -1, 4, 16, 2).sum(-2)
            self.assertTrue(torch.allclose(got, expected, atol=3e-6), length)
        self.assertEqual(c.stats()['layers']['0']['summary_builds'], 1)
        self.assertEqual(c.stats()['layers']['0']['summary_updates'], 65)

    def test_fixed_budget_partial_tail_and_padding_rejection(self):
        c = self.controller(mode='screen_ising', samples=1)
        a = self.model.model.layers[0].self_attn
        q, k, v = torch.randn(1, 4, 1, 2), torch.randn(1, 2, 2049, 2), torch.randn(1, 2, 2049, 2)
        with patch.object(c, '_sample_indices', side_effect=lambda logits, layer: (torch.zeros(4, 1, dtype=torch.long), {})):
            c._core(a, q, k, v)
        self.assertEqual(c.stats()['layers']['0']['candidate_min'], 449)
        self.assertEqual(c.stats()['layers']['0']['candidate_max'], 449)
        with patch.object(c, '_sample_indices', return_value=(torch.full((4, 1), 449, dtype=torch.long), {})):
            with self.assertRaisesRegex(RuntimeError, 'padding'):
                c._core(a, q, k, v)

    def test_decode_cache_update_and_mask_failure(self):
        c = self.controller(mode='digital_exact')
        a, cache = self.model.model.layers[0].self_attn, FakeCache()
        for _ in range(2):
            a(torch.randn(1, 1, 8), past_key_value=cache, cache_position=torch.tensor([0]))
        self.assertEqual(cache.data[0][0].shape, (1, 2, 2, 2))
        self.assertEqual(set(cache.kwargs[0]), {'sin', 'cos', 'cache_position'})
        with self.assertRaisesRegex(ValueError, 'unmasked'):
            a(torch.randn(1, 1, 8), attention_mask=torch.zeros(1, 1, 1, 2))

    def test_reset_replays_selection_and_refuses_double_patch(self):
        c = self.controller(mode='screen_exact')
        a = self.model.model.layers[0].self_attn
        q, k = torch.randn(1, 4, 1, 2), torch.randn(1, 2, 1024, 2)
        first = c._select(a, q, k)[0]
        c.reset()
        self.assertTrue(torch.equal(first, c._select(a, q, k)[0]))
        with self.assertRaisesRegex(RuntimeError, 'already patched'):
            JointAttentionController().install(self.model)

    def test_selector_random_stream_does_not_depend_on_samples_or_backend(self):
        q, k = torch.randn(2, 4, 1, 2), torch.randn(2, 2, 2048, 2)
        expected = None
        for mode, samples in (('screen_exact', 32), ('screen_iid', 128), ('screen_ising', 512)):
            c = JointAttentionController(mode=mode, samples=samples, seed=9).install(self.model)
            a = self.model.model.layers[0].self_attn
            masks = [tuple(x.clone() for x in c._select(a, q, k)) for _ in range(2)]
            c.close()
            if expected is None:
                expected = masks
            else:
                for first, second in zip(expected, masks):
                    self.assertTrue(all(torch.equal(x, y) for x, y in zip(first, second)))

    def test_calibrated_variable_selector_and_true_padding(self):
        calibration = {'parameter': torch.full((24, 4), -1000.), 'temperature': torch.ones(24, 4)}
        c = self.controller(mode='screen_ising', samples=1, selection='variable', calibration=calibration)
        a = self.model.model.layers[0].self_attn
        q, k, v = torch.randn(1, 4, 1, 2), torch.randn(1, 2, 2049, 2), torch.randn(1, 2, 2049, 2)
        selected, raw = c._select(a, q, k)
        self.assertTrue(torch.equal(selected, raw))
        self.assertTrue(torch.equal(selected.sum(-1), torch.full((1, 4), 3)))
        # One head has an extra block; the other heads have invalid padded slots.
        selected[0, 0, 1] = True
        def invalid_padding(logits, layer):
            self.assertEqual(logits.shape, (4, 193))
            self.assertTrue(torch.isneginf(logits[1:, 129:]).all())
            return torch.full((4, 1), 129, dtype=torch.long), {}
        with patch.object(c, '_select', return_value=(selected, raw)), patch.object(c, '_sample_indices', side_effect=invalid_padding):
            with self.assertRaisesRegex(RuntimeError, 'padding'):
                c._core(a, q, k, v)

    def test_query_token_and_head_units(self):
        c = self.controller(mode='digital_exact')
        a = self.model.model.layers[0].self_attn
        a(torch.randn(2, 1, 8))
        layer = c.stats()['layers']['0']
        self.assertEqual(layer['query_rows'], 8)
        self.assertEqual(layer['query_token_rows'], 2)

    def test_bf16_sdpa_core_bit_identical_to_original_invocation(self):
        c = self.controller(mode='digital_sdpa')
        a = self.model.model.layers[0].self_attn
        q, k, v = (x.to(torch.bfloat16) for x in
                   (torch.randn(2, 4, 1, 2), torch.randn(2, 2, 67, 2), torch.randn(2, 2, 67, 2)))
        expected = torch.nn.functional.scaled_dot_product_attention(q, k.repeat_interleave(2, 1),
            v.repeat_interleave(2, 1), attn_mask=None, dropout_p=0., is_causal=False)
        with patch.object(torch.Tensor, 'float', side_effect=AssertionError('SDPA input dtype must stay BF16')):
            got = c._core(a, q, k, v)
        self.assertEqual(got.dtype, torch.bfloat16)
        self.assertTrue(torch.equal(got, expected))
        layer = c.stats()['layers']['0']
        self.assertEqual(layer['query_token_rows'], 2)
        self.assertEqual(layer['query_rows'], 8)
        self.assertEqual(layer['candidate_min'], 67)
        self.assertEqual(layer['sample_events'], 0)

    def test_bf16_sdpa_wrapper_bit_identical_with_rope_and_gqa_cache(self):
        self.model.to(dtype=torch.bfloat16)
        c = self.controller(mode='digital_sdpa')
        a = self.model.model.layers[0].self_attn
        reference, patched = FakeCache(), FakeCache()
        initial_k, initial_v = torch.randn(2, 2, 5, 2).bfloat16(), torch.randn(2, 2, 5, 2).bfloat16()
        reference.data[0], patched.data[0] = (initial_k.clone(), initial_v.clone()), (initial_k.clone(), initial_v.clone())
        for position in (5, 6):
            x = torch.randn(2, 1, 8).bfloat16()
            angle = torch.randn(2, 1, 2)
            cos, sin = angle.cos().bfloat16(), angle.sin().bfloat16()
            cache_position = torch.tensor([position])
            expected = reference_qwen_sdpa(a, x, reference, cos, sin, cache_position)
            got, _, returned_cache = a(x, past_key_value=patched, position_embeddings=(cos, sin), cache_position=cache_position)
            self.assertTrue(torch.equal(got, expected))
            self.assertIs(returned_cache, patched)
            self.assertTrue(all(torch.equal(x, y) for x, y in zip(reference.data[0], patched.data[0])))
        self.assertEqual(c.stats()['layers']['0']['query_token_rows'], 4)


if __name__ == '__main__':
    unittest.main()
