"""Export exact committed UTF-8 blobs for GitHub tree API, without shell interpolation."""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf8')
parser=argparse.ArgumentParser();parser.add_argument('--build',action='store_true');parser.add_argument('--chunk',type=int)
args=parser.parse_args()
out=Path('C:/Users/86134/Documents/a_P_BIT/project_archives/rng_ideal_quality_20261025/publish_payload.json')
base='d6d33995754fcdcea99286e4ce43f91647aa231a'
if args.build:
    paths=subprocess.check_output(['git','diff','--name-only','-z',base,'HEAD']).decode('utf8').strip('\0').split('\0')
    entries=[];manifest={}
    for p in paths:
        blob=subprocess.check_output(['git','show','HEAD:'+p])
        entries.append(dict(path=p,mode='100644',type='blob',content=blob.decode('utf8')))
        manifest[p]=hashlib.sha256(blob).hexdigest()
    data=dict(elements=entries,manifest=manifest,local_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        tree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],text=True).strip(),
        base_tree=subprocess.check_output(['git','rev-parse',base+'^{tree}'],text=True).strip())
    out.write_bytes(json.dumps(data,ensure_ascii=False,separators=(',',':')).encode('utf8'))
text=out.read_text(encoding='utf8')
if args.chunk is not None:print(json.dumps(text[args.chunk*60000:(args.chunk+1)*60000],ensure_ascii=False))
else:
    d=json.loads(text);print(json.dumps(dict(chunks=(len(text)+59999)//60000,characters=len(text),files=len(d['elements']),
        local_commit=d['local_commit'],tree=d['tree'],base_tree=d['base_tree'],paths=[e['path'] for e in d['elements']]),ensure_ascii=False))
