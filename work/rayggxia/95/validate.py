"""Run scoped checks with task-local temporary directories and a saved receipt."""
import hashlib
import io
import json
import platform
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
WORK=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
tmp=WORK/'test_tmp';tmp.mkdir(exist_ok=True)
tempfile.tempdir=str(tmp)
suite=unittest.TestSuite()
for folder,pattern in [('architecture_tlm/random_service/tests','test_*.py'),
                       ('architecture_tlm/checks','test_parallel_sampler_v5.py'),
                       ('architecture_tlm/checks','test_screen_ising_v4.py')]:
    # Separate loader avoids namespace collision between two test discovery roots.
    suite.addTests(unittest.TestLoader().discover(str(ROOT/folder),pattern=pattern))
log=io.StringIO()
r=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
(WORK/'python_tests.log').write_text(log.getvalue(),encoding='utf-8',newline='\n')
receipt=dict(python=platform.python_version(),tests=r.testsRun,failures=len(r.failures),
             errors=len(r.errors),skipped=len(r.skipped),success=r.wasSuccessful(),
             command='python work/rayggxia/95/validate.py',
             model_revision='not applicable: no model inference',
             dataset_sha256='not applicable: protocol/algorithm fixtures only',
             baseline='83e15289434af50fc09c35e699d8b39965389d98',
             source_sha256={str(p.relative_to(ROOT)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in sorted((ROOT/'architecture_tlm/random_service').rglob('*'))
                 if p.is_file() and '__pycache__' not in p.parts},
             adapter_sha256=hashlib.sha256((ROOT/'architecture_tlm/parallel_sampler_v5.py').read_bytes()).hexdigest())
(WORK/'VALIDATION.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps({k:v for k,v in receipt.items() if k not in ('source_sha256',)},indent=2))
if not r.wasSuccessful():
    print(log.getvalue());sys.exit(1)

