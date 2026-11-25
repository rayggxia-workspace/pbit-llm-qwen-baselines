"""Bounded Slurm entry; machine paths remain in an external sealed settings file."""
import argparse
import hashlib
import json
import os
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--settings', type=Path, required=True)
    p.add_argument('--kind', choices=['cpu','gate','bf16','array','merge'], required=True)
    a = p.parse_args()
    raw = a.settings.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == a.settings.with_suffix('.sha256').read_text().strip()
    settings = json.loads(raw)
    root, source = Path(settings['root']).resolve(), Path(settings['source']).resolve()
    assert root in source.parents
    if a.kind == 'array':
        case, seed, shard = settings['array'][int(os.environ['SLURM_ARRAY_TASK_ID'])]
        phase, subdir = 'full', 'full/%s/%d/%d' % (case,seed,shard)
    else:
        phase = 'full' if a.kind == 'bf16' else a.kind
        case, seed, shard, subdir = 'bf16', 101, 0, a.kind
    env = os.environ.copy()
    env.update(PYTHONHASHSEED='0', CUBLAS_WORKSPACE_CONFIG=':4096:8',
               PYTORCH_CUDA_ALLOC_CONF='expandable_segments:True',
               HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', PYTHONDONTWRITEBYTECODE='1')
    for key, folder in [('TMPDIR','tmp'),('TRITON_CACHE_DIR','triton')]:
        dest = root/folder/(os.environ['SLURM_JOB_ID']+'_'+os.environ.get('SLURM_ARRAY_TASK_ID','0'))
        dest.mkdir(parents=True, exist_ok=True)
        env[key] = str(dest)
    cmd = [settings['python'], str(source/'runner.py'), '--phase',phase,
           '--runtime',settings['runtime'], '--inputs',str(root/'INPUTS.json'),
           '--output',str(root/'outputs'/subdir), '--case',case, '--seed',str(seed),
           '--shard',str(shard), '--gate',str(root/'outputs/gate/RESULT.json')]
    os.execve(settings['python'], cmd, env)


if __name__=='__main__':
    main()
