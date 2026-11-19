"""Stage a new immutable personal snapshot and submit CPU -> GPU via Slurm."""
from pathlib import Path
import base64
import hashlib
import json
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SSH = ['C:/Windows/System32/OpenSSH/ssh.exe', '-F',
       'C:/Users/86134/.ssh/lab-server-ai.ssh_config', '-o', 'BatchMode=yes',
       '-o', 'ConnectTimeout=12', 'lab-server-ai', 'python3 -']


def remote(code):
    p = subprocess.run(SSH, input=code, text=True, encoding='utf-8', capture_output=True, timeout=120)
    if p.returncode:
        raise RuntimeError(p.stdout[-2000:] + p.stderr[-3000:])
    return json.loads(p.stdout)


def save(name, obj):
    (HERE / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n',
                            encoding='utf-8', newline='\n')


def stage():
    assert not (HERE / 'SUBMISSION.json').exists(), 'Inspect existing submission; do not resubmit.'
    plan = json.loads((HERE / 'PLAN.json').read_bytes())
    plan['code_commit'] = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip()
    payload = dict(runner=base64.b64encode((HERE / 'runner.py').read_bytes()).decode(), plan=plan)
    code = 'D=' + repr(payload) + '\n' + r'''
from pathlib import Path
import base64,datetime,hashlib,json,os,subprocess
base=Path('/home/Hongjie_Zeng/projects/pbit-w8-dense-original-issue259-20261118')
base.mkdir(exist_ok=True)
runtime=Path('/home/Hongjie_Zeng/projects/ffn-stratified-validation-issue204-20261105/runtime_original')
runtime_manifest=runtime/'SOURCE_MANIFEST.json'
assert hashlib.sha256(runtime_manifest.read_bytes()).hexdigest()=='eb23a172efbd18e3e56060a6b10d2bfcde33fc7a014c5b10949038921ffb9076'
upstream=json.loads(runtime_manifest.read_bytes())
for name in ['qwen3/training/sc_qat/evaluate.py','qwen3/weight_quantization/pot64.py']:
 assert hashlib.sha256((runtime/name).read_bytes()).hexdigest()==upstream[name]
old_inputs=Path('/home/Hongjie_Zeng/projects/ffn-digital-rng-issue204-20261109/digital_dbf88bf32976/source/INPUTS.json')
inputs=json.loads(old_inputs.read_bytes())
inputs={k:inputs[k] for k in ['parent_model','parent_files_sha256','text','tokenizer']}
files={'runner.py':base64.b64decode(D['runner']),
 'PLAN.json':(json.dumps(D['plan'],sort_keys=True,indent=2)+'\n').encode(),
 'INPUTS.json':(json.dumps(inputs,sort_keys=True,indent=2)+'\n').encode(),
 'wt2_reference.py':(runtime/'qwen3/training/sc_qat/evaluate.py').read_bytes(),
 'pot64_reference.py':(runtime/'qwen3/weight_quantization/pot64.py').read_bytes()}
manifest={n:hashlib.sha256(b).hexdigest() for n,b in files.items()}
identity=hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest()
r=base/('run_'+identity[:12]);r.mkdir(exist_ok=False)
source=r/'source';source.mkdir()
for n,b in files.items():(source/n).write_bytes(b)
(source/'SOURCE_MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
for name in ['results','tmp','logs']:(r/name).mkdir()
python='/home/Hongjie_Zeng/projects/pbit-qwen3-baseline-20261023-issue136/venv/bin/python'
def script(phase):
 return '\n'.join(['#!/bin/bash','set -euo pipefail',
 'export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4',
 'export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false CUBLAS_WORKSPACE_CONFIG=:4096:8',
 'export TMPDIR='+str(r/'tmp'),
 'export TRITON_CACHE_DIR='+str(r/'tmp')+'/triton-$SLURM_JOB_ID',
 'export CUDA_CACHE_PATH='+str(r/'tmp')+'/cuda-$SLURM_JOB_ID',
 'cd '+str(source),python+' -u -B runner.py --phase '+phase+' --output '+str(r/'results'),''])
for phase in ['cpu','gpu']:(r/(phase+'.sh')).write_text(script(phase))
sbatch='/opt/slurm/21.08.8/bin/sbatch'
def submit(phase,extra):
 args=[sbatch,'--parsable','--partition=gpu5090','--job-name=w8dense259-'+phase,
       '--output='+str(r/'logs'/('%j-'+phase+'.out'))]+extra+[str(r/(phase+'.sh'))]
 p=subprocess.run(args,text=True,capture_output=True,check=True)
 return p.stdout.strip().split(';')[0],args
cpu,cpu_command=submit('cpu',['--cpus-per-task=1','--mem=8G','--time=00:15:00'])
gpu,gpu_command=submit('gpu',['--cpus-per-task=4','--mem=48G','--time=02:00:00',
                            '--gres=gpu:1','--dependency=afterok:'+cpu])
receipt=dict(issue=259,root=str(r),source=str(source),identity=identity,
 source_sha256=manifest,code_commit=D['plan']['code_commit'],jobs={'cpu':cpu,'gpu':gpu},
 commands={'cpu':cpu_command,'gpu':gpu_command},created_at_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat())
(r/'SUBMISSION.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt))
'''
    result = remote(code)
    save('SUBMISSION.json', result)
    print(json.dumps(result))


