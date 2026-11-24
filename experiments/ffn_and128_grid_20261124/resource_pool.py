"""Use only GPUs assigned to this Slurm job and currently large enough for a model.

Some shared clusters do not account for unmanaged GPU processes in GRES.
This worker never kills them or uses a device outside CUDA_VISIBLE_DEVICES.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import queue
import subprocess

from dispatch import read
from scoring import save


def free_devices(minimum_mib):
    assigned = os.environ['CUDA_VISIBLE_DEVICES'].split(',')
    assert assigned and all(x and x != '-1' for x in assigned)
    devices = []
    for device in assigned:
        free = int(subprocess.check_output(['nvidia-smi', '-i', device, '--query-gpu=memory.free',
                   '--format=csv,noheader,nounits'], text=True).strip())
        if free >= minimum_mib:
            devices.append((device, free))
    return sorted(devices, key=lambda x: -x[1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--phase', choices=['gate', 'evaluate'], required=True)
    ap.add_argument('--settings', type=Path, required=True)
    a = ap.parse_args()
    assert os.environ.get('SLURM_JOB_ID')
    s = read(a.settings)
    root, source = Path(s['root']), Path(s['source'])
    devices = free_devices(s.get('minimum_free_mib', 40960))
    receipt = root / ('RESOURCE_' + a.phase + '_' + os.environ['SLURM_JOB_ID'] + '.json')
    save(receipt, {'status': 'started', 'assigned': os.environ['CUDA_VISIBLE_DEVICES'],
                   'usable_devices_free_mib': devices, 'phase': a.phase})
    assert devices, 'No assigned GPU has enough free memory; model was not loaded.'
    env = os.environ.copy()
    env.update(PYTHONHASHSEED='0', CUBLAS_WORKSPACE_CONFIG=':4096:8',
               HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
               PYTORCH_CUDA_ALLOC_CONF='expandable_segments:True')
    if a.phase == 'gate':
        env['CUDA_VISIBLE_DEVICES'] = devices[0][0]
        for key, folder in [('TMPDIR', 'tmp'), ('TRITON_CACHE_DIR', 'cache')]:
            dest = root / folder / ('gate_' + os.environ['SLURM_JOB_ID'])
            dest.mkdir(parents=True, exist_ok=True)
            env[key] = str(dest)
        cmd = [s['python'], str(source / 'runner.py'), '--phase', 'gate', '--output', str(root / 'gate')]
        for key in ['reference_source', 'runtime', 'task_source', 'data_root', 'inputs', 'overlay']:
            cmd += ['--' + key.replace('_', '-'), s[key]]
        subprocess.check_call(cmd, env=env)
        return
    specs = read(root / 'JOB_SPECS.json')
    pending = queue.Queue()
    for i in range(len(specs)):
        pending.put(i)
    results = []

    def worker(device):
        while True:
            try:
                i = pending.get_nowait()
            except queue.Empty:
                return
            child_env = env.copy()
            child_env.update(CUDA_VISIBLE_DEVICES=device, SLURM_ARRAY_TASK_ID=str(i),
                             SLURM_ARRAY_JOB_ID=os.environ['SLURM_JOB_ID'])
            log = root / 'logs' / ('worker_' + os.environ['SLURM_JOB_ID'] + '_' + str(i) + '.log')
            with log.open('xb') as handle:
                rc = subprocess.call([s['python'], s['dispatcher'], '--settings', str(a.settings),
                                      '--specs', str(root / 'JOB_SPECS.json')], env=child_env,
                                     stdout=handle, stderr=subprocess.STDOUT)
            results.append({'spec': i, 'device': device, 'returncode': rc})
            print(json.dumps(results[-1]), flush=True)

    with ThreadPoolExecutor(max_workers=len(devices)) as pool:
        list(pool.map(worker, [x[0] for x in devices]))
    save(receipt.with_name(receipt.stem + '_DONE.json'),
         {'status': 'completed' if all(r['returncode'] == 0 for r in results) else 'failed',
          'results': sorted(results, key=lambda x: x['spec'])})
    assert len(results) == len(specs) and all(r['returncode'] == 0 for r in results)


if __name__ == '__main__':
    main()
