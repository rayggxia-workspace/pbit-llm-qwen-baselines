"""Inspect and relax our own three-case array, preserving frozen execution."""
from pathlib import Path
import json,sys
H=Path(__file__).resolve().parent
sys.path.insert(0,str(H.parent/'digital250_20261110'));from ops import remote
code=r'''
import subprocess,json,datetime,os
def call(args):
    p=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
    return dict(args=args,rc=p.returncode,out=p.stdout.strip(),err=p.stderr.strip())
before=call(['scontrol','show','job','38650228'])
assert before['rc']==0 and 'tlm28d_full_34375c559476' in before['out'] and os.environ['USER'] in before['out']
update=call(['scontrol','update','JobId=38650228','ArrayTaskThrottle=3']);assert update['rc']==0,update
after=call(['scontrol','show','job','38650228'])
queue=call(['squeue','-j','38650228','-h','-o','%i|%T|%R|%C'])
capacity=call(['sinfo','-p','v6_384','-h','-o','%D|%C'])
print(json.dumps(dict(status='USER_ARRAY_THROTTLE_CHANGED_2_TO3',observed_UTC=datetime.datetime.utcnow().isoformat(),
    before=before,update=update,after=after,queue=queue,partition_capacity=capacity,
    not_global_server_two_job_limit=True,no_restart_or_source_change=True)))
'''
x=remote(code);(H/'THROTTLE_UPDATE.json').write_bytes((json.dumps(x,indent=2)+'\n').encode())
print(json.dumps({k:v for k,v in x.items() if k in ('status','observed_UTC','update','queue','partition_capacity')}))
