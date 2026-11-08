"""Separate immutable aggregation DAG;never changes submitted execution files."""
from pathlib import Path
import hashlib,json,ops
ops.HERE=Path(__file__).resolve().parent/'revision2'
out=ops.HERE/'FINALIZER_SUBMISSION.json'
if out.exists():raise RuntimeError('Already submitted;inspect receipt')
d=json.loads((ops.HERE/'SUBMISSION.json').read_bytes());dispatch=json.loads((ops.HERE/'DISPATCH.json').read_bytes())
source=(ops.CHECKOUT/'architecture_tlm/model_scaling_20261106/aggregate_current.py').read_text()
receipt=ops.remote('D='+repr(d)+'\nDISPATCH='+repr(dispatch)+'\nSOURCE='+repr(source)+'\n'+r"""
from pathlib import Path
import datetime,hashlib,json,os,subprocess
sha=hashlib.sha256(SOURCE.encode()).hexdigest()
r=Path(D['root']+'_aggregate_'+sha[:10]);assert not r.exists();r.mkdir();assert r.stat().st_uid==os.getuid()
compile(SOURCE,'aggregate_current.py','exec');(r/'aggregate_current.py').write_bytes(SOURCE.encode());(r/'logs').mkdir()
script='''#!/bin/bash
#SBATCH --partition=v6_384
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:10:00
set -euo pipefail
export PATH=/public3/soft/python/3.9.6/bin:$PATH
export LD_LIBRARY_PATH=/public3/soft/python/3.9.6/lib:${LD_LIBRARY_PATH:-}
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
cd DIRECTORY
'''.replace('DIRECTORY',str(r))
(r/'aggregate.sbatch').write_text(script+'python3 -B aggregate_current.py --root '+D['root']+' --out '+str(r/'summary')+'\n')
coordinator='''from pathlib import Path
import json,subprocess
r=Path(DIRECTORY);dispatch=Path(DISPATCH_ROOT)
full=json.loads((dispatch/'FULL_SUBMISSION.json').read_text())
p=subprocess.run(['sbatch','--parsable','--dependency=afterok:'+full['full_worker_job'],'--job-name=cm245_aggregate','--output='+str(r/'logs/aggregate-%j.log'),str(r/'aggregate.sbatch')],stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
(r/'AGGREGATE_RESPONSE.json').write_text(json.dumps(dict(returncode=p.returncode,stdout=p.stdout,stderr=p.stderr),indent=2)+'\\n')
if p.returncode:raise RuntimeError(p.stderr)
(r/'AGGREGATE_JOB.json').write_text(json.dumps(dict(job=p.stdout.strip(),depends_on_full_worker=full['full_worker_job']),indent=2)+'\\n')
print(p.stdout.strip(),flush=True)
'''.replace('DIRECTORY',repr(str(r))).replace('DISPATCH_ROOT',repr(DISPATCH['root']))
compile(coordinator,'coordinator.py','exec');(r/'coordinator.py').write_text(coordinator)
(r/'coordinator.sbatch').write_text(script+'python3 -B coordinator.py\n')
p=subprocess.run(['sbatch','--parsable','--dependency=afterok:'+DISPATCH['coordinator_job'],'--job-name=cm245_agg_dispatch','--output='+str(r/'logs/coordinator-%j.log'),str(r/'coordinator.sbatch')],stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
if p.returncode:raise RuntimeError('Inspect existing root before retry: '+p.stderr)
x=dict(root=str(r),coordinator_job=p.stdout.strip(),depends_on=DISPATCH['coordinator_job'],source_sha256=sha,
      status='AGGREGATOR_COORDINATOR_SUBMITTED',execution_snapshot_changed=False,submitted_UTC=datetime.datetime.utcnow().isoformat(),
      source_manifest_sha256=D['manifest_sha256'],expected_full_cases=36,
      files_sha256={n:hashlib.sha256((r/n).read_bytes()).hexdigest() for n in ('aggregate_current.py','coordinator.py','aggregate.sbatch','coordinator.sbatch')})
(r/'SUBMISSION.json').write_text(json.dumps(x,indent=2)+'\n');print(json.dumps(x))
""")
out.write_bytes((json.dumps(receipt,indent=2)+'\n').encode());print(json.dumps(receipt))
