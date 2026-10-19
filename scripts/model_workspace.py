"""Model-specific project navigation and unchanged legacy command dispatch."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
MODELS = ('qwen', 'llama1', 'llama2')


def project_path(value: str) -> Path:
    name = PurePosixPath(value)
    if not value or name.is_absolute() or '..' in name.parts or '\\' in value or ':' in value:
        raise ValueError('Project paths must be relative to the repository: ' + value)
    resolved = (ROOT / value).resolve()
    if not resolved.is_relative_to(ROOT) or not resolved.exists():
        raise ValueError('Missing or external project path: ' + value)
    return resolved


def load_project(model: str) -> dict:
    if model not in MODELS:
        raise ValueError('Unknown model directory: ' + model)
    data = json.loads((ROOT / model / 'project.json').read_text(encoding='utf-8'))
    if data.get('directory') != model or data.get('schema_version') != 1:
        raise ValueError('Model project identity mismatch')
    for section in ('code', 'configs', 'baselines', 'results', 'shared'):
        for row in data['locations'][section]:
            project_path(row['path'])
    for row in data['commands'].values():
        if project_path(row['script']).suffix != '.py':
            raise ValueError('Only explicit Python entry points are dispatched')
    return data


def check_project(data: dict) -> dict:
    for row in data['anchors']:
        raw = project_path(row['path']).read_bytes()
        if len(raw) != row['bytes'] or hashlib.sha256(raw).hexdigest() != row['sha256']:
            raise ValueError('Indexed model source/result changed: ' + row['path'])
    return {'model': data['directory'], 'anchors_verified': len(data['anchors']),
            'commands': sorted(data['commands']), 'historical_files_moved': False}


def main(model: str, argv: list[str] | None = None) -> int:
    data = load_project(model)
    parser = argparse.ArgumentParser(description=data['model'] + ': model project entry point')
    parser.add_argument('--dry-run', action='store_true', help='Print the exact command without loading a model or running TLM')
    parser.add_argument('action', nargs='?', default='info', choices=['info', 'check', *data['commands']])
    parser.add_argument('arguments', nargs=argparse.REMAINDER, help='Arguments passed unchanged to the selected script; relative paths use caller cwd')
    args = parser.parse_args(argv)
    if args.action in ('info', 'check'):
        if args.arguments:
            parser.error('info/check accept no forwarded arguments')
        result = data if args.action == 'info' else check_project(data)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    command = [sys.executable, str(project_path(data['commands'][args.action]['script'])), *args.arguments]
    if args.dry_run:
        print(json.dumps({'model': model, 'command': command,
                          'cwd': str(Path.cwd()), 'scope': data['commands'][args.action]['scope']},
                         ensure_ascii=False, indent=2))
        return 0
    # A subprocess prevents run.py/common.py and other model imports from leaking
    # across projects. Keeping cwd preserves the caller's relative input paths.
    return subprocess.run(command, check=False).returncode


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('model', choices=MODELS)
    parsed, rest = parser.parse_known_args()
    raise SystemExit(main(parsed.model, rest))
