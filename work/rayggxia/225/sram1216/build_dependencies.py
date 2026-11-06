from pathlib import Path
import hashlib,json
PROJECT=Path('C:/Users/86134/Documents/a_P_BIT')
DEST=PROJECT/'project_archives/sram1216_225_20261106/dependencies'
files={}
for package in ('ffn_sram_batch_20261106','ordinary_mapping_20261106'):
    folder=PROJECT/'architecture_tlm'/package
    selected=list(folder.rglob('*.py')) if package.startswith('ffn') else [folder/'model.py']
    for source in selected:
        rel=source.relative_to(PROJECT).as_posix();data=source.read_bytes()
        target=DEST/rel;target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists():assert target.read_bytes()==data, 'immutable dependency changed: '+rel
        else:target.write_bytes(data)
        files[rel]=dict(sha256=hashlib.sha256(data).hexdigest(),source=str(source))
    initializer=DEST/'architecture_tlm'/package/'__init__.py'
    if initializer.relative_to(DEST).as_posix() not in files:
        if not initializer.exists():initializer.write_bytes(b'')
        assert initializer.read_bytes()==b''
        files[initializer.relative_to(DEST).as_posix()]=dict(sha256=hashlib.sha256(b'').hexdigest(),source='empty package initializer')
manifest=dict(scope='read-only selected existing owner source dependencies; not a new PPA/RTL run',files=files)
DEST.mkdir(parents=True,exist_ok=True)
raw=(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode()
target=DEST/'MANIFEST.json'
if target.exists():assert target.read_bytes()==raw,'immutable dependency manifest changed'
else:target.write_bytes(raw)
print(json.dumps(dict(directory=str(DEST),files=len(files),manifest_sha256=hashlib.sha256(raw).hexdigest())))
