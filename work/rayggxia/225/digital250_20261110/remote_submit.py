from pathlib import Path
import datetime,hashlib,json,os,subprocess,zipfile
r=Path(P['root']);archive=Path(P['remote']);assert hashlib.sha256(archive.read_bytes()).hexdigest()==P['sha256']
if not r.exists():
    r.mkdir()
    with zipfile.ZipFile(str(archive)) as z:
        for n in z.namelist():assert r.resolve() in (r/n).resolve().parents
        z.extractall(str(r))
assert hashlib.sha256((r/'FROZEN_MANIFEST.json').read_bytes()).hexdigest()==P['manifest_sha256']
manifest=json.loads((r/'FROZEN_MANIFEST.json').read_text());e=manifest['environment']
for n,v in manifest['files_sha256'].items():assert hashlib.sha256((r/n).read_bytes()).hexdigest()==v
receipt=r/'SUBMISSION.json'
if receipt.exists():print(receipt.read_text());raise SystemExit
env=os.environ.copy();env['LD_LIBRARY_PATH']='/public3/soft/gcc/11.2.0/lib64:/public3/soft/python/3.9.6/lib:'+env.get('LD_LIBRARY_PATH','')
py='/public3/soft/python/3.9.6/bin/python3'
probe=subprocess.run([py,'-c','import ctypes;ctypes.CDLL('+repr(e['runtime']+'/base/liblpbridge.so')+');print("nativeOK")'],
    env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True);assert probe.returncode==0,probe.stderr
for name,part in [('runtime','EXECUTION_MANIFEST.json'),('dependencies','MANIFEST.json'),('snapshot','SNAPSHOT_MANIFEST.json')]:
    assert hashlib.sha256((Path(e[name])/part).read_bytes()).hexdigest()==e[name+'_manifest_sha256']
(r/'logs').mkdir(exist_ok=True)
prefix='\n'.join(['#!/bin/bash','#SBATCH --partition=v6_384','#SBATCH --cpus-per-task=1','#SBATCH --mem=12G',
    'set -euo pipefail','export PATH=/public3/soft/gcc/11.2.0/bin:/public3/soft/python/3.9.6/bin:$PATH',
    'export LD_LIBRARY_PATH=/public3/soft/gcc/11.2.0/lib64:/public3/soft/python/3.9.6/lib:${LD_LIBRARY_PATH:-}',
    'export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1','cd '+str(r),''])
for phase,limit in [('pilot','04:00:00'),('full','24:00:00')]:
    (r/(phase+'.sbatch')).write_text(prefix.replace('set -euo pipefail','#SBATCH --time='+limit+'\nset -euo pipefail')+
        'python3 -B '+str(r/'worker.py')+' '+phase+' "$SLURM_ARRAY_TASK_ID"\n')
rec=dict(status='SUBMITTING',root=str(r),submitted_UTC=datetime.datetime.utcnow().isoformat(),
    archive_sha256=P['sha256'],manifest_sha256=P['manifest_sha256'],environment=e,
    pilot=None,full_array=None,schemes=manifest['schemes'],full_layers=36,full_vocab=151936,
    CPU_per_task=1,GiB_per_task=12,concurrency=2,GPUs=0)
def persist():receipt.write_text(json.dumps(rec,indent=2)+'\n')
def sbatch(args):
    q=subprocess.run(['sbatch','--parsable']+args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
    assert q.returncode==0,q.stderr
    return q.stdout.strip().split(';')[0]
persist();tag=r.name[-12:]
rec['pilot']=sbatch(['--array=0-2%2','--job-name=tlm28d_gate_'+tag,'--output='+str(r/'logs/gate-%A_%a.log'),str(r/'pilot.sbatch')]);persist()
rec['full_array']=sbatch(['--array=0-2%2','--dependency=aftercorr:'+rec['pilot'],'--kill-on-invalid-dep=yes',
    '--job-name=tlm28d_full_'+tag,'--output='+str(r/'logs/full-%A_%a.log'),str(r/'full.sbatch')]);rec['status']='SUBMITTED';persist();print(json.dumps(rec))
