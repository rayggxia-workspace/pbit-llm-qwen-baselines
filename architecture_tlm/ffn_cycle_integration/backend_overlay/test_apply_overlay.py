"""Safety regressions use synthetic source, never a bundled Issue116 copy."""
import difflib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('ffn_overlay_installer', HERE / 'apply_overlay.py')
INSTALL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INSTALL)


class OverlayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='ov-', dir=os.environ.get('FFN_OVERLAY_TEST_TMP'))
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name).resolve()
        self.root = self.base / 'backend'
        self.package = self.base / 'package'
        (self.root / 'architecture_tlm/cycle_v1').mkdir(parents=True)
        (self.package / 'files').mkdir(parents=True)
        self.before = b'# synthetic fixture\nvalue = 1\n' + b'pass\n' * 12 + b'end = 1\n'
        self.after = self.before.replace(b'value = 1', b'value = 2').replace(b'end = 1', b'end = 3')
        self.ffn = self.root / INSTALL.FFN
        self.ffn.write_bytes(self.before)
        patch = ''.join(difflib.unified_diff(self.before.decode().splitlines(keepends=True),
            self.after.decode().splitlines(keepends=True), fromfile='a/' + INSTALL.FFN,
            tofile='b/' + INSTALL.FFN)).encode()
        (self.package / 'ffn.py.patch').write_bytes(patch)
        self.dependencies = {}
        for name in ('alpha.py', 'zz_last.py'):
            relative = 'architecture_tlm/cycle_v1/' + name
            raw = ('# synthetic dependency: ' + name + '\n').encode()
            (self.root / relative).write_bytes(raw)
            self.dependencies[relative] = self.record(raw)
        snapshot = dict(self.dependencies)
        snapshot[INSTALL.FFN] = self.record(self.after)
        payloads = []
        for target in sorted(INSTALL.OWN):
            raw = ('# synthetic own file ' + target + '\n').encode()
            payload = 'files/' + Path(target).name
            (self.package / payload).write_bytes(raw)
            snapshot[target] = self.record(raw)
            payloads.append(dict(target=target, payload=payload,
                                 sha256_lf=INSTALL.sha(raw), before='absent'))
        self.manifest = dict(schema='ffn.backend_overlay.1', overlay_id='test-v1',
            dependencies=self.dependencies, snapshot_files=snapshot, payloads=payloads,
            patch=dict(target=INSTALL.FFN, payload='ffn.py.patch', sha256_lf=INSTALL.sha(patch),
                       before_sha256_lf=INSTALL.sha(self.before), after_sha256_lf=INSTALL.sha(self.after)))
        self.save_manifest()

    @staticmethod
    def record(raw):
        return dict(snapshot_sha256=INSTALL.sha(raw), sha256_lf=INSTALL.sha(INSTALL.lf(raw)), bytes=len(raw))

    def save_manifest(self):
        (self.package / 'MANIFEST.json').write_bytes(INSTALL.json_bytes(self.manifest))

    def run_apply(self, **kwargs):
        return INSTALL.apply(self.root, package=self.package, **kwargs)

    def state(self):
        return {p.relative_to(self.root).as_posix(): (p.read_bytes(), p.stat().st_mtime_ns)
                if p.is_file() else None for p in self.root.rglob('*')}

    def assert_refused_unchanged(self, message=None):
        state = self.state()
        with self.assertRaises((ValueError, OSError), msg=message):
            self.run_apply()
        self.assertEqual(self.state(), state)

    def test_lf_check_then_apply_preserves_exact_original_and_receipt(self):
        before = self.state()
        self.assertEqual(self.run_apply(check=True)['status'], 'ready')
        self.assertEqual(self.state(), before)
        report = self.run_apply()
        self.assertEqual(report['status'], 'applied')
        journal = Path(report['journal'])
        self.assertEqual((journal / 'ffn.py.original').read_bytes(), self.before)
        self.assertEqual(self.ffn.read_bytes(), self.after)
        receipt = json.loads((journal / 'receipt.json').read_bytes())
        self.assertEqual(len(receipt['files']), 7)
        self.assertEqual(receipt['backup_sha256'], INSTALL.sha(self.before))
        self.assertEqual(len(list(journal.glob('step-*.json'))), 5)

    def test_crlf_dependencies_input_patch_and_payloads(self):
        for path in [*self.root.rglob('*.py'), *self.package.rglob('*.py'), self.package / 'ffn.py.patch']:
            path.write_bytes(path.read_bytes().replace(b'\n', b'\r\n'))
        original = self.ffn.read_bytes()
        report = self.run_apply()
        self.assertEqual(self.ffn.read_bytes(), self.after.replace(b'\n', b'\r\n'))
        self.assertEqual((Path(report['journal']) / 'ffn.py.original').read_bytes(), original)
        for target in INSTALL.OWN:
            self.assertNotIn(b'\r', (self.root / target).read_bytes())

    def test_repeated_apply_and_check_are_read_only(self):
        self.run_apply()
        before = self.state()
        for check in (False, True, False):
            self.assertEqual(self.run_apply(check=check)['status'], 'already_applied')
            self.assertEqual(self.state(), before)

    def test_last_dependency_wrong_hash_prevents_every_write(self):
        last = self.root / sorted(self.dependencies)[-1]
        last.write_bytes(last.read_bytes() + b'# incompatible\n')
        self.assert_refused_unchanged()

    def test_missing_dependency_prevents_every_write(self):
        (self.root / sorted(self.dependencies)[-1]).unlink()
        self.assert_refused_unchanged()

    def test_wrong_baseline_prevents_every_write(self):
        self.ffn.write_bytes(self.before + b'# changed\n')
        self.assert_refused_unchanged()

    def test_already_applied_still_verifies_full_dependency_closure(self):
        self.run_apply()
        last = self.root / sorted(self.dependencies)[-1]
        last.write_bytes(last.read_bytes() + b'# later edit\n')
        self.assert_refused_unchanged()

    def test_interrupted_write_keeps_original_and_refuses_automatic_replay(self):
        real_write = INSTALL.write_new
        def injected_failure(path, raw):
            if path.name == 'ffn_contract_reference.py':
                raise OSError('injected write failure')
            return real_write(path, raw)
        with mock.patch.object(INSTALL, 'write_new', side_effect=injected_failure):
            with self.assertRaisesRegex(OSError, 'injected'):
                self.run_apply()
        journal = self.root / '.ffn_contract_overlay/test-v1'
        self.assertEqual((journal / 'ffn.py.original').read_bytes(), self.before)
        self.assertEqual(self.ffn.read_bytes(), self.before)
        failure = json.loads((journal / 'failure.json').read_bytes())
        self.assertEqual(failure['written'], ['architecture_tlm/cycle_v1/ffn_contract.py'])
        self.assert_refused_unchanged()

    def test_preexisting_own_file_and_partial_states_are_rejected(self):
        target = self.root / sorted(INSTALL.OWN)[0]
        target.write_bytes(b'# someone else\n')
        self.assert_refused_unchanged()
        self.ffn.write_bytes(self.after)
        self.assert_refused_unchanged()

    def test_corrupt_payload_prevents_every_write(self):
        payload = self.package / self.manifest['payloads'][-1]['payload']
        payload.write_bytes(payload.read_bytes() + b'# corruption\n')
        self.assert_refused_unchanged()

    def test_exact_patch_rejects_fuzz_even_with_updated_package_hash(self):
        patch_path = self.package / 'ffn.py.patch'
        raw = patch_path.read_bytes().replace(b'-value = 1\n', b'-value = 9\n')
        patch_path.write_bytes(raw)
        self.manifest['patch']['sha256_lf'] = INSTALL.sha(raw)
        self.save_manifest()
        self.assert_refused_unchanged()

    def test_journal_or_staged_file_blocks_fresh_apply(self):
        staged = self.root / (INSTALL.FFN + '.test-v1.new')
        staged.write_bytes(b'# preserve me\n')
        self.assert_refused_unchanged()
        staged.unlink()
        (self.root / '.ffn_contract_overlay/test-v1').mkdir(parents=True)
        self.assert_refused_unchanged()

    def test_path_escape_and_relative_root_rejected(self):
        with self.assertRaises(ValueError):
            INSTALL.apply(Path('backend'), package=self.package)
        self.manifest['payloads'][0]['payload'] = '../outside.py'
        self.save_manifest()
        self.assert_refused_unchanged()

    def test_publication_tree_cannot_be_target(self):
        with self.assertRaisesRegex(ValueError, 'independent'):
            INSTALL.apply(INSTALL.PUBLICATION_ROOT, check=True)

    def test_dependency_symlink_rejected_when_platform_supports_links(self):
        target = self.root / sorted(self.dependencies)[-1]
        external = self.base / 'external.py'
        external.write_bytes(target.read_bytes())
        target.unlink()
        try:
            target.symlink_to(external)
        except OSError as error:
            self.skipTest('creating symlinks is not permitted: ' + str(error))
        self.assert_refused_unchanged()


if __name__ == '__main__':
    unittest.main(verbosity=2)
