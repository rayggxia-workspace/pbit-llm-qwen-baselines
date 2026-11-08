from pathlib import Path
import hashlib,json
HERE=Path(__file__).resolve().parent;WD=HERE.parents[3];PROJECT=Path('C:/Users/86134/Documents/a_P_BIT')
def sha(b):return hashlib.sha256(b).hexdigest()
def save(n,x):(HERE/n).write_bytes((json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode())
folder='architecture_tlm/module_refresh_20261107/tsmc28_review_20261108'
formal=[folder+'/'+n for n in ('REPORT_ZH.md','review.py','CANDIDATE_COMPONENTS.json','COMPARISON.json','SOURCE_INDEX.json','VALIDATION.json')]
mirror={}
for rel in formal:
    p=PROJECT/rel;b=(WD/rel).read_bytes()
    if p.exists():assert p.read_bytes()==b,'concurrent mirror '+rel
    p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b);mirror[rel]=sha(b)
note=(HERE/'MEMORY_NOTE_ZH.md').read_bytes()
status=WD/'progress/rayggxia/STATUS.md'
if not status.read_bytes().startswith(note):status.write_bytes(note+status.read_bytes())
canonical=PROJECT/'tmp/project-memory-issue28-20261018/PROJECT_MEMORY_ZH.md';root=PROJECT/'PROJECT_MEMORY_ZH.md'
b=canonical.read_bytes();assert b==root.read_bytes(),'memory differs'
if not b.startswith(note):
    assert canonical.read_bytes()==b and root.read_bytes()==b
    canonical.write_bytes(note+b);root.write_bytes(note+b)
save('SYNC.json',dict(root_mirrors=mirror,memory_same_byte=canonical.read_bytes()==root.read_bytes(),memory_sha256=sha(canonical.read_bytes()),prior_bytes_preserved=True))
paths=formal+['progress/rayggxia/STATUS.md']+[str((HERE/n).relative_to(WD)).replace('\\','/') for n in ('HANDOFF.md','MEMORY_NOTE_ZH.md','SYNC.json','prepare.py')]
files=[dict(path=p,mode='100644',type='blob',content=(WD/p).read_bytes().decode()) for p in paths]
save('PUBLIC_FILES.json',files)
save('FILES.json',{x['path']:dict(sha256=sha(x['content'].encode()),bytes=len(x['content'].encode())) for x in files})
print(json.dumps(dict(public_files=len(files),mirrors=len(formal),no_default_change=True,no_new_run=True)))
