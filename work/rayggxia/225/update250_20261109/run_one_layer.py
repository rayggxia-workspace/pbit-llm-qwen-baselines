from pathlib import Path
import hashlib,json,subprocess,time
H=Path(__file__).resolve().parent;p=json.loads((H/'PLAN.json').read_bytes());a=list(p['jobs'][0]['command'])
a[a.index('--layers')+1]='1';a[a.index('--out')+1]=str(H/'p250_one')
assert not (H/'p250_one').exists()
(H/'EXTRA_PLAN.json').write_bytes((json.dumps(dict(name='p250_one',command=a,execution=p['execution'],
    purpose='separate cold/steady layer and once-only embedding/finalnorm in explicit extrapolation'),indent=2)+'\n').encode())
start=time.time()
with (H/'p250_one.log').open('xb') as log:code=subprocess.run(a,stdout=log,stderr=subprocess.STDOUT).returncode
r=dict(exit_code=code,wall_seconds=time.time()-start,log_sha256=hashlib.sha256((H/'p250_one.log').read_bytes()).hexdigest())
(H/'p250_one_RETURN.json').write_bytes((json.dumps(r,indent=2)+'\n').encode());print(json.dumps(r));raise SystemExit(code)
