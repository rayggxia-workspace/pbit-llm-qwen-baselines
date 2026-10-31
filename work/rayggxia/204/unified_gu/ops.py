"""Stage one small source zip and CPU->GPU gate->three-seed Slurm jobs.

Uses existing SSH configuration; never reads or publishes credentials.
"""
import argparse,ast,base64,datetime,hashlib,io,json,pathlib,subprocess,tarfile,zipfile

REPO=pathlib.Path(__file__).resolve().parents[4]
WORK=pathlib.Path(__file__).resolve().parent
ROOT='/home/Hongjie_Zeng/projects/pbit-gu-unified-code-20261030-issue204'
DEP='/home/Hongjie_Zeng/projects/pbit-qwen3-group64-scale-20261028-issue206/full-wt2-source-5d49ea97502d'
PY='/home/Hongjie_Zeng/projects/pbit-qwen3-baseline-20261023-issue136/venv/bin/python'
SSH=['C:/Windows/System32/OpenSSH/ssh.exe','-F','C:/Users/86134/.ssh/lab-server-ai.ssh_config','-o','BatchMode=yes','lab-server-ai']


def save(p,v):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n',encoding='utf-8',newline='\n')


def remote_python(code):
    ast.parse(code)
    return subprocess.check_output(SSH+['bash -l -s'],input=("/usr/bin/python3 - <<'CODEC_REMOTE_PY'\n"+code+"\nCODEC_REMOTE_PY\n").encode(),timeout=50)


def package():
    head=subprocess.check_output(['git','-C',str(REPO),'rev-parse','HEAD'],text=True).strip()
    src=REPO/'experiments/gu_unified_codec_20261030'
    files={p.relative_to(src.parent).as_posix():p.read_bytes() for p in sorted(src.iterdir()) if p.is_file()}
    for n,b in files.items():
        assert subprocess.check_output(['git','-C',str(REPO),'show',head+':experiments/'+n])==b,n
    tree=ast.parse((src/'run.py').read_text(encoding='utf-8'))
    modes=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='RUN_MODES' for t in n.targets))
    manifest=dict(source_commit=head,created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        files_sha256={k:hashlib.sha256(v).hexdigest() for k,v in files.items()},
        issue=204,owner='rayggxia',dependency_commit='5d49ea97502d2c11bf0745d50689b4c558c384d1',
        comparison=modes,protocol='1024-target suffix/all36FFN;not fullWT2')
    files['execution.json']=(json.dumps(manifest,indent=2)+'\n').encode()
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:
        for n,b in files.items():z.writestr(n,b)
    archive=REPO.parents[1]/'project_archives/gu_unified_codec204_20261030'/('source_'+head[:12]+'_'+'_'.join(modes[1:])+'_posix.zip')
    archive.parent.mkdir(parents=True,exist_ok=True);assert not archive.exists();archive.write_bytes(buf.getvalue())
    plan=dict(package=str(archive),bytes=archive.stat().st_size,sha256=hashlib.sha256(buf.getvalue()).hexdigest(),
              source_commit=head,remote_root=ROOT,remote_source=ROOT+'/source-'+head[:12],dependency_source=DEP,
              files_sha256=manifest['files_sha256'],stager_sha256=hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),no_credentials_or_PDK_or_model_data=True)
    save(WORK/'UPLOAD_PLAN.json',plan);print(json.dumps(plan,indent=2))


