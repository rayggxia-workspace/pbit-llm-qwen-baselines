"""CPU mechanism tests; synthetic 24-layer models are not task accuracy."""
from dataclasses import asdict
import copy
import json
from pathlib import Path
import tempfile
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import torch
from torch import nn
from torch.nn import functional as F

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from experiments.pdnn_ffn.full_path_pdnn_ffn import FullPathPBitFFN, FullPathPBitFFNConfig
from experiments.pdnn_task_accuracy_20261023 import pdnn_score as score


class Qwen2MLP(nn.Module):
    def __init__(self):
        super().__init__()
        self.linear = nn.Linear(4, 4)

    def forward(self, hidden):
        return self.linear(hidden) * .025


class TinyDecoder(nn.Module):
    def __init__(self):
        super().__init__()
        self.mlp = Qwen2MLP()

    def forward(self, hidden_states):
        return hidden_states + self.mlp(hidden_states)


class TinyBody(nn.Module):
    def __init__(self):
        super().__init__()
        self.embed = nn.Embedding(17, 4)
        self.layers = nn.ModuleList(TinyDecoder() for _ in range(24))

    def forward(self, input_ids, past_key_values=None, use_cache=True):
        hidden = self.embed(input_ids)
        if past_key_values is None:
            past_key_values = {'sum': torch.zeros(input_ids.shape[0], 1, 4, device=hidden.device, dtype=hidden.dtype)}
        initial = past_key_values['sum'].clone()
        past_key_values['sum'].add_(hidden.sum(1, keepdim=True))  # Intentionally mutable cache.
        hidden = hidden.cumsum(1) + initial
        for layer in self.layers:
            hidden = layer(hidden)
        return SimpleNamespace(last_hidden_state=hidden, past_key_values=past_key_values)


class TinyModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.model = TinyBody()
        self.lm_head = nn.Linear(4, 17)
        self.config = SimpleNamespace(hidden_size=4, vocab_size=17)


def fresh_model(layers=(6, 12), samples=4, coding='bipolar'):
    torch.random.default_generator.manual_seed(123)
    model = TinyModel()
    for index in layers:
        student = FullPathPBitFFN(FullPathPBitFFNConfig(input_size=4, hidden_sizes=(6,), output_size=4,
                                                     input_temperature=.25, coding=coding))
        student.set_sample_count(samples)
        model.model.layers[index].mlp = student
    return model.to(dtype=torch.bfloat16).eval().requires_grad_(False)


def variant(layers=(6, 12), samples=4, seed=7, batch=2):
    return dict(layers=list(layers), samples=samples, seed=seed, batch=batch, context=32)


def documents():
    return [dict(id='tiny:0', task='tiny', context_ids=[1, 2, 3], choices_ids=[[4, 5, 6], [7]]),
            dict(id='tiny:1', task='tiny', context_ids=[3, 2, 1], choices_ids=[[8], [9, 10]]),
            dict(id='tiny:2', task='tiny', context_ids=[2, 3, 4, 5], choices_ids=[[6, 7], [8, 9, 10]])]


def independent_cached_reference(model, docs, case):
    """Repeat the entire prefix per choice; no shared KV/first-logits snapshot."""
    rows = score._validated_documents(docs, case['context'])
    outputs = {}
    caller = score.rng_snapshot(torch.device('cpu'))
    try:
        with torch.inference_mode():
            for batch_rows in score.document_batches(rows, case['batch']):
                seed = score.batch_seed(batch_rows, case['seed'])
                orders = [sorted(range(len(r['choices_ids'])), key=lambda j, r=r: tuple(r['choices_ids'][j]))
                          for r in batch_rows]
                for branch in range(len(batch_rows[0]['choices_ids'])):
                    # Recompute from the initial batch seed, including every prefix draw.
                    score.rng_seed(seed, torch.device('cpu'))
                    context = torch.tensor([r['context_ids'] for r in batch_rows])
                    answers = [r['choices_ids'][order[branch]] for r, order in zip(batch_rows, orders)]
                    prefix = model.model(input_ids=context[:, :-1], use_cache=True)
                    cache = prefix.past_key_values
                    values = torch.zeros(len(answers), dtype=torch.float64)
                    greedy = torch.ones(len(answers), dtype=torch.bool)
                    for step in range(max(map(len, answers))):
                        tokens = context[:, -1:] if step == 0 else torch.tensor(
                            [[a[step-1] if step-1 < len(a) else 0] for a in answers])
                        result = model.model(input_ids=tokens, past_key_values=cache, use_cache=True)
                        cache = result.past_key_values
                        logits = model.lm_head(result.last_hidden_state[:, -1]).float()
                        target = torch.tensor([a[step] if step < len(a) else 0 for a in answers])
                        active = torch.tensor([step < len(a) for a in answers])
                        ll = F.log_softmax(logits, -1).gather(-1, target[:, None]).squeeze(-1).double()
                        values += torch.where(active, ll, 0.)
                        greedy &= (~active) | (logits.argmax(-1) == target)
                    for row, order, answer, value, exact in zip(batch_rows, orders, answers, values.tolist(), greedy.tolist()):
                        outputs.setdefault(row['id'], {})[order[branch]] = dict(logprob=value, is_greedy=exact, tokens=len(answer))
    finally:
        score.rng_restore(caller)
    return {key: [values[i] for i in sorted(values)] for key, values in outputs.items()}


class ScoringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)

    def test_cached_scores_match_independent_repeated_prefix_oracle(self):
        for layers in ((), (6, 12), (10, 11, 12, 13)):
            with self.subTest(layers=layers):
                model = fresh_model(layers)
                expected = independent_cached_reference(model, documents(), variant(layers))
                result = score.evaluate_tasks(model, documents(), variant(layers))
                self.assertEqual({r['id']: r['choices'] for r in result['documents']}, expected)
                self.assertEqual(result['execution_audit']['completed_documents'], 3)
                self.assertEqual(result['execution_audit']['scored_choice_tokens'], 12)
                self.assertEqual(result['execution_audit']['actual_prefill_calls'], 2)
                self.assertTrue(result['execution_audit']['every_scored_target_used_24_decoder_ffn_layers'])
                self.assertEqual(result['execution_audit']['ffn_decode_calls_per_layer'],
                                 [result['execution_audit']['actual_decode_calls']] * 24)

    def test_binary_operator_supported_and_actual_stochastic_seed_changes_scores(self):
        model = fresh_model(coding='binary')
        a = score.evaluate_tasks(model, documents(), variant(seed=7))
        b = score.evaluate_tasks(model, documents(), variant(seed=8))
        self.assertNotEqual([r['choices'] for r in a['documents']], [r['choices'] for r in b['documents']])

    def test_exact_replay_and_caller_rng_preserved(self):
        model = fresh_model()
        before = torch.get_rng_state().clone()
        a = score.evaluate_tasks(model, documents(), variant())
        self.assertTrue(torch.equal(before, torch.get_rng_state()))
        b = score.evaluate_tasks(model, documents(), variant())
        self.assertEqual(a['documents'], b['documents'])
        self.assertEqual(a['batches'], b['batches'])

    def test_option_permutation_leaves_mapped_scores_identical(self):
        model = fresh_model()
        a = score.evaluate_tasks(model, documents(), variant())
        changed = copy.deepcopy(documents())
        for row in changed:
            row['choices_ids'].reverse()
        b = score.evaluate_tasks(model, changed, variant())
        for left, right in zip(a['documents'], b['documents']):
            self.assertEqual(left['choices'], list(reversed(right['choices'])))

    def test_cpu_path_never_calls_cuda_or_initializes_it(self):
        model = fresh_model()
        calls = ('get_rng_state', 'set_rng_state', 'manual_seed', 'manual_seed_all',
                 'is_available', 'synchronize', 'current_device', 'init')
        patches = [patch.object(torch.cuda, name, side_effect=AssertionError('CPU used CUDA')) for name in calls]
        for guard in patches:
            guard.start()
        try:
            result = score.evaluate_tasks(model, documents(), variant())
            self.assertEqual(result['device'], 'cpu')
        finally:
            for guard in reversed(patches):
                guard.stop()

    def test_progress_failure_restores_rng_and_hooks(self):
        model = fresh_model()
        before = torch.get_rng_state().clone()
        def fail(_):
            torch.rand(3)
            raise RuntimeError('intentional interruption')
        with self.assertRaisesRegex(RuntimeError, 'intentional interruption'):
            score.evaluate_tasks(model, documents(), variant(), progress=fail)
        self.assertTrue(torch.equal(before, torch.get_rng_state()))
        self.assertTrue(all(not m._forward_pre_hooks for m in model.modules()))
        score.evaluate_tasks(model, documents(), variant())

    def test_guard_rejects_parameter_sample_config_module_and_mode_changes(self):
        mutations = (
            lambda m: m.model.layers[6].mlp.projections[0].weight.add_(1),
            lambda m: m.model.layers[6].mlp.set_sample_count(8),
            lambda m: setattr(m.model.layers[6].mlp.config, 'input_temperature', .5),
            lambda m: setattr(m.model.layers[6], 'mlp', copy.deepcopy(m.model.layers[6].mlp)),
            lambda m: m.model.layers[6].mlp.train(),
        )
        for mutate in mutations:
            model = fresh_model()
            guard = score.ModelGuard(model, variant())
            with torch.no_grad():
                mutate(model)
            with self.assertRaises(RuntimeError):
                guard.verify()

    def test_guard_checks_all_actual_devices_and_dtypes(self):
        model = fresh_model()
        model.model.layers[0].mlp.linear.to(dtype=torch.float32)
        with self.assertRaisesRegex(ValueError, 'BF16'):
            score.evaluate_tasks(model, documents(), variant())
        model = fresh_model()
        model.register_buffer('unexpected_meta', torch.empty(1, device='meta'))
        with self.assertRaisesRegex(ValueError, 'unsharded'):
            score.evaluate_tasks(model, documents(), variant())

    def test_guard_rejects_undeclared_student_or_wrong_sample_count(self):
        for case in (variant(layers=()), variant(samples=8), variant(layers=(6, 13))):
            with self.assertRaises(ValueError):
                score.evaluate_tasks(fresh_model(), documents(), case)

    def test_invalid_requests_variants_and_vocabulary_rejected(self):
        bad_docs = [[], [documents()[0], documents()[0]],
            [dict(documents()[0], context_ids=[1, 2])],
            [dict(documents()[0], choices_ids=[[1], []])],
            [dict(documents()[0], choices_ids=[[1], [17]])],
            [dict(documents()[0], choices_ids=[[1], [-1]])],
            [dict(documents()[0], choices_ids=[[1], [True]])]]
        for docs in bad_docs:
            with self.assertRaises(ValueError):
                score.evaluate_tasks(fresh_model(), docs, variant())
        for changes in (dict(samples=0), dict(batch=17), dict(seed=-1), dict(layers=[6]),
                        dict(layers=[6, 6]), dict(layers=[6, True]), dict(unknown=True), dict(context=3)):
            with self.assertRaises(ValueError):
                score.evaluate_tasks(fresh_model(), documents(), dict(variant(), **changes))

    def test_rng_and_mutable_cache_snapshot_replay(self):
        state = score.rng_snapshot(torch.device('cpu'))
        cache = {'x': torch.arange(3.)}
        saved = copy.deepcopy(cache)
        a = torch.rand(13)
        cache['x'].add_(8)
        score.rng_restore(state)
        self.assertTrue(torch.equal(a, torch.rand(13)))
        self.assertTrue(torch.equal(saved['x'], torch.arange(3.)))

    def test_cuda_rng_helpers_address_only_explicit_model_device(self):
        fake_state = torch.arange(5, dtype=torch.uint8)
        with patch.object(torch.cuda, 'get_rng_state', return_value=fake_state) as get_state:
            state = score.rng_snapshot('cuda:3')
            get_state.assert_called_once_with(torch.device('cuda:3'))
        with patch.object(torch.cuda, 'set_rng_state') as set_state:
            score.rng_restore(state)
            self.assertTrue(torch.equal(set_state.call_args.args[0], fake_state))
            self.assertEqual(set_state.call_args.kwargs['device'], torch.device('cuda:3'))
        with patch.object(torch.cuda, 'device') as context, patch.object(torch.cuda, 'manual_seed') as seed, \
                patch.object(torch.cuda, 'manual_seed_all', side_effect=AssertionError('must not touch other GPUs')):
            score.rng_seed(1234, 'cuda:3')
            context.assert_called_once_with(torch.device('cuda:3'))
            seed.assert_called_once_with(1234)


