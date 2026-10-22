import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
OUT=Path(__file__).resolve().parent
tempfile.tempdir=str(OUT/'test_tmp');Path(tempfile.tempdir).mkdir(exist_ok=True)
groups={
 'observer': 'architecture_tlm.checks.test_observation_hooks_v6',
 'v5':'architecture_tlm.checks.test_parallel_sampler_v5',
 'whole_model':'architecture_tlm.unified_v6.test_model',
 'inspector':'architecture_tlm.inspector.test_inspector',
}
stats={}
for name,mod in groups.items():
 suite=unittest.defaultTestLoader.loadTestsFromName(mod)
 log=io.StringIO();r=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
 (OUT/(name+'.log')).write_text(log.getvalue(),encoding='utf-8',newline='\n')
 stats[name]=dict(tests=r.testsRun,failures=len(r.failures),errors=len(r.errors),skips=len(r.skipped))
 if not r.wasSuccessful():print(log.getvalue());raise SystemExit(1)
suite=unittest.defaultTestLoader.discover(str(ROOT/'architecture_tlm/random_service/tests'))
log=io.StringIO();r=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
(OUT/'random_service.log').write_text(log.getvalue(),encoding='utf-8',newline='\n')
stats['random_service']=dict(tests=r.testsRun,failures=len(r.failures),errors=len(r.errors),skips=len(r.skipped))
if not r.wasSuccessful():print(log.getvalue());raise SystemExit(1)
page=ROOT/'architecture_tlm/inspector/model-inspector.html';text=page.read_text(encoding='utf-8')
script=OUT/'script_check.js';script.write_text(text[text.index('<script>')+8:text.index('</script>')],encoding='utf-8',newline='\n')
subprocess.run(['node','--check',str(script)],check=True,cwd=ROOT)
data=json.loads((ROOT/'architecture_tlm/inspector/snapshot.json').read_text(encoding='utf-8'))
record=dict(groups=stats,tests=sum(v['tests'] for v in stats.values()),passed=True,
 archived_invariants=data['audit'],observation_checks=data['observations']['checks'],
 node_syntax_check=True,html_sha256=hashlib.sha256(page.read_bytes()).hexdigest(),
 scope='local CPU TLM and interface/accounting tests; no PPL/GPU/EDA/actual DRAMSys')
(OUT/'VALIDATION.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(tests=record['tests'],groups=stats,archived_checks=data['audit']['checks'],observation_checks=len(record['observation_checks']),passed=True)))
