"""Retry one confirmed failed shard, then collect immutable completed outputs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time


def sealed(path):
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == path.with_suffix('.sha256').read_text().strip()
    return json.loads(raw)


def save(path, value):
    raw = (json.dumps(value, indent=2) + '\n').encode()
    path.write_bytes(raw)
    path.with_suffix('.sha256').write_bytes((hashlib.sha256(raw).hexdigest() + '\n').encode())


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--settings', type=Path, required=True)
    p.add_argument('--phase', choices=['retry', 'collect'], required=True)
    a = p.parse_args()
    assert os.environ.get('SLURM_JOB_ID')
    cfg = sealed(a.settings)
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == cfg['wrapper_sha256']
    root = Path(cfg['original_root'])
    original = sealed(root / 'SETTINGS.json')
    resume = sealed(root / 'RESUME_SETTINGS.json')
    source = Path(original['source'])
    assert hashlib.sha256((source / 'EXECUTION_MANIFEST.json').read_bytes()).hexdigest() == resume['source_manifest_sha256']
    dest = Path(cfg['retry_root'])
    if a.phase == 'retry':
        index = cfg['failed_index']
        receipt = sealed(root / 'resource_resume_v1' / ('RECEIPT_%d.json' % index))
        assert receipt['returncode'] != 0
        case, seed, shard = original['array'][index]
        out = dest / 'full' / case / str(seed) / str(shard)
        assert not out.exists()
        devices = os.environ.get('CUDA_VISIBLE_DEVICES', '').split(',')
        assert devices and all(re.fullmatch(r'[A-Za-z0-9_:\-]+', d) for d in devices)
        chosen = None
        deadline = time.monotonic() + 3600
        while chosen is None and time.monotonic() < deadline:
            for device in devices:
                free = int(subprocess.check_output(['nvidia-smi', '-i', device, '--query-gpu=memory.free',
                           '--format=csv,noheader,nounits'], text=True).strip())
                if free >= 24576:
                    chosen = device
                    break
            if chosen is None:
                time.sleep(15)
        assert chosen is not None, 'No free assigned GPU; model not loaded'
        env = os.environ.copy()
        env.update(CUDA_VISIBLE_DEVICES=chosen, PYTHONHASHSEED='0', CUBLAS_WORKSPACE_CONFIG=':4096:8',
                   PYTORCH_CUDA_ALLOC_CONF='expandable_segments:True', PYTHONDONTWRITEBYTECODE='1',
                   HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
        for key, name in [('TMPDIR', 'tmp'), ('TRITON_CACHE_DIR', 'triton')]:
            folder = dest / name
            folder.mkdir(exist_ok=True)
            env[key] = str(folder)
        cmd = [original['python'], str(source / 'runner.py'), '--phase', 'full',
               '--runtime', original['runtime'], '--inputs', str(root / 'INPUTS.json'),
               '--output', str(out), '--case', case, '--seed', str(seed), '--shard', str(shard),
               '--gate', str(root / 'outputs/gate/RESULT.json')]
        rc = subprocess.call(cmd, env=env)
        save(dest / 'RETRY_RECEIPT.json', dict(index=index, case=case, seed=seed, shard=shard,
             returncode=rc, output=str(out), device=chosen, numerical_source_unchanged=True))
        assert rc == 0 and sealed(out / 'RESULT.json')['status'] == 'completed'
        return
    collection = dest / 'collection'
    collection.mkdir(exist_ok=False)
    sources = []
    for i, (case, seed, shard) in enumerate(original['array']):
        if i == cfg['failed_index']:
            folder = dest / 'full' / case / str(seed) / str(shard)
        else:
            base = root / ('outputs/full' if i in resume['preserve_indices'] else 'resource_resume_v1/full')
            folder = base / case / str(seed) / str(shard)
        result = sealed(folder / 'RESULT.json')
        assert result['status'] == 'completed' and (result['case'], result['seed'], result['shard']) == (case, seed, shard)
        link = collection / 'full' / case / str(seed) / str(shard)
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(folder, target_is_directory=True)
        sources.append(dict(index=i, path=str(folder), result_sha256=hashlib.sha256((folder / 'RESULT.json').read_bytes()).hexdigest()))
    (collection / 'bf16').symlink_to(root / 'outputs/bf16', target_is_directory=True)
    save(dest / 'COLLECTION_INDEX.json', sources)
    env = os.environ.copy()
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    subprocess.check_call([original['python'], str(source / 'runner.py'), '--phase', 'merge',
                           '--runtime', original['runtime'], '--inputs', str(root / 'INPUTS.json'),
                           '--output', str(collection / 'merge')], env=env)


if __name__ == '__main__':
    main()