class LoaderTests(unittest.TestCase):
    def setUp(self):
        # Use the writable checkout; Windows sandbox TEMP can name a different
        # profile's inaccessible package directory.
        self.directory = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2])
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.manifest = []
        for index in (6, 12):
            config = FullPathPBitFFNConfig(input_size=4, hidden_sizes=(6,), output_size=4,
                                          input_temperature=.25)
            student = FullPathPBitFFN(config)
            path = self.root / f'layer{index}.pt'
            torch.save(dict(student_type='full_path_bipolar_pdnn_v1', student_config=asdict(config),
                            student_state_dict=student.state_dict(), training_args=dict(layer=index)), path)
            self.manifest.append(dict(layer=index, path=str(path), bytes=path.stat().st_size,
                                      sha256=score.file_sha256(path), student_config=asdict(config)))

    def load(self, entries=None, model=None, root=None, samples=4, device='cpu'):
        model = fresh_model(layers=()) if model is None else model
        records = score.install_students(model, self.manifest if entries is None else entries,
                                         samples, self.root if root is None else root, device)
        return model, records

    def edit_payload(self, index, mutate):
        entry = self.manifest[index]
        path = Path(entry['path'])
        payload = torch.load(path, map_location='cpu', weights_only=True)
        mutate(payload)
        torch.save(payload, path)
        entry.update(bytes=path.stat().st_size, sha256=score.file_sha256(path))

    def test_strict_cpu_load_preserves_floating_weights_and_records_original_sha(self):
        model, records = self.load()
        self.assertEqual([r['layer'] for r in records], [6, 12])
        self.assertEqual(records[0]['sha256'], self.manifest[0]['sha256'])
        self.assertEqual(records[0]['device'], 'cpu')
        self.assertTrue(all(p.dtype == torch.bfloat16 and not p.requires_grad for p in model.parameters()))
        result = score.evaluate_tasks(model, documents(), variant())
        self.assertEqual(result['variant']['samples'], 4)

    def test_sha_size_layer_and_root_rejected_before_any_install(self):
        for change in (dict(sha256='0' * 64), dict(bytes=1), dict(layer=7)):
            entries = copy.deepcopy(self.manifest)
            entries[0].update(change)
            model = fresh_model(layers=())
            with self.assertRaises(ValueError):
                self.load(entries, model=model)
            self.assertTrue(all(type(x.mlp).__name__ == 'Qwen2MLP' for x in model.model.layers))
        outside = self.root / 'empty_personal_root'
        outside.mkdir()
        with self.assertRaisesRegex(ValueError, 'personal root'):
            self.load(root=outside)

    def test_duplicate_layer_device_and_count_rejected(self):
        with self.assertRaisesRegex(ValueError, 'repeated'):
            self.load([self.manifest[0], self.manifest[0]])
        with self.assertRaisesRegex(ValueError, 'actual base model device'):
            self.load(device='cuda:0')
        with self.assertRaises(ValueError):
            self.load(self.manifest[:1])
        with self.assertRaises(ValueError):
            self.load(samples=0)

    def test_payload_architecture_width_student_type_and_config_binding(self):
        changes = (
            lambda p: p['student_config'].update(architecture='gated_dual_rail'),
            lambda p: p['student_config'].update(input_encoding='continuous_raw'),
            lambda p: p['student_config'].update(input_bits=4),
            lambda p: p['student_config'].update(input_size=5),
            lambda p: p.update(student_type='unexpected'),
            lambda p: p['student_config'].update(input_temperature=.5),
        )
        original = Path(self.manifest[0]['path']).read_bytes()
        original_entry = copy.deepcopy(self.manifest[0])
        for mutate in changes:
            Path(original_entry['path']).write_bytes(original)
            self.manifest[0] = copy.deepcopy(original_entry)
            self.edit_payload(0, mutate)
            with self.assertRaises(ValueError):
                self.load()

    def test_nonfinite_and_state_key_errors_rejected(self):
        self.edit_payload(0, lambda p: p['student_state_dict']['projections.0.weight'].fill_(float('nan')))
        with self.assertRaisesRegex(ValueError, 'finite floating'):
            self.load()
        self.edit_payload(0, lambda p: p['student_state_dict'].pop('projections.0.weight'))
        with self.assertRaises(RuntimeError):
            self.load()

    def test_september_minimal_config_uses_public_defaults_and_retains_source(self):
        legacy = dict(input_size=4, hidden_sizes=[6], output_size=4,
                      input_temperature=.25, hidden_temperature=1.)
        self.edit_payload(0, lambda p: p.update(student_config=legacy,
                          phase='joint_end_to_end_distillation', step=1000))
        self.manifest[0]['student_config'] = legacy
        model, records = self.load()
        self.assertEqual(records[0]['source_student_config'], legacy)
        self.assertEqual(records[0]['student_config']['coding'], 'bipolar')
        self.assertEqual(records[0]['student_config']['architecture'], 'serial')
        self.assertEqual(records[0]['phase'], 'joint_end_to_end_distillation')
        self.assertEqual(records[0]['step'], 1000)
        self.assertEqual(model.model.layers[6].mlp.config.coding, 'bipolar')


if __name__ == '__main__':
    unittest.main()
