from pathlib import Path,PurePosixPath
import subprocess,json,hashlib
A=Path(__file__).resolve().parent;R=A.parent.parent/'pbit-llm-qwen-baselines'
def git(*a):return subprocess.check_output(['git','-C',str(R),*a])
result={}
for n in [194,195,196,197,205]:
 p=json.loads((A/f'PR{n}.json').read_text(encoding='utf-8'));head=p['head']['sha'];base=p['base']['sha']
 paths=git('diff','--name-only',base,head,'--','digital_circuit_simulation_registry/records').decode().splitlines()
 if n==197:paths+=['work/jieruiz/110/PPA_SUMMARY_VALIDATION.json']
 checked=[];missing=[];bad=[];seen=set()
 def walk(v,src):
  if isinstance(v,list):
   for x in v:walk(x,src)
  elif isinstance(v,dict):
   path=v.get('path');sha=v.get('sha256');size=v.get('bytes')
   if isinstance(path,str) and isinstance(sha,str) and len(sha)==64 and (path,sha) not in seen:
    seen.add((path,sha));f=Path(path)
    b=None
    if not f.is_absolute():
     proc=subprocess.run(['git','-C',str(R),'show',head+':'+path],capture_output=True)
     if proc.returncode==0:b=proc.stdout
    elif f.is_file():b=f.read_bytes()
    if b is not None:
     got=hashlib.sha256(b).hexdigest();row=dict(source_record=src,path=path,expected=sha,actual=got,bytes=len(b))
     if got==sha and (size is None or len(b)==size):checked.append(row)
     else:bad.append(row)
    else:missing.append(dict(source_record=src,path=path,sha256=sha))
   for x in v.values():walk(x,src)
 for path in paths:walk(json.loads(git('show',head+':'+path)),path)
 result[str(n)]={'head':head,'records':paths,'verified':checked,'unavailable_here':missing,'mismatches':bad}
 print(n,'records',len(paths),'verified',len(checked),'unavailable',len(missing),'mismatches',len(bad))
(A/'MATERIAL_AUDIT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
