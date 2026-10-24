"""Create a small portable source delivery; no libraries, models or large waves."""
import argparse,hashlib,json,zipfile,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def entries():
    for p in sorted(ROOT.rglob('*')):
        if p.is_file() and not any(x in p.relative_to(ROOT).parts for x in ('__pycache__','runs','snapshots','logs')) and p.name!='package_manifest.json' and p.suffix not in ('.pyc','.zip','.vvp','.vcd'):
            yield p
def sha(b):return hashlib.sha256(b).hexdigest()
def verify():
    m=json.loads((ROOT/'package_manifest.json').read_text())
    for rel,v in m['files'].items():
        data=(ROOT/rel).read_bytes()
        if len(data)!=v['bytes'] or sha(data)!=v['sha256']:raise ValueError('Manifest mismatch '+rel)
    return len(m['files'])

def snapshot(dest):
    verify()
    dest=dest.resolve()
    if dest==ROOT or ROOT in dest.parents:
        raise ValueError('Snapshot must be outside the package source')
    dest.mkdir(parents=True,exist_ok=False)
    m=json.loads((ROOT/'package_manifest.json').read_text())
    for rel in list(m['files'])+['package_manifest.json']:
        target=dest/rel
        if dest not in target.resolve().parents:
            raise ValueError('Unsafe manifest path')
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(str(ROOT/rel),str(target))
        if (ROOT/rel).read_bytes()!=target.read_bytes():raise ValueError('Snapshot mismatch '+rel)
    return dest
def main():
    a=argparse.ArgumentParser();a.add_argument('--zip',type=Path);a.add_argument('--verify',action='store_true');a.add_argument('--snapshot',type=Path);a.add_argument('--prefix',default='counter_rtl_compare');x=a.parse_args()
    if x.verify:print('VERIFIED',verify());return
    if x.snapshot:print(snapshot(x.snapshot));return
    assert x.zip is not None
    files=list(entries());m=dict(scope='counter comparison RTL and flow only; PPA not run',files={str(p.relative_to(ROOT)).replace('\\','/'):dict(bytes=p.stat().st_size,sha256=sha(p.read_bytes())) for p in files})
    (ROOT/'package_manifest.json').write_bytes((json.dumps(m,indent=2)+'\n').encode('utf-8'))
    with zipfile.ZipFile(x.zip,'w',zipfile.ZIP_DEFLATED) as z:
        for p in files+[ROOT/'package_manifest.json']:z.write(p,x.prefix+'/'+str(p.relative_to(ROOT)).replace('\\','/'))
    assert verify()==len(files)
    print(json.dumps(dict(zip=str(x.zip),bytes=x.zip.stat().st_size,sha256=sha(x.zip.read_bytes()),files=len(files))))
if __name__=='__main__':main()
