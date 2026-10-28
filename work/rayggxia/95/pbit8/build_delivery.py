from pathlib import Path
import hashlib
import json
import zipfile

TASK=Path(__file__).resolve().parents[4]
WORKSPACE=TASK.parent.parent
PKG=TASK/'architecture_tlm/random_service/pbit8_char'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_bytes((json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode())
files=[p for p in sorted(PKG.rglob('*')) if p.is_file() and '__pycache__' not in p.parts
       and p.name!='DELIVERY_MANIFEST.json']
save(PKG/'DELIVERY_MANIFEST.json',{'files':{p.relative_to(PKG).as_posix():sha(p) for p in files}})
files.append(PKG/'DELIVERY_MANIFEST.json')
out=WORKSPACE/'远端上传/pbit8_char_20261027_v1.zip'
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
    for p in files:z.write(p,'pbit8_char/'+p.relative_to(PKG).as_posix())
with zipfile.ZipFile(out) as z:
    assert z.testzip() is None
    for p in files:assert z.read('pbit8_char/'+p.relative_to(PKG).as_posix())==p.read_bytes()
save(Path(__file__).parent/'DELIVERY.json',{'workspace_relative_path':out.relative_to(WORKSPACE).as_posix(),
  'sha256':sha(out),'bytes':out.stat().st_size,'files':len(files),'archive_verified':True,
  'raw_vcd_included':False,'pdk_included':False})
print(out.name,sha(out),out.stat().st_size)
