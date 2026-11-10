from pathlib import Path
import datetime,hashlib,json,os,subprocess,zipfile
r=Path(P['root']);archive=Path(P['remote']);assert hashlib.sha256(archive.read_bytes()).hexdigest()==P['sha256']
if not r.exists():
    r.mkdir()
    with zipfile.ZipFile(str(archive)) as z:
        for n in z.namelist():assert r.resolve() in (r/n).resolve().parents
        z.extractall(str(r))
assert hashlib.sha256((r/'FROZEN_MANIFEST.json').read_bytes()).hexdigest()==P['manifest_sha256']
mf=json.loads((r/'FROZEN_MANIFEST.json').read_text());e=mf['environment']
for n,v in mf['files_sha256'].items():assert hashlib.sha256((r/n).read_bytes()).hexdigest()==v
for name,k in [('runtime','EXECUTION_MANIFEST.json'),('dependencies','MANIFEST.json'),('snapshot','SNAPSHOT_MANIFEST.json')]:
    assert hashlib.sha256((Path(e[name])/k).read_bytes()).hexdigest()==e[name+'_manifest_sha256']
receipt=r/'SUBMISSION.json'
if receipt.exists():rec=json.loads(receipt.read_text())
else:rec=dict(status='SUBMITTING',root=str(r),submitted_UTC=datetime.datetime.utcnow().isoformat(),
    archive_sha256=P['sha256'],manifest_sha256=P['manifest_sha256'],environment=e,pilot=None,full_jobs=[],
    CPU_per_task=1,pilot_GiB=12,full_GiB=24,GPUs=0,artificial_full_concurrency_cap=None)
env=os.environ.copy();env['LD_LIBRARY_PATH']='/public3/soft/gcc/11.2.0/lib64:/public3/soft/python/3.9.6/lib:'+env.get('LD_LIBRARY_PATH','')
py='/public3/soft/python/3.9.6/bin/python3'
q=subprocess.run([py,'-c','import ctypes;ctypes.CDLL('+repr(e['runtime']+'/base/liblpbridge.so')+');print("OK")'],
    env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True);assert q.returncode==0,q.stderr
(r/'logs').mkdir(exist_ok=True)
prefix='\n'.join(['#!/bin/bash','#SBATCH --partition=v6_384','#SBATCH --cpus-per-task=1',
    'set -euo pipefail','export PATH=/public3/soft/gcc/11.2.0/bin:/public3/soft/python/3.9.6/bin:$PATH',
    'export LD_LIBRARY_PATH=/public3/soft/gcc/11.2.0/lib64:/public3/soft/python/3.9.6/lib:'+chr(36)+'{LD_LIBRARY_PATH:-}',
    'export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1','cd '+str(r),''])
for phase,mem,limit,arg in [('pilot',12,'04:00:00','"$SLURM_ARRAY_TASK_ID"'),('full',24,'24:00:00','"$1"')]:
    (r/(phase+'.sbatch')).write_text(prefix.replace('set -euo pipefail','#SBATCH --mem='+str(mem)+'G\n#SBATCH --time='+limit+'\nset -euo pipefail')+
        'python3 -B '+str(r/'worker.py')+' '+phase+' '+arg+'\n')
def persist():receipt.write_text(json.dumps(rec,indent=2)+'\n')
def sbatch(args):
    q=subprocess.run(['sbatch','--parsable']+args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
    assert q.returncode==0,q.stderr
    return q.stdout.strip().split(';')[0]
persist();tag=r.name[-12:]
if rec['pilot'] is None:
    rec['pilot']=sbatch(['--array=0-7','--job-name=cross28_gate_'+tag,'--output='+str(r/'logs/gate-%A_%a.log'),str(r/'pilot.sbatch')]);persist()
for case in mf['full']:
    if any(x['index']==case['index'] for x in rec['full_jobs']):continue
    dependency='afterok:'+rec['pilot']+'_'+str(case['gate_index'])
    job=sbatch(['--dependency='+dependency,'--kill-on-invalid-dep=yes','--job-name=cross28_'+str(case['index'])+'_'+tag,
        '--output='+str(r/('logs/full-'+str(case['index'])+'-%j.log')),str(r/'full.sbatch'),str(case['index'])])
    rec['full_jobs'].append(dict(case,job_id=job,dependency=dependency));persist()
assert len(rec['full_jobs'])==12
rec['status']='SUBMITTED';persist();print(json.dumps(rec))
