"""Resume only missing shards on actually free, Slurm-assigned GPUs.

Numerical snapshot stays immutable. Existing completed/healthy shards and BF16
are reused through an explicit collection index; failed attempts remain intact.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import fcntl
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import subprocess
import time


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(value, indent=2) + '\n').encode()
    path.write_bytes(raw)
    path.with_suffix('.sha256').write_bytes((hashlib.sha256(raw).hexdigest()+'\n').encode())


def sealed(path):
    assert hashlib.sha256(path.read_bytes()).hexdigest()==path.with_suffix('.sha256').read_text().strip()
    return json.loads(path.read_bytes())


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--settings', type=Path, required=True)
    p.add_argument('--phase', choices=['evaluate','collect'], required=True)
    a=p.parse_args()
    assert os.environ.get('SLURM_JOB_ID')
    settings=sealed(a.settings)
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==settings['resource_wrapper_sha256']
    original=sealed(Path(settings['original_settings']))
    root=Path(original['root'])
    retry=root/'resource_resume_v1'
    retry.mkdir(exist_ok=True)
    source=Path(original['source'])
    assert hashlib.sha256((source/'EXECUTION_MANIFEST.json').read_bytes()).hexdigest()==settings['source_manifest_sha256']
    if a.phase=='collect':
        report=sealed(retry/'RESULT.json')
        assert report['status']=='completed'
        collection=retry/'collection'
        collection.mkdir(exist_ok=False)
        index=[]
        for i,(case,seed,shard) in enumerate(original['array']):
            folder=(root/'outputs/full' if i in settings['preserve_indices'] else retry/'full')/case/str(seed)/str(shard)
            r=sealed(folder/'RESULT.json')
            assert r['status']=='completed' and r['case']==case and r['seed']==seed and r['shard']==shard
            dest=collection/'full'/case/str(seed)/str(shard)
            dest.parent.mkdir(parents=True,exist_ok=True)
            dest.symlink_to(folder, target_is_directory=True)
            index.append(dict(index=i,path=str(folder),result_sha256=hashlib.sha256((folder/'RESULT.json').read_bytes()).hexdigest()))
        (collection/'bf16').symlink_to(root/'outputs/bf16', target_is_directory=True)
        save(retry/'COLLECTION_INDEX.json',index)
        env=os.environ.copy();env['PYTHONDONTWRITEBYTECODE']='1'
        subprocess.check_call([original['python'],str(source/'runner.py'),'--phase','merge',
                              '--runtime',original['runtime'],'--inputs',str(root/'INPUTS.json'),
                              '--output',str(collection/'merge')],env=env)
        return
    assigned=os.environ.get('CUDA_VISIBLE_DEVICES','').split(',')
    assert assigned and all(re.fullmatch(r'[A-Za-z0-9_:\-]+',d) for d in assigned)
    lease_dir=retry/'leases';lease_dir.mkdir(exist_ok=True)
    leases=[]
    deadline=time.monotonic()+3600
    while not leases and time.monotonic()<deadline:
        for d in assigned:
            f=(lease_dir/(d+'.lock')).open('a')
            try:
                fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:
                f.close();continue
            free=int(subprocess.check_output(['nvidia-smi','-i',d,'--query-gpu=memory.free',
                       '--format=csv,noheader,nounits'],text=True).strip())
            if free>=settings['minimum_free_mib']:
                leases.append((d,free,f))
                if len(leases)>=settings['max_workers']:break
            else:
                fcntl.flock(f,fcntl.LOCK_UN);f.close()
        if not leases:
            save(retry/'RESOURCE_WAIT.json',dict(status='waiting_for_free_assigned_gpu',assigned=assigned))
            time.sleep(15)
    assert leases,'No assigned GPU has enough memory; no model loaded'
    save(retry/'RESOURCE.json',dict(status='started',assigned=assigned,
                                   usable=[dict(device=d,free_mib=n) for d,n,_ in leases],job=os.environ['SLURM_JOB_ID']))
    tasks=queue.Queue()
    for i in settings['retry_indices']:tasks.put(i)
    results=[]
    def worker(lease):
        device,_,lock=lease
        try:
            while True:
                try:i=tasks.get_nowait()
                except queue.Empty:break
                case,seed,shard=original['array'][i]
                out=retry/'full'/case/str(seed)/str(shard)
                assert not out.exists()
                env=os.environ.copy()
                env.update(CUDA_VISIBLE_DEVICES=device,PYTHONHASHSEED='0',CUBLAS_WORKSPACE_CONFIG=':4096:8',
                           PYTORCH_CUDA_ALLOC_CONF='expandable_segments:True',PYTHONDONTWRITEBYTECODE='1',
                           HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
                for key,folder in [('TMPDIR','tmp'),('TRITON_CACHE_DIR','triton')]:
                    dest=retry/folder/device/str(i);dest.mkdir(parents=True,exist_ok=True);env[key]=str(dest)
                cmd=[original['python'],str(source/'runner.py'),'--phase','full',
                     '--runtime',original['runtime'],'--inputs',str(root/'INPUTS.json'),
                     '--output',str(out),'--case',case,'--seed',str(seed),'--shard',str(shard),
                     '--gate',str(root/'outputs/gate/RESULT.json')]
                log=retry/'logs'/('%d.log'%i);log.parent.mkdir(exist_ok=True)
                with log.open('xb') as f:
                    rc=subprocess.call(cmd,env=env,stdout=f,stderr=subprocess.STDOUT)
                row=dict(index=i,case=case,seed=seed,shard=shard,device=device,returncode=rc,output=str(out))
                if rc==0:
                    r=sealed(out/'RESULT.json');assert r['status']=='completed'
                    row['result_sha256']=hashlib.sha256((out/'RESULT.json').read_bytes()).hexdigest()
                results.append(row)
                save(retry/('RECEIPT_%d.json'%i),row)
                print(json.dumps(row),flush=True)
        finally:
            fcntl.flock(lock,fcntl.LOCK_UN);lock.close()
    with ThreadPoolExecutor(max_workers=len(leases)) as pool:
        list(pool.map(worker,leases))
    assert len(results)==len(settings['retry_indices'])
    ok=all(r['returncode']==0 for r in results)
    save(retry/'RESULT.json',dict(status='completed' if ok else 'failed',results=sorted(results,key=lambda r:r['index'])))
    assert ok


if __name__=='__main__':
    main()
