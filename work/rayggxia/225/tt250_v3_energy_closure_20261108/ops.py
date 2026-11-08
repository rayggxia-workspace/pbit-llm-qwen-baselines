"""CPU native replay with immutable accepted-v3 sources and energy ledger."""
from pathlib import Path
import hashlib,io,json,sys,zipfile

HERE=Path(__file__).resolve().parent
CHECKOUT=HERE.parents[3]
WORKSPACE=Path('C:/Users/86134/Documents/a_P_BIT')
sys.path.insert(0,str(WORKSPACE/'local_tools/paracloud_client'))
import client
BASE='/public3/home/t6s011227/pbit_chimera_pipeline_20260920'
RUNTIME=BASE+'/tlm236_joint_20261105/retry_time_audit_ed028cc70e06'
DEPENDENCIES=BASE+'/attention_resources198_20261107/ee741a72b48e/dependencies'
ENTRY='architecture_tlm/sram1216_20261106/250MHz/run.py'

def save(n,x):(HERE/n).write_bytes((json.dumps(x,indent=2)+'\n').encode())
def sha(b):return hashlib.sha256(b).hexdigest()
def remote(code):
    with client.connect(client.load_password()) as ssh:
        i,o,e=ssh.exec_command('python3 -B -',timeout=60);i.write(code);i.flush();i.channel.shutdown_write()
        out=o.read().decode();err=e.read().decode();rc=o.channel.recv_exit_status()
        if rc:raise RuntimeError(str(rc)+' '+out[-1800:]+' '+err[-1800:])
        return json.loads(out)

