"""CPU fixtures test scoring boundaries and branch state, not task quality."""
import copy
from types import SimpleNamespace
import unittest

import torch
from torch import nn
from torch.nn import functional as F

from .cached_score import (_restore_branch, _seed_streams, _snapshot_branch,
                          batch_seed, document_batches, evaluate_tasks)


class FakeCache:
    def __init__(self, values):
        self.values = values


class FakeAttention(nn.Module):
    def forward(self, hidden_states):
        return hidden_states


class Qwen2MLP(nn.Module):
    def __init__(self, noise=False):
        super().__init__()
        self.noise = noise
        self.rng_input = torch.Generator().manual_seed(1)
        self.rng_product = torch.Generator().manual_seed(2)

    def forward(self, x):
        if not self.noise:
            return x
        return x + .002 * (torch.rand(x.shape, generator=self.rng_input) +
                           torch.rand(x.shape, generator=self.rng_product))


class FakeLayer(nn.Module):
    def __init__(self, noise=False):
        super().__init__()
        self.self_attn = FakeAttention()
        self.mlp = Qwen2MLP(noise)


class FakeBackbone(nn.Module):
    def __init__(self, noise=False):
        super().__init__()
        self.layers = nn.ModuleList([FakeLayer(noise) for _ in range(24)])
        self.parameter = nn.Parameter(torch.zeros(1))
        self.queries = []

    def forward(self, input_ids, past_key_values=None, use_cache=True):
        prefix = (input_ids.new_zeros((input_ids.shape[0], 0)) if past_key_values is None
                  else past_key_values.values)
        tokens = torch.cat((prefix, input_ids), dim=1)
        if past_key_values is None:
            cache = FakeCache(tokens.clone())
        else:
            # Deliberately mutate, like the real DynamicCache.
            past_key_values.values = tokens.clone()
            cache = past_key_values
        self.queries.append((tuple(prefix.shape), input_ids.clone()))
        hidden = tokens.cumsum(1)[:, -input_ids.shape[1]:].float().unsqueeze(-1)
        for layer in self.layers:
            hidden = layer.self_attn(hidden)
            hidden = layer.mlp(hidden)
        return SimpleNamespace(last_hidden_state=hidden, past_key_values=cache)


class FakeHead(nn.Module):
    def forward(self, hidden):
        centers = torch.arange(8, device=hidden.device).float()
        return -.03 * (hidden - centers).square()


class FakeModel(nn.Module):
    def __init__(self, noise=False):
        super().__init__()
        self.model, self.lm_head = FakeBackbone(noise), FakeHead()
        self.config = SimpleNamespace(vocab_size=8)


def document(name='x', context=None, choices=None):
    return dict(id=name, task='toy', context_ids=context or [1, 2, 3],
                choices_ids=choices or [[4], [5, 6, 1]])


def score(rows, noise=False, **kwargs):
    model = FakeModel(noise).eval()
    result = evaluate_tasks(model, rows, dict(mode='sdpa', ffn='none', context=128,
                                           **kwargs))
    return model, result


