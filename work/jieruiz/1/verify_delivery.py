"""Check this documentation delivery; --record writes validation and hashes."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
BASE = '8068bfbb71d892ef8b0850dea391aa612739aa4f'
RULES = '595c3ab44be27799878353395d30645df0441983'
PAYLOAD = [
    'AGENTS.md', 'README.md', '.github/ISSUE_TEMPLATE/task.yml',
    '.github/pull_request_template.md', 'progress/jieruiz/STATUS.md',
    'work/jieruiz/1/HANDOFF.md', 'work/jieruiz/1/verify_delivery.py',
]
GENERATED = ['work/jieruiz/1/validation.json', 'work/jieruiz/1/manifest.json']

def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args])

def checks():
    # Legacy rules exist on another published branch, so a shallow checkout
    # must fetch that source before this preservation check can be reproduced.
    old = git('show', RULES + ':AGENTS.md').decode('utf-8').rstrip()
    current = (ROOT/'AGENTS.md').read_text(encoding='utf-8')
    assert current.startswith(old + '\n'), 'Legacy rules changed'
    original_readme = git('show', BASE + ':README.md')
    actual = (ROOT/'README.md').read_bytes()
    assert actual.endswith(original_readme), 'Existing README bytes changed'
    allowed = set(PAYLOAD + GENERATED)
    changed = set(git('diff', '--name-only', BASE).decode().splitlines())
    untracked = set(git('ls-files', '--others', '--exclude-standard').decode().splitlines())
    assert (changed | untracked) <= allowed, f'Unexpected files: {(changed | untracked)-allowed}'
    subprocess.run(['git', '-C', str(ROOT), 'diff', '--check', BASE], check=True)
    link_count = 0
    for name in PAYLOAD:
        data = (ROOT/name).read_bytes()
        text = data.decode('utf-8')
        if name != 'README.md':
            assert b'\r\n' not in data, f'Unexpected CRLF: {name}'
        if name.endswith('.md'):
            for target in re.findall(r'\]\(([^)]+)\)', text):
                if '://' in target or target.startswith('#'):
                    continue
                target = target.split('#', 1)[0]
                resolved = (ROOT/name).parent.joinpath(target).resolve()
                pending_manifest = '--record' in sys.argv and resolved == HERE/'manifest.json'
                assert resolved.exists() or pending_manifest, (name, target)
                link_count += 1
    task = (ROOT/'.github/ISSUE_TEMPLATE/task.yml').read_text(encoding='utf-8')
    for field in ('owner', 'scope', 'acceptance', 'coordination'):
        assert f'id: {field}\n' in task
    # Manual semantic review is recorded separately; these checks verify bytes,
    # scope and links, not the behavior of GitHub's server-side template renderer.
    return {'legacy_rules_verbatim': True, 'existing_readme_bytes_preserved': True,
            'git_diff_check': 'passed', 'explicit_file_scope': 'passed',
            'utf8_and_new_document_lf': 'passed', 'relative_links_checked': link_count,
            'task_template_required_fields_present': True,
            'manual_review': 'All user collaboration clauses reviewed; no experiment implementation changed.',
            'not_run': ['GPU/PPL', 'RTL/DC/PT', 'DRAMSys', 'GitHub template UI rendering'],
            'not_run_reason': 'Documentation and collaboration templates only.'}

def digest(name):
    data = (ROOT/name).read_bytes()
    return {'path': name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}

def write_json(path, obj):
    path.write_bytes((json.dumps(obj, ensure_ascii=False, indent=2)+'\n').encode('utf-8'))

result = checks()
if '--record' in sys.argv:
    result['checked_at_utc'] = datetime.now(timezone.utc).isoformat()
    result['command'] = 'python work/jieruiz/1/verify_delivery.py --record'
    write_json(HERE/'validation.json', result)
    manifest = {
        'task_issue': 'https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/1',
        'owner': 'jieruiz', 'repository': 'rayggxia-workspace/pbit-llm-qwen-baselines',
        'branch': 'collab/issue-1-governance', 'source_code_commit': BASE,
        'delivery_version': 'Git commit containing this manifest; exact pushed head recorded in Issue/PR.',
        'source_refs': {
            'legacy_rules_last_change': RULES,
            'legacy_rules_branch_read_head': '80c605952173c06b96d9369210227de4f590f01a',
            'latest_published_tlm': '9608c0d06cf8b421cbbd348aca4fc84c5990aae7',
            'other_member_review': 'cd3b471a4e33234ed60bc07bcff0b86b22cd1695',
        },
        'config': None, 'data_version': None,
        'not_applicable_reason': 'Documentation-only governance task; no model, dataset or simulation configuration changed.',
        'storage': 'Repository documents only; no large artifacts uploaded.',
        'artifacts': [digest(name) for name in PAYLOAD + [GENERATED[0]]],
        'self_hash_note': 'Manifest does not hash itself; Git commit versions the manifest bytes.',
    }
    write_json(HERE/'manifest.json', manifest)
    checks()  # Includes links to the now-generated manifest.
else:
    manifest = json.loads((HERE/'manifest.json').read_text(encoding='utf-8'))
    assert {a['path'] for a in manifest['artifacts']} == set(PAYLOAD+[GENERATED[0]])
    for item in manifest['artifacts']:
        assert digest(item['path']) == item, 'Artifact bytes differ: '+item['path']
print(json.dumps({'result': 'passed', 'repository_documents': len(PAYLOAD+GENERATED),
                  'checks': result}, ensure_ascii=True))
