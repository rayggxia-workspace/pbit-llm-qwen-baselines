"""Export committed UTF-8 blobs only; preserve parent tree with a leased API update."""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf8')
p=argparse.ArgumentParser()
p.add_argument('--build',action='store_true')
p.add_argument('--base',default='3b878c15ddb56179815c5afa8193ea816a96037a')
p.add_argument('--chunk',type=int)
a=p.parse_args()
out=Path('C:/Users/86134/Documents/a_P_BIT/project_archives/rng_correlation_20261025/publish_payload.json')
if a.build:
    paths=subprocess.check_output(['git','diff','--name-only','-z',a.base,'HEAD']).decode('utf8').strip('\0').split('\0')
    entries=[]; manifest={}
    for path in paths:
        blob=subprocess.check_output(['git','show','HEAD:'+path])
        entries.append(dict(path=path,mode='100644',type='blob',content=blob.decode('utf8')))
        manifest[path]=hashlib.sha256(blob).hexdigest()
    d=dict(elements=entries,manifest=manifest,
        local_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        tree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],text=True).strip(),
        base_tree=subprocess.check_output(['git','rev-parse',a.base+'^{tree}'],text=True).strip())
    out.write_bytes(json.dumps(d,ensure_ascii=False,separators=(',',':')).encode('utf8'))
text=out.read_text(encoding='utf8')
if a.chunk is not None:
    print(json.dumps(text[a.chunk*60000:(a.chunk+1)*60000],ensure_ascii=False))
else:
    d=json.loads(text)
    print(json.dumps(dict(chunks=(len(text)+59999)//60000,characters=len(text),files=len(d['elements']),
        local_commit=d['local_commit'],tree=d['tree'],base_tree=d['base_tree'],paths=[e['path'] for e in d['elements']]),ensure_ascii=False))
