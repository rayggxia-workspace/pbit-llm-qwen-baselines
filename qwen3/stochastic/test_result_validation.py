"""Tamper tests against actual tiny archived metadata, never model execution."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
from .validate_results import validate


def main():
    p = argparse.ArgumentParser()
    p.add_argument('archive')
    args = p.parse_args()
    source = Path(args.archive).resolve()
    validate(source)
    changes = {
        'ppl': lambda d: d.update(perplexity=d['perplexity'] + 1),
        'target': lambda d: d['examples'][0].update(first_target=0),
        'coverage': lambda d: d['execution_audit']['decode_calls_per_layer'].__setitem__(0, 0),
        'token_hash': lambda d: d.update(token_ids_sha256_le_int64='0' * 64),
        'revision': lambda d: d['model'].update(revision='0' * 40),
        'config': lambda d: d.update(config_sha256='0' * 64),
        'protocol': lambda d: d.update(protocol='full'),
        'calibration': lambda d: d.update(calibration_sha256='0' * 64),
    }
    for label, change in changes.items():
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2] / 'work/jieruiz/144') as tmp:
            target = Path(tmp) / 'archive'
            shutil.copytree(source, target)
            path = target / 'results/Qwen3-1.7B-Base/bf16_s0.json'
            d = json.loads(path.read_bytes())
            change(d)
            path.write_bytes((json.dumps(d, indent=2) + '\n').encode())
            side = path.with_suffix('.sha256.json')
            side.write_bytes((json.dumps(dict(name=path.name, sha256=hashlib.sha256(path.read_bytes()).hexdigest())) + '\n').encode())
            manifest_path = target / 'SERVER_SHA256.json'
            manifest = json.loads(manifest_path.read_bytes())
            for changed in [path, side]:
                manifest[str(changed.relative_to(target)).replace('\\', '/')] = hashlib.sha256(changed.read_bytes()).hexdigest()
            manifest_path.write_bytes((json.dumps(manifest) + '\n').encode())
            try:
                validate(target)
            except AssertionError:
                pass
            else:
                raise AssertionError('tamper accepted: ' + label)
    print(json.dumps(dict(status='PASS', original_archive_valid=True, semantic_negative_guards=list(changes))))


if __name__ == '__main__':
    main()
