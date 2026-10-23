"""Small source-only archive; never package PDK/netlist/waveforms."""
import argparse,hashlib,json,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def files():
    return sorted(p for p in ROOT.rglob('*') if p.is_file() and '__pycache__' not in p.parts
                  and p.name!='SOURCE_MANIFEST.json' and p.suffix in ['.sv','.py','.tcl','.sh','.md','.txt','.json','.template'])

def manifest():return {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files()}

def main():
    a=argparse.ArgumentParser();a.add_argument('--out',type=Path);a.add_argument('--verify',action='store_true');x=a.parse_args()
    m=ROOT/'SOURCE_MANIFEST.json'
    if x.verify:
        if json.loads(m.read_text(encoding='utf-8'))!=manifest():raise ValueError('package source changed')
        print('SOURCE_MANIFEST PASS');return
    with m.open('w',encoding='utf-8',newline='\n') as f:f.write(json.dumps(manifest(),indent=2)+'\n')
    if x.out:
        if x.out.exists():raise ValueError('refusing to overwrite archive')
        with zipfile.ZipFile(x.out,'w',compression=zipfile.ZIP_DEFLATED) as z:
            for p in files()+[m]:z.write(p,ROOT.name+'/'+p.relative_to(ROOT).as_posix())
        print(json.dumps(dict(path=str(x.out),bytes=x.out.stat().st_size,sha256=hashlib.sha256(x.out.read_bytes()).hexdigest())))

if __name__=='__main__':main()
