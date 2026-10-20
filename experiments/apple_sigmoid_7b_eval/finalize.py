"""CPU-only post-run receipt and SHA index; starts after the GPU job terminates."""
from pathlib import Path
import datetime,hashlib,json,os,pwd,subprocess
P=Path('/home/Weican_Chen/projects/apple-sigmoid-7b-eval-20261019');u=pwd.getpwuid(os.getuid())
assert u.pw_name=='Weican_Chen' and str(Path(u.pw_dir).resolve())=='/home/Weican_Chen' and P.resolve()==P and P.is_relative_to(Path(u.pw_dir))
assert os.environ.get('CUDA_VISIBLE_DEVICES')=='' and os.environ.get('SLURM_JOB_ID')
r=subprocess.run(['/opt/slurm/21.08.8/bin/scontrol','show','job','2542'],capture_output=True,text=True)
if r.returncode==0:
 assert 'UserId=Weican_Chen(1002)' in r.stdout
 f=P/'reports/scheduler-first-terminal-2542.txt'
 if not f.exists():f.write_text(r.stdout)
state=json.loads((P/'reports/gpu_fp32_status.json').read_text());missing=[];counts={}
expected={'boolq':3270,'piqa':1838,'hellaswag':10042,'winogrande':1267,'arc_easy':2376,'arc_challenge':1172}
for kind in ['softmax','sigmoid']:
 base=P/'reports/float32'/kind;counts[kind]={}
 for name,n in expected.items():
  f=base/(name+'_samples.jsonl')
  if not f.exists():missing.append(str(f));continue
  with f.open('rb') as h:actual=sum(1 for _ in h)
  counts[kind][name]=actual
  if actual!=n:missing.append(str(f)+' wrong row count')
 for name in ['ppl.json','six_task_summary.json']:
  f=base/name
  if not f.exists() or not json.loads(f.read_text()).get('complete'):missing.append(str(f))
files=[]
for root in [P/'reports/float32',P/'source/run-v6']:
 for f in sorted(root.rglob('*')):
  if f.is_file():
   h=hashlib.sha256()
   with f.open('rb') as stream:
    for block in iter(lambda:stream.read(8*1024*1024),b''):h.update(block)
   files.append({'path':f.relative_to(P).as_posix(),'bytes':f.stat().st_size,'sha256':h.hexdigest()})
(P/'reports/final_artifact_manifest.json').write_text(json.dumps({'code_commit':'6d3d5d5a64a7709aab5733f38269c1b331521cd2','gpu_job':'2542','files':files},indent=2)+'\n')
complete=state.get('state')=='COMPLETED' and not missing
report={'finalizer_job':os.environ['SLURM_JOB_ID'],'gpu_job':'2542','updated_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'finalizer_completed':True,'paired_full_quality_complete':complete,'scheduler_rc':r.returncode,'gpu_state':state,'sample_counts':counts,'missing_or_invalid':missing,'artifact_manifest_sha256':hashlib.sha256((P/'reports/final_artifact_manifest.json').read_bytes()).hexdigest()}
(P/'reports/finalization_status.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
if not complete:raise SystemExit(1)
