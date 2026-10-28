"""Freeze a small diagnostic, submit once through Slurm, preserve receipts."""
from deploy_quality import remote,ROOT,PY,R,W
from pathlib import Path
import base64,hashlib,io,json,tarfile,sys,subprocess
A=Path('C:/Users/86134/Documents/a_P_BIT/project_archives/attention_compare_issue198_20261027/score_dtype_20261028')
def save(p,x):p.write_bytes((json.dumps(x,indent=2,ensure_ascii=False)+'\n').encode())
def main():
    action=sys.argv[1]
    if action=='check':
        print(remote("import subprocess;print(subprocess.check_output(['squeue','-u','Hongjie_Zeng','-o','%.18i %.12j %.8T %.10M %.15R'],text=True))"));return
    if action=='stage':
        files={p:(R/p).read_bytes() for p in ['experiments/attention_score_dtype_20261028/audit.py','experiments/sparq_ising_20261028/core.py','experiments/sparq_ising_20261028/config.json','experiments/sparq_ising_20261028/vendor/support.py','experiments/sparq_ising_20261028/vendor/plans.py']}
        manifest=dict(parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R).decode().strip(),files_sha256={p:hashlib.sha256(b).hexdigest() for p,b in files.items()},binding='exact working patch frozen by per-file SHA; later Git source must match')
        files['execution.json']=(json.dumps(manifest,indent=2)+'\n').encode();buf=io.BytesIO()
        with tarfile.open(fileobj=buf,mode='w:gz') as t:
            for p,b in files.items():
                m=tarfile.TarInfo(p);m.size=len(b);t.addfile(m,io.BytesIO(b))
        data=buf.getvalue();digest=hashlib.sha256(data).hexdigest();A.mkdir(exist_ok=False);(A/'source.tar.gz').write_bytes(data)
        root=ROOT+'/dtype-'+digest[:12]
        code="""import pathlib,os,base64,hashlib,tarfile,io,json
root=pathlib.Path(ROOT);assert root.parent.stat().st_uid==os.getuid();root.mkdir()
for n in ['tmp','source']: (root/n).mkdir()
b=base64.b64decode(DATA);assert hashlib.sha256(b).hexdigest()==SHA
with tarfile.open(fileobj=io.BytesIO(b),mode='r:gz') as t:
 for m in t.getmembers():
  p=(root/'source'/m.name).resolve();assert p.is_relative_to(root/'source') and m.isfile();p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(t.extractfile(m).read())
print(json.dumps(dict(root=str(root),package_sha256=SHA)))
""".replace('ROOT',repr(root)).replace('DATA',repr(base64.b64encode(data).decode())).replace('SHA',repr(digest))
        d=json.loads(remote(code));d['manifest']=manifest;save(W/'DTYPE_SOURCE.json',d);print(json.dumps(d));return
    d=json.loads((W/'DTYPE_SOURCE.json').read_bytes());root=d['root']
    if action=='submit':
        assert not (W/'DTYPE_SUBMISSION.json').exists()
        script=f'''#!/bin/bash
#SBATCH --partition=gpu5090
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --time=00:20:00
set -euo pipefail
export PYTHONPATH={root}/source PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 TMPDIR={root}/tmp
cd {root}/source
{PY} -u -m experiments.attention_score_dtype_20261028.audit --root {root}
'''
        code="""import pathlib,json,subprocess
r=pathlib.Path(ROOT);p=r/'audit.sbatch';receipt=r/'SUBMISSION.json';assert not receipt.exists() and not p.exists();p.write_text(SCRIPT)
job=subprocess.check_output(['sbatch','--parsable','--job-name','attn198-dtype','--output',str(r/'slurm-%j.log'),str(p)],text=True).strip()
d=dict(job=job,root=str(r),script_sha256=__import__('hashlib').sha256(p.read_bytes()).hexdigest());receipt.write_text(json.dumps(d));print(json.dumps(d))
""".replace('ROOT',repr(root)).replace('SCRIPT',repr(script))
        result=json.loads(remote(code));save(W/'DTYPE_SUBMISSION.json',result);print(json.dumps(result));return
    if action=='poll':
        code="""import pathlib,subprocess,json
r=pathlib.Path(ROOT);print(subprocess.check_output(['squeue','-u','Hongjie_Zeng','-o','%.18i %.12j %.8T %.10M %.15R'],text=True))
for p in r.glob('slurm-*.log'):print(p.read_text()[-5000:])
p=r/'results/COMPLETE.json';print(p.read_text() if p.exists() else 'PENDING')
""".replace('ROOT',repr(root));print(remote(code));return
    if action=='collect':
        code="""import pathlib,json,hashlib,base64
r=pathlib.Path(ROOT);assert (r/'results/COMPLETE.json').exists()
paths=list((r/'results').glob('*.json'))+list(r.glob('slurm-*.log'))+[r/'SUBMISSION.json',r/'audit.sbatch']
print(json.dumps({str(p.relative_to(r)):dict(sha256=hashlib.sha256(p.read_bytes()).hexdigest(),data=base64.b64encode(p.read_bytes()).decode()) for p in paths}))
""".replace('ROOT',repr(root));received=json.loads(remote(code));index={}
        for rel,m in received.items():
            b=base64.b64decode(m['data']);assert hashlib.sha256(b).hexdigest()==m['sha256'];p=A/rel;p.parent.mkdir(exist_ok=True,parents=True)
            if p.exists():assert p.read_bytes()==b
            else:p.write_bytes(b)
            index[rel]=dict(sha256=m['sha256'],bytes=len(b))
        complete=json.loads((A/'results/COMPLETE.json').read_bytes())
        for name,m in complete['files'].items():assert index['results/'+name]==m
        save(W/'DTYPE_COLLECTION.json',dict(archive=str(A),files=index));print(json.dumps(dict(files=len(index),archive=str(A))))
if __name__=='__main__':main()
