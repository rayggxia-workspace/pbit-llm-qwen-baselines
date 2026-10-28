"""Run an explicit request via existing local Paracloud client; no auth handling."""
import argparse
import base64
import json
from pathlib import Path
import subprocess
import sys

p=argparse.ArgumentParser();p.add_argument('request',type=Path);p.add_argument('--client',type=Path,required=True)
a=p.parse_args();d=json.loads(a.request.read_text(encoding='utf-8'))
if d['action']=='exec':
    payload=base64.b64encode(d['script'].encode()).decode()
    command='/usr/bin/python3 -c "import base64;exec(base64.b64decode(\''+payload+'\'))"'
    args=['exec',command,'--timeout',str(d.get('timeout',90))]
else:
    assert d['action'] in ('put','get');args=[d['action'],d['source'],d['destination']]
r=subprocess.run([sys.executable,str(a.client)]+args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
if d.get('log'):
    log=Path(d['log']);assert not log.exists();log.parent.mkdir(parents=True,exist_ok=True);log.write_bytes(r.stdout)
sys.stdout.buffer.write(r.stdout);sys.exit(r.returncode)
