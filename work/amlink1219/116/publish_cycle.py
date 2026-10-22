"""Publish/recover the authorized Issue116 PR; credentials remain in memory."""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
REPO = 'rayggxia-workspace/pbit-llm-qwen-baselines'
BRANCH = 'task/116-cycle-execution'
BASE = 'pbit-tlm-attention-details-20261016'
BASE_SHA = '46804fb3a1c50b29a19a7d0a3da6bb8f8b59af7d'


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['create', 'verify'])
    args = parser.parse_args()
    cred = subprocess.run(['git', 'credential', 'fill'],
        input='protocol=https\nhost=github.com\nusername=amlink1219\n\n',
        text=True, capture_output=True, check=True, cwd=ROOT)
    fields = dict(line.split('=', 1) for line in cred.stdout.splitlines() if '=' in line)
    headers = {'Authorization': 'Bearer '+fields['password'],
        'Accept': 'application/vnd.github+json', 'User-Agent': 'Codex-Issue116'}

    def api(path, data=None, method=None):
        url = 'https://api.github.com'+path
        payload = None if data is None else json.dumps(data).encode()
        request = urllib.request.Request(url, data=payload, headers=headers, method=method)
        with urllib.request.urlopen(request, timeout=45) as response:
            return json.load(response)

    me = api('/user')
    assert (me['login'], me['id']) == ('amlink1219', 75301230)
    repo_path = '/repos/'+REPO
    repo = api(repo_path)
    assert repo['id'] == 1420564659 and repo['permissions']['push']
    head = git('rev-parse', 'HEAD').decode().strip()
    assert git('branch', '--show-current').decode().strip() == BRANCH
    push_urls = git('remote', 'get-url', '--all', '--push', 'origin').decode().splitlines()
    assert push_urls == ['https://github.com/'+REPO+'.git']
    ref = api(repo_path+'/git/ref/heads/'+BRANCH)
    assert ref['object']['sha'] == head, 'push/ref verification must precede PR creation'
    existing = api(repo_path+'/pulls?state=all&head='+urllib.parse.quote('rayggxia-workspace:'+BRANCH))
    if args.action == 'create':
        intent = {'session_id': str(uuid.uuid4()), 'created_utc': datetime.now(timezone.utc).isoformat(),
                  'repo': REPO, 'branch': BRANCH, 'base': BASE, 'head': head, 'identity': me['login']}
        save(HERE/'PUBLICATION_INTENT.json', intent)
        if existing:
            assert len(existing) == 1 and existing[0]['state'] == 'open'
            pr = existing[0]
        else:
            pr = api(repo_path+'/pulls', {
                'title': '周期TLM后端：有限FFN/query、真实片段矩阵与独立审查',
                'head': BRANCH, 'base': BASE, 'body': (HERE/'PR_BODY.md').read_text(encoding='utf-8'),
                'draft': False}, 'POST')
        save(HERE/'PUBLICATION.json', {**intent, 'pr_number': pr['number'], 'pr_id': pr['id'],
            'pr_url': pr['html_url'], 'status': 'published_pending_remote_artifact_verification',
            'merged': pr['merged_at'] is not None})
        print(json.dumps({'pr_number':pr['number'], 'url':pr['html_url'], 'head':head}))
        return

    assert len(existing) == 1
    pr = existing[0]
    for attempt in range(5):
        if pr['head']['sha'] == head:
            break
        time.sleep(2)
        pr = api(repo_path+'/pulls/'+str(pr['number']))
    assert pr['head']['sha'] == head
    assert pr['base']['ref'] == BASE and pr['state'] == 'open' and pr['merged_at'] is None
    changes = git('diff', '--name-only', '-z', BASE_SHA, 'HEAD').decode().split('\0')
    changes = [p for p in changes if p]
    allowed = ('architecture_tlm/cycle_v1/', 'work/amlink1219/116/',
               'digital_circuit_simulation_registry/', 'progress/amlink1219/STATUS.md')
    assert all(p.startswith(allowed) for p in changes)
    assert not any('/private_fixtures/' in p or p.endswith(('.safetensors', '.pt', '.npz')) for p in changes)
    remote = api(repo_path+'/git/trees/'+head+'?recursive=1')
    assert not remote['truncated']
    remote_blobs = {item['path']:item['sha'] for item in remote['tree'] if item['type']=='blob'}
    local = {}
    for entry in git('ls-tree', '-rz', 'HEAD').split(b'\0'):
        if not entry:
            continue
        metadata, path = entry.split(b'\t', 1)
        local[path.decode()] = metadata.split()[2].decode()
    assert all(remote_blobs.get(p) == local[p] for p in changes)
    selected = ['architecture_tlm/cycle_v1/'+name for name in (
        'kernel.py','memory.py','ffn.py','attention.py','rng_protocol.py','IMPLEMENTATION_ZH.md',
        'audit/REVIEW_ZH.md','results/matrix_20261023/PUBLISHED_MANIFEST.json')]
    checks = []
    for path in selected:
        raw = base64.b64decode(api(repo_path+'/git/blobs/'+local[path])['content'])
        original = git('show', 'HEAD:'+path)
        assert raw == original
        checks.append({'path':path, 'sha256':hashlib.sha256(raw).hexdigest(), 'git_blob':local[path]})
    old = json.loads((HERE/'PUBLICATION.json').read_text(encoding='utf-8'))
    old.update(status='published_verified_open_unmerged', verified_utc=datetime.now(timezone.utc).isoformat(),
        verified_head=head, verified_changed_git_objects=len(changes), raw_blob_checks=checks,
        legacy_changed_paths=[], push_urls=push_urls)
    save(HERE/'PUBLICATION.json', old)
    print(json.dumps({'pr':pr['number'], 'head':head, 'git_objects_verified':len(changes),
                      'raw_blobs_verified':len(checks), 'merged':False}))


if __name__ == '__main__':
    main()
