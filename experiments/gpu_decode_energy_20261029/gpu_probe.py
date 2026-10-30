import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

import torch
import transformers
from meter import Nvml

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    assert 'SLURM_JOB_ID' in os.environ, 'GPU tests require Slurm'
    assert torch.cuda.device_count()==1
    props=torch.cuda.get_device_properties(0)
    uuid=str(props.uuid)
    if not uuid.startswith('GPU-'):uuid='GPU-'+uuid
    device=Nvml(uuid)
    errors={}
    try:before=device.energy_mJ();energy_supported=True
    except Exception as e:before=None;energy_supported=False;errors['energy']=str(e)
    torch.manual_seed(17)
    x=torch.randn(2048,2048,device='cuda',dtype=torch.bfloat16)
    y=torch.randn_like(x)
    for _ in range(8):z=x@y
    torch.cuda.synchronize()
    start=time.perf_counter();e0=device.energy_mJ() if energy_supported else None;n=0
    while time.perf_counter()-start<2:
        for _ in range(16):z=x@y
        torch.cuda.synchronize();n+=16
    elapsed=time.perf_counter()-start;e1=device.energy_mJ() if energy_supported else None
    samples=[]
    for _ in range(100):
        samples.append({'t':time.perf_counter(),'energy_mJ':device.energy_mJ() if energy_supported else None,'power_W':device.power_W()})
        time.sleep(.01)
    with torch.profiler.profile(activities=[torch.profiler.ProfilerActivity.CPU,torch.profiler.ProfilerActivity.CUDA]) as profile:
        z=x@y;torch.cuda.synchronize()
    cuda=[e.name for e in profile.events() if str(e.device_type).endswith('CUDA')]
    apps=subprocess.run(['nvidia-smi','--query-compute-apps=gpu_uuid,pid','--format=csv,noheader,nounits'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
    foreign=[]
    for line in apps.stdout.splitlines():
        parts=[s.strip() for s in line.split(',')]
        if len(parts)==2 and parts[0]==uuid and parts[1]!=str(os.getpid()):foreign.append(parts[1])
    assert not foreign, 'allocated GPU has another compute process'
    result={'status':'completed','kind':'preflight_only_not_LLM_measurement',
        'Slurm_job_id':os.environ['SLURM_JOB_ID'],'gpu_name':props.name,'gpu_memory_bytes':props.total_memory,
        'gpu_uuid_sha256':hashlib.sha256(uuid.encode()).hexdigest(),'CUDA_VISIBLE_DEVICES':os.environ.get('CUDA_VISIBLE_DEVICES'),
        'torch':torch.__version__,'transformers':transformers.__version__,'energy_counter_supported':energy_supported,
        'probe_energy_J':(e1-e0)/1000 if energy_supported else None,'probe_elapsed_s':elapsed,
        'probe_operations':n,'power_reading_W':device.power_W(),'state':device.state(),
        'counter_samples':samples,'CUDA_profiler_kernels':cuda,'nsys':shutil.which('nsys'),'ncu':shutil.which('ncu'),
        'foreign_compute_processes':foreign,'foreign_check_returncode':apps.returncode,'errors':errors}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k not in ['counter_samples','CUDA_profiler_kernels']}),flush=True)

if __name__=='__main__':main()
