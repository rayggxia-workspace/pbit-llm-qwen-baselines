from pathlib import Path,PurePosixPath
import subprocess,json,hashlib
A=Path(__file__).resolve().parent;R=A.parent.parent/'pbit-llm-qwen-baselines';H='91f68416acad0e8306b920b1b8ac779f3d24ad98'
def git(*a):return subprocess.check_output(['git','-C',str(R),*a])
changed=git('diff','--name-only','d83eeb1f...'+H,'--','architecture_tlm').decode().splitlines();allfiles=set(git('ls-tree','-r','--name-only',H).decode().splitlines());verified=[];external=[];source_versions=[]
for p in changed:
 if not p.endswith('MANIFEST.json'):continue
 m=json.loads(git('show',H+':'+p));files=m.get('files',{})
 if not isinstance(files,dict):continue
 for name,v in files.items():
  h=v.get('sha256') if isinstance(v,dict) else v
  if not isinstance(h,str) or len(h)!=64:continue
  target=(PurePosixPath(p).parent/name).as_posix()
  if target not in allfiles:
   if name in allfiles:source_versions.append({'manifest':p,'source':name,'recorded_sha256':h,'current_sha256':hashlib.sha256(git('show',H+':'+name)).hexdigest()})
   else:external.append({'manifest':p,'path':name,'sha256':h})
   continue
  b=git('show',H+':'+target);actual=hashlib.sha256(b).hexdigest();assert actual==h,(p,target,h,actual)
  verified.append({'path':target,'sha256':h,'bytes':len(b)})
out=dict(head=H,status='passed',verified_published_manifest_entries=verified,execution_source_versions=source_versions,external_not_retrieved=external)
(A/'AUDIT192.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print('PASS',len(verified),'published manifest entries;',len(source_versions),'execution source entries;',len(external),'external entries not retrieved')
