"""Immutable CPU-only Slurm DAG:8 pilot gates then36 full-model evaluations."""
from pathlib import Path
import hashlib,io,json,sys,zipfile
HERE=Path(__file__).resolve().parent;CHECKOUT=HERE.parents[3]
WORKSPACE=Path('C:/Users/86134/Documents/a_P_BIT')
sys.path.insert(0,str(WORKSPACE/'local_tools/paracloud_client'))
import client
BASE='/public3/home/t6s011227/pbit_chimera_pipeline_20260920'
RUNTIME=BASE+'/tlm236_joint_20261105/retry_time_audit_ed028cc70e06'
DEPS=BASE+'/attention_resources198_20261107/ee741a72b48e/dependencies'
def sha(b):return hashlib.sha256(b).hexdigest()
def save(n,x):(HERE/n).write_bytes((json.dumps(x,indent=2)+'\n').encode())
def remote(code):
    with client.connect(client.load_password()) as s:
        i,o,e=s.exec_command('python3 -B -',timeout=60);i.write(code);i.flush();i.channel.shutdown_write()
        raw=o.read().decode();err=e.read().decode();rc=o.channel.recv_exit_status()
        if rc:raise RuntimeError(str(rc)+' '+raw[-1200:]+' '+err[-1800:])
        return json.loads(raw)

