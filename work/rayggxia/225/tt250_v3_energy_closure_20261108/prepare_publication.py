"""Explicit owned files, CAS root mirrors and single canonical memory update."""
from pathlib import Path
import hashlib,json,subprocess

HERE=Path(__file__).resolve().parent;WD=HERE.parents[3]
PROJECT=Path('C:/Users/86134/Documents/a_P_BIT')
def sha(b):return hashlib.sha256(b).hexdigest()
def save(p,x):p.write_bytes((json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode())

formal=[
 'architecture_tlm/module_refresh_20261107/'+n for n in
 ('FFN_PROFILE.json','bindings.py','energy_ledger.py','test_energy_ledger.py','README_ZH.md')]
formal+=['architecture_tlm/sram1216_20261106/250MHz/'+n for n in
 ('ffn_actor.py','model.py','pricing.py','bootstrap.py','run.py','README_ZH.md','ENERGY_CLOSURE_ZH.md','ASSEMBLY_STATUS.json')]
prior_sync=json.loads((HERE/'ROOT_SYNC.json').read_bytes())
mirrors={}
for rel in formal:
    source=WD/rel;b=source.read_bytes();root=PROJECT/rel
    if root.exists() and root.read_bytes()!=b:
        old=subprocess.run(['git','show','HEAD:'+rel],cwd=WD,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        allowed=[old.stdout] if old.returncode==0 else []
        if rel in prior_sync.get('files',{}):
            assert sha(root.read_bytes())==prior_sync['files'][rel] or root.read_bytes() in allowed,rel
        else:assert root.read_bytes() in allowed,rel
    root.parent.mkdir(parents=True,exist_ok=True);root.write_bytes(b);mirrors[rel]=sha(b)
save(HERE/'ROOT_SYNC.json',dict(status='same_byte',files=mirrors))
note=(HERE/'MEMORY_NOTE_ZH.md').read_bytes()
status=WD/'progress/rayggxia/STATUS.md'
if not status.read_bytes().startswith(note):status.write_bytes(note+status.read_bytes())
canonical=PROJECT/'tmp/project-memory-issue28-20261018/PROJECT_MEMORY_ZH.md';rootmemo=PROJECT/'PROJECT_MEMORY_ZH.md'
b=canonical.read_bytes();assert b==rootmemo.read_bytes(),'concurrent memory divergence'
if not b.startswith(note):
    old_sha=sha(b);assert canonical.read_bytes()==b and rootmemo.read_bytes()==b
    canonical.write_bytes(note+b);rootmemo.write_bytes(note+b)
    save(HERE/'MEMORY_SYNC.json',dict(prior_sha256=old_sha,new_sha256=sha(note+b),all_prior_bytes_preserved=True,canonical=str(canonical)))
assert canonical.read_bytes()==rootmemo.read_bytes()
aux=['HANDOFF.md','MEMORY_NOTE_ZH.md','MEMORY_SYNC.json','ROOT_SYNC.json','PR_BODY_ZH.md',
 'VERIFIED_GATE.json','VERIFIED_GATE_LEDGER.csv','VERIFIED_GATE_VALIDATION.json','COLLECTION.json',
 'EXECUTED_FFN_PROFILE.json','PROFILE_NORMALIZATION.json','MANIFEST.json','SUBMISSION.json',
 'ops.py','finish_artifacts.py','prepare_publication.py']
paths=formal+['progress/rayggxia/STATUS.md']+[str((HERE/n).relative_to(WD)).replace('\\','/') for n in aux]
files=[]
for rel in paths:
    b=(WD/rel).read_bytes();b.decode('utf-8')
    files.append(dict(path=rel,mode='100644',type='blob',content=b.decode('utf-8')))
save(HERE/'PUBLIC_MANIFEST.json',{x['path']:dict(bytes=len(x['content'].encode()),sha256=sha(x['content'].encode())) for x in files})
save(HERE/'PUBLIC_FILES.json',files)
print(json.dumps(dict(public_files=len(files),bytes=sum(len(x['content'].encode()) for x in files),mirrors=len(mirrors),memory_same_byte=True)))
