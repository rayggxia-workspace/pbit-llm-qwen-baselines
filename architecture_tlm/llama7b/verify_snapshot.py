"""Reject mutated execution inputs before every server task."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
manifest = json.loads((ROOT / 'EXECUTION_MANIFEST.json').read_text(encoding='utf-8'))
for row in manifest['files']:
    path = ROOT / row['path']
    raw = path.read_bytes()
    assert len(raw) == row['bytes'] and hashlib.sha256(raw).hexdigest() == row['sha256'], row['path']
print('Immutable input snapshot verified:', len(manifest['files']), 'files; code', manifest['code_commit'])
