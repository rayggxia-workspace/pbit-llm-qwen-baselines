"""Quota-compatible launcher. Original execution snapshot/healthy gates unchanged."""
import json,ops
if (ops.HERE/'DISPATCH.json').exists():raise RuntimeError('Already dispatched; inspect status')
d=json.loads((ops.HERE/'SUBMISSION.json').read_bytes())
receipt=ops.remote('D='+repr(d)+'\n'+r"""
from pathlib import Path
import hashlib,json,os,subprocess,datetime
original=Path(D['root']);r=Path(D['root']+'_dispatch_v3');assert not r.exists();r.mkdir();assert r.stat().st_uid==os.getuid()
assert hashlib.sha256((original/'SNAPSHOT_MANIFEST.json').read_bytes()).hexdigest()==D['manifest_sha256']
(r/'logs').mkdir()
worker='''from pathlib import Path
import hashlib,json,subprocess,sys,time
r=Path(ORIGINAL)
assert hashlib.sha256((r/'SNAPSHOT_MANIFEST.json').read_bytes()).hexdigest()==EXPECTED_SHA
worker=int(sys.argv[1]);assert0<=worker<8
for index in range(worker,36,8):
 print(json.dumps(dict(event="case_start",worker=worker,index=index)),flush=True)
 subprocess.run([sys.executable,"-B",str(r/"driver.py"),"full",str(index)],check=True)
 print(json.dumps(dict(event="case_completed",worker=worker,index=index)),flush=True)
'''.replace('ORIGINAL',repr(str(original))).replace('EXPECTED_SHA',repr(D['manifest_sha256'])).replace('assert0','assert 0')
compile(worker,'worker.py','exec');(r/'worker.py').write_text(worker)
prefix='''#!/bin/bash
#SBATCH --partition=v6_384
#SBATCH --cpus-per-task=1
#SBATCH --mem=12G
#SBATCH --time=48:00:00
set -euo pipefail
export PATH=/public3/soft/gcc/11.2.0/bin:/public3/soft/python/3.9.6/bin:$PATH
export LD_LIBRARY_PATH=/public3/soft/gcc/11.2.0/lib64:/public3/soft/python/3.9.6/lib:${LD_LIBRARY_PATH:-}
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
cd DIRECTORY
'''.replace('DIRECTORY',str(r))
(r/'worker.sbatch').write_text(prefix+'python3 -B worker.py "$SLURM_ARRAY_TASK_ID"\n')
coordinator=r'''from pathlib import Path
import json,subprocess
r=Path(DIRECTORY)
args=["sbatch","--parsable","--array=0-7%8","--job-name=cm245_full8","--output="+str(r/"logs/full-%A_%a.log"),str(r/"worker.sbatch")]
p=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
(r/"FULL_SUBMIT_RESPONSE.json").write_text(json.dumps(dict(returncode=p.returncode,stdout=p.stdout,stderr=p.stderr),indent=2)+"\n")
if p.returncode:raise RuntimeError("Keep completedgates; inspect quota andreceipt before any retry:"+p.stderr)
(r/"FULL_SUBMISSION.json").write_text(json.dumps(dict(full_worker_job=p.stdout.strip(),workers=8,cases=36,logicalthreads_per_case=1),indent=2)+"\n")
print(p.stdout.strip(),flush=True)
'''.replace('DIRECTORY',repr(str(r)))
compile(coordinator,'coordinator.py','exec');(r/'coordinator.py').write_text(coordinator)
(r/'coordinator.sbatch').write_text(prefix.replace('#SBATCH --mem=12G','#SBATCH --mem=4G').replace('48:00:00','00:10:00')+'python3 -B coordinator.py\n')
p=subprocess.run(['sbatch','--parsable','--dependency=afterok:'+D['pilot_job'],'--job-name=cm245_dispatch',
 '--output='+str(r/'logs/coordinator-%j.log'),str(r/'coordinator.sbatch')],stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
if p.returncode:raise RuntimeError('inspect before retry: '+p.stderr)
receipt=dict(root=str(r),original_snapshot=str(original),snapshot_sha256=D['snapshot_sha256'],
 manifest_sha256=D['manifest_sha256'],pilot_job=D['pilot_job'],coordinator_job=p.stdout.strip(),
 status='COORDINATOR_SUBMITTED_FULL_WORKERS_AFTER_SUCCESSFUL_GATES',requested_CPU=1,GiB=12,concurrency=8,
 original_failed_36array_receipt_retained=True,healthy_gate_jobs_not_resubmitted=True,
 execution_source_changed=False,workload_cases=36,primary_configs=24,
 files_sha256={n:hashlib.sha256((r/n).read_bytes()).hexdigest() for n in ('worker.py','coordinator.py','worker.sbatch','coordinator.sbatch')})
(r/'DISPATCH.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
""")
ops.save('DISPATCH.json',receipt);print(json.dumps(receipt))
