"""Publish exact own task commits, preserving the verified upstream merge."""
import base64,concurrent.futures,hashlib,importlib.util,json,subprocess,sys
from pathlib import Path
TASK=Path(__file__).resolve().parents[1];ROOT=TASK.parents[2]
s=importlib.util.spec_from_file_location('issue96_publish',TASK/'publish.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
ARCHIVE=ROOT.parent.parent/'project_archives/rng_integration_issue96_20261022'
ARCHIVE.mkdir(parents=True,exist_ok=True)

def allowed(p):
 return m.allowed(p) or p=='architecture_tlm/parallel_sampler_v5.py'
def push():
 user=m.api('GET','/user')['login']
 if user!='jieruiz':raise ValueError('identity mismatch')
 original=m.api('GET',m.PREFIX+'/git/ref/heads/'+m.BRANCH)['object']['sha']
 head=m.git('rev-parse','HEAD').decode().strip()
 subprocess.run(['git','merge-base','--is-ancestor',original,head],cwd=ROOT,check=True)
 commits=m.git('rev-list','--first-parent','--reverse',original+'..'+head).decode().splitlines();parent=original;receipts=[]
 for commit in commits:
  raw=m.git('cat-file','commit',commit).decode('utf-8');header,message=raw.split('\n\n',1)
  lines=[line.split(' ',1) for line in header.splitlines()];parents=[v for k,v in lines if k=='parent'];fields=dict(lines)
  if not parents or parents[0]!=parent or len(parents)>2:raise ValueError('unexpected task ancestry')
  base=parents[-1]
  if len(parents)==2:m.api('GET',m.PREFIX+'/git/commits/'+base)
  paths=m.git('diff','--name-only','-z',base,commit).decode('utf-8').rstrip('\0').split('\0')
  paths=[p for p in paths if p]
  if not all(allowed(p) for p in paths):raise ValueError('outside own scope: '+repr([p for p in paths if not allowed(p)]))
  def blob(p):
   tree=m.git('ls-tree','-z',commit,'--',p)
   if not tree:return dict(path=p,mode='100644',type='blob',sha=None)
   mode,kind,oid=tree.split(b'\t',1)[0].decode().split(' ')
   if kind!='blob' or mode!='100644':raise ValueError('non-regular publication')
   data=m.git('show',commit+':'+p)
   if len(data)>2000000:raise ValueError('large artifact needs shared storage: '+p)
   got=m.api('POST',m.PREFIX+'/git/blobs',dict(content=base64.b64encode(data).decode(),encoding='base64'))
   if got['sha']!=oid:raise ValueError('blob mismatch')
   return dict(path=p,mode=mode,type=kind,sha=oid)
  with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:entries=list(pool.map(blob,paths))
  tree=m.api('POST',m.PREFIX+'/git/trees',dict(base_tree=m.git('rev-parse',base+'^{tree}').decode().strip(),tree=entries))
  if tree['sha']!=fields['tree']:raise ValueError('tree mismatch')
  c=m.api('POST',m.PREFIX+'/git/commits',dict(message=message,tree=tree['sha'],parents=parents,author=m.person(fields['author']),committer=m.person(fields['committer'])))
  if c['sha']!=commit:raise ValueError('commit mismatch')
  receipts.append(dict(commit=commit,parents=parents,paths=len(paths)));parent=commit
  print(json.dumps(dict(uploaded=commit,files=len(paths))),flush=True)
 if m.api('GET',m.PREFIX+'/git/ref/heads/'+m.BRANCH)['object']['sha']!=original:raise ValueError('remote branch moved; review before updating')
 got=m.api('PATCH',m.PREFIX+'/git/refs/heads/'+m.BRANCH,dict(sha=head,force=False))
 if got['object']['sha']!=head:raise ValueError('ref mismatch')
 receipt=dict(repo=m.REPO,user=user,branch=m.BRANCH,previous=original,head=head,commits=receipts,exact_objects=True)
 (ARCHIVE/('PUSH_'+head[:12]+'.json')).write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8',newline='\n')
 print(json.dumps(receipt))
if __name__=='__main__':push()
