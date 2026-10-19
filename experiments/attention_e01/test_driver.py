from pathlib import Path
import hashlib
import json
import tempfile
import unittest
from unittest.mock import patch
import run


class DriverTests(unittest.TestCase):
    def test_environment_executable_path_preserves_virtualenv(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as folder:
            root=Path(folder).resolve();venv=root/'venv';bin_dir=venv/'bin';bin_dir.mkdir(parents=True)
            (venv/'pyvenv.cfg').write_text('include-system-site-packages = false\n',encoding='utf-8')
            executable=bin_dir/'python';executable.write_bytes(b'placeholder')
            self.assertEqual(run.environment_python(executable,root),executable)
            with self.assertRaisesRegex(ValueError,'absolute'):
                run.environment_python('venv/bin/python',root)
            (venv/'pyvenv.cfg').unlink()
            with self.assertRaisesRegex(ValueError,'virtual environment'):
                run.environment_python(executable,root)

    def test_personal_scope_and_symlink_escape(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as folder:
            root=Path(folder).resolve(); inside=root/'source';inside.mkdir()
            self.assertEqual(run.inside(inside,root),inside)
            for path in [root,root.parent,root/'..'/'outside']:
                with self.assertRaises((ValueError,FileNotFoundError)):
                    run.inside(path,root)

    def test_source_manifest_rejects_missing_files_and_changed_commit(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as folder:
            manifest=Path(folder)/'source.json'
            manifest.write_text(json.dumps({'code_commit':'a'*40,'files':[]}),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'requested commit'):
                run.check_source(manifest,'b'*40)
            with self.assertRaisesRegex(ValueError,'missing'):
                run.check_source(manifest,'a'*40)

    def test_hash_is_byte_exact(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as folder:
            p=Path(folder)/'bytes';p.write_bytes(b'line\r\n')
            self.assertEqual(run.digest(p),hashlib.sha256(b'line\r\n').hexdigest())
            self.assertNotEqual(run.digest(p),hashlib.sha256(b'line\n').hexdigest())


if __name__=='__main__':
    unittest.main()
