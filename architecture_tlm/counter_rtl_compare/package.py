"""Create a small portable source delivery; no libraries, models or large waves."""
import argparse,hashlib,json,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def entries():
    for p in sorted(ROOT.rglob('*')):
        if p.is_file() and '__pycache__' not in p.parts and p.name!='package_manifest.json' and p.suffix not in ('.pyc','.zip','.vvp','.vcd'):
            yield p
def sha(b):return hashlib.sha256(b).hexdigest()
def verify():
    m=json.loads((ROOT/'package_manifest.json').read_text())
    for rel,v in m['files'].items():
        data=(ROOT/rel).read_bytes()
        if len(data)!=v['bytes'] or sha(data)!=v['sha256']:raise ValueError('Manifest mismatch '+rel)
    return len(m['files'])
def main():
    a=argparse.ArgumentParser();a.add_argument('--zip',type=Path);a.add_argument('--verify',action='store_true');x=a.parse_args()
    if x.verify:print('VERIFIED',verify());return
    assert x.zip is not None
    files=list(entries());m=dict(scope='counter comparison RTL and flow only; PPA not run',files={str(p.relative_to(ROOT)).replace('\\','/'):dict(bytes=p.stat().st_size,sha256=sha(p.read_bytes())) for p in files})
    (ROOT/'package_manifest.json').write_text(json.dumps(m,indent=2)+'\n',encoding='utf-8')
    with zipfile.ZipFile(x.zip,'w',zipfile.ZIP_DEFLATED) as z:
        for p in files+[ROOT/'package_manifest.json']:z.write(p,'counter_rtl_compare/'+str(p.relative_to(ROOT)).replace('\\','/'))
    assert verify()==len(files)
    print(json.dumps(dict(zip=str(x.zip),bytes=x.zip.stat().st_size,sha256=sha(x.zip.read_bytes()),files=len(files))))
if __name__=='__main__':main()
