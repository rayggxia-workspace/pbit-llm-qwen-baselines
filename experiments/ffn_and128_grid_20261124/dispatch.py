"""Slurm-array entry; settings with private paths are provided separately."""
import argparse
import hashlib
import json
import os
from pathlib import Path


def read(path):
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == path.with_suffix('.sha256').read_text().strip()
    return json.loads(raw)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--settings', type=Path, required=True)
    p.add_argument('--specs', type=Path, required=True)
    a = p.parse_args()
    settings, specs = read(a.settings), read(a.specs)
    spec = specs[int(os.environ['SLURM_ARRAY_TASK_ID'])]
    root, source = Path(settings['root']).resolve(), Path(settings['source']).resolve()
    out = (root / spec['output']).resolve()
    assert root in out.parents and root in source.parents
    env = os.environ.copy()
    env.update(PYTHONHASHSEED='0', CUBLAS_WORKSPACE_CONFIG=':4096:8',
               PYTORCH_CUDA_ALLOC_CONF='expandable_segments:True',
               HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
    for key, folder in [('TMPDIR', 'tmp'), ('TRITON_CACHE_DIR', 'cache')]:
        dest = root / folder / (os.environ['SLURM_ARRAY_JOB_ID'] + '_' + os.environ['SLURM_ARRAY_TASK_ID'])
        dest.mkdir(parents=True, exist_ok=True)
        env[key] = str(dest)
    cmd = [settings['python'], str(source / 'runner.py'), '--phase', spec['phase'],
           '--case', spec['case'], '--seed', str(spec['seed']), '--shard', str(spec['shard']),
           '--task', spec['task'], '--gate', str(root / 'gate/RESULT.json'), '--output', str(out)]
    for key in ['reference_source', 'runtime', 'task_source', 'data_root']:
        cmd += ['--' + key.replace('_', '-'), settings[key]]
    for key in ['inputs', 'overlay']:
        if key in settings:
            cmd += ['--' + key, settings[key]]
    os.execve(settings['python'], cmd, env)


if __name__ == '__main__':
    main()
