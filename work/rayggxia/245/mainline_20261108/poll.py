import json,ops
d=json.loads((ops.HERE/'SUBMISSION.json').read_bytes());dispatch=json.loads((ops.HERE/'DISPATCH.json').read_bytes())
f=ops.HERE/'FINALIZER_SUBMISSION.json';finalizer=json.loads(f.read_bytes()) if f.exists() else None
x=ops.remote('D='+repr(d)+'\n'+'DISPATCH='+repr(dispatch)+'\nFINALIZER='+repr(finalizer)+'\n'+r'''
from pathlib import Path
import datetime,json,subprocess,hashlib
r=Path(D['root']);dr=Path(DISPATCH['root']);f=dr/'FULL_SUBMISSION.json'
full=json.loads(f.read_text()) if f.exists() else None
ids=[D['pilot_job'],DISPATCH['coordinator_job']]+([full['full_worker_job']] if full else [])
aggregation=None
if FINALIZER:
 ar=Path(FINALIZER['root']);af=ar/'AGGREGATE_JOB.json';aggregation=json.loads(af.read_text()) if af.exists() else None
 ids+=[FINALIZER['coordinator_job']]+([aggregation['job']] if aggregation else [])
p=subprocess.run(['squeue','-h','-j',','.join(ids),'-o','%i|%j|%T|%M|%C|%R'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
accounting=subprocess.run(['sacct','-n','-X','-P','-j',','.join(ids),'-o','JobID,State,ExitCode,Elapsed,AllocCPUS'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
out=dict(checked_UTC=datetime.datetime.utcnow().isoformat(),queue=p.stdout,accounting=accounting.stdout,full=full,aggregation=aggregation,sealed=[],logs={},pilot_gates=[])
for seal in (r/'results').rglob('SEAL.json'):
 s=json.loads(seal.read_text())
 for n,h in s['files_sha256'].items():assert hashlib.sha256((seal.parent/n).read_bytes()).hexdigest()==h
 q=json.loads((seal.parent/'RESULT.json').read_text())
 out['sealed'].append(dict(path=str(seal.parent.relative_to(r)),model=q['model'],clock=q['clock_MHz'],scheme=q['scheme'],layers=q['layers'],ms=q['time_ms']))
for log in (r/'logs').glob('*.log'):
 raw=log.read_text(errors='replace');out['logs'][log.name]=raw[-500:]
 for line in raw.splitlines():
  if 'SEALED_AND_GATE_VERIFIED' in line:out['pilot_gates'].append(json.loads(line))
for log in (dr/'logs').glob('*.log'):out['logs'][log.name]=log.read_text(errors='replace')[-500:]
if FINALIZER:
 for log in (ar/'logs').glob('*.log'):out['logs'][log.name]=log.read_text(errors='replace')[-500:]
 out['aggregate_seal_exists']=(ar/'summary/SEAL.json').exists()
print(json.dumps(out))
''')
ops.save('STATUS_CURRENT.json',x)
print(json.dumps(dict(checked=x['checked_UTC'],queue=x['queue'],full=x['full'],sealed=x['sealed'],
 pilot_gates_passed=len(x['pilot_gates']),aggregation=x['aggregation'],
 failures={k:v for k,v in x['logs'].items() if 'Traceback' in v or 'Error' in v})))
