"""Load the pinned, external execution runtime without editing its sources."""
from pathlib import Path
import hashlib
import json
import sys


def use_runtime(runtime):
    runtime = Path(runtime).resolve()
    base = runtime/'base'
    manifest = json.loads((base/'SOURCE_MANIFEST.json').read_bytes())
    for name, expected in manifest['files_sha256'].items():
        if hashlib.sha256((base/name).read_bytes()).hexdigest() != expected:
            raise ValueError('pinned runtime mismatch: '+name)
    sys.path[:0] = [str(runtime), str(base)]
    import architecture_tlm
    extension = str(Path(__file__).resolve().parents[1])
    paths = [extension, str(runtime/'architecture_tlm'), str(base/'architecture_tlm')]
    architecture_tlm.__path__[:] = paths + [p for p in architecture_tlm.__path__ if p not in paths]
    return dict(base_manifest_sha256=hashlib.sha256((base/'SOURCE_MANIFEST.json').read_bytes()).hexdigest(),
                base_files_sha256=manifest['files_sha256'])