def prepare():
    if (HERE/'SUBMISSION.json').exists():raise RuntimeError('Already submitted;status/collect only')
    snapshot=HERE/'snapshot';manifest=json.loads((snapshot/'SNAPSHOT_MANIFEST.json').read_bytes())
    for n in ('current_mainline.py','current_run.py','current_pricing.py','execution.py','CURRENT_WORKLOAD_PLAN.json'):
        source=CHECKOUT/'architecture_tlm/model_scaling_20261106'/n
        path='glue/'+n;(snapshot/path).write_bytes(source.read_bytes());manifest['sources'][path]=dict(source=str(source),sha256=sha(source.read_bytes()))
    cases=[dict(model=m,clock=c,scheme=p,seed=s) for m in ('qwen3_4b','llama32_3b','deepseek_7b') for c in (100,250)
        for p in ('SC_ising','BF16_dense','W8_dense','W8_screen') for s in ((17,503,1009) if p=='SC_ising' else (17,))]
    assert len(cases)==36
    pilots=[dict(model='qwen3_4b',clock=c,scheme='SC_ising',seed=17,backend='analytic',anchor=True) for c in (100,250)]
    pilots += [dict(model=m,clock=c,scheme=p,seed=17,backend='native',anchor=False) for m,c,p in
        [('deepseek_7b',250,'SC_ising'),('llama32_3b',100,'BF16_dense'),('qwen3_4b',250,'W8_screen'),
         ('deepseek_7b',100,'W8_dense'),('llama32_3b',250,'SC_ising'),('qwen3_4b',250,'BF16_dense')]]
    for n,x in [('PLAN.json',cases),('PILOTS.json',pilots)]:
        (snapshot/n).write_bytes((json.dumps(x,indent=2)+'\n').encode());manifest['sources'][n]=dict(generated='current36full/8gates',sha256=sha((snapshot/n).read_bytes()))
    driver=r'''from pathlib import Path
import hashlib,json,subprocess,sys
r=Path(__file__).resolve().parent
phase,index=sys.argv[1],int(sys.argv[2]);manifest=json.loads((r/'SNAPSHOT_MANIFEST.json').read_text())
for n,x in manifest['sources'].items():assert hashlib.sha256((r/n).read_bytes()).hexdigest()==x['sha256'],n
p=json.loads((r/('PILOTS.json' if phase=='pilot' else 'PLAN.json')).read_text())[index]
out=r/'results'/phase/('%02d_%s_%s_%s_s%s'%(index,p['model'],p['clock'],p['scheme'],p['seed']))
assert not out.exists(),'Preserve existing result'
cmd=[sys.executable,'-B',str(r/'glue/current_run.py'),'--snapshot',str(r),'--runtime',RUNTIME,'--dependencies',DEPS,
 '--model',p['model'],'--clock',str(p['clock']),'--scheme',p['scheme'],'--seed',str(p['seed']),
 '--backend',p.get('backend','native'),'--out',str(out)]
if phase=='pilot':cmd+=['--layers','1','--skip-head']
if p.get('anchor'):cmd+=['--anchor-captured']
subprocess.run(cmd,check=True)
v=json.loads((out/'VALIDATION.json').read_text());assert v['status']=='PASS'
s=json.loads((out/'SEAL.json').read_text())
for n,h in s['files_sha256'].items():assert hashlib.sha256((out/n).read_bytes()).hexdigest()==h
if p.get('anchor'):
 d=json.loads((out/'RESULT.json').read_text());expected=1.20615 if p['clock']==100 else1.08572
 assert abs(d['time_ms']-expected)<=expected*.001,(d['time_ms'],expected)
print(json.dumps(dict(status='SEALED_AND_GATE_VERIFIED',phase=phase,index=index,case=p)),flush=True)
'''.replace('RUNTIME',repr(RUNTIME)).replace('DEPS',repr(DEPS)).replace('else1.08572','else 1.08572')
    (snapshot/'driver.py').write_bytes(driver.encode());manifest['sources']['driver.py']=dict(generated='owned checked CPUentry',sha256=sha(driver.encode()))
    manifest.update(status='immutable_current_mainline36full_DAG',code_git_head_before_freeze=client_git_head(),
        source_files_include_working_changes=True,primary_process='55nm_equivalent',no28nm_in_primary=True,
        context=2048,batch=1,full_cases=36,unique_primary_configs=24,pilots=8,
        publication_note='SHA pins exact working source;laterGitpublication receipt separate')
    (snapshot/'SNAPSHOT_MANIFEST.json').write_bytes((json.dumps(manifest,indent=2)+'\n').encode())
    files={n:(snapshot/n).read_bytes() for n in manifest['sources']}
    files['SNAPSHOT_MANIFEST.json']=(snapshot/'SNAPSHOT_MANIFEST.json').read_bytes()
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as z:
        for n,b in sorted(files.items()):z.writestr(n,b)
    raw=stream.getvalue();digest=sha(raw);root=BASE+'/tlm245_current_'+digest[:12];archive=root+'.zip'
    (HERE/'snapshot.zip').write_bytes(raw)
    with client.connect(client.load_password()) as s:
        with s.open_sftp() as f:
            try:
                with f.open(archive,'rb') as q:assert sha(q.read())==digest
            except FileNotFoundError:
                with f.open(archive,'wx') as q:q.write(raw)
            with f.open(archive,'rb') as q:assert sha(q.read())==digest
    save('UPLOAD.json',dict(root=root,archive=archive,sha256=digest,bytes=len(raw)))
    result=remote('D='+repr(dict(root=root,archive=archive,sha256=digest,runtime=RUNTIME,deps=DEPS))+'\n'+r"""
from pathlib import Path
import datetime,hashlib,json,os,subprocess,zipfile
r=Path(D['root']);assert not r.exists(),'Inspect existing root/submission before retry';r.mkdir();assert r.stat().st_uid==os.getuid()
raw=Path(D['archive']).read_bytes();assert hashlib.sha256(raw).hexdigest()==D['sha256']
with zipfile.ZipFile(D['archive']) as z:
 for n in z.namelist():
  p=Path(n);assert not p.is_absolute() and '..' not in p.parts
 z.extractall(r)
m=json.loads((r/'SNAPSHOT_MANIFEST.json').read_text())
for n,x in m['sources'].items():assert hashlib.sha256((r/n).read_bytes()).hexdigest()==x['sha256'],n
assert hashlib.sha256((Path(D['runtime'])/'EXECUTION_MANIFEST.json').read_bytes()).hexdigest()=='7c5cb9b603ca2bd139ac6fa7b75d789e00c316acde994ff3db9bdcbb33c4bb40'
assert hashlib.sha256((Path(D['deps'])/'MANIFEST.json').read_bytes()).hexdigest()=='4ce8d1065aa7d4b5f2067e9e409d5bc56bad987cb6b3edf945719ac85777e483'
(r/'logs').mkdir()
receipt=dict(root=str(r),snapshot_sha256=D['sha256'],manifest_sha256=hashlib.sha256((r/'SNAPSHOT_MANIFEST.json').read_bytes()).hexdigest(),
 submitted_UTC=datetime.datetime.utcnow().isoformat(),full_cases=36,primary_configs=24,gate_cases=8,
 requested_CPUs_per_task=1,GiB_per_task=12,gate_concurrency=4,full_concurrency=8,GPU=0,
 runtime=D['runtime'],dependencies=D['deps'],status='SUBMITTING')
def persist():(r/'SUBMISSION.json').write_text(json.dumps(receipt,indent=2)+'\n')
persist()
prefix='''#!/bin/bash
#SBATCH --partition=v6_384
#SBATCH --cpus-per-task=1
#SBATCH --mem=12G
set -euo pipefail
export PATH=/public3/soft/gcc/11.2.0/bin:/public3/soft/python/3.9.6/bin:$PATH
export LD_LIBRARY_PATH=/public3/soft/gcc/11.2.0/lib64:/public3/soft/python/3.9.6/lib:${LD_LIBRARY_PATH:-}
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
cd ROOT
'''.replace('ROOT',str(r))
for phase,limit in [('pilot','04:00:00'),('full','12:00:00')]:
 (r/(phase+'.sbatch')).write_text(prefix.replace('set -euo pipefail','#SBATCH --time='+limit+'\nset -euo pipefail')+'python3 -B driver.py '+phase+' "$SLURM_ARRAY_TASK_ID"\n')
def submit(phase,indices,dependency=None):
 args=['sbatch','--parsable','--array='+indices,'--job-name=cm245_'+phase+'_'+D['sha256'][:8],
  '--output='+str(r/'logs'/((phase+'-%A_%a.log')))]
 if dependency:args+=['--dependency=afterok:'+dependency]
 args+=[str(r/(phase+'.sbatch'))]
 p=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
 if p.returncode:raise RuntimeError('Submission failed;inspect receipt/queue before retry: '+p.stderr)
 return p.stdout.strip()
receipt['pilot_job']=submit('pilot','0-7%4');persist()
receipt['full_job']=submit('full','0-35%8',receipt['pilot_job']);receipt['status']='SUBMITTED_GATED';persist()
print(json.dumps(receipt))
""")
    save('SUBMISSION.json',result);print(json.dumps(result))

