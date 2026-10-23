"""Archive exact committed Git blobs, including protected historical CRLF."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT/'work/jieruiz/150'
AREAS = ['experiments/'+p for p in ('qwen_static_multiscale_20261023',
    'qwen_multiscale_stratified_20261019', 'qwen_fixedw_multiscale_20261019',
    'qwen_dual_range_20261018', 'qwen_dual_iid_exact_20261018')]
sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
paths = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', sha, '--']+AREAS,
                                cwd=ROOT, text=True).splitlines()
archive = OUT/('source-'+sha+'.tar')
manifest = {}
with tarfile.open(archive, 'w') as tar:
    for path in paths:
        if Path(path).suffix not in ('.py', '.json', '.md', '.sbatch', '.gitattributes'):
            continue
        data = subprocess.check_output(['git', 'show', sha+':'+path], cwd=ROOT)
        info = tarfile.TarInfo(path)
        info.size, info.mode, info.mtime = len(data), 0o644, 0
        tar.addfile(info, io.BytesIO(data))
        manifest[path] = dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
result = dict(commit=sha, archive=archive.name, bytes=archive.stat().st_size,
              sha256=hashlib.sha256(archive.read_bytes()).hexdigest(), files=manifest)
(OUT/'PACKAGE.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
print(json.dumps(dict(commit=sha, archive=str(archive), sha256=result['sha256'], files=len(manifest))))
