"""Slurm-only launcher; use free assigned GPU and immutable numeric snapshot."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time


def save(path, value):
    raw = (json.dumps(value, indent=2) + '\n').encode()
    path.write_bytes(raw)
    path.with_suffix('.sha256').write_bytes((hashlib.sha256(raw).hexdigest() + '\n').encode())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--settings', type=Path, required=True)
    args = parser.parse_args()
    assert os.environ.get('SLURM_JOB_ID')
    raw = args.settings.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == args.settings.with_suffix('.sha256').read_text().strip()
    s = json.loads(raw)
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == s['launcher_sha256']
    root = args.settings.parent
    source = Path(s['source'])
    assert hashlib.sha256((source / 'EXECUTION_MANIFEST.json').read_bytes()).hexdigest() == s['manifest_sha256']
    assert hashlib.sha256(Path(s['inputs']).read_bytes()).hexdigest() == s['inputs_sha256']
    assigned = os.environ.get('CUDA_VISIBLE_DEVICES', '').split(',')
    assert assigned and all(re.fullmatch(r'[A-Za-z0-9_:\-]+', d) for d in assigned)
    selected = None
    deadline = time.monotonic() + s.get('resource_wait_seconds', 3600)
    while selected is None and time.monotonic() < deadline:
        free = []
        for device in assigned:
            mib = int(subprocess.check_output(['nvidia-smi', '-i', device, '--query-gpu=memory.free',
                      '--format=csv,noheader,nounits'], text=True).strip())
            free.append(dict(device=device, free_mib=mib))
            if mib >= 24576:
                selected = device
                break
        save(root / 'RESOURCE.json', dict(status='started' if selected is not None else 'waiting',
             job=os.environ['SLURM_JOB_ID'], assigned=assigned, observed=free, selected=selected))
        if selected is None:
            time.sleep(15)
    assert selected is not None, 'No free assigned GPU; numerical evaluation not started'
    env = os.environ.copy()
    env.update(CUDA_VISIBLE_DEVICES=selected, PYTHONHASHSEED='0', CUBLAS_WORKSPACE_CONFIG=':4096:8',
               PYTORCH_CUDA_ALLOC_CONF='expandable_segments:True', PYTHONDONTWRITEBYTECODE='1',
               HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
    for key, name in [('TMPDIR', 'tmp'), ('TRITON_CACHE_DIR', 'triton')]:
        folder = root / name
        folder.mkdir(exist_ok=True)
        env[key] = str(folder)
    cmd = [s['python'], str(source / 'driver.py'), '--assets', str(root / 'assets'),
           '--inputs', s['inputs'], '--output', str(root / 'outputs')]
    rc = subprocess.call(cmd, env=env)
    save(root / 'EXECUTION.json', dict(status='completed' if rc == 0 else 'failed', returncode=rc,
         command=cmd, selected_device=selected, manifest_sha256=s['manifest_sha256']))
    raise SystemExit(rc)


if __name__ == '__main__':
    main()
