"""CPU scoring mechanisms plus native-Qwen3 gates when Transformers is installed."""
import copy
import importlib.util
import math
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import torch
from torch import nn
from torch.nn import functional as F

from .scoring import evaluate_ppl, evaluate_tasks, full_window_plan, target_positions
from .adapter import SparQController
from .batch_scoring import evaluate_tasks_batched, document_groups


class ToyAttention(nn.Module):
    def __init__(self, layer):
        super().__init__()
        self.layer = layer

    def forward(self, hidden_states, cache):
        old, count = cache[self.layer]
        values = hidden_states.cumsum(1) + old[:, None]
        positions = torch.arange(count + 1, count + hidden_states.shape[1] + 1,
                                 device=hidden_states.device)[None, :, None]
        cache[self.layer] = (values[:, -1].clone(), count + hidden_states.shape[1])
        return hidden_states + values / positions * .03


class Qwen3MLP(nn.Module):
    def __init__(self, width):
        super().__init__()
        self.weight = nn.Parameter(torch.randn(width, width) * .04)

    def forward(self, hidden_states):
        return hidden_states + torch.tanh(F.linear(hidden_states, self.weight)) * .1


class ToyDecoder(nn.Module):
    def __init__(self, width, layer):
        super().__init__()
        self.self_attn = ToyAttention(layer)
        self.mlp = Qwen3MLP(width)


class ToyBody(nn.Module):
    def __init__(self, config):
        super().__init__()
        self.embedding = nn.Embedding(config.vocab_size, config.hidden_size)
        self.layers = nn.ModuleList(ToyDecoder(config.hidden_size, i)
                                   for i in range(config.num_hidden_layers))

    def forward(self, input_ids, past_key_values=None, use_cache=True):
        hidden = self.embedding(input_ids)
        cache = past_key_values
        if cache is None:
            cache = [(hidden.new_zeros(hidden.shape[0], hidden.shape[-1]), 0) for _ in self.layers]
        for layer in self.layers:
            hidden = layer.mlp(layer.self_attn(hidden, cache))
        return SimpleNamespace(last_hidden_state=hidden, past_key_values=cache)


class ToyModel(nn.Module):
    def __init__(self, layers=36):
        super().__init__()
        self.config = SimpleNamespace(model_type='qwen3', num_hidden_layers=layers,
                                      vocab_size=19, hidden_size=8, _attn_implementation='sdpa')
        self.model = ToyBody(self.config)
        self.lm_head = nn.Linear(8, 19, bias=False)


def model():
    torch.manual_seed(21)
    return ToyModel().eval()


def docs():
    return [dict(id='t:0', task='t', doc_id=0, context_ids=[1, 3, 4, 2],
                 choices_ids=[[5, 6, 2], [8], [7, 2]]),
            dict(id='t:1', task='t', doc_id=1, context_ids=[5],
                 choices_ids=[[2], [6, 9]])]


def mixed_docs():
    rows = docs() + [
        dict(id='t:2', task='t', doc_id=2, context_ids=[8, 9, 2, 4],
             choices_ids=[[2, 2], [3, 4, 5, 6], [4, 8, 9], [5], [6, 7]]),
        dict(id='t:3', task='t', doc_id=3, context_ids=[6, 1],
             choices_ids=[[3, 4], [5]]),
        dict(id='t:4', task='t', doc_id=4, context_ids=[2, 1, 2, 1],
             choices_ids=[[2, 3, 4], [5]]),
        dict(id='t:5', task='t', doc_id=5, context_ids=[8],
             choices_ids=[[6, 3, 1], [8, 2], [9]])]
    return rows


def independent_logprob(m, prefix, answer):
    terms, greedy = [], True
    with torch.inference_mode():
        for i, target in enumerate(answer):
            ids = torch.tensor([prefix + answer[:i]])
            output = m.model(ids, use_cache=False)
            lp = F.log_softmax(m.lm_head(output.last_hidden_state[:, -1]).float(), -1)
            terms.append(float(lp[0, target]))
            greedy &= int(lp.argmax(-1)[0]) == target
    return math.fsum(terms), greedy


class ScoringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)

    def test_full_ppl_matches_independent_repeated_prefix_oracle(self):
        m = model()
        ids = torch.tensor([i % 19 for i in range(23)])
        actual = evaluate_ppl(m, ids, mode='native', context=8, stride=4, batch=3)
        expected = []
        for row in full_window_plan(len(ids), 8, 4):
            for target in target_positions(row):
                ll, _ = independent_logprob(m, ids[row['begin']:target].tolist(), [int(ids[target])])
                expected.append(-ll)
        self.assertAlmostEqual(actual['nll_sum'], math.fsum(expected), places=5)
        self.assertEqual(actual['scored_tokens'], len(ids) - 1)
        self.assertTrue(actual['scoring_plan']['every_full_corpus_target_once'])
        self.assertEqual(actual['execution_audit']['tokens_per_layer']['decode']['attention'], [22] * 36)
        self.assertEqual(actual['execution_audit']['tokens_per_layer']['decode']['ffn'], [22] * 36)
        self.assertIn('qwen3/sparq/scoring.py', actual['source_files_sha256'])

    def test_full_plan_and_one_token_prefill_cover_targets_once(self):
        for length in (2, 3, 2048, 2049, 299078):
            plan = full_window_plan(length)
            self.assertEqual([p for row in plan for p in target_positions(row)], list(range(1, length)))
        result = evaluate_ppl(model(), torch.arange(9), mode='native', context=4, stride=2)
        self.assertTrue(any(row['prefill_tokens'] == 1 for row in result['records']))
        self.assertEqual(result['scored_tokens'], 8)

    def test_window_batching_preserves_ppl_and_coverage(self):
        m, ids = model(), torch.arange(31) % 19
        a = evaluate_ppl(m, ids, mode='native', context=8, stride=4, batch=1)
        b = evaluate_ppl(m, ids, mode='native', context=8, stride=4, batch=4)
        self.assertAlmostEqual(a['nll_sum'], b['nll_sum'], places=5)
        self.assertEqual(a['scoring_plan']['target_positions_sha256_le_int64'],
                         b['scoring_plan']['target_positions_sha256_le_int64'])
        self.assertLess(b['execution_audit']['calls']['decode'], a['execution_audit']['calls']['decode'])

    def test_task_cache_isolation_independent_oracle_and_option_permutation(self):
        m, documents = model(), docs()
        result = evaluate_tasks(m, documents, mode='native')
        for row, actual in zip(documents, result['documents']):
            for answer, score in zip(row['choices_ids'], actual['choices']):
                ll, greedy = independent_logprob(m, row['context_ids'], answer)
                self.assertAlmostEqual(score['logprob'], ll, places=5)
                self.assertEqual(score['is_greedy'], greedy)
        changed = copy.deepcopy(documents)
        for row in changed:
            row['choices_ids'].reverse()
        permuted = evaluate_tasks(m, changed, mode='native')
        for a, b in zip(result['documents'], permuted['documents']):
            self.assertEqual(a['choices'], list(reversed(b['choices'])))
        self.assertEqual(result['choice_target_scores'], 9)
        self.assertEqual(result['shared_first_target_reuses'], 3)
        self.assertEqual(result['execution_audit']['tokens_per_layer']['decode']['attention'], [6] * 36)

    def test_smoke_limits_never_claim_complete(self):
        result = evaluate_ppl(model(), torch.arange(12), mode='native', context=8,
                              stride=4, max_windows=10)
        self.assertFalse(result['complete'])
        self.assertFalse(result['scoring_plan']['every_full_corpus_target_once'])
        task_result = evaluate_tasks(model(), docs(), mode='native', doc_limit=20)
        self.assertFalse(task_result['complete'])

    def test_choice_batch_removes_finished_rows_and_matches_serial_scores(self):
        documents = docs() + [dict(id='t:2', task='t', doc_id=2, context_ids=[8, 9],
                                  choices_ids=[[2, 2], [3, 4, 5, 6], [4, 8, 9]])]
        m = model()
        a = evaluate_tasks(m, documents, mode='native', choice_batch=1)
        b = evaluate_tasks(m, documents, mode='native', choice_batch=4)
        for x, y in zip(a['documents'], b['documents']):
            for p, q in zip(x['choices'], y['choices']):
                self.assertAlmostEqual(p['logprob'], q['logprob'], places=5)
                self.assertEqual(p['is_greedy'], q['is_greedy'])
        self.assertEqual(a['execution_audit']['tokens_per_layer'], b['execution_audit']['tokens_per_layer'])
        self.assertLess(b['execution_audit']['calls']['decode'], a['execution_audit']['calls']['decode'])

    def test_contiguous_segment_resume_preserves_ids_nll_and_exact_coverage(self):
        m, ids = model(), torch.arange(23) % 19
        whole = evaluate_ppl(m, ids, mode='native', context=8, stride=4, batch=1)
        left = evaluate_ppl(m, ids, mode='native', context=8, stride=4, batch=1,
                            segment_start=0, segment_count=2)
        right = evaluate_ppl(m, ids, mode='native', context=8, stride=4, batch=1,
                             segment_start=2)
        self.assertEqual(left['records'] + right['records'], whole['records'])
        self.assertEqual(math.fsum([left['nll_sum'], right['nll_sum']]), whole['nll_sum'])
        self.assertEqual(left['scored_tokens'] + right['scored_tokens'], 22)
        for result in (left, right):
            self.assertFalse(result['complete'])
            self.assertEqual(result['scope'], 'partial_segments')
            self.assertFalse(result['scoring_plan']['every_full_corpus_target_once'])
            self.assertEqual(result['scoring_plan']['requested_segments'], len(whole['records']))
        self.assertEqual(right['records'][0]['segment_id'], 2)
        with self.assertRaisesRegex(ValueError, 'outside'):
            evaluate_ppl(m, ids, mode='native', context=8, stride=4, segment_start=99)
        with self.assertRaisesRegex(ValueError, 'exclusive'):
            evaluate_ppl(m, ids, mode='native', segment_count=1, max_windows=1)
        with self.assertRaisesRegex(ValueError, 'RNG-state'):
            evaluate_ppl(m, ids, mode='native', segment_count=1, ffn='b4_t32')

    def test_official_metrics_receive_original_loglikelihood_and_greedy(self):
        calls = []
        task = SimpleNamespace(eval_docs=['doc0', 'doc1'])
        def metrics(doc, values):
            calls.append((doc, values))
            return {'acc': 0., 'acc_norm': 1.}
        task.process_results = metrics
        result = evaluate_tasks(model(), docs(), mode='native', tasks={'t': task})
        self.assertEqual([c[0] for c in calls], ['doc0', 'doc1'])
        self.assertEqual(calls[0][1], [(v['logprob'], v['is_greedy']) for v in result['documents'][0]['choices']])
        self.assertEqual(result['documents'][0]['metrics'], {'acc': 0., 'acc_norm': 1.})

    def test_cpu_no_cuda_and_progress_exception_removes_hooks(self):
        m = model()
        with (patch.object(torch.cuda, 'is_available', side_effect=AssertionError('CUDA probed')),
              patch.object(torch.cuda, 'get_rng_state', side_effect=AssertionError('CUDA initialized'))):
            evaluate_tasks(m, docs(), mode='native')
        def fail(_):
            raise RuntimeError('injected artifact callback failure')
        with self.assertRaisesRegex(RuntimeError, 'injected'):
            evaluate_tasks(m, docs(), mode='native', progress=fail)
        self.assertTrue(all(not module._forward_pre_hooks for module in m.modules()))

    def test_duplicate_and_overlength_requests_fail_before_forward(self):
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            evaluate_tasks(model(), docs() * 2, mode='native')
        with self.assertRaisesRegex(ValueError, 'length'):
            evaluate_tasks(model(), docs(), mode='native', max_length=2)

    def test_logical_counter_vector_preserves_exact_integer_totals_and_schema(self):
        controller = SparQController('dense')
        state = {'diagnostics': {}}
        controller.layers[0] = state
        for value in (2**40, 3):
            controller._record(state, dict(candidate_ids=torch.tensor([999]),
                logical_counts={'groups': torch.tensor(2), 'reads': torch.tensor(value)}))
        result = controller.stats()['layers']['0']['diagnostics']
        self.assertEqual(result, {'logical_counts.groups': 4, 'logical_counts.reads': 2**40 + 3})
        with self.assertRaisesRegex(RuntimeError, 'schema'):
            controller._record(state, {'logical_counts': {'renamed': torch.tensor(1)}})

    def test_document_batches_match_independent_scores_and_restore_all_orders(self):
        m, rows, progress = model(), mixed_docs(), []
        result = evaluate_tasks_batched(m, rows, mode='native', progress=progress.append)
        self.assertEqual([row['id'] for row in result['documents']], [row['id'] for row in rows])
        self.assertEqual([event['record']['id'] for event in progress], [row['id'] for row in rows])
        self.assertEqual([event['completed'] for event in progress], list(range(1, 7)))
        for source, scored in zip(rows, result['documents']):
            for answer, score in zip(source['choices_ids'], scored['choices']):
                expected, greedy = independent_logprob(m, source['context_ids'], answer)
                self.assertAlmostEqual(score['logprob'], expected, places=5)
                self.assertEqual(score['is_greedy'], greedy)
        serial = evaluate_tasks(m, rows, mode='native', choice_batch=1)
        self.assertEqual(result['execution_audit']['tokens_per_layer'], serial['execution_audit']['tokens_per_layer'])
        self.assertLess(result['execution_audit']['calls']['decode'], serial['execution_audit']['calls']['decode'])
        self.assertEqual(result['group_document_counts'], [3, 2, 1])
        self.assertEqual(result['group_choice_counts'], [10, 5, 2])

    def test_document_option_permutation_and_other_document_change_do_not_leak(self):
        m, rows = model(), mixed_docs()
        result = evaluate_tasks_batched(m, rows, mode='native')
        changed = copy.deepcopy(rows)
        for row in changed:
            row['choices_ids'].reverse()
        permuted = evaluate_tasks_batched(m, changed, mode='native')
        for a, b in zip(result['documents'], permuted['documents']):
            self.assertEqual(a['choices'], list(reversed(b['choices'])))
        changed = copy.deepcopy(rows)
        changed[0]['context_ids'][-1] = 18
        mutated = evaluate_tasks_batched(m, changed, mode='native')
        self.assertNotEqual(result['documents'][0]['choices'], mutated['documents'][0]['choices'])
        self.assertEqual(result['documents'][1:], mutated['documents'][1:])

    def test_document_groups_use_actual_arc_choice_count_and_enforce_limits(self):
        rows = [dict(id=str(i), context_ids=[1, 2], choices_ids=[[j] for j in range(5)])
                for i in range(15)]
        groups = list(document_groups(rows, 8, 32))
        self.assertEqual([len(group) for group in groups], [6, 6, 3])
        self.assertTrue(all(sum(len(rows[i]['choices_ids']) for i in group) <= 32 for group in groups))
        with self.assertRaisesRegex(ValueError, 'limits'):
            evaluate_tasks_batched(model(), mixed_docs(), mode='native', document_batch=9)
        with self.assertRaisesRegex(ValueError, 'original FFN'):
            evaluate_tasks_batched(model(), mixed_docs(), mode='native', ffn='b4_t32')

    def test_document_batch_official_metrics_smoke_and_exception_cleanup(self):
        rows, m, seen = mixed_docs(), model(), []
        task = SimpleNamespace(eval_docs=list(range(len(rows))))
        def metric(doc, pairs):
            seen.append((doc, pairs))
            return {'acc': float(doc % 2), 'acc_norm': float((doc + 1) % 2)}
        task.process_results = metric
        result = evaluate_tasks_batched(m, rows, mode='native', tasks={'t': task}, doc_limit=20)
        self.assertFalse(result['complete'])
        by_id = {index: pairs for index, pairs in seen}
        for index, row in enumerate(result['documents']):
            self.assertEqual(by_id[index], [(v['logprob'], v['is_greedy']) for v in row['choices']])
            self.assertEqual(row['metrics']['acc'], float(index % 2))
        def fail(_):
            raise RuntimeError('group progress failed')
        with self.assertRaisesRegex(RuntimeError, 'group progress'):
            evaluate_tasks_batched(m, rows, mode='native', progress=fail)
        self.assertTrue(all(not module._forward_pre_hooks for module in m.modules()))