def stage():
    plan=json.loads((WORK/'UPLOAD_PLAN.json').read_bytes())
    b=pathlib.Path(plan['package']).read_bytes();assert hashlib.sha256(b).hexdigest()==plan['sha256']
    code=r'''import base64,hashlib,io,json,pathlib,subprocess,zipfile
p=PLAN;b=base64.b64decode(PAYLOAD);assert hashlib.sha256(b).hexdigest()==p['sha256']
root=pathlib.Path(p['remote_root']);root.mkdir(parents=True,exist_ok=True)
src=pathlib.Path(p['remote_source']);src.mkdir(exist_ok=False)
with zipfile.ZipFile(io.BytesIO(b)) as z:
 for n in z.namelist():
  assert not pathlib.PurePosixPath(n).is_absolute() and '..' not in pathlib.PurePosixPath(n).parts
 z.extractall(src)
m=json.loads((src/'execution.json').read_bytes())
for n,h in m['files_sha256'].items():assert hashlib.sha256((src/n).read_bytes()).hexdigest()==h,n
jobs=root/('jobs-'+m['source_commit'][:12]);jobs.mkdir(exist_ok=False)
logs=root/'logs';logs.mkdir(exist_ok=True)
common='#!/bin/bash\n#SBATCH --partition=gpu5090\n#SBATCH --cpus-per-task=4\n#SBATCH --mem=32G\n#SBATCH --time=00:20:00\nset -euo pipefail\ncd '+str(src)+'\nexport PYTHONDONTWRITEBYTECODE=1\nexport PYTHONPATH='+str(src)+':'+DEP+'\n'
tests='PY -u -B -m unittest gu_unified_codec_20261030.test_core qwen3.group_shared.test_group_sweep qwen3.group_shared.test_full_wt2 -v\n'
(jobs/'cpu.sbatch').write_text(common+'export CUDA_VISIBLE_DEVICES=""\n'+tests.replace('PY',PY))
(jobs/'gate.sbatch').write_text(common+tests.replace('PY',PY)+PY+' -u -B -m gu_unified_codec_20261030.run --phase gate --seed 0\n')
(jobs/'eval.sbatch').write_text(common+PY+' -u -B -m gu_unified_codec_20261030.run --phase eval --seed "${SLURM_ARRAY_TASK_ID}"\n')
def submit(name,extra):
 cmd=['sbatch','--parsable','--job-name=gu-codec204-'+name,'--output='+str(logs/(name+'-%A_%a.out'))]+extra+[str(jobs/(name+'.sbatch'))]
 return subprocess.check_output(cmd,text=True).strip().split(';')[0]
cpu=submit('cpu',[])
gate=submit('gate',['--dependency=afterok:'+cpu,'--gres=gpu:1'])
array=submit('eval',['--dependency=afterok:'+gate,'--gres=gpu:1','--array=0-2%3'])
receipt=dict(plan=p,cpu_job=cpu,gate_job=gate,array_job=array,result_root=str(root/'results'/m['source_commit'][:12]))
(root/('submission-'+m['source_commit'][:12]+'.json')).write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt))
'''.replace('PLAN',repr(plan)).replace('PAYLOAD',repr(base64.b64encode(b).decode()))
    code='PY='+repr(PY)+'\nDEP='+repr(DEP)+'\n'+code
    data=remote_python(code);v=json.loads(data);save(WORK/'SUBMISSION.json',v);print(data.decode())


def status():
    v=json.loads((WORK/'SUBMISSION.json').read_bytes())
    script='squeue -j '+','.join(v[k] for k in ('cpu_job','gate_job','array_job'))+' -o "%.18i %.25j %.10T %.9M %R"\n'
    script+='for j in '+ ' '.join(v[k] for k in ('cpu_job','gate_job','array_job'))+'; do scontrol show job "$j" 2>&1 | grep -E "JobId=|JobState=|RunTime=|Invalid job"; done\n'
    script+='for f in '+ROOT+'/logs/*'+v['cpu_job']+'* '+ROOT+'/logs/*'+v['gate_job']+'* '+ROOT+'/logs/*'+v['array_job']+'*; do test -f "$f" && tail -n 12 "$f"; done\n'
    r=subprocess.run(SSH+['bash -l -s'],input=script.encode(),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=45)
    print(r.stdout.decode())


def collect():
    v=json.loads((WORK/'SUBMISSION.json').read_bytes())
    code=r'''import hashlib,io,json,pathlib,sys,tarfile
v=RECEIPT;base=pathlib.Path(v['result_root']);files={}
for c in base.glob('*/complete.json'):
 d=json.loads(c.read_bytes());assert d['status']=='completed'
 for n,h in d['documents'].items():assert hashlib.sha256((c.parent/n).read_bytes()).hexdigest()==h
 for p in c.parent.glob('*.json'):files[str(p.relative_to(base))]=p.read_bytes()
for p in pathlib.Path(ROOT+'/logs').glob('*.out'):
 if any(j in p.name for j in (v['cpu_job'],v['gate_job'],v['array_job'])):files['logs/'+p.name]=p.read_bytes()
with tarfile.open(fileobj=sys.stdout.buffer,mode='w:gz') as t:
 for n,b in files.items():
  i=tarfile.TarInfo(n);i.size=len(b);t.addfile(i,io.BytesIO(b))
'''.replace('RECEIPT',repr(v)).replace('ROOT',repr(ROOT))
    b=remote_python(code);out=REPO/'experiments/gu_unified_codec_20261030/results'/v['plan']['source_commit'][:12]
    hashes={}
    with tarfile.open(fileobj=io.BytesIO(b),mode='r:gz') as t:
        for member in t.getmembers():
            assert member.isfile() and '..' not in pathlib.PurePosixPath(member.name).parts and not member.name.startswith('/')
            p=out/member.name;raw=t.extractfile(member).read();p.parent.mkdir(parents=True,exist_ok=True)
            if p.exists():assert p.read_bytes()==raw,str(p)
            else:p.write_bytes(raw)
            hashes[member.name]=hashlib.sha256(raw).hexdigest()
    save(WORK/'COLLECTION.json',dict(source=v['plan']['source_commit'],remote=v['result_root'],files_sha256=hashes))
    print('Collected',len(hashes),'files;', [p.parent.name for p in out.glob('*/complete.json')])


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=('package','stage','status','collect'));a=p.parse_args()
    globals()[a.action]()
