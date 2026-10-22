"""One bounded extension of the pinned public/synthetic GQA diagnostic."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

root=Path(__file__).resolve().parents[3]
snapshot=root.parent/'gqa-active-snapshot'
directory=root/'work/amlink1219/116/active_gqa_probe'
source=json.loads((directory/'RESULT.json').read_text(encoding='utf-8'))
manifest=json.loads((root/'work/amlink1219/116/gqa_validation_v1/SOURCE_MANIFEST.json').read_text(encoding='utf-8'))
for name,expected in manifest['files'].items():
    assert hashlib.sha256((snapshot/name).read_bytes()).hexdigest()==expected
candidate=directory/'active_memory_candidate.py'
assert hashlib.sha256(candidate.read_bytes()).hexdigest()==source['candidate_sha256']
summary={k:source[k] for k in ('public_candidate_commit','candidate_git_blob','candidate_sha256','baseline_core_commit','baseline_source_archive_sha256')}
summary.update(context=256,per_case_hard_timeout_seconds=60,cases=[],same_shape_equivalence_checked=False)
out=directory/'RESULT256.json'
assert not out.exists()
for kind in ('original','candidate'):
    before=time.perf_counter()
    command=[sys.executable,'-P','-X','utf8',str(root/'work/amlink1219/116/probe_active_gqa.py'),
        '--worker','--kind',kind,'--context','256','--snapshot',str(snapshot),'--candidate',str(candidate)]
    try:
        run=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',timeout=60)
        receipt=json.loads(run.stdout) if run.returncode==0 else dict(status='failed',returncode=run.returncode,stderr=run.stderr)
    except subprocess.TimeoutExpired:
        receipt=dict(status='timeout',hard_limit_seconds=60)
    receipt.update(kind=kind,parent_wall_seconds=time.perf_counter()-before)
    summary['cases'].append(receipt)
    out.write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(receipt),flush=True)
if all(c['status']=='pass' for c in summary['cases']):
    old,new=[c['records'][0] for c in summary['cases']]
    assert all(old[k]==new[k] for k in ('payload_sha256','state_sha256','output_sha256','finish_ps','operations'))
    summary['same_shape_equivalence_checked']=True
    out.write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8',newline='\n')
