"""Scoped CPU snapshot/submission; existing jobs and owner sources untouched."""
from pathlib import Path
import base64,hashlib,io,json,sys,tarfile

HERE=Path(__file__).resolve().parent
CHECKOUT=HERE.parents[3]
WORKSPACE=Path('C:/Users/86134/Documents/a_P_BIT')
sys.path.insert(0,str(WORKSPACE/'tmp/digital-fair-issue236-20261105/work/rayggxia/236'))
import eda
PARENT='/public3/home/t6s011227/pbit_chimera_pipeline_20260920/tlm236_joint_20261105/retry_time_audit_ed028cc70e06'

def save(n,x):(HERE/n).write_bytes((json.dumps(x,indent=2)+'\n').encode())

def prepare():
    if (HERE/'SUBMISSION.json').exists():raise RuntimeError('Already submitted: use status; no duplicate')
    local=HERE/'local_runtime'
    # Last local fixes are frozen before transfer, not patched after submission.
    for n in ('execution.py','run_case.py'):
        src=CHECKOUT/'architecture_tlm/model_scaling_20261106'/n;dest=local/'architecture_tlm/model_scaling_20261106'/n;dest.write_bytes(src.read_bytes())
    mf=json.loads((local/'EXECUTION_MANIFEST.json').read_bytes())
    for n in ('execution.py','run_case.py'):
        name='architecture_tlm/model_scaling_20261106/'+n
        mf['sources'][name]=dict(sha256=hashlib.sha256((local/name).read_bytes()).hexdigest(),source='Issue245 owned glue')
    (local/'EXECUTION_MANIFEST.json').write_bytes((json.dumps(mf,indent=2)+'\n').encode())
    stream=io.BytesIO()
    with tarfile.open(fileobj=stream,mode='w:gz') as tar:
        for p in sorted(local.rglob('*')):
            if p.is_file() and p.suffix in ('.py','.json'):tar.add(p,arcname=str(p.relative_to(local)).replace('\\','/'))
    raw=stream.getvalue();digest=hashlib.sha256(raw).hexdigest();remote_base='/public3/home/t6s011227/pbit_chimera_pipeline_20260920/tlm245_crossmodel_20261107'
    archive=remote_base+'/source_'+digest[:12]+'.tar.gz'
    with eda.client.connect(eda.client.load_password()) as ssh:
        with ssh.open_sftp() as s:
            try:s.stat(remote_base)
            except FileNotFoundError:s.mkdir(remote_base)
            try:
                with s.open(archive,'rb') as f:assert hashlib.sha256(f.read()).hexdigest()==digest
            except FileNotFoundError:
                with s.open(archive,'wx') as f:f.write(raw)
            with s.open(archive,'rb') as f:assert hashlib.sha256(f.read()).hexdigest()==digest
    d=dict(archive=archive,sha256=digest,base=remote_base,parent=PARENT)
    save('UPLOAD.json',dict(d,bytes=len(raw)))
    result=eda.remote('D='+repr(d)+'\n'+r"""
import pathlib,hashlib,json,os,shutil,subprocess,tarfile,datetime
base=pathlib.Path(D['base']);r=base/('pilot_'+D['sha256'][:12]);r.mkdir();assert r.stat().st_uid==os.getuid()
assert hashlib.sha256(pathlib.Path(D['archive']).read_bytes()).hexdigest()==D['sha256']
with tarfile.open(D['archive']) as t:
 for m in t.getmembers():
  p=pathlib.PurePosixPath(m.name);assert not p.is_absolute() and '..' not in p.parts and not m.issym() and not m.islnk()
 t.extractall(str(r))
manifest=json.loads((r/'EXECUTION_MANIFEST.json').read_text())
for name,x in manifest['sources'].items():assert hashlib.sha256((r/name).read_bytes()).hexdigest()==x['sha256'],name
native={}
for name in ('base/liblpbridge.so','base/profiles/derived8533.yaml','base/profiles/PROFILES.json'):
 source=pathlib.Path(D['parent'])/name;dest=r/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(str(source),str(dest));native[name]=hashlib.sha256(dest.read_bytes()).hexdigest()
expected=json.loads((r/'architecture_tlm/equal_area_100_250_20261107/TARGETS.json').read_text())['same_external_config_sha256']
assert native['base/profiles/derived8533.yaml']==expected,(native,expected)
(r/'NATIVE_DEPENDENCIES.json').write_text(json.dumps(dict(parent=D['parent'],sha256=native),indent=2)+'\n')
(r/'logs').mkdir()
script='''#!/bin/bash
#SBATCH --partition=v6_384
#SBATCH --cpus-per-task=1
#SBATCH --mem=10G
#SBATCH --time=02:00:00
set -euo pipefail
export PATH=/public3/soft/gcc/11.2.0/bin:/public3/soft/python/3.9.6/bin:$PATH
export LD_LIBRARY_PATH=/public3/soft/gcc/11.2.0/lib64:/public3/soft/python/3.9.6/lib:${LD_LIBRARY_PATH:-}
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
cd ROOT
python3 -B architecture_tlm/model_scaling_20261106/run_case.py --runtime . --index "$SLURM_ARRAY_TASK_ID" --phase pilot
'''.replace('ROOT',str(r))
(r/'pilot.sbatch').write_text(script)
receipt=dict(root=str(r),kind='24_native_single_layer_pilots_not_full_model',submitted_UTC=datetime.datetime.utcnow().isoformat(),
 archive_sha256=D['sha256'],manifest_sha256=hashlib.sha256((r/'EXECUTION_MANIFEST.json').read_bytes()).hexdigest(),
 native_sha256=native,CPUs_per_task=1,max_concurrent_tasks=2,GiB_per_task=10,GPU=0,full_model_submitted=False)
proc=subprocess.run(['sbatch','--parsable','--array=0-23%2','--job-name=cm245_'+D['sha256'][:8],
 '--output='+str(r/'logs/pilot-%A_%a.log'),str(r/'pilot.sbatch')],stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
if proc.returncode:
 q=subprocess.check_output(['squeue','-h','--name=cm245_'+D['sha256'][:8],'-o','%A|%o'],universal_newlines=True)
 found={line.split('|')[0] for line in q.splitlines() if str(r/'pilot.sbatch') in line}
 if len(found)!=1:raise RuntimeError('inspect scheduler before any retry:'+proc.stderr+' '+q)
 receipt['job']=next(iter(found));receipt['recovered_submit_stderr']=proc.stderr
else:receipt['job']=proc.stdout.strip()
(r/'SUBMISSION.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
""")
    save('SUBMISSION.json',result);print(json.dumps(result))

