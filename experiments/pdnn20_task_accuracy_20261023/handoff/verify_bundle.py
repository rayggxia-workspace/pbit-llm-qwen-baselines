"""Verify the explicit handoff payload; stdlib only, never load checkpoints."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath


def verify(root):
    root = Path(root).resolve(strict=True)
    manifest = json.loads((root / 'BUNDLE_MANIFEST.json').read_text(encoding='utf-8'))
    if manifest['repository'] != 'rayggxia-workspace/pbit-llm-qwen-baselines':
        raise ValueError('wrong repository')
    seen = set()
    for e in manifest['files']:
        rel = PurePosixPath(e['path'])
        if rel.is_absolute() or '..' in rel.parts or '\\' in e['path'] or e['path'] in seen:
            raise ValueError('unsafe or duplicate manifest path')
        seen.add(e['path'])
        p = (root / rel).resolve(strict=True)
        if not p.is_relative_to(root) or not p.is_file():
            raise ValueError('file leaves extracted root')
        if p.stat().st_size != e['bytes'] or hashlib.sha256(p.read_bytes()).hexdigest() != e['sha256']:
            raise ValueError('payload changed: ' + e['path'])
    exp = 'experiments/pdnn20_task_accuracy_20261023/'
    required = {exp+n for n in ('portable_runner.py','test_portable.py','config.json',
                'runner.py','checkpoints.expected.json','portable_reference.expected.json')}
    required |= {'experiments/pdnn_task_accuracy_20261023/pdnn_score.py',
                 'experiments/pdnn_ffn/full_path_pdnn_ffn.py',
                 'experiments/qwen_task_accuracy_20261019/task_data.py'}
    if not required <= seen:
        raise ValueError('incomplete executable dependency closure: ' + str(required - seen))
    actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    if actual != seen | {'BUNDLE_MANIFEST.json'}:
        raise ValueError('unexpected or omitted payload files: ' + str(actual.symmetric_difference(seen | {'BUNDLE_MANIFEST.json'})))
    return dict(status='verified', files=len(seen), code_commit=manifest['code_commit'],
                profile='portable_fresh_bf16_v1', real_twenty_layer_inference=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True)
    print(json.dumps(verify(parser.parse_args().root)))
