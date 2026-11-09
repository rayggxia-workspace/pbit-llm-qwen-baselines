"""Freeze decoder-only repair;resume lostworkers and retain all healthy runs."""
from pathlib import Path
import hashlib,io,json,sys,zipfile,ops
HERE=Path(__file__).resolve().parent;R2=HERE/'revision2';HERE3=HERE/'repair3';HERE3.mkdir(exist_ok=True)
if (HERE3/'SUBMISSION.json').exists():raise RuntimeError('Already submitted;inspect receipts')
sha=lambda b:hashlib.sha256(b).hexdigest()
d=json.loads((R2/'SUBMISSION.json').read_bytes());old=json.loads((R2/'snapshot/SNAPSHOT_MANIFEST.json').read_bytes())
sources={n:(R2/'snapshot'/n).read_bytes() for n in old['sources']}
replacement=(ops.CHECKOUT/'architecture_tlm/model_scaling_20261106/current_mainline.py').read_bytes()
sources['glue/current_mainline.py']=replacement
pilots=[dict(model=m,clock=100,scheme='SC_ising',seed=17,backend='native',anchor=False) for m in ('llama32_3b','deepseek_7b')]
sources['PILOTS.json']=(json.dumps(pilots,indent=2)+'\n').encode()
manifest=json.loads(json.dumps(old))
for n in ('glue/current_mainline.py','PILOTS.json'):manifest['sources'][n]['sha256']=sha(sources[n])
manifest.update(repair_parent_manifest_sha256=d['manifest_sha256'],repair_scope='SC100_large_model_vector_decoder_binding_only',
 repaired_case_indices=[12,13,14,24,25,26],status='immutable_decoder_only_repair',front_end_changed=False,SRAM_capacity_changed=False)
mb=(json.dumps(manifest,indent=2)+'\n').encode();sources['SNAPSHOT_MANIFEST.json']=mb
stream=io.BytesIO()
with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as z:
 for n,b in sorted(sources.items()):z.writestr(n,b)
raw=stream.getvalue();digest=sha(raw);root=ops.BASE+'/tlm245_decoder_repair_'+digest[:12];archive=root+'.zip'
(HERE3/'snapshot.zip').write_bytes(raw);(HERE3/'SNAPSHOT_MANIFEST.json').write_bytes(mb)
with ops.client.connect(ops.client.load_password()) as s:
 with s.open_sftp() as f:
  with f.open(archive,'wx') as q:q.write(raw)
  with f.open(archive,'rb') as q:assert sha(q.read())==digest
