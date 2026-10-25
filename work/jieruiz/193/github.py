"""Publish narrow Issue193 exact Git objects; no merge, no force push."""
import base64
import concurrent.futures
import datetime
import gzip
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
REPO = 'rayggxia-workspace/pbit-llm-qwen-baselines'
PREFIX = '/repos/'+REPO
BRANCH = 'task/193-ffn-calibration-stage1'
BASE = 'd83eeb1fc6b89a3dff51b5b62bf79acf665c7166'
os.environ.update(GCM_INTERACTIVE='Never', GIT_TERMINAL_PROMPT='0')
cred = subprocess.run(['git','-c','credential.username=jieruiz','credential','fill'],
    input='protocol=https\nhost=github.com\nusername=jieruiz\n\n', cwd=ROOT,
    text=True,capture_output=True,check=True,timeout=20)
auth = dict(x.split('=',1) for x in cred.stdout.splitlines() if '=' in x)

def api(method,path,value=None):
    req=urllib.request.Request('https://api.github.com'+path,method=method,
        data=None if value is None else json.dumps(value,ensure_ascii=False).encode('utf-8'),
        headers={'Authorization':'Bearer '+auth['password'],'Accept':'application/vnd.github+json',
        'Accept-Encoding':'gzip','Content-Type':'application/json','User-Agent':'pbit-issue193'})
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req,timeout=45) as r:
        data=r.read()
        if r.headers.get('Content-Encoding')=='gzip':data=gzip.decompress(data)
        return json.loads(data)

def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
def save(name,value):
    with (OUT/name).open('w',encoding='utf-8',newline='\n') as f:
        json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n')
def person(line):
    m=re.fullmatch(r'(.*) <(.*)> (\d+) ([+-])(\d\d)(\d\d)',line)
    if not m:raise ValueError('invalid Git person')
    minutes=(1 if m[4]=='+' else -1)*(int(m[5])*60+int(m[6]))
    return dict(name=m[1],email=m[2],date=datetime.datetime.fromtimestamp(
        int(m[3]),datetime.timezone(datetime.timedelta(minutes=minutes))).isoformat())
def allowed(p):
    return p.startswith(('architecture_tlm/ffn_calibration_stage1/', 'work/jieruiz/193/', 'digital_circuit_simulation_registry/records/')) or p in ('README.md','AGENTS.md','progress/jieruiz/STATUS.md','PROJECT_MEMORY_ZH.md')


def push():
    refs=api('GET',PREFIX+'/git/matching-refs/heads/'+BRANCH)
    current=next((r for r in refs if r['ref']=='refs/heads/'+BRANCH),None)
    parent=current['object']['sha'] if current else BASE
    head=git('rev-parse','HEAD').decode().strip()
    subprocess.run(['git','merge-base','--is-ancestor',parent,head],cwd=ROOT,check=True)
    commits=git('rev-list','--reverse',parent+'..'+head).decode().splitlines()
    for commit in commits:
        raw=git('cat-file','commit',commit).decode('utf-8');header,message=raw.split('\n\n',1)
        fields=dict(line.split(' ',1) for line in header.splitlines())
        if fields.get('parent')!=parent:raise ValueError('Task history must be linear')
        paths=git('diff-tree','--no-commit-id','--name-only','-r',commit).decode().splitlines()
        if not all(allowed(p) for p in paths):raise ValueError('Publication outside task scope')
        def blob(p):
            data=git('show',commit+':'+p)
            if len(data)>2500000:raise ValueError('Large artifact must use shared storage')
            b=api('POST',PREFIX+'/git/blobs',dict(content=base64.b64encode(data).decode(),encoding='base64'))
            if b['sha']!=git('rev-parse',commit+':'+p).decode().strip():raise ValueError('blob mismatch')
            return dict(path=p,mode='100644',type='blob',sha=b['sha'])
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:entries=list(pool.map(blob,paths))
        tree=api('POST',PREFIX+'/git/trees',dict(base_tree=git('rev-parse',parent+'^{tree}').decode().strip(),tree=entries))
        if tree['sha']!=fields['tree']:raise ValueError('tree mismatch')
        obj=api('POST',PREFIX+'/git/commits',dict(message=message,tree=tree['sha'],parents=[parent],
            author=person(fields['author']),committer=person(fields['committer'])))
        if obj['sha']!=commit:raise ValueError('commit mismatch')
        parent=commit
    result=api('PATCH',PREFIX+'/git/refs/heads/'+BRANCH,dict(sha=head,force=False)) if current else \
        api('POST',PREFIX+'/git/refs',dict(ref='refs/heads/'+BRANCH,sha=head))
    if result['object']['sha']!=head:raise ValueError('ref mismatch')
    return dict(repo=REPO,branch=BRANCH,head=head,commits_uploaded=len(commits),exact_objects=True)
