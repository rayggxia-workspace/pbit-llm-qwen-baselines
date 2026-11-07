"""Scoped CPU-only Slurm submission; reuse frozen source and inputs read-only."""
from pathlib import Path
import base64
import datetime
import hashlib
import json
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
PROJECT=Path('C:/Users/86134/Documents/a_P_BIT')
sys.path.insert(0,str(PROJECT/'local_tools/paracloud_client'))
import client
RUNTIME='/public3/home/t6s011227/pbit_chimera_pipeline_20260920/tlm236_joint_20261105/retry_time_audit_ed028cc70e06'
PERSONAL='/public3/home/t6s011227/pbit_chimera_pipeline_20260920/tlm225_norm_stream_20261106'


def save(name,x):(HERE/name).write_bytes((json.dumps(x,indent=2,ensure_ascii=False)+'\n').encode())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def remote(code):
    with client.connect(client.load_password()) as ssh:
        i,o,e=ssh.exec_command('python3 -B -',timeout=60)
        i.write(code);i.flush();i.channel.shutdown_write()
        body=o.read().decode();error=e.read().decode();rc=o.channel.recv_exit_status()
        if rc:raise RuntimeError('remote rc='+str(rc)+'\n'+body[-2000:]+'\n'+error[-2000:])
    return json.loads(body)


def probe():
    r=remote('RUNTIME='+repr(RUNTIME)+'\n'+r'''
from pathlib import Path
import os,pwd,hashlib,json,subprocess
r=Path(RUNTIME)
names=['EXECUTION_MANIFEST.json','base/SOURCE_MANIFEST.json','base/liblpbridge.so',
       'inputs/representative.json','inputs/SAMPLES.json','PRICES.json',
       'architecture_tlm/digital_fair_20261105/LATEST_SC_PRICES.json']
files={n:dict(bytes=(r/n).stat().st_size,sha256=hashlib.sha256((r/n).read_bytes()).hexdigest()) for n in names}
queue=subprocess.check_output(['squeue','-h','-u',pwd.getpwuid(os.getuid()).pw_name,'-o','%i|%j|%T|%C'],universal_newlines=True)
print(json.dumps(dict(user=pwd.getpwuid(os.getuid()).pw_name,runtime=RUNTIME,files=files,queue=queue)))
''')
    assert r['user']=='t6s011227'
    save('REMOTE_PROBE.json',r);print(json.dumps(r))


def submit():
    if (HERE/'SUBMISSION.json').exists():raise RuntimeError('Already submitted; use status')
    folder=ROOT/'architecture_tlm/norm_stream_20261106'
    files={str(p.relative_to(ROOT)).replace('\\','/'):dict(sha256=sha(p),base64=base64.b64encode(p.read_bytes()).decode())
        for p in sorted(folder.glob('*.py'))}
    identity=hashlib.sha256(json.dumps({n:x['sha256'] for n,x in files.items()},sort_keys=True).encode()).hexdigest()
    code='FILES='+repr(files)+'\nIDENTITY='+repr(identity)+'\nPERSONAL='+repr(PERSONAL)+'\nRUNTIME='+repr(RUNTIME)+'\n'+r"""
from pathlib import Path
import base64,hashlib,json,os,subprocess,datetime
runtime=Path(RUNTIME)
assert runtime.stat().st_uid==os.getuid()
parent=Path(PERSONAL);parent.mkdir(exist_ok=True)
r=parent/IDENTITY[:12];r.mkdir();assert r.stat().st_uid==os.getuid()
for n,x in FILES.items():
 q=r/n;q.relative_to(r);q.parent.mkdir(parents=True,exist_ok=True)
 data=base64.b64decode(x['base64']);assert hashlib.sha256(data).hexdigest()==x['sha256'];q.write_bytes(data)
manifest=dict(files_sha256={n:x['sha256'] for n,x in FILES.items()},identity=IDENTITY,
    runtime=RUNTIME,runtime_manifest_sha256=hashlib.sha256((runtime/'EXECUTION_MANIFEST.json').read_bytes()).hexdigest())
(r/'MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
(r/'logs').mkdir()
env='''#!/bin/bash
#SBATCH --partition=v6_384
#SBATCH --cpus-per-task=1
set -euo pipefail
export PATH=/public3/soft/gcc/11.2.0/bin:/public3/soft/python/3.9.6/bin:$PATH
export LD_LIBRARY_PATH=/public3/soft/gcc/11.2.0/lib64:/public3/soft/python/3.9.6/lib:${LD_LIBRARY_PATH:-}
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
'''
entry=r/'architecture_tlm/norm_stream_20261106/launch.py'
cmd='python3 -B '+str(entry)+' --runtime '+RUNTIME
(r/'tests.sbatch').write_text(env+cmd+' --tests\n')
select='''profiles=(resident_2p5 stream_2p5 stream_2m)
seeds=(17 503 1009)
'''
(r/'prefix.sbatch').write_text(env+select+cmd+' --profile "${profiles[$SLURM_ARRAY_TASK_ID]}" --seed 17 --prefix-layers 2 --out '+str(r/'prefix')+'/${profiles[$SLURM_ARRAY_TASK_ID]}\n')
(r/'full.sbatch').write_text(env+select+'i=$SLURM_ARRAY_TASK_ID\np=$((i/3))\ns=$((i%3))\n'+cmd+' --profile "${profiles[$p]}" --seed "${seeds[$s]}" --out '+str(r/'results')+'/${profiles[$p]}_s${seeds[$s]}\n')
def sbatch(script,name,mem,wall,extra=()):
 return subprocess.check_output(['sbatch','--parsable','--mem='+mem,'--time='+wall,'--job-name='+name,
    '--output='+str(r/'logs'/('%x-%A_%a.log')),*extra,str(r/script)],universal_newlines=True).strip()
gate=sbatch('tests.sbatch','norm225_tests','4G','00:10:00')
prefix=sbatch('prefix.sbatch','norm225_prefix','8G','01:00:00',('--array=0-2%3','--dependency=afterok:'+gate))
full=sbatch('full.sbatch','norm225_full','12G','08:00:00',('--array=0-8%6','--dependency=afterok:'+prefix))
receipt=dict(root=str(r),runtime=RUNTIME,identity=IDENTITY,gate=gate,prefix=prefix,full=full,
    full_cases=9,CPU_per_task=1,maximum_concurrency=6,GPU=0,source_files_sha256=manifest['files_sha256'],
    runtime_manifest_sha256=manifest['runtime_manifest_sha256'],submitted_UTC=datetime.datetime.utcnow().isoformat(),
    status='submitted_not_completed')
(r/'SUBMISSION.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt))
"""
    r=remote(code);save('SUBMISSION.json',r);print(json.dumps(r))


