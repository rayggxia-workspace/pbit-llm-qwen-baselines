"""Offline readiness/metric gates; no model, dataset, GPU or fake accuracy run."""
import copy
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from experiments.pdnn20_task_accuracy_20261023 import runner


class ReadinessGates(unittest.TestCase):
    def expected(self):
        return [dict(layer=i, bytes=34893765 if i < 10 else 34893775,
                     sha256=runner.HISTORICAL_HASHES[i],
                     relative_path=f'results/joint_full_path_pdnn_layers1_22_twenty_v1/best_layer{i}.pt',
                     student_type='full_path_bipolar_pdnn_v1', phase='joint_end_to_end_distillation', step=1000)
                for i in runner.LAYERS]

    def test_exact_twenty_layer_manifest_and_flat_checkpoint_mapping(self):
        entries = runner.validate_expected(self.expected())
        self.assertEqual(sum(e['bytes'] for e in entries), 697875430)
        paths = runner.checkpoint_entries(entries, '/personal/joint20')
        self.assertEqual([Path(e['path']).name for e in paths], [f'best_layer{i}.pt' for i in runner.LAYERS])
        self.assertTrue(all(Path(e['path']).parent == Path('/personal/joint20') for e in paths))
        for alter in (lambda x: x.pop(), lambda x: x.reverse(),
                      lambda x: x[0].update(sha256='0' * 64),
                      lambda x: x[0].update(student_type='full_path_binary_pdnn_v2'),
                      lambda x: x[0].update(relative_path='../best_layer1.pt'),
                      lambda x: x[0].update(step=900)):
            bad = copy.deepcopy(entries)
            alter(bad)
            with self.assertRaises(ValueError):
                runner.validate_expected(bad)

    def test_inspection_missing_weights_or_pending_baseline_cannot_enable_gpu(self):
        complete = dict(missing=[], all_checkpoint_bytes_present=True, all_strict_states_loaded=True)
        self.assertTrue(runner.preparation_state(complete, [], False)['gpu_allowed'])
        for inventory, missing, inspect in ((complete, [], True), (complete, ['bf16_piqa'], False),
                (dict(complete, all_strict_states_loaded=False), [], False),
                (dict(complete, missing=[dict(layer=1)], all_checkpoint_bytes_present=False), [], False)):
            state = runner.preparation_state(inventory, missing, inspect)
            self.assertFalse(state['gpu_allowed'])
            self.assertEqual(state['status'], 'awaiting_external_inputs')

    def test_fixed_protocol_rejects_changed_layer_set_samples_and_seed_selection(self):
        config = dict(protocol_version=1, model_weight_sha256=runner.MODEL_SHA, layers=runner.LAYERS,
                      samples=4, seeds=[0, 1, 2], batch=16, context=2048,
                      expected_checkpoint_manifest='checkpoints.expected.json')
        runner.validate_config(config)
        for changes in (dict(layers=[10, 12]), dict(samples=16), dict(seeds=[0]), dict(batch=32),
                        dict(expected_checkpoint_manifest='../other.json')):
            with self.assertRaises(ValueError):
                runner.validate_config(dict(config, **changes))


class SavedBaselineGates(unittest.TestCase):
    def setUp(self):
        if os.environ.get('SLURM_JOB_ID'):
            temporary_root = Path(os.environ['TMPDIR']).resolve(strict=True)
            runner.require(temporary_root.is_relative_to(runner.PROJECT)
                           and not temporary_root.is_relative_to(runner.REPO)
                           and temporary_root.stat().st_uid == os.getuid(),
                           'server tests require personal TMPDIR outside the immutable snapshot')
        else:
            temporary_root = Path(__file__).resolve().parents[2]
        self.temp = tempfile.TemporaryDirectory(dir=temporary_root)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.docs = [dict(id='task:3', task='task', doc_id=3, context_ids=[1, 2, 3], choices_ids=[[4], [5, 6]])]
        self.row = dict(id='task:3', task='task', doc_id=3,
                        choices=[dict(tokens=1, logprob=-1., is_greedy=True),
                                 dict(tokens=2, logprob=-3., is_greedy=False)],
                        metrics=dict(acc=1., acc_norm=0.))
        self.case = dict(case='bf16_task', code_commit='a' * 40, n_documents=1, metrics=dict(acc=1., acc_norm=0.))
        self.store()

    def store(self):
        for name, rows in (('documents.jsonl', [self.row]), ('progress.jsonl', [
                dict(event='started', case=self.case['case'], code_commit=self.case['code_commit']), self.row])):
            p = self.root / name
            p.write_text(''.join(json.dumps(r) + '\n' for r in rows), encoding='utf-8')
            key = 'document_artifact' if name.startswith('documents') else 'progress_artifact'
            self.case[key] = runner.artifact(p)

    def checked(self, entry):
        p = Path(entry['path'])
        runner.require(p.stat().st_size == entry['bytes'] and runner.sha(p) == entry['sha256'], 'SHA changed')
        return p

    def verify(self):
        return runner.verify_saved_metrics(self.case, self.docs, self.checked, lambda r: dict(acc=1., acc_norm=0.))

    def test_saved_official_baseline_and_progress_are_bound_to_exact_request(self):
        self.assertEqual(self.verify(), self.case['metrics'])
        self.row['doc_id'] = 4
        self.store()
        with self.assertRaisesRegex(ValueError, 'alignment'):
            self.verify()

    def test_baseline_sha_count_score_and_official_metric_mismatches_rejected(self):
        original = copy.deepcopy(self.case)
        self.case['document_artifact']['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'SHA'):
            self.verify()
        self.case = original
        self.case['n_documents'] = 2
        with self.assertRaisesRegex(ValueError, 'count'):
            self.verify()
        self.case['n_documents'] = 1
        self.row['choices'][0]['tokens'] = 2
        self.store()
        with self.assertRaisesRegex(ValueError, 'alignment'):
            self.verify()
        self.row['choices'][0]['tokens'] = 1
        self.row['metrics']['acc'] = 0.
        self.store()
        with self.assertRaisesRegex(ValueError, 'process_results'):
            self.verify()

    def test_progress_callback_uses_actual_payload_without_completed_documents_stats(self):
        path = self.root / 'callback.jsonl'
        record = runner.ProgressRecorder(path, self.docs, lambda r: dict(acc=1., acc_norm=0.), 'pdnn20_task')
        update = dict(documents=[dict(id=self.row['id'], choices=self.row['choices'])],
                      elapsed_seconds=.25, batch=0, execution_audit=dict(actual_decode_calls=3))
        captured = io.StringIO()
        with redirect_stdout(captured):
            record(update)
        self.assertEqual(record.completed, 1)
        self.assertEqual(runner.jsonlines(path), [self.row])
        self.assertEqual(json.loads(captured.getvalue())['completed'], 1)


if __name__ == '__main__':
    unittest.main()