def status():
    d = json.loads((HERE / 'SUBMISSION.json').read_bytes())
    code = 'D=' + repr(d) + '\n' + r'''
from pathlib import Path
import datetime,hashlib,json,subprocess
r=Path(D['root']);out={'checked_at_UTC':datetime.datetime.now(datetime.timezone.utc).isoformat()}
out['accounting']=subprocess.getoutput('/opt/slurm/21.08.8/bin/sacct -n -P -j '+','.join(D['jobs'].values())+' --format=JobIDRaw,State,ExitCode,Elapsed')
out['queue']=subprocess.getoutput('/opt/slurm/21.08.8/bin/squeue -h -j '+','.join(D['jobs'].values())+' -o "%i %T %M %R"')
out['results']={}
for name in ['CPU_RESULT.json','GPU_QUANTIZER_GATE.json','REFERENCE.json','COMPLETE.json','QUANTIZATION_PROGRESS.json',
             'BF16_reference/PROGRESS.json','W8_dense_original/PROGRESS.json']:
 p=r/'results'/name
 if p.exists():out['results'][name]=json.loads(p.read_bytes())
out['logs']={p.name:p.read_text(errors='replace')[-1800:] for p in (r/'logs').glob('*.out')}
print(json.dumps(out))
'''
    result = remote(code)
    save('STATUS.json', result)
    print(json.dumps(result))


def collect():
    d = json.loads((HERE / 'SUBMISSION.json').read_bytes())
    code = 'D=' + repr(d) + '\n' + r'''
from pathlib import Path
import base64,hashlib,json
r=Path(D['root']);result=r/'results'
complete=json.loads((result/'COMPLETE.json').read_bytes());assert complete['status']=='completed'
names=['COMPLETE.json','PROTOCOL.json','QUANTIZATION.json','CPU_RESULT.json','GPU_QUANTIZER_GATE.json',
       'BF16_reference/RESULT.json','BF16_reference/WINDOWS.jsonl',
       'W8_dense_original/RESULT.json','W8_dense_original/WINDOWS.jsonl']
files={n:base64.b64encode((result/n).read_bytes()).decode() for n in names}
source=r/'source';manifest=json.loads((source/'SOURCE_MANIFEST.json').read_bytes())
for name,expected in manifest.items():
 data=(source/name).read_bytes();assert hashlib.sha256(data).hexdigest()==expected
 files['source/'+name]=base64.b64encode(data).decode()
files['source/SOURCE_MANIFEST.json']=base64.b64encode((source/'SOURCE_MANIFEST.json').read_bytes()).decode()
for k,n in [('BF16_result_sha256','BF16_reference/RESULT.json'),('W8_result_sha256','W8_dense_original/RESULT.json'),
            ('BF16_windows_sha256','BF16_reference/WINDOWS.jsonl'),('W8_windows_sha256','W8_dense_original/WINDOWS.jsonl'),
            ('quantization_sha256','QUANTIZATION.json'),('protocol_sha256','PROTOCOL.json')]:
 assert hashlib.sha256((result/n).read_bytes()).hexdigest()==complete[k]
print(json.dumps({'complete':complete,'files':files}))
'''
    result = remote(code)
    import io, zipfile
    archive = io.BytesIO()
    raw = {n:base64.b64decode(b) for n,b in result['files'].items()}
    for name in ['wt2_reference.py','pot64_reference.py']:
        data=raw['source/'+name]
        if (HERE/name).exists():assert (HERE/name).read_bytes()==data
        else:(HERE/name).write_bytes(data)
    for name, data in raw.items():
        if name.endswith('/WINDOWS.jsonl'):
            rows = [json.loads(line) for line in data.splitlines()]
            assert len(rows) == 292 and sum(row['targets'] for row in rows) == 299077
            cursor = 1
            for row in rows:
                assert row['first_scored'] == cursor
                cursor = row['end']
            score = json.loads(raw[name.replace('WINDOWS.jsonl','RESULT.json')])
            assert abs(sum(row['nll_sum'] for row in rows)-score['nll_sum']) < 1e-6
            assert all(v == 597062 for v in score['ffn_token_coverage'].values())
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for name,data in sorted(raw.items()):
            info=zipfile.ZipInfo(name);info.compress_type=zipfile.ZIP_DEFLATED;z.writestr(info,data)
    dest=Path('C:/Users/86134/Documents/a_P_BIT/project_archives/w8_dense_original259_20261118')
    dest.mkdir(exist_ok=True)
    target=dest/(d['identity'][:12]+'-results.zip');payload=archive.getvalue()
    if target.exists():assert target.read_bytes()==payload
    else:target.write_bytes(payload)
    save('RESULTS.json',dict(**result['complete'],archive=str(target),archive_sha256=hashlib.sha256(payload).hexdigest(),
         artifact_sha256={n:hashlib.sha256(b).hexdigest() for n,b in raw.items()},
         validation='matched292windows299077targets;continuouscoverage;NLLsum;all36layers597062tokens'))
    print(json.dumps(result['complete']))


if __name__ == '__main__':
    {'stage':stage,'status':status,'collect':collect}[sys.argv[1]]()