class ScoringTests(unittest.TestCase):
    def test_first_token_and_every_answer_token(self):
        model, result = score([document()])
        choices = result['documents'][0]['choices']
        def manual(answer):
            prefix, total = [1, 2, 3], 0.
            for target in answer:
                logits = FakeHead()(torch.tensor([[sum(prefix)]], dtype=torch.float32))
                total += float(F.log_softmax(logits, -1)[0, target])
                prefix.append(target)
            return total
        self.assertAlmostEqual(choices[0]['logprob'], manual([4]), places=6)
        self.assertAlmostEqual(choices[1]['logprob'], manual([5, 6, 1]), places=6)
        queries = model.model.queries
        self.assertEqual(queries[0][1].tolist(), [[1, 2]])
        self.assertEqual(queries[1][1].tolist(), [[3]])
        self.assertEqual(queries[2][1].tolist(), [[5]])
        self.assertEqual(queries[3][1].tolist(), [[6]])
        audit = result['execution_audit']
        self.assertEqual(audit['scored_choice_tokens'], 4)
        self.assertEqual(audit['actual_decode_calls'], 3)
        self.assertEqual(audit['attention_decode_calls_per_layer'], [3] * 24)
        self.assertEqual(audit['ffn_decode_calls_per_layer'], [3] * 24)

    def test_multilength_dummy_never_scores(self):
        rows = [document('a'), document('b', choices=[[2, 3, 4, 1], [1]])]
        _, result = score(rows)
        self.assertEqual([r['id'] for r in result['documents']], ['a', 'b'])
        audit = result['execution_audit']
        self.assertEqual(audit['scored_choice_tokens'], 9)
        self.assertEqual(audit['shared_first_query_rows'], 2)
        self.assertEqual(audit['branch_query_rows'], 5)
        self.assertEqual(audit['dummy_query_rows'], 1)
        self.assertEqual(audit['actual_decode_query_rows'], 8)
        # A real row is independent of the other row's longer branch/dummies.
        _, alone = score([rows[0]])
        self.assertEqual(result['documents'][0]['choices'], alone['documents'][0]['choices'])

    def test_choice_permutation_restores_noise(self):
        row = document(choices=[[4, 3, 1, 2], [5], [7, 6]])
        _, original = score([row], noise=True)
        swapped = copy.deepcopy(row)
        permutation = [2, 0, 1]
        swapped['choices_ids'] = [row['choices_ids'][i] for i in permutation]
        _, alternative = score([swapped], noise=True)
        actual = alternative['documents'][0]['choices']
        expect = original['documents'][0]['choices']
        self.assertEqual(actual, [expect[i] for i in permutation])

    def test_repeat_and_shared_one_token_logits(self):
        row = document(choices=[[4], [4], [3]])
        _, first = score([row], noise=True, seed=2)
        _, again = score([row], noise=True, seed=2)
        self.assertEqual(first['documents'], again['documents'])
        self.assertEqual(first['documents'][0]['choices'][0], first['documents'][0]['choices'][1])
        self.assertEqual(first['execution_audit']['actual_decode_calls'], 1)
        self.assertEqual(first['execution_audit']['scored_choice_tokens'], 3)

    def test_grouping_preserves_return_order_and_choice_counts(self):
        rows = [document('a', context=[1, 2, 3, 4]), document('b'),
                document('c', choices=[[1], [2], [3]])]
        batches = list(document_batches(rows, 16))
        self.assertEqual([[x['id'] for x in b] for b in batches], [['b'], ['c'], ['a']])
        _, result = score(rows)
        self.assertEqual([r['id'] for r in result['documents']], ['a', 'b', 'c'])

    def test_progress_receives_complete_batches(self):
        updates = []
        model = FakeModel().eval()
        result = evaluate_tasks(model, [document('a'), document('b')],
            dict(mode='sdpa', ffn='none', context=128, batch=1), progress=updates.append)
        self.assertEqual(len(updates), 2)
        self.assertEqual(updates[-1]['execution_audit']['scored_choice_tokens'], 8)
        self.assertEqual(result['execution_audit']['completed_documents'], 2)

    def test_invalid_requests_rejected(self):
        for rows in ([document(context=[1, 2])],
                     [document(choices=[[], [1]])],
                     [document(), document()],
                     [document(choices=[[9], [2]])]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                score(rows)
        with self.assertRaises(ValueError):
            score([document()], batch=17)
        with self.assertRaises(ValueError):
            evaluate_tasks(FakeModel().eval(), [document()],
                           dict(mode='sdpa', ffn='none', context=3))

    def test_batch_seed_excludes_choices(self):
        row = document()
        changed = copy.deepcopy(row)
        changed['choices_ids'] = [[7], [1]]
        self.assertEqual(batch_seed([row], 0), batch_seed([changed], 0))
        self.assertNotEqual(batch_seed([row], 0), batch_seed([row], 1))

    def test_cache_rng_summary_restore_without_counter_reset(self):
        layers = [SimpleNamespace(mlp=Qwen2MLP(True)) for _ in range(24)]
        generator = torch.Generator().manual_seed(123)
        controller = SimpleNamespace(seed=0, _rng={(0, 'cpu', 'sampler'): generator},
            _state={0: {'summary': (3, torch.ones(2, 2)), 'decode_calls': 1}})
        cache = FakeCache(torch.tensor([[1, 2, 3]]))
        snapshot = _snapshot_branch(cache, layers, controller)
        expected = torch.rand(4, generator=generator)
        ffn_expected = torch.rand(4, generator=layers[0].mlp.rng_input)
        cache.values.add_(99)
        controller._state[0]['summary'][1].add_(12)
        controller._state[0]['decode_calls'] += 1
        controller._rng[(0, 'cpu', 'selector')] = torch.Generator()
        restored = _restore_branch(snapshot, layers, controller)
        self.assertEqual(restored.values.tolist(), [[1, 2, 3]])
        self.assertTrue(torch.equal(controller._state[0]['summary'][1], torch.ones(2, 2)))
        self.assertEqual(controller._state[0]['decode_calls'], 2)
        self.assertNotIn((0, 'cpu', 'selector'), controller._rng)
        self.assertTrue(torch.equal(torch.rand(4, generator=generator), expected))
        self.assertTrue(torch.equal(torch.rand(4, generator=layers[0].mlp.rng_input), ffn_expected))
        restored.values.add_(5)
        twice = _restore_branch(snapshot, layers, controller)
        self.assertEqual(twice.values.tolist(), [[1, 2, 3]])

    def test_seed_streams_clear_summary_preserve_metrics(self):
        layers = [SimpleNamespace(mlp=Qwen2MLP(True))]
        controller = SimpleNamespace(seed=0, _rng={'old': torch.Generator()},
            _state={0: {'summary': (3, torch.ones(2)), 'decode_calls': 17}})
        _seed_streams(layers, controller, 42)
        self.assertEqual(controller.seed, 42)
        self.assertEqual(controller._rng, {})
        self.assertIsNone(controller._state[0]['summary'])
        self.assertEqual(controller._state[0]['decode_calls'], 17)
        self.assertEqual(layers[0].mlp.rng_input.initial_seed(), 742001)


class RealAdapterTests(unittest.TestCase):
    """24-layer synthetic model, actual unchanged FFN and finite Ising kernels."""
    @classmethod
    def setUpClass(cls):
        cls.threads = torch.get_num_threads()
        torch.set_num_threads(1)

    @classmethod
    def tearDownClass(cls):
        torch.set_num_threads(cls.threads)

    def setUp(self):
        from experiments.qwen_joint_stratified_attention_20261019.test_joint_evaluate import Model
        torch.manual_seed(3)
        self.model = Model().eval()
        self.rows = [document('a', choices=[[4], [5, 6, 1]]),
                     document('b', choices=[[2, 3, 4, 1], [1]])]
        self.calibration = dict(parameter=torch.zeros(24, 4), temperature=torch.ones(24, 4))
        self.case = dict(mode='screen_ising', ffn='b4_t32', context=128,
                         samples=4, burn=.2, spacing=.3, budget_blocks=3, seed=1)

    def test_actual_ising_ffn_audits_and_dummy_metrics(self):
        result = evaluate_tasks(self.model, self.rows, self.case, self.calibration)
        audit = result['execution_audit']
        self.assertEqual(audit['scored_choice_tokens'], 9)
        self.assertEqual(audit['actual_decode_query_rows'], 8)
        self.assertEqual(audit['attention_decode_calls_per_layer'], [4] * 24)
        self.assertEqual(audit['ffn_decode_calls_per_layer'], [4] * 24)
        self.assertEqual(result['sampling_stats']['totals']['query_token_rows'], 8 * 24)
        self.assertEqual(result['active_sampling_stats']['query_token_rows'], 7 * 24)
        self.assertEqual(result['active_sampling_stats']['selected_fraction'], 1.)
        self.assertEqual(result['sampling_stats']['totals']['sample_events'], 8 * 24 * 4 * 4)
        self.assertTrue(all(x['calls'] == 5 for x in result['ffn_stats'].values()))
        self.assertTrue(all(not hasattr(x.self_attn, '_joint_attention_owner') for x in self.model.model.layers))

    def test_real_adapter_choice_permutation_exact(self):
        model = copy.deepcopy(self.model)
        original = evaluate_tasks(self.model, self.rows, self.case, self.calibration)
        permuted_rows = copy.deepcopy(self.rows)
        permuted_rows[0]['choices_ids'].reverse()
        permuted = evaluate_tasks(model, permuted_rows, self.case, self.calibration)
        self.assertEqual(original['documents'][0]['choices'], list(reversed(permuted['documents'][0]['choices'])))
        self.assertEqual(original['documents'][1]['choices'], permuted['documents'][1]['choices'])

    def test_sdpa_wrapper_scores_exact_with_ffn(self):
        clone = copy.deepcopy(self.model)
        plain = evaluate_tasks(self.model, self.rows, dict(self.case, mode='sdpa'), self.calibration)
        wrapper = evaluate_tasks(clone, self.rows, dict(self.case, mode='digital_sdpa'), self.calibration)
        self.assertEqual(plain['documents'], wrapper['documents'])


if __name__ == '__main__':
    unittest.main()
