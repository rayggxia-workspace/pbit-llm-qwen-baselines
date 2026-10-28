"""Own immutable source staging, checksum verification, and Slurm entrypoints."""
import argparse,base64,hashlib,io,json,pathlib,subprocess,tarfile
R=pathlib.Path(__file__).resolve().parents[3]
W=pathlib.Path(__file__).resolve().parent
SSH=['C:/Windows/System32/OpenSSH/ssh.exe','-F','C:/Users/86134/.ssh/lab-server-ai.ssh_config','-o','BatchMode=yes','lab-server-ai']
ROOT='/home/Hongjie_Zeng/projects/attention-sparq-ising-issue198-20261028'
PY='/home/Hongjie_Zeng/projects/pbit-qwen3-baseline-20261023-issue136/venv/bin/python'

def remote(code):
    return subprocess.check_output(SSH+['bash -lc "python3 -"'],input=code.encode(),timeout=60).decode()

def stage():
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R).decode().strip()
    paths=subprocess.check_output(['git','ls-tree','-r','--name-only',commit,'experiments/sparq_ising_20261028'],cwd=R).decode().splitlines()
    files={p:subprocess.check_output(['git','show',commit+':'+p],cwd=R) for p in paths}
    assert files and all((R/p).read_bytes()==b for p,b in files.items())
    manifest=dict(commit=commit,files_sha256={p:hashlib.sha256(b).hexdigest() for p,b in files.items()})
    files['execution.json']=(json.dumps(manifest,indent=2)+'\n').encode()
    buf=io.BytesIO()
    with tarfile.open(fileobj=buf,mode='w:gz') as tar:
        for p,b in files.items():
            info=tarfile.TarInfo(p);info.size=len(b);tar.addfile(info,io.BytesIO(b))
    data=buf.getvalue();digest=hashlib.sha256(data).hexdigest()
    archive=pathlib.Path('C:/Users/86134/Documents/a_P_BIT/project_archives/attention_compare_issue198_20261027/quality')
    archive.mkdir(parents=True,exist_ok=True);(archive/(commit+'.tar.gz')).write_bytes(data)
    text=remote('''import base64,hashlib,io,json,os,pathlib,tarfile
root=pathlib.Path(ROOT)
assert pathlib.Path.home()==pathlib.Path('/home/Hongjie_Zeng')
root.mkdir(exist_ok=True)
assert root.stat().st_uid==os.getuid()
for n in ('logs','tmp','results'): (root/n).mkdir(exist_ok=True)
source=root/('source-'+COMMIT[:12]);source.mkdir(exist_ok=False)
data=base64.b64decode(DATA);assert hashlib.sha256(data).hexdigest()==DIGEST
with tarfile.open(fileobj=io.BytesIO(data),mode='r:gz') as tar:
 for item in tar.getmembers():
  dest=(source/item.name).resolve();assert dest.is_relative_to(source) and item.isfile()
  dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(tar.extractfile(item).read())
manifest=json.loads((source/'execution.json').read_bytes())
for p,sha in manifest['files_sha256'].items():assert hashlib.sha256((source/p).read_bytes()).hexdigest()==sha
print(json.dumps({'commit':COMMIT,'source':str(source),'root':str(root),'package_sha256':DIGEST,'files':len(manifest['files_sha256'])}))
'''.replace('ROOT',repr(ROOT)).replace('COMMIT',repr(commit)).replace('DATA',repr(base64.b64encode(data).decode())).replace('DIGEST',repr(digest)))
    receipt=json.loads(text)
    for name in ('QUALITY_SOURCE.json',f'QUALITY_SOURCE_{commit[:12]}.json'):
        (W/name).write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(text)

def submit(phase,dependency=None,samples=128):
    receipt=json.loads((W/'QUALITY_SOURCE.json').read_bytes());source=receipt['source'];sha=receipt['commit'][:12]
    assert not (W/f'QUALITY_SUBMISSION_{sha}_{phase}.json').exists(), 'already submitted; inspect receipt/queue'
    gpu=phase!='cpu';array=phase in ('short','full')
    script='#!/bin/bash\n#SBATCH --partition=gpu5090\n#SBATCH --cpus-per-task=4\n#SBATCH --mem='+('48G' if gpu else '8G')+'\n#SBATCH --time='+('24:00:00' if phase=='full' else '02:00:00')+'\n'
    if gpu:script+='#SBATCH --gres=gpu:1\n'
    if array:script+='#SBATCH --array=0-2%3\n'
    script+='set -euo pipefail\n'
    script+=f'export PYTHONPATH={source} PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false\n'
    script+=f'export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 TMPDIR={ROOT}/tmp\nexport TRITON_CACHE_DIR={ROOT}/triton-$SLURM_JOB_ID\ncd {source}\n'
    if phase=='cpu':
        script+=f'srun env CUDA_VISIBLE_DEVICES="" {PY} -B -m unittest experiments.sparq_ising_20261028.test_core -v\n'
        script+=f'srun env CUDA_VISIBLE_DEVICES="" {PY} -c "import os,torch; assert os.environ[\'CUDA_VISIBLE_DEVICES\']==\'\' and not torch.cuda.is_initialized(); print(\'CPU_NO_CUDA_OK\')"\n'
    else:
        script+=f'{PY} -u -m experiments.sparq_ising_20261028.run --root {ROOT} --phase {phase}'
        if array:script+=' --seed "$SLURM_ARRAY_TASK_ID"'
        if phase=='full':script+=f' --samples {samples}'
        script+='\n'
    code='''import json,pathlib,subprocess
source=pathlib.Path(SOURCE)
path=source/NAME
if path.exists():assert path.read_text()==SCRIPT
else:path.write_text(SCRIPT)
args=['sbatch','--parsable','--job-name',JOB,'--output',OUTPUT,'--error',OUTPUT]
if DEP:args+=['--dependency','afterok:'+DEP]
args+=[str(path)]
job=subprocess.check_output(args,text=True).strip()
print(json.dumps({'job':job,'phase':PHASE,'source':SOURCE,'dependency':DEP,'script':str(path)}))
'''.replace('SOURCE',repr(source)).replace('NAME',repr(phase+'.sbatch')).replace('JOB',repr('attn198-'+phase)).replace('OUTPUT',repr(ROOT+'/logs/'+sha+'-'+phase+'-%A_%a.out')).replace('DEP',repr(dependency)).replace('PHASE',repr(phase)).replace('SCRIPT',repr(script))
    text=remote(code);obj=json.loads(text)
    (W/f'QUALITY_SUBMISSION_{sha}_{phase}.json').write_text(json.dumps(obj,indent=2)+'\n',encoding='utf-8',newline='\n');print(text)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['stage','cpu','preflight','short','full']);p.add_argument('--dependency');p.add_argument('--samples',type=int,default=128);a=p.parse_args()
    if a.action=='stage':stage()
    else:submit(a.action,a.dependency,a.samples)
