"""Offline portable-profile safety and identity gates, not task accuracy."""
import copy
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from experiments.pdnn20_task_accuracy_20261023 import portable_runner as runner


class PortableIdentityGates(unittest.TestCase):
    def setUp(self):
        self.pin = runner.read(Path(__file__).with_name('portable_reference.expected.json'))

    def test_reference_pin_covers_model_tokenizer_task_and_runtime_contract(self):
        runner.check_pin(self.pin)
        self.assertEqual(len(self.pin['model_files']), 7)
        self.assertEqual(len(self.pin['harness_sources']), 4)
        for key, replacement in (('torch', '2.8.0'), ('transformers', '4.46.0'),
                                 ('lm_eval', '0.4.9'), ('cuda', '13.0')):
            changed = copy.deepcopy(self.pin)
            changed['environment_versions'][key] = replacement
            with self.assertRaises(ValueError):
                runner.check_pin(changed)
        changed = copy.deepcopy(self.pin)
        changed['statistics']['hellaswag']['documents'] = 10042
        with self.assertRaises(ValueError):
            runner.check_pin(changed)

    def test_unchanged_model_weight_does_not_hide_a_changed_tokenizer(self):
        model = dict(files={name: dict(value, path='/home/recipient/models/' + name)
                            for name, value in self.pin['model_files'].items()})
        runner.verify_model_pin(model, self.pin)
        model['files']['tokenizer.json']['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'tokenizer'):
            runner.verify_model_pin(model, self.pin)

    def test_harness_identity_normalizes_only_install_prefix_not_source_role_or_hash(self):
        mapping = {'/home/recipient/isolated/lib/python3.12/site-packages/' + role: digest
                   for role, digest in self.pin['harness_sources'].items()}
        self.assertEqual(runner.normalized_harness(mapping), self.pin['harness_sources'])
        with self.assertRaises(ValueError):
            runner.normalized_harness({'/somewhere/unidentified/task.py': 'a' * 64})
        changed = dict(mapping)
        changed[next(iter(changed))] = '0' * 64
        self.assertNotEqual(runner.normalized_harness(changed), self.pin['harness_sources'])

    def test_full_matrix_has_three_fresh_bf16_and_nine_pdnn_cases(self):
        matrix = runner.full_matrix(dict(seeds=[0, 1, 2]))
        self.assertEqual(len(matrix), 12)
        self.assertEqual(sum(not case['layers'] for _, case in matrix), 3)
        for task in runner.TASKS:
            rows = [case for name, case in matrix if name == task]
            self.assertEqual([case['seed'] for case in rows if case['layers']], [0, 1, 2])
            self.assertEqual([case['seed'] for case in rows if not case['layers']], [0])
            self.assertTrue(all(case['layers'] in ([], runner.LAYERS) for case in rows))

    def test_missing_weights_and_inspection_cannot_claim_gpu_readiness(self):
        full = dict(all_checkpoint_bytes_present=True, all_strict_states_loaded=True,
                    entries=list(range(20)), inspected=list(range(20)), missing=[])
        self.assertTrue(runner.cpu_ready(full, False))
        self.assertFalse(runner.cpu_ready(full, True))
        for changes in (dict(all_strict_states_loaded=False), dict(entries=list(range(19))),
                        dict(inspected=list(range(19))), dict(missing=[dict(layer=1)])):
            self.assertFalse(runner.cpu_ready(dict(full, **changes), False))


class PortableOwnershipGates(unittest.TestCase):
    def setUp(self):
        source_root = Path(__file__).resolve().parents[2]
        if os.environ.get('SLURM_JOB_ID'):
            temporary_root = Path(os.environ['TMPDIR']).resolve(strict=True)
            actual_home = Path.home().resolve(strict=True)
            if not temporary_root.is_relative_to(actual_home) or temporary_root.is_relative_to(source_root):
                raise RuntimeError('server test TMPDIR must be personal and outside immutable source')
        else:
            temporary_root = source_root
        self.directory = tempfile.TemporaryDirectory(dir=temporary_root)
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.home = self.root / 'recipient_home'
        self.home.mkdir()
        self.project = self.home / 'personal_project'
        self.project.mkdir()

    def test_paths_are_scoped_to_actual_recipient_home_not_a_fixed_username(self):
        file = self.project / 'input.json'
        file.write_text('{}', encoding='utf-8')
        with patch.object(os, 'getuid', return_value=file.stat().st_uid, create=True):
            self.assertEqual(runner.own_path(file, self.home), file.resolve())
            self.assertEqual(runner.own_path(self.project / 'future/file', self.home, False),
                             (self.project / 'future/file').resolve())
            with self.assertRaises(ValueError):
                runner.own_path(self.root, self.home)
            with self.assertRaises(ValueError):
                runner.own_path(self.project / '../../outside', self.home, False)
            with patch.object(os, 'getuid', return_value=file.stat().st_uid + 1, create=True):
                with self.assertRaisesRegex(ValueError, 'UID'):
                    runner.own_path(file, self.home)

    def test_readback_rejects_changed_bytes_even_with_matching_relative_location(self):
        file = self.project / 'input.json'
        file.write_text('{}', encoding='utf-8')
        entry = runner.artifact(file)
        with patch.object(os, 'getuid', return_value=file.stat().st_uid, create=True):
            runner.checked(entry, self.home, self.project)
            file.write_text('[]', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'SHA'):
                runner.checked(entry, self.home, self.project)


if __name__ == '__main__':
    unittest.main()
