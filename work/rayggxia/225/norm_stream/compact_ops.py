"""One bounded compact-layout prefix; never changes existing snapshots/jobs."""
from pathlib import Path
import base64,hashlib,json,sys
import ops
H=Path(__file__).resolve().parent


def submit():
    if (H/'COMPACT_SUBMISSION.json').exists():raise RuntimeError('Already submitted; use status')
    root=H.parents[3];folder=root/'architecture_tlm/norm_stream_20261106'
    files={str(p.relative_to(root)).replace('\\','/'):dict(sha256=ops.sha(p),data=base64.b64encode(p.read_bytes()).decode()) for p in sorted(folder.glob('*.py'))}
    ident=hashlib.sha256(json.dumps({k:v['sha256'] for k,v in files.items()},sort_keys=True).encode()).hexdigest()
    code='FILES='+repr(files)+'\nIDENT='+repr(ident)+'\nRUNTIME='+repr(ops.RUNTIME)+'\nPARENT='+repr(ops.PERSONAL)+'\n'+r"""
from pathlib import Path
import base64,hashlib,json,subprocess,os,datetime
parent=Path(PARENT);assert parent.stat().st_uid==os.getuid()
r=parent/('compact_'+IDENT[:12]);r.mkdir()
for name,x in FILES.items():
 p=r/name;p.relative_to(r);p.parent.mkdir(parents=True,exist_ok=True)
 data=base64.b64decode(x['data']);assert hashlib.sha256(data).hexdigest()==x['sha256'];p.write_bytes(data)
manifest=dict(identity=IDENT,files_sha256={n:x['sha256'] for n,x in FILES.items()},runtime=RUNTIME)
(r/'MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
entry=r/'architecture_tlm/norm_stream_20261106/launch_compact.py'
env='''#!/bin/bash
#SBATCH --partition=v6_384
#SBATCH --cpus-per-task=1
set -euo pipefail
export PATH=/public3/soft/gcc/11.2.0/bin:/public3/soft/python/3.9.6/bin:$PATH
export LD_LIBRARY_PATH=/public3/soft/gcc/11.2.0/lib64:/public3/soft/python/3.9.6/lib:${LD_LIBRARY_PATH:-}
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
'''
cmd='python3 -B '+str(entry)+' --runtime '+RUNTIME
(r/'test.sbatch').write_text(env+cmd+' --tests\n')
(r/'prefix.sbatch').write_text(env+cmd+' --seed 17 --prefix-layers 2 --out '+str(r/'prefix')+'\n')
def sbatch(name,mem,wall,extra=()):
 return subprocess.check_output(['sbatch','--parsable','--mem='+mem,'--time='+wall,
   '--job-name=compact225_'+name,'--output='+str(r/(name+'-%j.log')),*extra,str(r/(name+'.sbatch'))],universal_newlines=True).strip()
gate=sbatch('test','4G','00:10:00')
prefix=sbatch('prefix','8G','01:00:00',('--dependency=afterok:'+gate,))
receipt=dict(root=str(r),identity=IDENT,runtime=RUNTIME,gate=gate,prefix=prefix,
   files_sha256=manifest['files_sha256'],CPU=1,GPU=0,scope='two-layer native compact layout only; not whole token',submitted_UTC=datetime.datetime.utcnow().isoformat())
(r/'SUBMISSION.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt))
"""
    r=ops.remote(code);ops.save('COMPACT_SUBMISSION.json',r);print(json.dumps(r))


def status():
    d=json.loads((H/'COMPACT_SUBMISSION.json').read_bytes())
    code='D='+repr(d)+'\n'+r'''
from pathlib import Path
import json,subprocess,hashlib
r=Path(D['root']);jobs=','.join(D[k] for k in ('gate','prefix'))
x=dict(queue=subprocess.check_output(['squeue','-h','-j',jobs,'-o','%i|%T|%M|%R'],universal_newlines=True),
 accounting=subprocess.check_output(['sacct','-n','-P','-j',jobs,'--format=JobIDRaw,State,ExitCode,Elapsed'],universal_newlines=True),
 logs={p.name:p.read_text()[-2000:] for p in r.glob('*.log')})
if (r/'prefix/SEAL.json').is_file():
 seal=json.loads((r/'prefix/SEAL.json').read_text())
 for n,k in [('RESULT.json','result_sha256'),('BUDGET.json','budget_sha256')]:assert hashlib.sha256((r/'prefix'/n).read_bytes()).hexdigest()==seal[k]
 for n,h in D['files_sha256'].items():assert hashlib.sha256((r/n).read_bytes()).hexdigest()==h
 a=json.loads((r/'prefix/RESULT.json').read_text());b=json.loads((r/'prefix/BUDGET.json').read_text())
 x['sealed_result']=dict(status=a['status'],scope=a['scope'],time_ms=a['simulated_ms'],area55_mm2=b['covered_area55_mm2'],
  total_mJ=b['covered_system_mJ_at4pJ'],compaction=a['sram_compaction_contract'],actions=a['actions'],dram_counts=a['memory']['counts'],
  result_sha256=seal['result_sha256'],budget_sha256=seal['budget_sha256'])
print(json.dumps(x))
'''
    r=ops.remote(code);ops.save('COMPACT_STATUS.json',r);print(json.dumps(r))


if __name__=='__main__':globals()[sys.argv[1]]()
