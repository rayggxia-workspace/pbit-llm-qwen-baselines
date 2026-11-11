"""Immutable paired-path integration plus finite actual-head probes; CPU only."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import ast,hashlib,json,subprocess,sys,time
H=Path(__file__).resolve().parent;ROOT=H.parents[3];WS=ROOT.parents[1];D=ROOT/'architecture_tlm/process_28nm'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,x):p.write_bytes((json.dumps(x,indent=2)+'\n').encode())
names=['run_whole.py','whole_model.py','whole_pricing.py','pricing250.py','candidate_sram.py',
       'sram_characterization.py','mixed_sram.py','head_probe.py','refresh250.py']
for n in names:ast.parse((D/n).read_text(),filename=n)
names+=[f'{f}MHz/{n}.json' for f in (250,500) for n in ('BINDINGS','WHOLE_CONFIG')]
hashes={n:sha(D/n) for n in names};digest=hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest()[:12]
snap=H/('execution_'+digest);snap.mkdir(parents=True,exist_ok=True)
for name in names:
    p=snap/name;p.parent.mkdir(parents=True,exist_ok=True)
    if p.exists():assert sha(p)==hashes[name]
    else:p.write_bytes((D/name).read_bytes())
dump(snap/'MANIFEST.json',dict(files_sha256=hashes))
common=['--snapshot',str(WS/'tmp/cross-model245-20261106/work/rayggxia/245/mainline_20261108/revision2/snapshot'),
    '--runtime',str(WS/'project_archives/ffn_sram_batch204_20261106/runtime'),
    '--dependencies',str(WS/'project_archives/sram1216_225_20261106/dependencies')]
jobs=[]
for f in (250,500):
    name=f'p{f}';cmd=[sys.executable,'-X','utf8','-B',str(snap/'run_whole.py'),*common,
        '--bindings',str(snap/f'{f}MHz/BINDINGS.json'),'--cores','3' if f==250 else '2',
        '--layers','2' if f==250 else '1','--head','--head-probe-rows','384','--seed','17',
        '--backend','analytic','--out',str(H/name)]
    jobs.append(dict(name=name,command=cmd))
for rows in (1024,1152,2048):
    name='head250_'+str(rows);jobs.append(dict(name=name,command=[sys.executable,'-X','utf8','-B',str(snap/'head_probe.py'),
        '--execution',str(snap),*common,'--mhz','250','--rows',str(rows),'--out',str(H/name)]))
dump(H/'PLAN.json',dict(status='FROZEN_250_REFRESH_INTEGRATION_AND500_REGRESSION',execution=str(snap),
    files_sha256=hashes,jobs=jobs,workers=2,scope='250two_layers+384head;500one_layer+384head;250threeheadprobes;notfulltoken',GPU=0))
def run(j):
    out=H/j['name'];log=H/(j['name']+'.log')
    if (out/'SEAL.json').exists():
        s=json.loads((out/'SEAL.json').read_bytes());assert s['status']=='completed'
        for n,v in s['files_sha256'].items():assert sha(out/n)==v
        return dict(name=j['name'],status='sealed_reused')
    assert not out.exists(),'preserve failed attempt;use new validation folder'
    start=time.time();print(json.dumps(dict(name=j['name'],status='starting')),flush=True)
    with log.open('xb') as stream:code=subprocess.run(j['command'],cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT).returncode
    r=dict(name=j['name'],exit_code=code,wall_seconds=time.time()-start,log_sha256=sha(log))
    dump(H/(j['name']+'_RETURN.json'),r);print(json.dumps(r),flush=True);return r
with ThreadPoolExecutor(max_workers=2) as pool:
    results=list(pool.map(run,jobs))
assert all(x.get('exit_code',0)==0 for x in results)
print(json.dumps(dict(status='FIVE_FROZEN_CASES_COMPLETED')),flush=True)