def status():
    d=json.loads((HERE/'SUBMISSION.json').read_bytes())
    result=eda.remote('D='+repr(d)+'\n'+r'''
import pathlib,json,subprocess,datetime
r=pathlib.Path(D['root']);out=dict(root=str(r),checked_UTC=datetime.datetime.utcnow().isoformat())
for name,cmd in [('queue',['squeue','-h','-j',D['job'],'-o','%i|%T|%M|%R']),('accounting',['sacct','-n','-P','-j',D['job'],'--format=JobIDRaw,State,ExitCode,Elapsed,MaxRSS'])]:
 p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True);out[name]=dict(rc=p.returncode,text=p.stdout,stderr=p.stderr)
out['results']=[]
for p in (r/'results/pilot').glob('*/RESULT.json'):
 d=json.loads(p.read_text());v=p.with_name('WORK_GATE.json');out['results'].append(dict(case=p.parent.name,status=d['status'],time_ms=d['time_ms'],work_gate=json.loads(v.read_text()) if v.exists() else None))
out['logs']={p.name:p.read_text()[-1800:] for p in (r/'logs').glob('*.log')}
print(json.dumps(out))
''')
    save('STATUS.json',result);print(json.dumps(result))

if __name__=='__main__':globals()[sys.argv[1]]()
