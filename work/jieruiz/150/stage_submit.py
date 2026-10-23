"""Personal server staging, then CPU -> GPU prepare -> 20-case Slurm array."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

ROOT = Path('/home/Hongjie_Zeng/projects/pbit-qwen-static-multiscale-20261023-issue150')
sha, expected = sys.argv[1:3]
assert len(sha) == 40 and all(c in '0123456789abcdef' for c in sha)
archive = ROOT/'incoming'/('source-'+sha+'.tar')
assert hashlib.sha256(archive.read_bytes()).hexdigest() == expected
snapshot = ROOT/'snapshots'/sha
snapshot.mkdir(parents=True, exist_ok=False)
with tarfile.open(archive) as tar:
    for member in tar.getmembers():
        assert member.isfile() and not Path(member.name).is_absolute() and '..' not in Path(member.name).parts
    tar.extractall(snapshot)
old = Path('/home/Hongjie_Zeng/projects/pbit-qwen-joint-ffn-attention-20261019-issue50/snapshots/c0fd54446d843f0b21e94bf138c692048e518c86/experiments/qwen_dual_iid_exact_20261018')
area = snapshot/'experiments/qwen_dual_iid_exact_20261018'
frozen = json.loads((area/'frozen_manifest.json').read_text())
assets = {}
for name in ('calibration.json', 'sz_calibration.json'):
    rel = 'vendor/frozen/results/'+name
    source, entry = old/rel, frozen['files'][rel]
    assert source.stat().st_size == entry['bytes']
    assert hashlib.sha256(source.read_bytes()).hexdigest() == entry['sha256']
    target = area/rel
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    assets[rel] = dict(entry, source=str(source))
manifest = {str(p.relative_to(snapshot)): dict(bytes=p.stat().st_size,
            sha256=hashlib.sha256(p.read_bytes()).hexdigest())
            for p in sorted(snapshot.rglob('*')) if p.is_file()}
(ROOT/'logs').mkdir(exist_ok=True)
receipt = dict(code_commit=sha, source_archive_sha256=expected, snapshot=str(snapshot),
               assets=assets, executed_source=manifest, jobs=[])
record = ROOT/('submission-'+sha+'.json')
env = dict(os.environ, PBIT_PROJECT_ROOT=str(ROOT), PBIT_SNAPSHOT=str(snapshot), PBIT_CODE_COMMIT=sha)
dependency = None
for action in ('cpu', 'prepare', 'worker'):
    env['PBIT_ACTION'] = action
    cmd = ['/opt/slurm/21.08.8/bin/sbatch', '--parsable', '--export=ALL',
           '--output='+str(ROOT/'logs'/(action+'-%A_%a.out'))]
    if action != 'cpu':
        cmd += ['--gres=gpu:1']
    if dependency:
        cmd += ['--dependency=afterok:'+dependency]
    if action == 'worker':
        cmd += ['--array=0-19%2']
    cmd += [str(snapshot/'experiments/qwen_static_multiscale_20261023/run.sbatch')]
    run = subprocess.run(cmd, env=env, capture_output=True, text=True, check=True)
    dependency = run.stdout.strip().split(';')[0]
    assert dependency.isdigit()
    receipt['jobs'].append(dict(action=action, job_id=dependency, command=cmd))
    record.write_text(json.dumps(receipt, indent=2)+'\n')
print(json.dumps(receipt))
