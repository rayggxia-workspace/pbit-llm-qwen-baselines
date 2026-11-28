"""Run only on a sufficiently free GPU assigned to this Slurm job."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time


def save(p,v):
    raw=(json.dumps(v,indent=2)+'\n').encode()
    p.write_bytes(raw)
    p.with_suffix('.sha256').write_bytes((hashlib.sha256(raw).hexdigest()+'\n').encode())


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--settings',type=Path,required=True)
    a=ap.parse_args();root=a.settings.parent
    assert os.environ.get('SLURM_JOB_ID')
    raw=a.settings.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==a.settings.with_suffix('.sha256').read_text().strip()
    s=json.loads(raw)
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==s['launcher_sha256']
    assigned=os.environ['CUDA_VISIBLE_DEVICES'].split(',')
    assert assigned and all(x and x!='-1' for x in assigned)
    selected=None;deadline=time.monotonic()+180
    while time.monotonic()<deadline:
        rows=[]
        for d in assigned:
            free=int(subprocess.check_output(['nvidia-smi','-i',d,'--query-gpu=memory.free','--format=csv,noheader,nounits'],text=True).strip())
            rows.append(dict(device=d,free_mib=free))
            if free>=24576:selected=d;break
        save(root/'RESOURCE.json',dict(status='started' if selected else 'waiting',assigned=assigned,
             observed=rows,selected=selected,job=os.environ['SLURM_JOB_ID']))
        if selected is not None:break
        time.sleep(15)
    if selected is None:
        save(root/'EXECUTION.json',dict(status='resource_unavailable',model_started=False,job=os.environ['SLURM_JOB_ID']))
        raise SystemExit(3)
    env=os.environ.copy()
    env.update(CUDA_VISIBLE_DEVICES=selected,PYTHONHASHSEED='0',CUBLAS_WORKSPACE_CONFIG=':4096:8',
        PYTORCH_CUDA_ALLOC_CONF='expandable_segments:True',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',
        PYTHONDONTWRITEBYTECODE='1',TOKENIZERS_PARALLELISM='false')
    for key,folder in [('TMPDIR','tmp'),('TRITON_CACHE_DIR','triton')]:
        p=root/folder;p.mkdir(exist_ok=True);env[key]=str(p)
    cmd=[s['python'],str(Path(__file__).with_name('run.py')),'--phase','gpu','--assets',str(root/'assets'),
         '--inputs',s['inputs'],'--old-pilot',s['old_pilot'],'--output',str(root/'outputs')]
    rc=subprocess.call(cmd,env=env)
    save(root/'EXECUTION.json',dict(status='completed' if rc==0 else 'failed',returncode=rc,command=cmd,
        job=os.environ['SLURM_JOB_ID'],selected_device=selected,manifest_sha256=s['manifest_sha256']))
    raise SystemExit(rc)


if __name__=='__main__':main()
