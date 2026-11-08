"""Retire only the queued old coordinator; keep all pilot results/jobs."""
import json,ops
d=json.loads((ops.HERE/'DISPATCH.json').read_bytes())
x=ops.remote('D='+repr(d)+'\n'+r'''
import json,subprocess
job=D['coordinator_job']
p=subprocess.run(['scontrol','show','job','-o',job],stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
if p.returncode:raise RuntimeError('inspect state before cancellation:'+p.stderr)
assert 'JobState=PENDING' in p.stdout and 'JobName=cm245_dispatch' in p.stdout,p.stdout
q=subprocess.run(['scancel',job],stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
assert q.returncode==0,q.stderr
print(json.dumps(dict(job=job,cancelled=True,only_pending_coordinator=True,reason='logicalKV source-offset fix and cross-environment12cycle regression tolerance;new immutable revision2;healthy pilots retained')))
''')
ops.save('RETIRED_DISPATCH.json',x);print(json.dumps(x))
