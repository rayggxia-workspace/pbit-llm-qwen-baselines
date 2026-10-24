import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[3]
def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args])
commit = git('rev-parse', 'HEAD').decode().strip()
paths = git('ls-tree', '-r', '--name-only', commit, 'qwen3/fixed_scale').decode().splitlines()
paths += ['qwen3/baselines/support.py']
paths += ['qwen3/stochastic/vendor/' + name + '.py' for name in
          ('core', 'range_core', 'shared_counts', 'stratified_core', 'scoring')]
assert not git('status', '--porcelain', '--', *paths).strip()
manifest = dict(repository='rayggxia-workspace/pbit-llm-qwen-baselines', commit=commit, files_sha256={})
out = ROOT / 'work/jieruiz/168' / ('source-' + commit[:12] + '.tar.gz')
with tarfile.open(out, 'x:gz') as archive:
    def add(name, raw):
        info = tarfile.TarInfo(name)
        info.size, info.mode = len(raw), 0o444
        archive.addfile(info, io.BytesIO(raw))
    for path in paths:
        raw = git('show', commit + ':' + path)
        manifest['files_sha256'][path] = hashlib.sha256(raw).hexdigest()
        add(path, raw)
    add('execution.json', (json.dumps(manifest, indent=2) + '\n').encode())
receipt = dict(commit=commit, package=str(out), sha256=hashlib.sha256(out.read_bytes()).hexdigest(),
               files_sha256=manifest['files_sha256'])
(ROOT / 'work/jieruiz/168/PACKAGE.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
print(json.dumps({k: v for k, v in receipt.items() if k != 'files_sha256'}))
