"""Resume the durable submission receipt; never resubmit the accepted tail array."""
from pathlib import Path
import json,ops
HERE=Path(__file__).resolve().parent/'tail_recovery_20261109'
assert not (HERE/'SUBMISSION.json').exists()
D=json.loads((HERE/'PARTIAL_SUBMISSION.json').read_bytes())
x=ops.remote('D='+repr(D)+'\n'+r'''
from pathlib import Path
import hashlib,json,subprocess
r=Path(D['root']);d=json.loads((r/'SUBMISSION.json').read_bytes());assert d['tail_job']==D['tail_job']
assert 'aggregate_job' not in d,'Inspect existing aggregator instead'
assert hashlib.sha256((r/'MANIFEST.json').read_bytes()).hexdigest()==d['manifest_sha256']
repair=Path(d['manifest']['repair_root'])
for index in (25,26):
 p=next((repair/'results/full').glob('%02d_*'%index));seal=json.loads((p/'SEAL.json').read_bytes())
 for n,h in seal['files_sha256'].items():assert hashlib.sha256((p/n).read_bytes()).hexdigest()==h
 assert json.loads((p/'RESULT.json').read_bytes())['status']=='completed'
# Finished316/317 may be evicted from the Slurm controller; their sealed work is checked above.
deps='afterany:38631668,afterok:38634114:38634115:'+d['tail_job']
p=subprocess.run(['sbatch','--parsable','--dependency='+deps,'--job-name=cm245_aggregate_complete','--output='+str(r/'logs/aggregate-%j.log'),str(r/'aggregate.sbatch')],stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
assert p.returncode==0,p.stderr
d['aggregate_job']=p.stdout.strip();d['aggregate_dependencies']=deps
(r/'SUBMISSION.json').write_text(json.dumps(d,indent=2)+'\n')
p=subprocess.run(['scontrol','show','job','-o','38634118'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
if p.returncode==0:
 assert 'JobState=PENDING' in p.stdout and 'JobName=cm245_aggregate_fixed' in p.stdout
 subprocess.run(['scancel','38634118'],check=True);d['retired_pending_aggregate']='38634118'
d['status']='THREE_UNSTARTED_TAILS_SUBMITTED_NO_EXECUTION_SOURCE_CHANGE'
d['initial_aggregate_dependency_rejection']='Completed38634116/17alreadysealed; removed from live-only dependencies, no tail resubmission'
(r/'SUBMISSION.json').write_text(json.dumps(d,indent=2)+'\n')
print(json.dumps(d))
''')
(HERE/'SUBMISSION.json').write_bytes((json.dumps(x,indent=2)+'\n').encode())
print(json.dumps({k:x[k] for k in ('status','tail_job','aggregate_job','retired_pending_aggregate','aggregate_dependencies')}))
