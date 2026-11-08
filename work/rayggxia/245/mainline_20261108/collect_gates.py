"""Collect small sealed gate receipts,not private runtime/fixtures."""
from pathlib import Path
import hashlib,json,ops
ops.HERE=Path(__file__).resolve().parent/'revision2'
d=json.loads((ops.HERE/'SUBMISSION.json').read_bytes());dd=json.loads((ops.HERE/'DISPATCH.json').read_bytes());ff=json.loads((ops.HERE/'FINALIZER_SUBMISSION.json').read_bytes())
data=ops.remote('D='+repr(d)+'\nDD='+repr(dd)+'\nFF='+repr(ff)+'\n'+r'''
from pathlib import Path
import hashlib,json
r=Path(D['root']);rows=[]
for f in (r/'results/pilot').glob('*/SEAL.json'):
 s=json.loads(f.read_bytes())
 for n,h in s['files_sha256'].items():assert hashlib.sha256((f.parent/n).read_bytes()).hexdigest()==h
 x=json.loads((f.parent/'RESULT.json').read_bytes());b=json.loads((f.parent/'BUDGET.json').read_bytes());v=json.loads((f.parent/'VALIDATION.json').read_bytes());assert v['status']=='PASS'
 rows.append(dict(path=str(f.parent),case=[x['model'],x['clock_MHz'],x['scheme']],layers=x['layers'],includes_head=x['includes_head'],
  time_ms=x['time_ms'],area55_mm2=b['area55_mm2'],wall_seconds=x['wall_seconds'],weight_read_bytes=v['weight_read_bytes'],
  source_manifest_sha256=x['snapshot_manifest_sha256'],seal_sha256=hashlib.sha256(f.read_bytes()).hexdigest(),files_sha256=s['files_sha256']))
assert len(rows)==8
print(json.dumps(dict(PILOT_SUMMARY=dict(status='8_SEALED_SINGLE_LAYER_GATES_NOT_FULL_TOKEN',rows=rows),
 FULL_SUBMISSION=json.loads((Path(DD['root'])/'FULL_SUBMISSION.json').read_bytes()),
 AGGREGATE_JOB=json.loads((Path(FF['root'])/'AGGREGATE_JOB.json').read_bytes()))))
''')
for name,value in data.items():(ops.HERE.parent/'delivery'/(name+'.json')).write_bytes((json.dumps(value,indent=2)+'\n').encode())
print(json.dumps(dict(gates=len(data['PILOT_SUMMARY']['rows']),full=data['FULL_SUBMISSION'],aggregate=data['AGGREGATE_JOB'])))
