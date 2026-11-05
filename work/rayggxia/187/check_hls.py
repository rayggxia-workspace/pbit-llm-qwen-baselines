"""Check provenance for the HLS research note; never executes hardware/model jobs."""
from pathlib import Path
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parents[3]
AUX = Path(__file__).resolve().parent
OUT = ROOT / 'architecture_tlm/simulator_survey_20261025'
PROJECT = ROOT.parents[1]
REF = PROJECT / 'tmp/mature-scheduling-issue186-20261025'
HEAD = 'ee21c0ce9a14662aad98abbda8277f8af37365b8'
source = json.loads((OUT / 'HLS_SOURCES.json').read_text(encoding='utf-8'))
assert len(source['sources']) == 12
assert len({x['id'] for x in source['sources']}) == 12
assert all(x['url'].startswith('https://') and x['locator'] for x in source['sources'])
assert subprocess.check_output(['git', '-C', str(REF), 'rev-parse', 'HEAD']).decode().strip() == HEAD
checked = []
for rel in source['project_ref']['inspected']:
    actual = (REF / rel).read_bytes()
    blob = subprocess.check_output(['git', '-C', str(REF), 'show', f'{HEAD}:{rel}'])
    # Checkout newline conversion is allowed; record actual bytes and committed bytes separately.
    assert actual.replace(b'\r\n', b'\n') == blob.replace(b'\r\n', b'\n'), rel
    checked.append({'path': rel, 'local_sha256': hashlib.sha256(actual).hexdigest(),
                    'git_blob_bytes_sha256': hashlib.sha256(blob).hexdigest()})
assert 6 + (64 // 16 - 1) * 1 == 9  # illustrative existing macro formula, not RTL evidence
note = (OUT / 'HLS_LATENCY_ZH.md').read_bytes()
assert b'\r' not in note
result = {'kind': 'documentation_and_provenance_only', 'status': 'passed',
          'project_head': HEAD, 'source_count': 12, 'project_sources': checked,
          'note_sha256': hashlib.sha256(note).hexdigest(),
          'example_macro_cycles': 9, 'not_run': source['not_run']}
(AUX / 'HLS_CHECK.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
print(json.dumps({'status': 'passed', 'source_count': 12, 'checked_project_files': len(checked)}))
