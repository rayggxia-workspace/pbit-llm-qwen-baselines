"""Read-only upstream sampler overlay; no edits to frozen execution modules."""
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
temp=OUT/'test_tmp'
temp.mkdir(exist_ok=True)
tempfile.tempdir=str(temp.resolve())
sys.path.insert(0,str(ROOT/'architecture_tlm'))
sys.path.insert(0,str(ROOT))
p=OUT/'UPSTREAM_PARALLEL_SAMPLER.py'
spec=importlib.util.spec_from_file_location('parallel_sampler_v5',p)
module=importlib.util.module_from_spec(spec)
sys.modules['parallel_sampler_v5']=module
spec.loader.exec_module(module)
suites=[unittest.defaultTestLoader.loadTestsFromName('architecture_tlm.unified_v6.test_model')]
for name,path in [('v5check','architecture_tlm/checks/test_parallel_sampler_v5.py'),
                  ('v4check','architecture_tlm/checks/test_screen_ising_v4.py')]:
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    suites.append(unittest.defaultTestLoader.loadTestsFromModule(module))
stream=io.StringIO()
result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.TestSuite(suites))
(OUT/'UPSTREAM_COMPATIBILITY_V3.log').write_bytes(stream.getvalue().encode('utf-8'))
record=dict(upstream_commit='27bf9c483e2b772b4fcdb4c988b3d86074c80049',
    testsRun=result.testsRun,failures=len(result.failures),errors=len(result.errors),
    successful=result.wasSuccessful(),temp_directory=str(temp.relative_to(ROOT)),
    scope='same21+18+10 tests with upstream sampler overlay; no timed backend or new full model runs',
    prior_attempt='V1 default-temp permission and V2 helper root import errors preserved; test/source bytes unchanged')
(OUT/'UPSTREAM_COMPATIBILITY_V3.json').write_bytes((json.dumps(record,indent=2)+'\n').encode())
print(json.dumps(record))
if not result.wasSuccessful():
    print(stream.getvalue())
    raise SystemExit(1)
