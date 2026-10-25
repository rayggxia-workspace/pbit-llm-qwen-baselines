"""Emit exact line changes from the delivery tree already verified on GitHub."""
import difflib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
BASE='f7e6110bfae671b09e75d6dca7d020fbff3d85bb'
def git(*args):return subprocess.check_output(['git','-C',str(ROOT),*args])
oldpaths={p.decode('utf-8') for p in git('ls-tree','-r','--name-only','-z',BASE).split(b'\0') if p}
entries=[]
for path in (p.decode('utf-8') for p in git('diff','--name-only','-z',BASE,'HEAD').split(b'\0') if p):
    old=git('cat-file','blob',BASE+':'+path).decode('utf-8') if path in oldpaths else ''
    new=git('cat-file','blob','HEAD:'+path).decode('utf-8')
    a,b=old.splitlines(keepends=True),new.splitlines(keepends=True)
    hunks=[dict(start=i1,delete=i2-i1,insert=b[j1:j2]) for op,i1,i2,j1,j2 in difflib.SequenceMatcher(None,a,b,autojunk=False).get_opcodes() if op!='equal']
    entries.append(dict(path=path,mode=git('ls-tree','HEAD','--',path).split()[0].decode(),new_file=path not in oldpaths,hunks=hunks))
print(json.dumps(dict(base=BASE,local_head=git('rev-parse','HEAD').strip().decode(),expected_tree=git('rev-parse','HEAD^{tree}').strip().decode(),entries=entries),ensure_ascii=False))