def status():
    d=json.loads((HERE/'SUBMISSION.json').read_bytes())
    r=remote('D='+repr(d)+'\n'+r'''
from pathlib import Path
import json,subprocess
r=Path(D['root']);jobs=','.join(D[x] for x in ('gate','prefix','full'))
out={'queue':subprocess.check_output(['squeue','-h','-j',jobs,'-o','%i|%j|%T|%M|%R'],universal_newlines=True),
     'accounting':subprocess.check_output(['sacct','-n','-P','-j',jobs,'--format=JobIDRaw,State,ExitCode,Elapsed,MaxRSS'],universal_newlines=True)}
out['logs']={p.name:p.read_text()[-2200:] for p in sorted((r/'logs').glob('*.log'))}
out['sealed']=[str(p.parent.relative_to(r)) for pattern in ('prefix/*/SEAL.json','results/*/SEAL.json') for p in r.glob(pattern)]
print(json.dumps(out))
''')
    save('STATUS.json',r);print(json.dumps(r))


def collect():
    d=json.loads((HERE/'SUBMISSION.json').read_bytes())
    r=remote('D='+repr(d)+'\n'+r'''
from pathlib import Path
import hashlib,json,math
root=Path(D['root']);out=[]
for kind in ('prefix','results'):
 for p in sorted((root/kind).glob('*/SEAL.json')):
  seal=json.loads(p.read_text());directory=p.parent
  for name,key in [('RESULT.json','result_sha256'),('BUDGET.json','budget_sha256')]:
   assert hashlib.sha256((directory/name).read_bytes()).hexdigest()==seal[key]
  for name,h in seal['source_files_sha256'].items():
   assert hashlib.sha256((root/'architecture_tlm/norm_stream_20261106'/name).read_bytes()).hexdigest()==h
  result=json.loads((directory/'RESULT.json').read_text());budget=json.loads((directory/'BUDGET.json').read_text())
  assert result['status']=='completed'
  assert abs(math.fsum(budget['onchip_components_mJ'].values())-budget['covered_onchip_mJ'])<1e-8
  assert abs(math.fsum(budget['covered_areas55_mm2'].values())-budget['covered_area55_mm2'])<1e-8
  assert result['memory']['final_pending']==result['memory']['final_response_occupied']==0
  out.append(dict(case=directory.name,kind=kind,scope=result['scope'],profile=budget['norm_memory_policy'],seed=result['seed'],
    time_ms=result['simulated_ms'],area55_mm2=budget['covered_area55_mm2'],onchip_mJ=budget['covered_onchip_mJ'],
    total_mJ=budget['covered_system_mJ_at4pJ'],external_mJ=budget['external_mJ_by_pJ_per_bit']['4.0'],
    norm=result['norm_storage_contract'],SRAM=result['memory']['SRAM'],
    dram_counts=result['memory']['counts'],actions=result['actions'],wall_seconds=result['wall_seconds'],
    result_sha256=seal['result_sha256'],budget_sha256=seal['budget_sha256']))
full=[x for x in out if x['kind']=='results']
assert len({x['case'] for x in full})==len(full)
print(json.dumps(dict(verified_sealed_cases=out,full_completed=len(full),expected_full=9,
    full_complete=len(full)==9,only_sealed_results_counted=True)))
''')
    save('COLLECTION.json',r)
    print(json.dumps({k:v for k,v in r.items() if k!='verified_sealed_cases'}))
    for x in r['verified_sealed_cases']:
        print(json.dumps({k:x[k] for k in ('case','scope','time_ms','total_mJ','area55_mm2','wall_seconds')}))


if __name__=='__main__':globals()[sys.argv[1]]()
