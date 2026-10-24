import hashlib,io,json,subprocess,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
def git(*a):return subprocess.check_output(['git',*a],cwd=ROOT)
head=git('rev-parse','HEAD').decode().strip()
paths=git('ls-tree','-r','--name-only',head,'qwen3/and_direct','qwen3/nonlinear_width','qwen3/fixed_scale').decode().splitlines()
paths+=['qwen3/baselines/support.py']
paths+=['qwen3/stochastic/vendor/'+n+'.py' for n in ('core','range_core','shared_counts','stratified_core','scoring')]
assert not git('status','--porcelain','--',*paths).strip()
manifest=dict(repository='rayggxia-workspace/pbit-llm-qwen-baselines',commit=head,files_sha256={})
out=ROOT/'work/jieruiz/173'/('source-'+head[:12]+'.tar.gz')
with tarfile.open(out,'x:gz') as tar:
    def add(name,data):
        info=tarfile.TarInfo(name);info.size=len(data);info.mode=0o444
        tar.addfile(info,io.BytesIO(data))
    for name in paths:
        data=git('show',head+':'+name);manifest['files_sha256'][name]=hashlib.sha256(data).hexdigest();add(name,data)
    add('execution.json',(json.dumps(manifest,indent=2)+'\n').encode())
r=dict(commit=head,path=str(out),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),files=manifest['files_sha256'])
(ROOT/'work/jieruiz/173/PACKAGE.json').write_bytes((json.dumps(r,indent=2)+'\n').encode())
print(json.dumps({k:v for k,v in r.items() if k!='files'}))
