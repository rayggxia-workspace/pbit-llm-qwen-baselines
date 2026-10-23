"""Read only finished JSON artifacts; snapshot log bytes, no weights/source edits."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import tarfile


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--root', required=True)
    p.add_argument('--output', required=True)
    args = p.parse_args()
    root = Path(args.root).resolve()
    assert str(root) == '/home/Hongjie_Zeng/projects/pbit-qwen3-stochastic-20261023-issue144'
    output = Path(args.output).resolve()
    assert output.is_relative_to(root / 'exports')
    output.parent.mkdir(parents=True, exist_ok=True)
    originals = {}
    for directory in [root, root / 'results', root / 'anchor/results']:
        iterator = directory.glob('*.sha256.json') if directory == root else directory.rglob('*.sha256.json')
        for sidecar in iterator:
            meta = json.loads(sidecar.read_bytes())
            path = sidecar.with_name(meta['name'])
            assert path.resolve().is_relative_to(root)
            raw = path.read_bytes()
            assert len(raw) < 3_000_000
            assert hashlib.sha256(raw).hexdigest() == meta['sha256']
            originals[str(path.relative_to(root))] = raw
            originals[str(sidecar.relative_to(root))] = sidecar.read_bytes()
    for log in sorted((root / 'logs').glob('*.log')):
        raw = log.read_bytes()
        assert len(raw) < 3_000_000
        originals[str(log.relative_to(root))] = raw
    checksums = {name: hashlib.sha256(raw).hexdigest() for name, raw in originals.items()}
    originals['SERVER_SHA256.json'] = (json.dumps(checksums, indent=2) + '\n').encode()
    assert sum(map(len, originals.values())) < 50_000_000
    with tarfile.open(output, 'x:gz') as archive:
        for name, raw in originals.items():
            info = tarfile.TarInfo(name)
            info.size, info.mode = len(raw), 0o444
            archive.addfile(info, io.BytesIO(raw))
    print(json.dumps(dict(path=str(output), sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
                         files=len(originals), finished_results_only=True)))


if __name__ == '__main__':
    main()