@unittest.skipUnless(importlib.util.find_spec('transformers'), 'native Qwen3 gates require pinned Transformers 4.51.3')
class NativeQwen3Tests(unittest.TestCase):
    @staticmethod
    def fresh():
        from transformers import Qwen3Config, Qwen3ForCausalLM
        torch.manual_seed(17)
        c = Qwen3Config(vocab_size=31, hidden_size=64, intermediate_size=128,
                       num_hidden_layers=2, num_attention_heads=4, num_key_value_heads=2,
                       head_dim=32, attention_dropout=0., max_position_embeddings=128)
        c._attn_implementation = 'sdpa'
        return Qwen3ForCausalLM(c).eval()

    def test_native_wrapper_bitwise_nonsquare_qkv_and_single_prefix(self):
        m, ids = self.fresh(), torch.arange(15)
        self.assertNotEqual(m.config.hidden_size, m.config.num_attention_heads * m.config.head_dim)
        a = evaluate_ppl(m, ids, mode='native', context=4, stride=2, capture_logits_hash=True)
        b = evaluate_ppl(m, ids, mode='dense', context=4, stride=2, capture_logits_hash=True)
        self.assertEqual(a['scored_logits_sha256'], b['scored_logits_sha256'])
        self.assertEqual(a['nll_sum'], b['nll_sum'])
        self.assertTrue(all(not hasattr(x.self_attn, '_sparq_owner') for x in m.model.layers))
        native_chunk = evaluate_ppl(m, ids, mode='native', context=4, stride=2,
                                   segment_start=1, segment_count=2, capture_logits_hash=True)
        dense_chunk = evaluate_ppl(m, ids, mode='dense', context=4, stride=2,
                                  segment_start=1, segment_count=2, capture_logits_hash=True)
        self.assertEqual(native_chunk['scored_logits_sha256'], dense_chunk['scored_logits_sha256'])
        self.assertEqual(native_chunk['nll_sum'], dense_chunk['nll_sum'])

    def test_native_mc_wrapper_and_b4_t32_opt_in(self):
        m = self.fresh()
        a = evaluate_tasks(m, docs(), mode='native')
        b = evaluate_tasks(m, docs(), mode='dense')
        self.assertEqual(a['documents'], b['documents'])
        x = evaluate_ppl(copy.deepcopy(m), torch.arange(8), mode='native', context=8,
                         stride=4, ffn='b4_t32', seed=9)
        y = evaluate_ppl(copy.deepcopy(m), torch.arange(8), mode='dense', context=8,
                         stride=4, ffn='b4_t32', seed=9)
        self.assertEqual(x['nll_sum'], y['nll_sum'])

    def test_native_dynamic_cache_document_branching_and_bf16_shape_boundary(self):
        from .core import SparQConfig
        for dtype in (torch.float32, torch.bfloat16):
            m = self.fresh()
            for parameter in m.parameters():
                parameter.data = parameter.data.to(dtype)
            self.assertEqual(m.model.rotary_emb.inv_freq.dtype, torch.float32)
            rows = mixed_docs()
            serial = evaluate_tasks(m, rows, mode='native', choice_batch=1)
            native = evaluate_tasks_batched(m, rows, mode='native')
            wrapped = evaluate_tasks_batched(m, rows, mode='dense')
            self.assertEqual(native['documents'], wrapped['documents'])
            for a, b in zip(serial['documents'], native['documents']):
                for p, q in zip(a['choices'], b['choices']):
                    # Predetermined numeric bound; BF16 batch-shape changes are
                    # measured separately from the strict same-shape wrapper gate.
                    per_token = abs(p['logprob'] - q['logprob']) / p['tokens']
                    self.assertLessEqual(per_token, .02 if dtype == torch.bfloat16 else 2e-5)
                self.assertEqual(max(range(len(a['choices'])), key=lambda i: a['choices'][i]['logprob']),
                                 max(range(len(b['choices'])), key=lambda i: b['choices'][i]['logprob']))
            sparse_config = SparQConfig(r=8, k_total=3, local_total=1)
            sparse_serial = evaluate_tasks(m, rows, mode='sparq', config=sparse_config, choice_batch=1)
            sparse_batched = evaluate_tasks_batched(m, rows, mode='sparq', config=sparse_config)
            self.assertGreater(sum(layer['diagnostics']['logical_counts.sparse_groups']
                                   for layer in sparse_batched['execution_audit']['replacement']['layers'].values()), 0)
            self.assertEqual(sparse_serial['execution_audit']['tokens_per_layer'],
                             sparse_batched['execution_audit']['tokens_per_layer'])
            for a, b in zip(sparse_serial['documents'], sparse_batched['documents']):
                for p, q in zip(a['choices'], b['choices']):
                    difference = abs(p['logprob'] - q['logprob']) / p['tokens']
                    self.assertLessEqual(difference, .02 if dtype == torch.bfloat16 else 2e-5)


if __name__ == '__main__':
    unittest.main()
