"""One-time structured merge of the latest registry; preserve all run records."""
import csv
import io
import json
from pathlib import Path
import re
import subprocess

ROOT=Path(__file__).resolve().parents[4]
REG='digital_circuit_simulation_registry/'


def git(*args):
    return subprocess.check_output(['git']+list(args),cwd=str(ROOT))


def stage(n,path):
    return git('show',':{}:{}'.format(n,path))


def main():
    for file in ('PROJECT_MEMORY_ZH.md','progress/jieruiz/STATUS.md'):
        p=ROOT/file;s=p.read_text(encoding='utf-8')
        pattern=r'<<<<<<< HEAD\n(.*?)=======\n(.*?)>>>>>>> [^\n]+\n'
        def resolve(m):
            ours,theirs=m.groups()
            if file=='PROJECT_MEMORY_ZH.md':
                theirs=theirs[theirs.index('## '):]
            return ours+'\n'+theirs
        s,n=re.subn(pattern,resolve,s,flags=re.S)
        assert n==1,(file,n)
        p.write_text(s,encoding='utf-8',newline='\n')
    (ROOT/REG/'registry.py').write_bytes(stage(3,REG+'registry.py'))
    paths=git('ls-files','--stage','--',REG+'records').decode().splitlines()
    names=[]
    for line in paths:
        info,path=line.split('\t',1)
        assert info.split()[2]=='0',path
        p=ROOT/path;p.parent.mkdir(parents=True,exist_ok=True)
        p.write_bytes(git('show',':0:'+path));names.append(p.stem)
    catalog=json.loads(stage(3,REG+'catalog.json'))
    catalog['record_ids']=sorted(names);catalog['as_of']='2026-10-23'
    (ROOT/REG/'catalog.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    merged={};fields=None
    for n in (2,3):
        reader=csv.DictReader(io.StringIO(stage(n,REG+'archive_inventory.csv').decode('utf-8')))
        fields=reader.fieldnames
        for row in reader:
            if row['path'] in merged:
                assert row['sha256']==merged[row['path']]['sha256'],row['path']
            merged[row['path']]=row
    with (ROOT/REG/'archive_inventory.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fields,lineterminator='\n');w.writeheader();w.writerows(merged.values())
    print('Preserved records',len(names),'archives',len(merged))


if __name__=='__main__':main()
