"""Freeze new source, fixtures and exact provenance; private runtime config stays local."""
from pathlib import Path
import json,hashlib,zipfile,subprocess,shutil
R=Path(__file__).resolve().parents[3];W=Path(__file__).parent;H=R/'architecture_tlm/attention_compare_20261027/control128_20261028'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    local=W/'.eda_private/control128_local_v2/VALIDATION.json';d=json.loads(local.read_bytes());assert d['status']=='pass'
    snap=W/'.eda_private/control128_snapshot_v1';snap.mkdir(exist_ok=False)
    for p in H.rglob('*'):
        if p.is_file() and '__pycache__' not in p.parts:
            dest=snap/p.relative_to(H);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
    shutil.copytree(W/'.eda_private/control128_vectors_v2',snap/'vectors')
    (snap/'reference').mkdir()
    for name in ['oracle.py','validate.py']:
        shutil.copyfile(H.parent/'control_v2'/name,snap/'reference'/name)
    shutil.copyfile(local,snap/'LOCAL_VALIDATION.json')
    source=dict(parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R).decode().strip(),binding='working patch frozen by exact file hashes, later Git commit must reproduce these source bytes',files={p.relative_to(snap).as_posix():dict(sha256=sha(p),bytes=p.stat().st_size) for p in snap.rglob('*') if p.is_file()})
    (snap/'SOURCE.json').write_bytes((json.dumps(source,indent=2)+'\n').encode())
    package=snap.with_suffix('.zip')
    with zipfile.ZipFile(package,'x',zipfile.ZIP_DEFLATED) as z:
        for p in snap.rglob('*'):
            if p.is_file():z.write(p,p.relative_to(snap).as_posix())
    (W/'CONTROL128_SOURCE.json').write_bytes((json.dumps(dict(parent=source['parent_commit'],manifest_sha256=sha(snap/'SOURCE.json'),package_sha256=sha(package),package_bytes=package.stat().st_size,files=source['files'],local_functional_checks=d['checks'],local_cycles=d['cycles']),indent=2)+'\n').encode())
    print(json.dumps(dict(package=str(package),bytes=package.stat().st_size,sha256=sha(package))))
if __name__=='__main__':main()
