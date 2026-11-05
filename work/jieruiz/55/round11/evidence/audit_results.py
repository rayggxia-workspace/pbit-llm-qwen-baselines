from pathlib import Path
import json,hashlib,subprocess,sys,time,math
A=Path(__file__).resolve().parent;R=A.parent.parent;W=R/'tmp/pr55-review-round11-20261025';B=W/'architecture_tlm/unified_v6/results'
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
records=[];files=[];remote=[]
for name in ['memory_20261025','scheduling_20261025','locality_20261025','hbm_20261025','resources_20261025','llmcompass_20261025/final']:
 for p in (B/name).rglob('MANIFEST.json'):
  m=load(p)
  if m.get('status')!='completed' or 'RESULT.json' not in m.get('files',{}):continue
  for rel,v in m['files'].items():
   q=p.parent/rel;expected=v.get('sha256') if isinstance(v,dict) else v
   if q.is_file():
    assert sha(q)==expected,('manifest mismatch',q)
    if isinstance(v,dict) and 'bytes' in v:assert q.stat().st_size==v['bytes'],q
    files.append({'path':str(q.relative_to(W)),'sha256':expected})
   else:remote.append({'manifest':str(p.relative_to(W)),'artifact':rel,'sha256':expected,'status':'remote_only_not_read_this_review'})
  records.append(str(p.relative_to(W)))
# Re-run bounded provenance/aggregate checks. Preserve all committed artifact bytes.
scripts=[['analyze_schedule.py','--require-complete'],['verify_delivery.py'],['verify_locality_delivery.py'],['analyze_hbm.py','--require-complete'],['analyze_resources.py'],['report_compass.py']]
old={p:p.read_bytes() for p in B.rglob('*') if p.is_file()};old.update({p:p.read_bytes() for p in (W/'work/jieruiz/186').glob('*.json')})
runs=[]
try:
 for args in scripts:
  cmd=[sys.executable,'-B','-X','utf8',str(W/'work/jieruiz/186'/args[0]),*args[1:]]
  t=time.monotonic();r=subprocess.run(cmd,cwd=W,capture_output=True,text=True,encoding='utf-8')
  (A/(args[0]+'.log')).write_text(r.stdout+r.stderr,encoding='utf-8')
  runs.append({'command':cmd,'rc':r.returncode,'seconds':time.monotonic()-t})
  assert r.returncode==0,(args,r.stderr)
finally:
 differences=[str(p.relative_to(W)) for p,b in old.items() if p.read_bytes()!=b]
 for p,b in old.items():
  if p.read_bytes()!=b:p.write_bytes(b)
 result={'completed_manifests':len(records),'local_files_checked':len(files),'remote_only_artifacts':len(remote),'manifests':records,'files':files,'remote_only':remote,'reruns':runs,'derived_rewrite_paths_restored':differences}
 (A/'RESULT_AUDIT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Completed manifests',len(records),'local hashes',len(files),'remote only',len(remote),'validators',len(runs))
