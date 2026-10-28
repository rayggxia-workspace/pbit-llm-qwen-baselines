from deploy_fixed import remote,W,A,save
import json,base64,hashlib
d=json.loads((W/'FIXED_SOURCE.json').read_bytes())
code="""import pathlib,json,hashlib,base64
r=pathlib.Path(ROOT)
paths=list(r.glob('slurm-*.log'))+list((r/'results').glob('*.json'))+list(r.glob('*.sbatch'))
print(json.dumps({str(p.relative_to(r)):dict(data=base64.b64encode(p.read_bytes()).decode(),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in paths}))
""".replace('ROOT',repr(d['root']))
data=json.loads(remote(code));index={}
for name,m in data.items():
    b=base64.b64decode(m['data']);assert hashlib.sha256(b).hexdigest()==m['sha256']
    p=A/name;p.parent.mkdir(parents=True,exist_ok=True)
    if p.exists():assert p.read_bytes()==b
    else:p.write_bytes(b)
    index[name]=dict(sha256=m['sha256'],bytes=len(b))
save(W/'FIXED_FAILURE.json',dict(source=d,job='3302',cpu='3301',status='failed assertion on all-zero fixed-reference P8 odds; no complete metrics',
    correction='v2 records invalid stationary rows explicitly, no probability fallback; v1 source retained immutable',archive=str(A),files=index))
print('failure source/logs archived and hashed',len(index))
