from pathlib import Path
import json,subprocess,hashlib
A=Path(__file__).resolve().parent;R=A.parent.parent;W=R/'tmp/pr55-review-round11-20261025'
paths=list((W/'work/jieruiz/186').glob('*SOURCE*.json'))+list((W/'work/jieruiz/182').glob('SOURCE_MANIFEST*.json'))
requests=[];maps=[]
for p in paths:
 m=json.loads(p.read_text(encoding='utf-8-sig'))
 if not isinstance(m,dict):continue
 commit=m.get('commit');files=m.get('files')
 if not commit or not isinstance(files,dict):continue
 for rel,v in files.items():
  if not isinstance(v,dict) or 'sha256' not in v:continue
  if rel.startswith('architecture_tlm/'):
   requests.append(commit+':'+rel);maps.append((p.name,commit,rel,v))
r=subprocess.run(['git','-C',str(W),'cat-file','--batch'],input=('\n'.join(requests)+'\n').encode(),capture_output=True);assert r.returncode==0
pos=0;checked=[];missing=[];bad=[]
for request,(manifest,commit,rel,v) in zip(requests,maps):
 end=r.stdout.index(b'\n',pos);header=r.stdout[pos:end].decode();pos=end+1
 if header.endswith(' missing'):missing.append(request);continue
 size=int(header.split()[2]);data=r.stdout[pos:pos+size];pos+=size+1
 digest=hashlib.sha256(data).hexdigest()
 if digest!=v['sha256'] or ('bytes' in v and len(data)!=v['bytes']):bad.append({'manifest':manifest,'path':rel,'expected':v['sha256'],'actual':digest})
 else:checked.append({'manifest':manifest,'commit':commit,'path':rel,'sha256':digest})
out={'checked':len(checked),'missing':missing,'bad':bad,'rows':checked};(A/'SOURCE_AUDIT.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
print('Frozen source blobs',len(checked),'missing',len(missing),'bad',len(bad));print(json.dumps(bad[:5]));assert not bad and not missing
