"""Read-only status of all live workers and the corrected complete-batch aggregate."""
from pathlib import Path
import json,ops
HERE=Path(__file__).resolve().parent/'tail_recovery_20261109'
D=json.loads((HERE/'SUBMISSION.json').read_bytes())
x=ops.remote('D='+repr(D)+'\n'+r'''
from pathlib import Path
import datetime,hashlib,json,subprocess
r=Path(D['root']);original=Path(D['manifest']['original_root']);repair=Path(D['manifest']['repair_root'])
assert hashlib.sha256((r/'MANIFEST.json').read_bytes()).hexdigest()==D['manifest_sha256']
for n,h in D['manifest']['execution_files_sha256'].items():assert hashlib.sha256((original/n).read_bytes()).hexdigest()==h
out=dict(UTC=datetime.datetime.utcnow().isoformat(),root=str(r))
ids='38631668,38634114,38634115,'+D['tail_job']+','+D['aggregate_job']
out['queue']=subprocess.check_output(['squeue','-h','-j',ids,'-o','%i|%T|%M|%C|%R'],universal_newlines=True)
out['tail_logs']={}
for p in (r/'logs').glob('tail*.log'):
 lines=p.read_text(errors='replace').splitlines();last=None
 for line in reversed(lines):
  try:z=json.loads(line)
  except:continue
  if 'stage' in z:last=z;break
 out['tail_logs'][p.name]=dict(last=last,traceback_present=any('Traceback' in line for line in lines),tail='\n'.join(lines[-2:]))
out['durations']={}
for root in (original,repair):
 for p in (root/'results/full').glob('*/SEAL.json'):
  z=json.loads((p.parent/'RESULT.json').read_bytes());out['durations'][int(p.parent.name.split('_')[0])]=z.get('wall_seconds')
print(json.dumps(out))
''')
(HERE/'STATUS.json').write_bytes((json.dumps(x,indent=2)+'\n').encode())
print(json.dumps(x))
