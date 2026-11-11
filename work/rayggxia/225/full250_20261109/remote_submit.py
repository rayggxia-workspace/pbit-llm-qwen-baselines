from pathlib import Path
import datetime,hashlib,json,os,subprocess,zipfile
# P is a structured upload plan prepended by the local caller.
r=Path(P['root']);archive=Path(P['remote'])
assert hashlib.sha256(archive.read_bytes()).hexdigest()==P['sha256']
if not r.exists():
    r.mkdir()
    with zipfile.ZipFile(str(archive)) as z:
        for n in z.namelist():assert r.resolve() in (r/n).resolve().parents
        z.extractall(str(r))
mf=r/'FROZEN_MANIFEST.json';assert hashlib.sha256(mf.read_bytes()).hexdigest()==P['manifest_sha256']
manifest=json.loads(mf.read_text())
for n,v in manifest['files_sha256'].items():assert hashlib.sha256((r/n).read_bytes()).hexdigest()==v,n
e=manifest['environment']
for name,part in [('runtime','EXECUTION_MANIFEST.json'),('dependencies','MANIFEST.json'),('snapshot','SNAPSHOT_MANIFEST.json')]:
    assert hashlib.sha256((Path(e[name])/part).read_bytes()).hexdigest()==e[name+'_manifest_sha256']
receipt=r/'SUBMISSION.json'
if receipt.exists():print(receipt.read_text());raise SystemExit
env=os.environ.copy();env['LD_LIBRARY_PATH']='/public3/soft/gcc/11.2.0/lib64:/public3/soft/python/3.9.6/lib:'+env.get('LD_LIBRARY_PATH','')
py='/public3/soft/python/3.9.6/bin/python3'
probe=subprocess.run([py,'-c','import sys,ctypes;ctypes.CDLL('+repr(e['runtime']+'/base/liblpbridge.so')+');print(sys.version.split()[0])'],
    env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
assert probe.returncode==0,probe.stderr[-1500:]
(r/'logs').mkdir(exist_ok=True)
prefix='\n'.join(['#!/bin/bash','#SBATCH --partition=v6_384','#SBATCH --cpus-per-task=1','#SBATCH --mem=12G',
    'set -euo pipefail','export PATH=/public3/soft/gcc/11.2.0/bin:/public3/soft/python/3.9.6/bin:$PATH',
    'export LD_LIBRARY_PATH=/public3/soft/gcc/11.2.0/lib64:/public3/soft/python/3.9.6/lib:${LD_LIBRARY_PATH:-}',
    'export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1','cd '+str(r),''])
for phase,limit,args in [('pilot','04:00:00','pilot 0'),('full','12:00:00','full "$SLURM_ARRAY_TASK_ID"')]:
    (r/(phase+'.sbatch')).write_text(prefix.replace('set -euo pipefail','#SBATCH --time='+limit+'\nset -euo pipefail')+
        'python3 -B '+str(r/'worker.py')+' '+args+'\n')
rec=dict(status='SUBMITTING',root=str(r),manifest_sha256=P['manifest_sha256'],archive_sha256=P['sha256'],
    source_commit='e6dc60c46d880df03efc2ca60ea9ba931ea576b1 plus recorded portable binary64epsilon patch',
    submitted_UTC=datetime.datetime.utcnow().isoformat(),python_version=probe.stdout.strip(),
    pilot=None,full_array=None,full_seeds=[17,503,1009],CPU_per_task=1,GiB_per_task=12,full_concurrency=2,GPUs=0,
    full_layers=36,full_vocab=151936,backend='native LPDDR5X8533derived',environment=e)
def persist():receipt.write_text(json.dumps(rec,indent=2)+'\n')
def sbatch(args):
    result=subprocess.run(['sbatch','--parsable']+args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
    assert result.returncode==0,result.stderr
    return result.stdout.strip().split(';')[0]
persist();tag=r.name[-12:]
rec['pilot']=sbatch(['--job-name=tlm28p250_gate_'+tag,'--output='+str(r/'logs/pilot-%j.log'),str(r/'pilot.sbatch')]);persist()
rec['full_array']=sbatch(['--array=0-2%2','--dependency=afterok:'+rec['pilot'],'--kill-on-invalid-dep=yes',
    '--job-name=tlm28p250_full_'+tag,'--output='+str(r/'logs/full-%A_%a.log'),str(r/'full.sbatch')])
rec['status']='SUBMITTED';persist();print(json.dumps(rec))