aggregate=(ops.CHECKOUT/'architecture_tlm/model_scaling_20261106/aggregate_current.py').read_text()
args=dict(root=root,archive=archive,sha256=digest,manifest_sha256=sha(mb),original=d['root'],original_manifest=d['manifest_sha256'],runtime=ops.RUNTIME,deps=ops.DEPS)
result=ops.remote('D='+repr(args)+'\nAGGREGATE='+repr(aggregate)+'\n'+r"""
from pathlib import Path
import datetime,hashlib,json,os,subprocess,zipfile
r=Path(D['root']);assert not r.exists();r.mkdir();assert r.stat().st_uid==os.getuid()
assert hashlib.sha256(Path(D['archive']).read_bytes()).hexdigest()==D['sha256']
with zipfile.ZipFile(D['archive']) as z:
 for n in z.namelist():assert not Path(n).is_absolute() and '..' not in Path(n).parts
 z.extractall(r)
assert hashlib.sha256((r/'SNAPSHOT_MANIFEST.json').read_bytes()).hexdigest()==D['manifest_sha256']
assert hashlib.sha256((Path(D['original'])/'SNAPSHOT_MANIFEST.json').read_bytes()).hexdigest()==D['original_manifest']
(r/'logs').mkdir();(r/'aggregate_current.py').write_bytes(AGGREGATE.encode())
prefix='''#!/bin/bash
#SBATCH --partition=v6_384
#SBATCH --cpus-per-task=1
#SBATCH --mem=12G
#SBATCH --time=48:00:00
set -euo pipefail
export PATH=/public3/soft/gcc/11.2.0/bin:/public3/soft/python/3.9.6/bin:$PATH
export LD_LIBRARY_PATH=/public3/soft/gcc/11.2.0/lib64:/public3/soft/python/3.9.6/lib:${LD_LIBRARY_PATH:-}
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
cd ROOT
'''.replace('ROOT',str(r))
(r/'gate.sbatch').write_text(prefix.replace('48:00:00','04:00:00')+'python3 -B driver.py pilot "$SLURM_ARRAY_TASK_ID"\n')
worker='''from pathlib import Path
import json,subprocess,sys
repair=Path(REPAIR);original=Path(ORIGINAL)
mode=sys.argv[1];i=int(sys.argv[2])
indices=([12+i,20+i,28+i] if mode=='lost' else [24+i])
for index in indices:
 root=repair if index in (12,13,14,24,25,26) else original
 print(json.dumps(dict(event='recovery_case_start',mode=mode,index=index,root=str(root))),flush=True)
 subprocess.run([sys.executable,'-B',str(root/'driver.py'),'full',str(index)],check=True)
 print(json.dumps(dict(event='recovery_case_completed',index=index)),flush=True)
'''.replace('REPAIR',repr(str(r))).replace('ORIGINAL',repr(D['original']))
compile(worker,'worker.py','exec');(r/'recovery_worker.py').write_text(worker)
(r/'lost.sbatch').write_text(prefix+'python3 -B recovery_worker.py lost "$SLURM_ARRAY_TASK_ID"\n')
(r/'deep.sbatch').write_text(prefix+'python3 -B recovery_worker.py deep "$1"\n')
(r/'aggregate.sbatch').write_text(prefix.replace('--mem=12G','--mem=4G').replace('48:00:00','00:20:00')+
 'python3 -B aggregate_current.py --root '+D['original']+' --repair-root '+str(r)+' --out '+str(r/'summary')+'\n')
coordinator='''from pathlib import Path
import json,subprocess
r=Path(ROOT)
receipt=dict(status='SUBMITTING_RECOVERY',lost_workers=None,deep_jobs=[],aggregate_job=None)
def persist():(r/'RECOVERY_JOBS.json').write_text(json.dumps(receipt,indent=2)+'\\n')
def submit(args):
 p=subprocess.run(['sbatch','--parsable']+args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
 if p.returncode:raise RuntimeError('Inspect receipt before retry:'+p.stderr)
 return p.stdout.strip()
persist()
receipt['lost_workers']=submit(['--array=0-2%3','--job-name=cm245_recover_lost','--output='+str(r/'logs/lost-%A_%a.log'),str(r/'lost.sbatch')]);persist()
for i in range(3):
 j=submit(['--dependency=afterany:38631668_'+str(i),'--job-name=cm245_recover_deep','--output='+str(r/'logs/deep-%j.log'),str(r/'deep.sbatch'),str(i)])
 receipt['deep_jobs'].append(dict(job=j,original_worker='38631668_'+str(i),index=24+i));persist()
# Replace only the queued aggregate whose prerequisite array alreadyfailed.
p=subprocess.run(['scontrol','show','job','-o','38631676'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
if p.returncode==0 and 'JobState=PENDING' in p.stdout and 'JobName=cm245_aggregate' in p.stdout:
 q=subprocess.run(['scancel','38631676']);assert q.returncode==0
 receipt['retired_pending_aggregate']='38631676';persist()
deps='afterany:38631668,afterok:'+receipt['lost_workers']+':'+':'.join(x['job'] for x in receipt['deep_jobs'])
receipt['aggregate_job']=submit(['--dependency='+deps,'--job-name=cm245_aggregate_fixed','--output='+str(r/'logs/aggregate-%j.log'),str(r/'aggregate.sbatch')])
receipt['status']='RECOVERY_SUBMITTED_HEALTHY_ORIGINAL_WORKERS_RETAINED';persist();print(json.dumps(receipt))
'''.replace('ROOT',repr(str(r)))
compile(coordinator,'coordinator.py','exec');(r/'coordinator.py').write_text(coordinator)
(r/'coordinator.sbatch').write_text(prefix.replace('--mem=12G','--mem=4G').replace('48:00:00','00:10:00')+'python3 -B coordinator.py\n')
receipt=dict(status='SUBMITTING',root=str(r),snapshot_sha256=D['sha256'],manifest_sha256=D['manifest_sha256'],
 parent_root=D['original'],parent_manifest_sha256=D['original_manifest'],submitted_UTC=datetime.datetime.utcnow().isoformat(),
 repaired_source_cases=[12,13,14,24,25,26],continued_original_source_cases=[20,21,22,28,29,30],healthy_jobs_not_cancelled=True)
def persist():(r/'SUBMISSION.json').write_text(json.dumps(receipt,indent=2)+'\n')
persist()
def submit(args):
 p=subprocess.run(['sbatch','--parsable']+args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
 if p.returncode:raise RuntimeError('Inspect '+str(r/'SUBMISSION.json')+' before retry:'+p.stderr)
 return p.stdout.strip()
receipt['gate_job']=submit(['--array=0-1%2','--job-name=cm245_decoder_gate','--output='+str(r/'logs/gate-%A_%a.log'),str(r/'gate.sbatch')]);persist()
receipt['coordinator_job']=submit(['--dependency=afterok:'+receipt['gate_job'],'--job-name=cm245_decoder_dispatch',
 '--output='+str(r/'logs/coordinator-%j.log'),str(r/'coordinator.sbatch')]);receipt['status']='SUBMITTED_GATED_DECODER_REPAIR';persist()
print(json.dumps(receipt))
""")
(HERE3/'SUBMISSION.json').write_bytes((json.dumps(result,indent=2)+'\n').encode());print(json.dumps(result))
