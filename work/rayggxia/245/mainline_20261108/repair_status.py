"""Read-only repair-aware status;verify seals without restarting any job."""
from pathlib import Path
import json,ops

HERE=Path(__file__).resolve().parent
d=json.loads((HERE/'repair3/SUBMISSION.json').read_bytes())
x=ops.remote('D='+repr(d)+'\n'+r'''
from pathlib import Path
import datetime,hashlib,json,subprocess
r=Path(D['root']);o=Path(D['parent_root'])
sha=lambda b:hashlib.sha256(b).hexdigest()
assert sha((r/'SNAPSHOT_MANIFEST.json').read_bytes())==D['manifest_sha256']
assert sha((o/'SNAPSHOT_MANIFEST.json').read_bytes())==D['parent_manifest_sha256']
x=dict(checked_UTC=datetime.datetime.utcnow().isoformat(),roots=dict(original=str(o),repair=str(r)),completed=[],gates=[])
f=r/'RECOVERY_JOBS.json';receipt=json.loads(f.read_bytes()) if f.exists() else None;x['recovery_jobs']=receipt
ids=['38631668',D['gate_job'],D['coordinator_job']]
if receipt:ids+=[receipt['lost_workers']]+[j['job'] for j in receipt['deep_jobs']]+[receipt['aggregate_job']]
ids=','.join(str(j) for j in ids if j)
for k,c in [('queue',['squeue','-h','-j',ids,'-o','%A|%j|%T|%M|%C|%R']),('accounting',['sacct','-n','-X','-P','-j',ids,'-o','JobID,State,Elapsed,ExitCode,AllocCPUS'])]:
 p=subprocess.run(c,stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True);assert p.returncode==0,p.stderr;x[k]=p.stdout
for root,phase,dest in [(o,'full','completed'),(r,'full','completed'),(r,'pilot','gates')]:
 for seal in sorted((root/'results'/phase).glob('*/SEAL.json')):
  sf=json.loads(seal.read_bytes())
  for n,h in sf['files_sha256'].items():assert sha((seal.parent/n).read_bytes())==h,(seal.parent,n)
  z=json.loads((seal.parent/'RESULT.json').read_bytes());v=json.loads((seal.parent/'VALIDATION.json').read_bytes());b=json.loads((seal.parent/'BUDGET.json').read_bytes())
  assert z['status']=='completed' and v['status']=='PASS'
  assert z['snapshot_manifest_sha256']==sha((root/'SNAPSHOT_MANIFEST.json').read_bytes())
  if phase=='full':assert z['includes_head'] and z['layers']==z['shape']['layers']
  x[dest].append(dict(path=str(seal.parent),case_index=int(seal.parent.name.split('_')[0]),model=z['model'],clock_MHz=z['clock_MHz'],scheme=z['scheme'],seed=z['seed'],
   layers=z['layers'],time_ms=z['time_ms'],system4pJ_mJ=b['system_mJ_by_pJbit']['4.0'],onchip_mJ=b['onchip_mJ'],area55_mm2=b['area55_mm2'],
   source_manifest_sha256=z['snapshot_manifest_sha256'],files_sha256=sf['files_sha256']))
assert len({z['case_index'] for z in x['completed']})==len(x['completed'])
x['repair_log_tails']={p.name:p.read_text(errors='replace')[-1300:] for p in (r/'logs').glob('*.log')}
print(json.dumps(x))
''')
out=HERE/'repair3/VERIFIED_STATUS.json';out.write_bytes((json.dumps(x,indent=2)+'\n').encode())
print(json.dumps(dict(checked_UTC=x['checked_UTC'],verified_full=len(x['completed']),verified_repair_gates=len(x['gates']),
 recovery_jobs=x['recovery_jobs'],queue=x['queue'],accounting=x['accounting'],status_file=str(out))))
