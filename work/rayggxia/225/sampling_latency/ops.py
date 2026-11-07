"""Personal EDA CPU jobs; no mutation of existing submitted snapshots."""
from pathlib import Path
import base64,hashlib,json,sys
from contextlib import nullcontext
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
PROJECT=Path('C:/Users/86134/Documents/a_P_BIT')
sys.path.insert(0,str(PROJECT/'local_tools/paracloud_client'))
import client
RUNTIME='/public3/home/t6s011227/pbit_chimera_pipeline_20260920/tlm236_joint_20261105/retry_time_audit_ed028cc70e06'
PERSONAL='/public3/home/t6s011227/pbit_chimera_pipeline_20260920/tlm225_sampling_latency_20261106'
DEPENDENCIES=PROJECT/'project_archives/sampling_latency225_20261106/dependencies'
ACTIVE=None
def save(n,x):(HERE/n).write_bytes((json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode())
def remote(code):
    with (nullcontext(ACTIVE) if ACTIVE is not None else client.connect(client.load_password())) as ssh:
        i,o,e=ssh.exec_command('python3 -B -',timeout=20)
        i.write(code);i.flush();i.channel.shutdown_write()
        body=o.read().decode();error=e.read().decode();rc=o.channel.recv_exit_status()
        if rc:raise RuntimeError('remote rc='+str(rc)+'\n'+body[-2000:]+'\n'+error[-2000:])
    return json.loads(body)
def _submit():
    if (HERE/'SUBMISSION.json').exists():raise RuntimeError('already submitted; inspect status')
    files={}
    for p in [*(ROOT/'architecture_tlm/sampling_latency_20261106').glob('*.py'),ROOT/'architecture_tlm/sampling_latency_20261106/REFERENCE_PROFILE.json']:
        files[p.relative_to(ROOT).as_posix()]=p.read_bytes()
    for p in DEPENDENCIES.rglob('*'):
        if p.is_file():files['dependencies/'+p.relative_to(DEPENDENCIES).as_posix()]=p.read_bytes()
    payload={n:dict(sha256=hashlib.sha256(b).hexdigest(),base64=base64.b64encode(b).decode()) for n,b in files.items()}
    identity=hashlib.sha256(json.dumps({n:v['sha256'] for n,v in payload.items()},sort_keys=True).encode()).hexdigest()
    destination=PERSONAL+'/'+identity[:12]
    prepared=dict(root=destination,identity=identity,files_sha256={n:v['sha256'] for n,v in payload.items()})
    save('PREPARED.json',prepared)
    # Upload bytes using SFTP, keeping remote Python stdin well below64KiB.
    remote('ROOT='+repr(destination)+'\n'+r'''
from pathlib import Path
import json,os,pwd
assert pwd.getpwuid(os.getuid()).pw_name=='t6s011227'
r=Path(ROOT);r.parent.mkdir(exist_ok=True);r.mkdir()
assert r.stat().st_uid==os.getuid()
print(json.dumps(dict(created=str(r))))
''')
    with (nullcontext(ACTIVE) if ACTIVE is not None else client.connect(client.load_password())) as ssh:
        with ssh.open_sftp() as ftp:
            made={destination}
            for name,data in files.items():
                parent=destination
                for part in name.split('/')[:-1]:
                    parent+='/'+part
                    if parent not in made:ftp.mkdir(parent);made.add(parent)
                with ftp.open(destination+'/'+name,'wb') as f:f.write(data)
    payload={n:dict(sha256=v['sha256']) for n,v in payload.items()}
    code='FILES='+repr(payload)+'\nIDENTITY='+repr(identity)+'\nRUNTIME='+repr(RUNTIME)+'\nPERSONAL='+repr(PERSONAL)+'\n'+r"""
from pathlib import Path
import base64,datetime,hashlib,json,os,pwd,subprocess
assert pwd.getpwuid(os.getuid()).pw_name=='t6s011227'
runtime=Path(RUNTIME);assert runtime.stat().st_uid==os.getuid()
assert hashlib.sha256((runtime/'EXECUTION_MANIFEST.json').read_bytes()).hexdigest()=='7c5cb9b603ca2bd139ac6fa7b75d789e00c316acde994ff3db9bdcbb33c4bb40'
parent=Path(PERSONAL);parent.mkdir(exist_ok=True)
root=parent/IDENTITY[:12];assert root.stat().st_uid==os.getuid()
assert not (root/'SUBMISSION.json').exists() and not (root/'logs').exists()
for name,x in FILES.items():
 p=root/name;p.relative_to(root)
 assert hashlib.sha256(p.read_bytes()).hexdigest()==x['sha256']
(root/'MANIFEST.json').write_text(json.dumps(dict(identity=IDENTITY,files_sha256={n:x['sha256'] for n,x in FILES.items()}),indent=2)+'\n')
(root/'logs').mkdir()
env='''#!/bin/bash
#SBATCH --partition=v6_384
#SBATCH --cpus-per-task=1
set -euo pipefail
export PATH=/public3/soft/gcc/11.2.0/bin:/public3/soft/python/3.9.6/bin:$PATH
export LD_LIBRARY_PATH=/public3/soft/gcc/11.2.0/lib64:/public3/soft/python/3.9.6/lib:${LD_LIBRARY_PATH:-}
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
'''
entry=root/'architecture_tlm/sampling_latency_20261106/launch.py'
cmd='python3 -B '+str(entry)+' --runtime '+RUNTIME+' --dependencies '+str(root/'dependencies')
(root/'tests.sbatch').write_text(env+cmd+' --tests\n')
select='cases=(T64_64 T8_32)\ngu=(64 8)\nwd=(64 32)\n'
(root/'prefix.sbatch').write_text(env+select+cmd+' --gu "${gu[$SLURM_ARRAY_TASK_ID]}" --wd "${wd[$SLURM_ARRAY_TASK_ID]}" --seed 17 --prefix-layers 2 --out '+str(root/'prefix')+'/${cases[$SLURM_ARRAY_TASK_ID]}\n')
(root/'full.sbatch').write_text(env+select+cmd+' --gu "${gu[$SLURM_ARRAY_TASK_ID]}" --wd "${wd[$SLURM_ARRAY_TASK_ID]}" --seed 17 --prefix-layers 0 --out '+str(root/'results')+'/${cases[$SLURM_ARRAY_TASK_ID]}\n')
def sb(script,name,mem,wall,extra=()):
 return subprocess.check_output(['sbatch','--parsable','--mem='+mem,'--time='+wall,'--job-name='+name,'--output='+str(root/'logs'/'%x-%A_%a.log'),*extra,str(root/script)],universal_newlines=True).strip()
gate=sb('tests.sbatch','sample225_tests','4G','00:10:00')
prefix=sb('prefix.sbatch','sample225_prefix','8G','01:30:00',('--array=0-1%2','--dependency=afterok:'+gate))
full=sb('full.sbatch','sample225_full','12G','08:00:00',('--array=0-1%2','--dependency=afterok:'+prefix))
receipt=dict(root=str(root),identity=IDENTITY,runtime=RUNTIME,gate=gate,prefix=prefix,full=full,
 CPU_per_task=1,GPU=0,maximum_prefix_concurrency=2,maximum_full_concurrency=2,
 submitted_UTC=datetime.datetime.utcnow().isoformat(),status='submitted_not_completed',
 source_files_sha256={n:x['sha256'] for n,x in FILES.items()})
(root/'SUBMISSION.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt))
"""
    r=remote(code);save('SUBMISSION.json',r)
    print(json.dumps({k:v for k,v in r.items() if k!='source_files_sha256'}))
def submit():
    global ACTIVE
    with client.connect(client.load_password()) as ssh:
        ACTIVE=ssh
        try:_submit()
        finally:ACTIVE=None
def status():
    d=json.loads((HERE/'SUBMISSION.json').read_bytes())
    r=remote('D='+repr(d)+'\n'+r'''
from pathlib import Path
import json,subprocess
r=Path(D['root']);jobs=','.join(D[x] for x in ('gate','prefix','full'))
out=dict(queue=subprocess.check_output(['squeue','-h','-j',jobs,'-o','%i|%T|%M|%R'],universal_newlines=True),
 accounting=subprocess.check_output(['sacct','-n','-P','-j',jobs,'--format=JobIDRaw,State,ExitCode,Elapsed,MaxRSS'],universal_newlines=True))
out['logs']={p.name:p.read_text()[-2200:] for p in sorted((r/'logs').glob('*.log'))}
out['sealed']=[str(p.parent.relative_to(r)) for pattern in ('prefix/*/SEAL.json','results/*/SEAL.json') for p in r.glob(pattern)]
print(json.dumps(out))
''');save('STATUS.json',r);print(json.dumps(r))
def probe():
    d=json.loads((HERE/'PREPARED.json').read_bytes())
    r=remote('D='+repr(d)+'\n'+r'''
from pathlib import Path
import json,subprocess
r=Path(D['root'])
queue=subprocess.check_output(['squeue','-h','-u','t6s011227','-o','%i|%j|%T'],universal_newlines=True)
receipt=json.loads((r/'SUBMISSION.json').read_text()) if (r/'SUBMISSION.json').exists() else None
if receipt:assert receipt['identity']==D['identity']
print(json.dumps(dict(root=str(r),exists=r.exists(),receipt=receipt,
 queue='\n'.join(line for line in queue.splitlines() if 'sample225_' in line))))
''')
    save('PROBE.json',r)
    if r['receipt'] is not None:save('SUBMISSION.json',r['receipt'])
    print(json.dumps(r))
def collect():
    d=json.loads((HERE/'SUBMISSION.json').read_bytes())
    r=remote('D='+repr(d)+'\n'+r'''
from pathlib import Path
from collections import defaultdict
import hashlib,json
root=Path(D['root']);rows=[]
for name,digest in D['source_files_sha256'].items():assert hashlib.sha256((root/name).read_bytes()).hexdigest()==digest,name
for kind in ('prefix','results'):
 for p in sorted((root/kind).glob('*/SEAL.json')):
  s=json.loads(p.read_text());r=p.parent/'RESULT.json';assert hashlib.sha256(r.read_bytes()).hexdigest()==s['result_sha256']
  x=json.loads(r.read_text());assert x['status']=='completed'
  phases=defaultdict(float)
  for phase in x['phases']:phases[phase['stage']]+=phase['duration_ns']*1e-6
  rows.append(dict(kind=kind,case=p.parent.name,remote_result=str(r),result_sha256=s['result_sha256'],seal=s,
    timing=x['decode_timing_ms'],scope=x['scope'],phases_ms=dict(phases),actions=x['actions'],
    memory_counts=x['memory']['counts'],SRAM_counts=x['memory']['SRAM']['counts'],
    samples=x['sampling_latency_contract'],memory=x['sram1216_contract']['memory'],wall_seconds=x['wall_seconds']))
print(json.dumps(dict(source_verified=True,sealed=rows)))
''')
    save('COLLECTION.json',r)
    for x in r['sealed']:print(json.dumps({k:x[k] for k in ('kind','case','scope','timing','wall_seconds')}))
def archive():
    collection=json.loads((HERE/'COLLECTION.json').read_bytes())
    dest=PROJECT/'project_archives/sampling_latency225_20261106/native'
    records=[]
    with client.connect(client.load_password()) as ssh:
        with ssh.open_sftp() as ftp:
            for x in collection['sealed']:
                folder=dest/x['kind']/x['case'];folder.mkdir(parents=True,exist_ok=True)
                for name in ('RESULT.json','SEAL.json'):
                    target=folder/name;remote_path=x['remote_result'].rsplit('/',1)[0]+'/'+name
                    if not target.exists():ftp.get(remote_path,str(target))
                    raw=target.read_bytes();digest=hashlib.sha256(raw).hexdigest()
                    if name=='RESULT.json':assert digest==x['result_sha256']
                    records.append(dict(path=str(target),sha256=digest,bytes=len(raw),remote=remote_path))
    save('ARCHIVE.json',dict(files=records));print(json.dumps(dict(archived_files=len(records))))
if __name__=='__main__':globals()[sys.argv[1]]()
