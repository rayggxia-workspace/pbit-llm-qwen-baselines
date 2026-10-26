"""Emit bounded JSON fragments of exact Git blobs for the connected GitHub API."""
import argparse,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
BASE='d6d33995754fcdcea99286e4ce43f91647aa231a'
def git(*args):return subprocess.check_output(['git','-C',str(ROOT),*args])
def plan(ref):
    old=set(line.split()[2] for line in git('ls-tree','-r',BASE).splitlines())
    paths=git('diff','--name-only','-z',BASE,ref).split(b'\0')
    fragments=[];entries=[]
    for raw in paths:
        if not raw:continue
        path=raw.decode('utf-8')
        blob=git('rev-parse',ref+':'+path).strip().decode()
        mode=git('ls-tree',ref,'--',path).split()[0].decode()
        if blob.encode() in old:
            entries.append(dict(path=path,mode=mode,type='blob',sha=blob));continue
        data=git('cat-file','blob',ref+':'+path).decode('utf-8')
        parts=[data[i:i+10000] for i in range(0,len(data),10000)] or ['']
        for i,content in enumerate(parts):fragments.append(dict(path=path,mode=mode,part=i,total=len(parts),content=content))
    # Pack short fragments together while keeping returned text comfortably bounded.
    batches=[];batch=[];length=0
    for f in fragments:
        n=len(f['content'])
        if batch and length+n>10000:batches.append(batch);batch=[];length=0
        batch.append(f);length+=n
    if batch:batches.append(batch)
    return dict(base=BASE,local_commit=ref,base_tree_sha=git('rev-parse',BASE+'^{tree}').strip().decode(),
        expected_tree_sha=git('rev-parse',ref+'^{tree}').strip().decode(),entries=entries,batches=batches)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--ref',default='HEAD');p.add_argument('--part',type=int);a=p.parse_args()
    x=plan(a.ref)
    if a.part is None:
        count=len(x.pop('batches'));x['batch_count']=count;print(json.dumps(x,ensure_ascii=False))
    else:print(json.dumps(x['batches'][a.part],ensure_ascii=False))
