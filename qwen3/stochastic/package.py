"""Package exact committed sources and small required configs only."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', required=True)
    args = p.parse_args()
    root = Path(__file__).resolve().parents[2]
    def git(*arguments):
        return subprocess.check_output(['git', '-C', str(root), *arguments])
    assert not git('status', '--porcelain', '--', 'qwen3/stochastic', 'qwen3/baselines').strip()
    revision = git('rev-parse', 'HEAD').decode().strip()
    paths = git('ls-tree', '-r', '--name-only', revision, 'qwen3/stochastic', 'qwen3/baselines').decode().splitlines()
    manifest = dict(repository='https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines',
                    commit=revision, files_sha256={})
    def put(archive, name, raw):
        info = tarfile.TarInfo(name)
        info.size, info.mode = len(raw), 0o444
        archive.addfile(info, io.BytesIO(raw))
    with tarfile.open(args.output, 'x:gz') as archive:
        for name in paths:
            raw = git('show', revision + ':' + name)
            manifest['files_sha256'][name] = hashlib.sha256(raw).hexdigest()
            put(archive, name, raw)
        put(archive, 'execution.json', (json.dumps(manifest, indent=2) + '\n').encode())
    print(json.dumps(dict(path=args.output, sha256=hashlib.sha256(Path(args.output).read_bytes()).hexdigest(),
                         commit=revision, files=len(paths))))


if __name__ == '__main__':
    main()
