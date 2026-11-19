"""Issue259 follow-up: three matched cached digital PPL configurations."""
from pathlib import Path
import base64
import importlib.util
import json
import subprocess
import sys

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[2]
spec=importlib.util.spec_from_file_location('original_ops',HERE.parent/'ops.py')
parent=importlib.util.module_from_spec(spec);spec.loader.exec_module(parent)


def save(name,value):
    (HERE/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')


def stage():
    assert not (HERE/'SUBMISSION.json').exists(),'Inspect existing follow-up; do not resubmit.'
    plan=json.loads((HERE/'PLAN.json').read_bytes())
    plan['local_code_commit']=subprocess.check_output(['git','-C',str(REPO),'rev-parse','HEAD'],text=True).strip()
    payload=dict(runner=base64.b64encode((HERE/'runner.py').read_bytes()).decode(),plan=plan)
    code='D='+repr(payload)+'\n'+r'''
from pathlib import Path
import base64,datetime,hashlib,json,subprocess
base=Path('/home/Hongjie_Zeng/projects/pbit-w8-dense-original-issue259-20261118')
prior=base/'run_d20328393f5f/source'
dep=Path('/home/Hongjie_Zeng/projects/attention-fig5-kwh128-gapfill-20261114/source-1cd58b43aabb')
dependency=json.loads((dep/'execution.json').read_bytes())
deps=['experiments/sparq_ising_20261028/'+n for n in [
 'core.py','adapter.py','scoring.py','test_core.py','vendor/plans.py','vendor/sparq_reference.py']]
files={'screen_runner.py':base64.b64decode(D['runner']),
 'PLAN.json':(json.dumps(D['plan'],indent=2)+'\n').encode(),
 'w8_original_reference.py':(prior/'runner.py').read_bytes(),
 'wt2_reference.py':(prior/'wt2_reference.py').read_bytes(),
 'pot64_reference.py':(prior/'pot64_reference.py').read_bytes(),
 'INPUTS.json':(prior/'INPUTS.json').read_bytes()}
assert hashlib.sha256(files['w8_original_reference.py']).hexdigest()=='b3a645d9b38c13dd6ff6e44bad22ae17ca51b36389980bfbc50617e6f8c709db'
for name in deps:
 b=(dep/name).read_bytes();assert hashlib.sha256(b).hexdigest()==dependency['files_sha256'][name],name
 files[name]=b
for package in ['experiments','experiments/sparq_ising_20261028','experiments/sparq_ising_20261028/vendor']:
 files[package+'/__init__.py']=b''
manifest={n:hashlib.sha256(b).hexdigest() for n,b in files.items()}
identity=hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest()
r=base/('screen_'+identity[:12]);r.mkdir(exist_ok=False)
src=r/'source';src.mkdir()
for n,b in files.items():
 p=src/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
(src/'SOURCE_MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
for n in ['results','logs','tmp']:(r/n).mkdir()
python='/home/Hongjie_Zeng/projects/pbit-qwen3-baseline-20261023-issue136/venv/bin/python'
for phase in ['cpu','gate','full']:
 lines=['#!/bin/bash','set -euo pipefail',
 'export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4',
 'export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false CUBLAS_WORKSPACE_CONFIG=:4096:8',
 'export TMPDIR='+str(r/'tmp'),
 'export TRITON_CACHE_DIR='+str(r/'tmp')+'/triton-$SLURM_JOB_ID',
 'export CUDA_CACHE_PATH='+str(r/'tmp')+'/cuda-$SLURM_JOB_ID',
 'cd '+str(src),python+' -u -B screen_runner.py --phase '+phase+' --output '+str(r/'results')+(' --index ${SLURM_ARRAY_TASK_ID}' if phase=='full' else ''),'']
 (r/(phase+'.sh')).write_text('\n'.join(lines))
sbatch='/opt/slurm/21.08.8/bin/sbatch'
commands={}
def submit(phase,extra):
 cmd=[sbatch,'--parsable','--partition=gpu5090','--job-name=digital259-'+phase,
 '--output='+str(r/'logs'/('%A_%a-'+phase+'.out'))]+extra+[str(r/(phase+'.sh'))]
 commands[phase]=cmd
 return subprocess.check_output(cmd,text=True).strip().split(';')[0]
cpu=submit('cpu',['--cpus-per-task=1','--mem=8G','--time=00:15:00'])
gate=submit('gate',['--gres=gpu:1','--cpus-per-task=4','--mem=48G','--time=01:00:00','--dependency=afterok:'+cpu])
full=submit('full',['--array=0-2','--gres=gpu:1','--cpus-per-task=4','--mem=48G','--time=06:00:00','--dependency=afterok:'+gate])
d=dict(root=str(r),source=str(src),identity=identity,source_sha256=manifest,
 dependency_execution=dependency['execution_identity'],local_code_commit=D['plan']['local_code_commit'],
 jobs={'cpu':cpu,'gate':gate,'full':full},modes=D['plan']['modes'],commands=commands,
 created_at_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat())
(r/'SUBMISSION.json').write_text(json.dumps(d,indent=2)+'\n')
print(json.dumps(d))
'''
    result=parent.remote(code);save('SUBMISSION.json',result);print(json.dumps(result))


def status():
    d=json.loads((HERE/'SUBMISSION.json').read_bytes())
    code='D='+repr(d)+'\n'+r'''
from pathlib import Path
import datetime,hashlib,json,subprocess
r=Path(D['root']);out={'checked_at_UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'queue':subprocess.getoutput('/opt/slurm/21.08.8/bin/squeue -h -j '+','.join(D['jobs'].values())+' -o "%i %j %T %M %R"'),
 'gates':{},'cases':{},'logs':{}}
for name in ['CPU_GATE.json','GPU_GATE.json']:
 p=r/'results'/name
 if p.exists():out['gates'][name]=json.loads(p.read_bytes())
for mode in D['modes']:
 p=r/'results'/mode/'COMPLETE.json'
 if p.exists():
  x=json.loads(p.read_bytes());raw=p.with_name('RESULT.json').read_bytes()
  assert hashlib.sha256(raw).hexdigest()==x['result_sha256'];out['cases'][mode]=x
 else:
  p=r/'results'/mode/'PROGRESS.json'
  if p.exists():out['cases'][mode]={'status':'running',**json.loads(p.read_bytes())}
for p in (r/'logs').glob('*.out'):out['logs'][p.name]=p.read_text(errors='replace')[-1300:]
print(json.dumps(out))
'''
    result=parent.remote(code);save('STATUS.json',result);print(json.dumps(result))


def collect():
    d=json.loads((HERE/'SUBMISSION.json').read_bytes())
    code='D='+repr(d)+'\n'+r'''
from pathlib import Path
import base64,hashlib,json,math
r=Path(D['root']);files={};summary=[];token_shas=set()
for mode in D['modes']:
 p=r/'results'/mode/'RESULT.json';raw=p.read_bytes();x=json.loads(raw)
 c=json.loads(p.with_name('COMPLETE.json').read_bytes())
 assert x['status']==c['status']=='completed' and hashlib.sha256(raw).hexdigest()==c['result_sha256']
 assert x['scored_tokens']==299077 and len(x['records'])==292 and x['tokens_per_layer']==[299077]*36
 cursor=1
 for row in x['records']:
  assert row['first_target']==cursor;cursor=row['last_target_exclusive']
 assert cursor==299078 and abs(math.fsum(q['nll_sum'] for q in x['records'])-x['nll_sum'])<1e-6
 assert abs(math.exp(x['nll_sum']/299077)-x['perplexity'])<1e-12
 assert x['no_sampling'] and x['no_training'] and x['no_trained_overlay']
 token_shas.add(x['token_ids_sha256'])
 files[mode+'/RESULT.json']=base64.b64encode(raw).decode()
 files[mode+'/COMPLETE.json']=base64.b64encode(p.with_name('COMPLETE.json').read_bytes()).decode()
 summary.append(dict(mode=mode,PPL=x['perplexity'],seconds=x['seconds'],job=x['job'],result_sha256=c['result_sha256']))
assert len(token_shas)==1
for name in ['CPU_GATE.json','GPU_GATE.json','W8_MAPS.json']:
 files[name]=base64.b64encode((r/'results'/name).read_bytes()).decode()
src=r/'source';m=json.loads((src/'SOURCE_MANIFEST.json').read_bytes())
for name,h in m.items():
 raw=(src/name).read_bytes();assert hashlib.sha256(raw).hexdigest()==h
 files['source/'+name]=base64.b64encode(raw).decode()
files['source/SOURCE_MANIFEST.json']=base64.b64encode((src/'SOURCE_MANIFEST.json').read_bytes()).decode()
print(json.dumps({'rows':summary,'files':files,'token_ids_sha256':next(iter(token_shas))}))
'''
    result=parent.remote(code)
    import hashlib,io,zipfile
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:
        for name,encoded in sorted(result['files'].items()):
            info=zipfile.ZipInfo(name);info.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(info,base64.b64decode(encoded))
    dest=Path('C:/Users/86134/Documents/a_P_BIT/project_archives/w8_dense_original259_20261118')
    dest.mkdir(exist_ok=True);p=dest/(d['identity'][:12]+'-screen-results.zip');raw=buf.getvalue()
    if p.exists():assert p.read_bytes()==raw
    else:p.write_bytes(raw)
    summary=dict(status='completed',rows=result['rows'],source_identity=d['identity'],
        archive=str(p),archive_sha256=hashlib.sha256(raw).hexdigest(),targets=299077,windows=292,
        token_ids_sha256=result['token_ids_sha256'],validation='sealSHA;continuouspositions;NLL;exp;36layers;no_sampling')
    save('RESULTS.json',summary);print(json.dumps(summary))


if __name__=='__main__':{'stage':stage,'status':status,'collect':collect}[sys.argv[1]]()
