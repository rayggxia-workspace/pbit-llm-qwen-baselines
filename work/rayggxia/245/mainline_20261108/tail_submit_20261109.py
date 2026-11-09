"""Recover only never-started32/33/34; keep immutable execution and healthy jobs."""
from pathlib import Path
import hashlib,json,ops

HERE=Path(__file__).resolve().parent/'tail_recovery_20261109';HERE.mkdir(exist_ok=True)
assert not (HERE/'SUBMISSION.json').exists(),'Use status;never submit twice'
D=json.loads((HERE.parent/'repair3/SUBMISSION.json').read_bytes())
script=r'''from pathlib import Path
import hashlib,json,subprocess,sys
r=Path(ROOT);m=json.loads((r/'MANIFEST.json').read_bytes());original=Path(m['original_root'])
for n,h in m['execution_files_sha256'].items():assert hashlib.sha256((original/n).read_bytes()).hexdigest()==h,n
i=m['indices'][int(sys.argv[1])];assert i in (32,33,34)
print(json.dumps(dict(event='tail_case_start',index=i)),flush=True)
subprocess.run([sys.executable,'-B',str(original/'driver.py'),'full',str(i)],check=True)
print(json.dumps(dict(event='tail_case_completed',index=i)),flush=True)
'''
x=ops.remote('D='+repr(D)+'\nSCRIPT='+repr(script)+'\n'+r'''
from pathlib import Path
import datetime,hashlib,json,os,subprocess
old=Path(D['parent_root']);repair=Path(D['root']);dispatch=Path(str(old)+'_dispatch_v3')
assert hashlib.sha256((old/'SNAPSHOT_MANIFEST.json').read_bytes()).hexdigest()==D['parent_manifest_sha256']
assert hashlib.sha256((repair/'SNAPSHOT_MANIFEST.json').read_bytes()).hexdigest()==D['manifest_sha256']
states=subprocess.check_output(['sacct','-n','-X','-P','-j','38631668','-o','JobID,State'],universal_newlines=True)
for worker in (0,1,2):
 assert '38631668_%d|FAILED'%worker in states
 text=(dispatch/'logs'/('full-38631668_%d.log'%worker)).read_text()
 assert ('"index": %d'%(32+worker)) not in text,'Tail already started'
plan=json.loads((old/'PLAN.json').read_bytes())
for i in (32,33,34):
 c=plan[i];folder='%02d_%s_%s_%s_s%s'%(i,c['model'],c['clock'],c['scheme'],c['seed'])
 assert not (old/'results/full'/folder).exists(),folder
assert plan[32]['scheme']=='SC_ising' and plan[32]['seed']==1009
assert plan[33]['scheme']=='BF16_dense' and plan[34]['scheme']=='W8_dense'
info=dict(original_root=str(old),repair_root=str(repair),indices=[32,33,34],cases=[plan[i] for i in (32,33,34)],
 execution_files_sha256={n:hashlib.sha256((old/n).read_bytes()).hexdigest() for n in ('SNAPSHOT_MANIFEST.json','driver.py','PLAN.json')},
 original_failed_workers=[0,1,2],execution_source_changed=False,healthy_jobs_restarted=False)
digest=hashlib.sha256(json.dumps(info,sort_keys=True).encode()).hexdigest()
r=old.parent/('tlm245_tail_20261109_'+digest[:12]);r.mkdir(exist_ok=False);assert r.stat().st_uid==os.getuid();(r/'logs').mkdir()
script=SCRIPT.replace('ROOT',repr(str(r)));(r/'tail.py').write_text(script)
(r/'MANIFEST.json').write_text(json.dumps(info,indent=2)+'\n')
prefix="""#!/bin/bash
#SBATCH --partition=v6_384
#SBATCH --cpus-per-task=3
#SBATCH --mem=12G
#SBATCH --time=24:00:00
set -euo pipefail
export PATH=/public3/soft/gcc/11.2.0/bin:/public3/soft/python/3.9.6/bin:$PATH
export LD_LIBRARY_PATH=/public3/soft/gcc/11.2.0/lib64:/public3/soft/python/3.9.6/lib:${LD_LIBRARY_PATH:-}
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
"""
(r/'tail.sbatch').write_text(prefix+'cd '+str(r)+'\npython3 -B tail.py "$SLURM_ARRAY_TASK_ID"\n')
aggregate=repair/'aggregate_current.py';aggsha=hashlib.sha256(aggregate.read_bytes()).hexdigest()
(r/'aggregate.sbatch').write_text(prefix.replace('24:00:00','00:20:00').replace('--mem=12G','--mem=4G')+
 'python3 -B '+str(aggregate)+' --root '+str(old)+' --repair-root '+str(repair)+' --out '+str(r/'summary')+'\n')
rec=dict(status='SUBMITTING',UTC=datetime.datetime.utcnow().isoformat(),root=str(r),manifest=info,
 manifest_sha256=hashlib.sha256((r/'MANIFEST.json').read_bytes()).hexdigest(),
 launcher_sha256=hashlib.sha256((r/'tail.py').read_bytes()).hexdigest(),aggregate_source_sha256=aggsha)
def persist():(r/'SUBMISSION.json').write_text(json.dumps(rec,indent=2)+'\n')
def submit(args):
 p=subprocess.run(['sbatch','--parsable']+args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
 assert p.returncode==0,p.stderr
 return p.stdout.strip()
persist();rec['tail_job']=submit(['--array=0-2%3','--job-name=cm245_tail3','--output='+str(r/'logs/tail-%A_%a.log'),str(r/'tail.sbatch')]);persist()
deps='afterany:38631668,afterok:38634114:38634115:38634116:38634117:'+rec['tail_job']
rec['aggregate_job']=submit(['--dependency='+deps,'--job-name=cm245_aggregate_complete','--output='+str(r/'logs/aggregate-%j.log'),str(r/'aggregate.sbatch')]);persist()
# Only retire our obsolete pending aggregate; never cancel a healthy case worker.
p=subprocess.run(['scontrol','show','job','-o','38634118'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
if p.returncode==0:
 assert 'JobState=PENDING' in p.stdout and 'JobName=cm245_aggregate_fixed' in p.stdout,p.stdout
 subprocess.run(['scancel','38634118'],check=True);rec['retired_pending_aggregate']='38634118';persist()
rec['status']='THREE_UNSTARTED_TAILS_SUBMITTED_NO_EXECUTION_SOURCE_CHANGE';persist();print(json.dumps(rec))
''')
(HERE/'SUBMISSION.json').write_bytes((json.dumps(x,indent=2)+'\n').encode())
print(json.dumps(x))