def prepare():
    if (HERE/'SUBMISSION.json').exists():raise RuntimeError('Already submitted: inspect status; no duplicate')
    files={}
    for name in ('sram1216_20261106/250MHz','module_refresh_20261107'):
        root=CHECKOUT/'architecture_tlm'/name
        for p in root.rglob('*'):
            if p.is_file() and p.suffix in ('.py','.json') and '__pycache__' not in p.parts:
                files[str(p.relative_to(CHECKOUT)).replace('\\','/')]=p.read_bytes()
    owner=WORKSPACE/'tmp/attention-compare-issue198-20261027/architecture_tlm/attention_supply_front_20261107'
    pin=json.loads(files['architecture_tlm/module_refresh_20261107/ATTENTION_SOURCE.json'])
    for name,h in pin['execution_sources'].items():
        b=(owner/name).read_bytes();assert sha(b)==h;files['owner_attention/'+name]=b
    inp=WORKSPACE/'project_archives/attention_integrated250_198_20261107/inputs'
    for n in ('SAMPLES.json','representative.json'):files['inputs/'+n]=(inp/n).read_bytes()
    files['PLAN.json']=(json.dumps([dict(scope='full',seed=s,cores=3) for s in (17,503,1009)],indent=2)+'\n').encode()
    files['driver.py']=('''from pathlib import Path
import json,subprocess,sys
r=Path(__file__).resolve().parent
if sys.argv[1]=='gate':a=dict(scope='layer',seed=17,cores=3);out=r/'gate'
else:a=json.loads((r/'PLAN.json').read_text())[int(sys.argv[1])];out=r/'results'/sys.argv[1]
cmd=[sys.executable,'-B',str(r/ENTRY),'--runtime',RUNTIME,'--dependencies',DEPENDENCIES,
 '--attention-source',str(r/'owner_attention'),'--inputs',str(r/'inputs'),'--backend','native',
 '--scope',a['scope'],'--cores',str(a['cores']),'--seed',str(a['seed']),'--out',str(out)]
assert not out.exists(),'Do not overwrite existing results'
manifest=json.loads((r/'EXECUTION_MANIFEST.json').read_text())
import hashlib
for n,h in manifest['files_sha256'].items():assert hashlib.sha256((r/n).read_bytes()).hexdigest()==h,n
raise SystemExit(subprocess.call(cmd))
'''.replace('ENTRY',repr(ENTRY)).replace('RUNTIME',repr(RUNTIME)).replace('DEPENDENCIES',repr(DEPENDENCIES))).encode()
    manifest=dict(owner='rayggxia',issue=225,PR=249,scope='actual current250 host,delta_pipeline_v3 and closed modeled-energy ledger',
        files_sha256={n:sha(b) for n,b in files.items()},runtime=RUNTIME,dependencies=DEPENDENCIES,
        numerical_inference=False,new_PPA=False,clock_MHz=250,GU_frame_cycles=19,Wd_frame_cycles=35,
        SRAM_KiB=960,FFN_cores=3,ingress_KiB=16,seeds=[17,503,1009])
    files['EXECUTION_MANIFEST.json']=(json.dumps(manifest,indent=2)+'\n').encode();save('MANIFEST.json',manifest)
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as z:
        for n,b in sorted(files.items()):z.writestr(n,b)
    raw=stream.getvalue();digest=sha(raw);root=BASE+'/energy225_tt250_v3_'+digest[:12];archive=root+'.zip'
    (HERE/'snapshot.zip').write_bytes(raw)
    with client.connect(client.load_password()) as ssh:
        with ssh.open_sftp() as s:
            try:
                with s.open(archive,'rb') as f:assert sha(f.read())==digest
            except FileNotFoundError:
                with s.open(archive,'wx') as f:f.write(raw)
            with s.open(archive,'rb') as f:assert sha(f.read())==digest
    d=dict(root=root,archive=archive,sha256=digest,runtime=RUNTIME,dependencies=DEPENDENCIES)
    save('UPLOAD.json',dict(d,bytes=len(raw)))
    x=remote('D='+repr(d)+'\n'+r"""
from pathlib import Path
import datetime,hashlib,json,os,subprocess,zipfile
r=Path(D['root']);assert not r.exists(),'Inspect existing root/submission before retry';r.mkdir();assert r.stat().st_uid==os.getuid()
raw=Path(D['archive']).read_bytes();assert hashlib.sha256(raw).hexdigest()==D['sha256']
with zipfile.ZipFile(D['archive']) as z:
 for n in z.namelist():
  q=Path(n);assert not q.is_absolute() and '..' not in q.parts
 z.extractall(r)
runtime=Path(D['runtime']);deps=Path(D['dependencies'])
assert hashlib.sha256((runtime/'EXECUTION_MANIFEST.json').read_bytes()).hexdigest()=='7c5cb9b603ca2bd139ac6fa7b75d789e00c316acde994ff3db9bdcbb33c4bb40'
assert (runtime/'base/liblpbridge.so').exists() and (deps/'MANIFEST.json').exists()
receipt=dict(root=str(r),snapshot_sha256=D['sha256'],manifest_sha256=hashlib.sha256((r/'EXECUTION_MANIFEST.json').read_bytes()).hexdigest(),
 runtime=D['runtime'],dependencies=D['dependencies'],dependencies_manifest_sha256=hashlib.sha256((deps/'MANIFEST.json').read_bytes()).hexdigest(),
 submitted_UTC=datetime.datetime.utcnow().isoformat(),CPU_per_task=1,GiB_per_task=12,max_full_concurrency=2,GPU=0,plan='native layer gate then3seed full36+head')
def persist():(r/'SUBMISSION.json').write_text(json.dumps(receipt,indent=2)+'\n')
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
(r/'gate.sbatch').write_text(prefix+'python3 -B driver.py gate\n')
(r/'full.sbatch').write_text(prefix+'python3 -B driver.py "$SLURM_ARRAY_TASK_ID"\n')
def submit(name,args,path):
 p=subprocess.run(['sbatch','--parsable','--job-name='+name]+args+[str(path)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
 if p.returncode==0:return p.stdout.strip()
 q=subprocess.check_output(['squeue','-h','--name='+name,'-o','%A|%o'],universal_newlines=True)
 found={line.split('|')[0] for line in q.splitlines() if str(path) in line}
 if len(found)!=1:raise RuntimeError('inspect scheduler before retry:'+p.stderr+' '+q)
 receipt.setdefault('recovered_submit_errors',[]).append(p.stderr);return next(iter(found))
persist();gate=submit('e225g_'+D['sha256'][:8],['--time=02:00:00','--output='+str(r/'gate-%j.log')],r/'gate.sbatch');receipt['gate_job']=gate;persist()
full=submit('e225f_'+D['sha256'][:8],['--time=08:00:00','--array=0-2%2','--dependency=afterok:'+gate,'--output='+str(r/'full-%A_%a.log')],r/'full.sbatch')
receipt['full_job']=full;receipt['status']='submitted';persist();print(json.dumps(receipt))
""")
    save('SUBMISSION.json',x);print(json.dumps(x))

