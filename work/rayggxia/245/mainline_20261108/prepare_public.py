from pathlib import Path
import hashlib,json,subprocess
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3]
f=HERE/'PUBLIC_FILES.json';paths={x['path'] for x in json.loads(f.read_bytes())}
paths.add('work/rayggxia/245/mainline_20261108/prepare_public.py')
files=[]
for n in sorted(paths):
    raw=(ROOT/n).read_bytes();files.append(dict(path=n,content=raw.decode('utf-8'),sha256=hashlib.sha256(raw).hexdigest()))
f.write_bytes((json.dumps(files,indent=2,ensure_ascii=True)+'\n').encode())
folder=HERE/'PUBLIC_BATCHES';folder.mkdir(exist_ok=True);batches=[];current=[]
for row in files:
    if current and len(json.dumps(current+[row],ensure_ascii=True))>50000:batches.append(current);current=[]
    current.append(row)
if current:batches.append(current)
for i,batch in enumerate(batches):(folder/('%02d.json'%i)).write_bytes(json.dumps(batch,ensure_ascii=True).encode())
subprocess.run(['git','-c','core.autocrlf=false','add','--sparse','--']+sorted(paths),cwd=ROOT,check=True)
staged=subprocess.check_output(['git','diff','--cached','--name-only'],cwd=ROOT).decode().splitlines()
assert set(staged)==paths,(set(staged)-paths,paths-set(staged))
for x in files:
    raw=subprocess.check_output(['git','show',':'+x['path']],cwd=ROOT)
    assert hashlib.sha256(raw).hexdigest()==x['sha256'],x['path']
subprocess.run(['git','-c','core.whitespace=cr-at-eol,-blank-at-eof','diff','--cached','--check'],cwd=ROOT,check=True)
print(json.dumps(dict(files=len(files),batches=len(batches),total_bytes=sum(len(x['content'].encode()) for x in files),staged_blob_bytes_verified=True)))
