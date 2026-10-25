"""Verify sealed remote bytes before collecting small HBM records."""
import base64,gzip,hashlib,json,pathlib,subprocess,sys
R=pathlib.Path(__file__).resolve().parents[3];W=R/'work/jieruiz/186'
pipeline='--pipeline' in sys.argv
s=json.loads((W/('HBM_PIPELINE_SUBMISSION.json' if pipeline else 'HBM_SUBMISSION.json')).read_text())
script=r'''import base64,gzip,hashlib,json,pathlib,sys
r=pathlib.Path(REMOTE);files={};done=[];failed=[];pending=[]
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def keep(p):files[p.relative_to(r).as_posix()]=base64.b64encode(p.read_bytes()).decode()
for i in range(CASE_COUNT):
 p=r/'results'/('case_'+str(i));mf=p/'MANIFEST.json'
 if (p/'FAILURE.json').exists():failed.append(json.loads((p/'FAILURE.json').read_text()));keep(p/'FAILURE.json')
 if not mf.exists():
  if not (p/'FAILURE.json').exists():pending.append(i)
  continue
 m=json.loads(mf.read_text());assert m['status']=='completed'
 for name,meta in m['files'].items():assert sha(p/name)==meta['sha256'],str(p/name)
 for name in ['MANIFEST.json','RESULT_SUMMARY.json','EXECUTION.json']:keep(p/name)
 done.append(dict(index=i,case=m['case'],manifest_sha256=sha(mf)))
for rel in ['build/MANIFEST.json','build.py','build.sbatch','run.sbatch','probe/RESULTS.json']:
 p=r/rel
 if p.exists():keep(p)
sys.stdout.buffer.write(gzip.compress(json.dumps(dict(remote=str(r),completed=done,failed=failed,pending=pending,files=files)).encode()))
'''.replace('REMOTE',repr(s['remote'])).replace('CASE_COUNT',str(s.get('cases',17)))
b=subprocess.check_output(['ssh','-F','C:/Users/86134/.ssh/lab-server-ai.ssh_config','lab-server-ai','/usr/bin/python3 -'],input=script.encode())
d=json.loads(gzip.decompress(b));out=R/'architecture_tlm/unified_v6/results/hbm_20261025';out=out/'pipelined' if pipeline else out;out.mkdir(parents=True,exist_ok=True)
for rel,encoded in d.pop('files').items():
 p=pathlib.PurePosixPath(rel);assert not p.is_absolute() and '..' not in p.parts
 dest=out.joinpath(*p.parts);dest.parent.mkdir(parents=True,exist_ok=True);data=base64.b64decode(encoded)
 if dest.exists():assert dest.read_bytes()==data,'immutable bytes changed'
 else:dest.write_bytes(data)
(W/('HBM_PIPELINE_COLLECTION.json' if pipeline else 'HBM_COLLECTION.json')).write_text(json.dumps(d,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(completed=len(d['completed']),pending=d['pending'],failed=d['failed'])))