def client_git_head():
    import subprocess
    return subprocess.check_output(['git','rev-parse','HEAD'],cwd=CHECKOUT,text=True).strip()

def status():
    d=json.loads((HERE/'SUBMISSION.json').read_bytes())
    x=remote('D='+repr(d)+'\n'+r'''
from pathlib import Path
import datetime,json,subprocess
r=Path(D['root']);ids=D['pilot_job']+','+D['full_job'];out=dict(checked_UTC=datetime.datetime.utcnow().isoformat())
for key,cmd in [('queue',['squeue','-h','-j',ids,'-o','%A|%j|%T|%M|%C|%R']),('accounting',['sacct','-n','-j',ids,'--format=JobID,State,Elapsed,ExitCode,AllocCPUS,MaxRSS','-P'])]:
 p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True);out[key]=dict(rc=p.returncode,text=p.stdout,stderr=p.stderr)
out['sealed']=[str(p.parent.relative_to(r)) for p in (r/'results').rglob('SEAL.json')]
out['logs']={p.name:p.read_text(errors='replace')[-900:] for p in (r/'logs').glob('*.log')}
print(json.dumps(out))
''');save('STATUS.json',x);print(json.dumps(x))

if __name__=='__main__':
    if sys.argv[1]=='prepare':prepare()
    elif sys.argv[1]=='status':status()
    else:raise ValueError(sys.argv[1])