def status():
    d=json.loads((HERE/'SUBMISSION.json').read_bytes())
    x=remote('D='+repr(d)+'\n'+r'''
from pathlib import Path
import datetime,json,subprocess
r=Path(D['root']);out=dict(checked_UTC=datetime.datetime.utcnow().isoformat(),root=str(r))
for k,cmd in [('queue',['squeue','-h','-j',D['gate_job']+','+D['full_job'],'-o','%i|%T|%M|%R']),
 ('accounting',['sacct','-n','-P','-j',D['gate_job']+','+D['full_job'],'--format=JobIDRaw,State,Elapsed,ExitCode,MaxRSS'])]:
 p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True);out[k]=dict(rc=p.returncode,text=p.stdout,stderr=p.stderr)
out['logs']={p.name:p.read_text()[-1600:] for p in r.glob('*.log')}
out['results']=[]
for p in [r/'gate']+list((r/'results').glob('*')):
 if (p/'SEAL.json').exists():
  import hashlib
  s=json.loads((p/'SEAL.json').read_text())
  for n,h in s['files_sha256'].items():assert hashlib.sha256((p/n).read_bytes()).hexdigest()==h
  b=json.loads((p/'BUDGET.json').read_text());out['results'].append(dict(folder=str(p),totals=b['totals'],ledger_status=b['energy_ledger']['status']))
print(json.dumps(out))
''')
    save('STATUS.json',x);print(json.dumps(x))

def collect():
    d=json.loads((HERE/'SUBMISSION.json').read_bytes())
    x=remote('D='+repr(d)+'\n'+r'''
from pathlib import Path
import hashlib,json
r=Path(D['root']);assert hashlib.sha256((r/'EXECUTION_MANIFEST.json').read_bytes()).hexdigest()==D['manifest_sha256']
rows=[]
for p in [r/'gate']+list((r/'results').glob('*')):
 if not (p/'SEAL.json').exists():continue
 s=json.loads((p/'SEAL.json').read_text());assert s['status']=='completed'
 for n,h in s['files_sha256'].items():assert hashlib.sha256((p/n).read_bytes()).hexdigest()==h
 v=json.loads((p/'VALIDATION.json').read_text());a=json.loads((p/'RESULT.json').read_text());b=json.loads((p/'BUDGET.json').read_text())
 assert v['status']=='PASS' and b['energy_ledger']['numerical_sum_closed']
 L=36 if a['scope']=='full' else 1
 assert a['resource_contract']['configuration']['reduction']==16
 assert a['actions']['attention_QK_MAC']==L*2621440,'coarse SparQ dimension remains32; r16 denotes reduction lanes'
 expected=L*26214400+(2560*151936 if a['scope']=='full' else 0)
 assert a['actions']['digital_BF16_MAC']==expected
 rows.append(dict(case=p.name,remote=str(p),files_sha256=dict(s['files_sha256'],**{'SEAL.json':hashlib.sha256((p/'SEAL.json').read_bytes()).hexdigest()}),
  scope=a['scope'],seed=a['seed'],time_ms=a['simulated_ms'],totals=b['totals'],configuration_sha256=a['configuration_sha256'],
  FP32_reduction_lanes=16,SparQ_dimensions=32,logical_work_checked=True))
print(json.dumps(dict(rows=rows)))
''')
    archive=WORKSPACE/'project_archives/tlm_energy225_20261108';archive.mkdir(exist_ok=True)
    with client.connect(client.load_password()) as ssh:
        with ssh.open_sftp() as s:
            for row in x['rows']:
                dest=archive/row['case'];dest.mkdir(exist_ok=True)
                for n,h in row['files_sha256'].items():
                    p=dest/n
                    if p.exists():assert sha(p.read_bytes())==h,'Do not overwrite distinct result'
                    else:s.get(row['remote']+'/'+n,str(p))
                    assert sha(p.read_bytes())==h
                row['local_archive']=str(dest)
    save('COLLECTION.json',x)
    print(json.dumps(dict(sealed_cases=len(x['rows']),cases=[r['case'] for r in x['rows']])))

if __name__=='__main__':globals()[sys.argv[1]]()
