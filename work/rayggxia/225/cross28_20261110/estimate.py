"""Read actual layer throughput; keep scheduler throttles out of future runs."""
from pathlib import Path
import json,sys
H=Path(__file__).resolve().parent
sys.path.insert(0,str(H.parent/'digital250_20261110'));from ops import remote
code=r'''
from pathlib import Path
import json,datetime,statistics,subprocess,os
base=Path('/public3/home/t6s011227/pbit_chimera_pipeline_20260920')
now=datetime.datetime.utcnow()
def cmd(a):
    x=subprocess.run(a,stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
    return dict(rc=x.returncode,out=x.stdout.strip(),err=x.stderr.strip())
# User explicitly requests no artificial concurrency cap. Change only this
# live owned array's scheduling metadata, never source/seed/config or jobs.
prior=cmd(['scontrol','show','job','38650228'])
change=None
if prior['rc']==0:
    assert 'tlm28d_full_34375c559476' in prior['out'] and os.environ['USER'] in prior['out']
    change=cmd(['scontrol','update','JobId=38650228','ArrayTaskThrottle=0'])
    assert change['rc']==0,change
queue=cmd(['squeue','-u',os.environ['USER'],'-h','-o','%i|%j|%T|%M|%R'])
def progress(root,name):
    d=root/'work'/name;rows=[]
    if (d/'run.log').exists():
        for line in (d/'run.log').read_text(errors='replace').splitlines():
            try:
                x=json.loads(line)
                if 'stage' in x and 'wall_seconds' in x:rows.append(x)
            except ValueError:pass
    ex=json.loads((d/'EXIT.json').read_text()) if (d/'EXIT.json').exists() else None
    inv=json.loads((d/'INVOCATION.json').read_text()) if (d/'INVOCATION.json').exists() else None
    body=[x for x in rows if x['stage']=='residual']
    deltas=[y['wall_seconds']-x['wall_seconds'] for x,y in zip(body,body[1:])]
    f=next((x['wall_seconds'] for x in rows if x['stage']=='final_norm'),None)
    e=next((x['wall_seconds'] for x in rows if x['stage']=='lm_head'),None)
    elapsed=None
    if inv:
        stamp=inv['started_UTC'];fmt='%Y-%m-%dT%H:%M:%S.%f' if '.' in stamp else '%Y-%m-%dT%H:%M:%S'
        elapsed=(now-datetime.datetime.strptime(stamp,fmt)).total_seconds()
    return dict(name=name,job_id=inv.get('job_id') if inv else None,started_UTC=inv.get('started_UTC') if inv else None,
        elapsed_seconds=elapsed,exit_code=ex.get('exit_code') if ex else None,
        complete_layers=len(body),last_progress=rows[-1] if rows else None,
        median_layer_seconds=statistics.median(deltas[-5:]) if deltas else None,
        last_layer_seconds=deltas[-5:],first_layer_wall_seconds=body[0]['wall_seconds'] if body else None,
        finalnorm_wall_seconds=f,observed_head_seconds=e-f if e is not None and f is not None else None,
        last_body_wall_seconds=body[-1]['wall_seconds'] if body else None)
cross=base/'tlm28cross250_225_e0291ed6b5a9';mf=json.loads((cross/'FROZEN_MANIFEST.json').read_text())
cases=[]
for c in mf['full']:
    name='full_'+c['model']+'_'+c['scheme']+'_s'+str(c['seed'])
    x=progress(cross,name);x.update(model=c['model'],scheme=c['scheme'],seed=c['seed'],
        target_layers=28 if c['model']=='llama32_3b' else 30)
    gate='pilot_'+c['model']+'_'+c['scheme']+'_s17'
    x['pilot']=progress(cross,gate);cases.append(x)
qroot=base/'tlm28d250_full225_34375c559476'
for scheme in ('BF16_dense','W8_dense','W8_screen'):
    x=progress(qroot,'full_'+scheme);x.update(model='qwen3_4b',scheme=scheme,target_layers=36)
    x['pilot']=progress(qroot,'pilot_'+scheme);cases.append(x)
old=base/'tlm28p250_full225_3c811d6efe58'
head_reference=[progress(old,'seed'+str(s)) for s in (17,503,1009)]
print(json.dumps(dict(observed_UTC=now.isoformat(),array_unlimited_update=change,queue=queue,
    cases=cases,completed_Qwen_head_reference=head_reference)))
'''
x=remote(code,120);(H/'ETA_OBSERVATION.json').write_bytes((json.dumps(x,indent=2)+'\n').encode())
for c in x['cases']:
    print(json.dumps({k:v for k,v in c.items() if k!='pilot'}))
print(json.dumps(dict(observed_UTC=x['observed_UTC'],array_unlimited_update=x['array_unlimited_update'],
    head_seconds=[z['observed_head_seconds'] for z in x['completed_Qwen_head_reference']],queue=x['queue'])))
