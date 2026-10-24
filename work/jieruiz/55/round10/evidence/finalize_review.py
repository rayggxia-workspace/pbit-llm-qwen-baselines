from pathlib import Path
import subprocess,json,hashlib,zipfile,shutil
A=Path(__file__).resolve().parent;R=A.parent.parent;W=R/'tmp/pr55-review-round10-20261024'
def git(*args):return subprocess.check_output(['git','-C',str(W),*args])
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
initial={p['number']:p for p in load(A/'OPEN_PRS.json')};fresh={p['number']:p for p in load(A/'PREFLIGHT_OPEN.json')}
assert set(initial)==set(fresh)
for n in initial:assert initial[n]['head']['sha']==fresh[n]['head']['sha'],n
assert load(A/'PREFLIGHT_BASE.json')['commit']['sha']=='e1b23d7766303a502934d8b6eb45b9209bbb58b9'
def tree(ref):
    d={}
    for row in git('ls-tree','-rz',ref).split(b'\0'):
        if row:
            meta,p=row.split(b'\t');d[p.decode()]=meta.split()[2].decode()
    return d
head=tree('HEAD');base=tree('e1b23d7766303a502934d8b6eb45b9209bbb58b9');out={}
for n in [161,164,165,166]:
    sha=fresh[n]['head']['sha'];git('merge-base','--is-ancestor',sha,'HEAD');src=tree(sha)
    mb=git('merge-base',sha,'e1b23d7766303a502934d8b6eb45b9209bbb58b9').decode().strip();old=tree(mb)
    paths=[p for p,b in src.items() if old.get(p)!=b and (p.startswith(('qwen3/','architecture_tlm/','digital_circuit_simulation_registry/records/')))]
    bad=[p for p in paths if head.get(p)!=src[p]];assert not bad,(n,bad)
    out[str(n)]={'head':sha,'unchanged_source_blobs':len(paths),'paths':paths}
for n in [137,143,147,149,153,155,160,163]:
    assert subprocess.run(['git','-C',str(W),'merge-base','--is-ancestor',fresh[n]['head']['sha'],'HEAD']).returncode==1,n
save(A/'SOURCE_BLOBS_VERIFIED.json',out)
with zipfile.ZipFile(R/'digital_ppa8_ss_tt_100_20261023_v2.zip') as z:
    mp=next(p for p in z.namelist() if p.endswith('/package_manifest.json'));prefix=mp.rsplit('/',1)[0]+'/'
    checked=[]
    for rel in load(W/'qwen3/training/sc_qat_20261023/SCAN_MANIFEST.json') if False else json.loads(z.read(mp))['files']:
        p=None
        if rel.startswith('rtl/'):p='architecture_tlm/digital_ppa_v1/'+rel
        elif rel.startswith('conversion/'):p='format_conversion_rtl_20261016/rtl/'+rel.split('/',1)[1]
        elif rel=='reference/original_validate.py':p='architecture_tlm/digital_ppa_v1/sim/validate.py'
        elif rel=='reference/reference.py':p='format_conversion_rtl_20261016/sim/reference.py'
        if p:
            assert z.read(prefix+rel)==git('show','HEAD:'+p),p
            checked.append(p)
save(A/'164_DEPENDENCY_BLOBS.json',checked)
for p in (W/'qwen3/training/sc_qat_20261023').glob('*.json'):load(p)
cmd=[str(Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'),'-B','-X','utf8']
for tag,args in [('registry_check',['digital_circuit_simulation_registry/registry.py','check']),('registry_tests',['-m','unittest','discover','-s','digital_circuit_simulation_registry','-p','test*.py'])]:
    r=subprocess.run(cmd+args,cwd=W,capture_output=True,text=True,encoding='utf-8');assert r.returncode==0,r.stderr
    (A/(tag+'.log')).write_text(r.stdout+r.stderr,encoding='utf-8',newline='\n');save(A/(tag+'.json'),{'command':cmd+args,'rc':r.returncode,'cwd':str(W)})
print('Source blobs, frozen dependencies, JSON templates and registry PASS', {n:v['unchanged_source_blobs'] for n,v in out.items()},'dependencies',len(checked))
