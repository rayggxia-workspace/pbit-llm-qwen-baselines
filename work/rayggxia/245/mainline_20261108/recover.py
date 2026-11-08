import json,ops
d=json.loads((ops.HERE/'UPLOAD.json').read_bytes())
x=ops.remote('D='+repr(d)+'\n'+r'''
from pathlib import Path
import json,subprocess
r=Path(D['root']);p=r/'SUBMISSION.json'
x=dict(receipt=json.loads(p.read_text()) if p.exists() else None)
for key,cmd in [('queue',['squeue','-h','-u','t6s011227','-o','%A|%j|%T|%M|%C']),
 ('partition',['scontrol','show','partition','v6_384'])]:
 q=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True);x[key]=q.stdout
print(json.dumps(x))
''')
ops.save('SUBMISSION_RECOVERY.json',x)
if x['receipt'] is not None:ops.save('SUBMISSION.json',x['receipt'])
print(json.dumps(x))
