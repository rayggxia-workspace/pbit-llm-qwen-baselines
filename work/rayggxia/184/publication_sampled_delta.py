"""Exact bounded Git delta; reuse already published helper blobs by identity."""
import argparse,difflib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
def git(*args):return subprocess.check_output(['git','-C',str(ROOT),*args])
def main():
    p=argparse.ArgumentParser();p.add_argument('--base',required=True);p.add_argument('--part',type=int);p.add_argument('--cache',type=Path);a=p.parse_args()
    oldpaths={s.decode('utf-8') for s in git('ls-tree','-r','--name-only','-z',a.base).split(b'\0') if s}
    oldblobs={line.split()[2].decode() for line in git('ls-tree','-r',a.base).splitlines()}
    entries=[]
    for raw in git('diff','--name-only','-z',a.base,'HEAD').split(b'\0'):
        if not raw:continue
        path=raw.decode('utf-8');mode=git('ls-tree','HEAD','--',path).split()[0].decode()
        blob=git('rev-parse','HEAD:'+path).strip().decode()
        if blob in oldblobs:entries.append(dict(path=path,mode=mode,reuse_sha=blob));continue
        old=git('cat-file','blob',a.base+':'+path).decode('utf-8') if path in oldpaths else ''
        new=git('cat-file','blob','HEAD:'+path).decode('utf-8');left,right=old.splitlines(keepends=True),new.splitlines(keepends=True)
        hunks=[dict(start=i,delete=j-i,insert=right[k:l]) for op,i,j,k,l in difflib.SequenceMatcher(None,left,right,autojunk=False).get_opcodes() if op!='equal']
        entries.append(dict(path=path,mode=mode,new_file=path not in oldpaths,hunks=hunks))
    data=dict(base=a.base,local_head=git('rev-parse','HEAD').strip().decode(),expected_tree=git('rev-parse','HEAD^{tree}').strip().decode(),entries=entries)
    text=json.dumps(data,ensure_ascii=False)
    if a.cache:
        with a.cache.open('x',encoding='utf-8',newline='\n') as f:f.write(text)
    if a.part is None:print(json.dumps(dict(parts=(len(text)+9999)//10000,characters=len(text),paths=[e['path'] for e in entries],local_head=data['local_head'],expected_tree=data['expected_tree']),ensure_ascii=False))
    else:print(json.dumps(text[a.part*10000:(a.part+1)*10000],ensure_ascii=False))
if __name__=='__main__':main()
