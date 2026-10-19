"""Verify all committed Llama2 execution inputs, including shared Llama1 engine bytes."""
import hashlib
import json
from pathlib import Path

root=Path(__file__).resolve().parents[2]
manifest=json.loads(Path(__file__).with_name('EXECUTION_MANIFEST.json').read_text(encoding='utf-8'))
for row in manifest['files']:
    name=Path(row['path'])
    if name.is_absolute() or '..' in name.parts:raise ValueError('Unsafe frozen input path')
    raw=(root/name).read_bytes()
    if len(raw)!=row['bytes'] or hashlib.sha256(raw).hexdigest()!=row['sha256']:
        raise RuntimeError('Immutable source mismatch: '+str(name))
print(json.dumps({'verified_inputs':len(manifest['files']),'source_commit':manifest['code_commit']}))
