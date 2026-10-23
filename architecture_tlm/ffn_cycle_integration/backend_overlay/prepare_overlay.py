"""Rebuild this task-owned overlay from a verified research snapshot.

Reads the external Issue116 checkout; never copies its unchanged backend code.
"""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import subprocess

BASE = '160f46e0b63bdf94499e2434dc35e09f44fc2fcc'
SCIENTIFIC_BASE = 'ddd2e3406caac5075689f9388a041603e17d2b19'
BASE_FFN_SHA256_LF = '45b5cf4b242ce0e60ff5438e5a8419245bfbe6ec5324288ed56a54c9bebe9036'
CHANGE = '15a87d93a5ce2626b21d0f6579a454fa02d74076'
FINAL = 'a0a0e53e901177053807f5cc5215a51f6383c93c'
SNAPSHOT = '7d3b45001b48e20d39d49237a5575b0d7b487ca5'
HISTORICAL_LOCAL_COMMITS = dict(
    baseline='902c49bfae790853c7930e6c9f999afc52f81c4a',
    ffn_change='b8290c7ecaad58e2ca3148f052f8ccd6cbe29fdf',
    final_runner='a68bb1e98b95588ab6a751db0fca00dd968643ba')
FFN = 'architecture_tlm/cycle_v1/ffn.py'
OWN = ('ffn_contract.py', 'ffn_contract_reference.py', 'run_contract_ffn.py', 'test_ffn_contract.py')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def lf(data):
    data = data.replace(b'\r\n', b'\n')
    if b'\r' in data:
        raise ValueError('bare carriage return is not supported')
    data.decode('utf-8')
    return data


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--snapshot-root', type=Path, required=True)
    ap.add_argument('--source-manifest', type=Path, required=True)
    args = ap.parse_args()
    root = args.snapshot_root.resolve(strict=True)
    here = Path(__file__).resolve().parent
    manifest_raw = args.source_manifest.read_bytes()
    snapshot = json.loads(manifest_raw)
    if snapshot.get('backend_local_commit') != SNAPSHOT:
        raise ValueError('source manifest is not the pinned revision4 backend commit')
    records = {}
    for path, expected in snapshot['files'].items():
        raw = (root / path).read_bytes()
        if sha(raw) != expected:
            raise ValueError('snapshot raw SHA mismatch: ' + path)
        records[path] = dict(snapshot_sha256=expected, sha256_lf=sha(lf(raw)), bytes=len(raw))
    def git_bytes(commit, path):
        return subprocess.run(['git', 'show', commit + ':' + path], cwd=root,
                              check=True, capture_output=True).stdout
    before = git_bytes(BASE, FFN)
    if sha(lf(before)) != BASE_FFN_SHA256_LF:
        raise ValueError('published PR126 ffn.py differs from the reviewed overlay baseline')
    after = git_bytes(CHANGE, FFN)
    if lf(after) != lf((root / FFN).read_bytes()):
        raise ValueError('ffn.py no longer equals the reviewed change commit')
    patch = ''.join(difflib.unified_diff(lf(before).decode().splitlines(keepends=True),
        lf(after).decode().splitlines(keepends=True), fromfile='a/' + FFN, tofile='b/' + FFN)).encode()
    if not patch:
        raise ValueError('expected a nonempty ffn.py patch')
    payloads = []
    prepared_payloads = []
    for name in OWN:
        path = 'architecture_tlm/cycle_v1/' + name
        commit = FINAL if name == 'run_contract_ffn.py' else CHANGE
        raw = lf((root / path).read_bytes())
        if raw != lf(git_bytes(commit, path)):
            raise ValueError('task-owned source differs from pinned commit: ' + path)
        payloads.append(dict(target=path, payload='files/' + name, sha256_lf=sha(raw),
                             source_commit=commit, before='absent'))
        prepared_payloads.append((here / 'files' / name, raw))
    targets = {FFN, *(p['target'] for p in payloads)}
    document = dict(schema='ffn.backend_overlay.1', overlay_id='issue123-pr126-revision4-v1',
        publication_state='PR126 backend published at fixed ref; overlay retained for revision4 reproduction and history, not a merge receipt',
        baseline_published_commit=BASE, baseline_scientific_commit=SCIENTIFIC_BASE,
        baseline_pull_request='https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/126',
        ffn_change_local_commit=CHANGE, final_runner_local_commit=FINAL,
        historical_local_commits=HISTORICAL_LOCAL_COMMITS,
        snapshot_revision=4, snapshot_source_state=snapshot.get('source_state'),
        snapshot_backend_local_commit=snapshot.get('backend_local_commit'),
        snapshot_manifest_sha256=sha(manifest_raw), snapshot_files=records,
        dependencies={path:record for path,record in records.items() if path not in targets},
        patch=dict(target=FFN, payload='ffn.py.patch', sha256_lf=sha(patch),
                   before_sha256_lf=sha(lf(before)), baseline_git_bytes_sha256=sha(before),
                   after_sha256_lf=sha(lf(after))), payloads=payloads,
        boundary='Only four task-owned new files and a unified ffn.py diff are supplied. Unchanged Issue116 source is external.')
    # A later snapshot can refresh dependency hashes while the reviewed payloads
    # stay frozen. Refuse changed payloads before writing any package files.
    for path, raw in prepared_payloads:
        if path.exists() and path.read_bytes() != raw:
            raise ValueError('existing payload differs; preserve it for review: ' + str(path))
    if (here / 'ffn.py.patch').exists() and (here / 'ffn.py.patch').read_bytes() != patch:
        raise ValueError('existing patch differs; preserve it for review')
    (here / 'files').mkdir(exist_ok=True)
    for path, raw in prepared_payloads:
        if not path.exists():
            path.write_bytes(raw)
    (here / 'ffn.py.patch').write_bytes(patch)
    (here / 'MANIFEST.json').write_text(json.dumps(document, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(dict(snapshot_files=len(records), dependencies=len(document['dependencies']),
                          new_files=len(payloads), patch_bytes=len(patch))))


if __name__ == '__main__':
    main()
