"""Small source-only archive; never package PDK/netlist/waveforms."""
import argparse,hashlib,json,zipfile,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def files():
    return sorted(p for p in ROOT.rglob('*') if p.is_file() and not set(p.relative_to(ROOT).parts)&{'__pycache__','runs','snapshots','logs','results'}
                  and p.name!='SOURCE_MANIFEST.json' and p.suffix in ['.sv','.py','.tcl','.sh','.md','.txt','.json','.template'])

def manifest():return {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files()}

def verify():
    if json.loads((ROOT/'SOURCE_MANIFEST.json').read_text(encoding='utf-8'))!=manifest():raise ValueError('package source changed')

def snapshot(dest):
    verify();dest=dest.resolve()
    if dest==ROOT or ROOT in dest.parents:raise ValueError('Snapshot must be outside source root')
    dest.mkdir(parents=True,exist_ok=False)
    for p in files()+[ROOT/'SOURCE_MANIFEST.json']:
        q=dest/p.relative_to(ROOT);q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(str(p),str(q))
    return dest

def main():
    a=argparse.ArgumentParser();a.add_argument('--out',type=Path);a.add_argument('--verify',action='store_true')
    a.add_argument('--snapshot',type=Path);a.add_argument('--prefix',default=ROOT.name);x=a.parse_args()
    m=ROOT/'SOURCE_MANIFEST.json'
    if x.verify:
        verify()
        print('SOURCE_MANIFEST PASS');return
    if x.snapshot:print(snapshot(x.snapshot));return
    with m.open('w',encoding='utf-8',newline='\n') as f:f.write(json.dumps(manifest(),indent=2)+'\n')
    if x.out:
        if x.out.exists():raise ValueError('refusing to overwrite archive')
        with zipfile.ZipFile(x.out,'w',compression=zipfile.ZIP_DEFLATED) as z:
            for p in files()+[m]:z.write(p,x.prefix+'/'+p.relative_to(ROOT).as_posix())
        print(json.dumps(dict(path=str(x.out),bytes=x.out.stat().st_size,sha256=hashlib.sha256(x.out.read_bytes()).hexdigest())))

if __name__=='__main__':main()
