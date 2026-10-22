"""Publish only Issue104's exact Git objects; never force-push or merge."""
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

ROOT=Path(__file__).resolve().parents[3]
REPO='rayggxia-workspace/pbit-llm-qwen-baselines'
PREFIX='/repos/'+REPO
BRANCH='task/104-architecture-inspector'
BASE='eb317e4f6fb1b0d8844887401f3275f128ef8a83'
OUT=Path(__file__).resolve().parent
os.environ['GCM_INTERACTIVE']='Never'
os.environ['GIT_TERMINAL_PROMPT']='0'
cred=subprocess.run(['git','-c','credential.username=jieruiz','credential','fill'],
    input='protocol=https\nhost=github.com\nusername=jieruiz\n\n',cwd=ROOT,
    text=True,capture_output=True,check=True,timeout=20)
auth=dict(x.split('=',1) for x in cred.stdout.splitlines() if '=' in x)


def api(method,path,value=None):
    req=urllib.request.Request('https://api.github.com'+path,method=method,
        data=None if value is None else json.dumps(value,ensure_ascii=False).encode('utf-8'),
        headers={'Authorization':'Bearer '+auth['password'],'Accept':'application/vnd.github+json',
            'Accept-Encoding':'gzip','Content-Type':'application/json','User-Agent':'pbit-issue104'})
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
    return (p.startswith(('architecture_tlm/inspector/','work/jieruiz/104/')) or
        p in ('architecture_tlm/WORKSPACE_LATEST_ZH.md','PROJECT_MEMORY_ZH.md','progress/jieruiz/STATUS.md') or
        p in ('architecture_tlm/parallel_sampler_v5.py','architecture_tlm/unified_v6/model.py','architecture_tlm/checks/test_observation_hooks_v6.py'))


def publish():
    refs=api('GET',PREFIX+'/git/matching-refs/heads/'+BRANCH)
    current=next((r for r in refs if r['ref']=='refs/heads/'+BRANCH),None)
    parent=current['object']['sha'] if current else BASE
    head=git('rev-parse','HEAD').decode().strip()
    subprocess.run(['git','merge-base','--is-ancestor',parent,head],cwd=ROOT,check=True)
    commits=git('rev-list','--reverse',parent+'..'+head).decode().splitlines()
    for commit in commits:
        raw=git('cat-file','commit',commit).decode('utf-8');header,message=raw.split('\n\n',1)
        fields=dict(line.split(' ',1) for line in header.splitlines())
        if fields.get('parent')!=parent:raise ValueError('only task linear history is allowed')
        paths=git('diff-tree','--no-commit-id','--name-only','-r',commit).decode().splitlines()
        if not all(allowed(p) for p in paths):raise ValueError('publication outside Issue104 scope')
        def blob(p):
            data=git('show',commit+':'+p)
            if len(data)>3000000:raise ValueError('large result needs shared storage: '+p)
            b=api('POST',PREFIX+'/git/blobs',dict(content=base64.b64encode(data).decode(),encoding='base64'))
            if b['sha']!=git('rev-parse',commit+':'+p).decode().strip():raise ValueError('blob mismatch')
            return dict(path=p,mode='100644',type='blob',sha=b['sha'])
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:entries=list(pool.map(blob,paths))
        tree=api('POST',PREFIX+'/git/trees',dict(base_tree=git('rev-parse',parent+'^{tree}').decode().strip(),tree=entries))
        if tree['sha']!=fields['tree']:raise ValueError('tree mismatch')
        uploaded=api('POST',PREFIX+'/git/commits',dict(message=message,tree=tree['sha'],parents=[parent],
            author=person(fields['author']),committer=person(fields['committer'])))
        if uploaded['sha']!=commit:raise ValueError('commit mismatch')
        parent=commit
    if current:
        x=api('PATCH',PREFIX+'/git/refs/heads/'+BRANCH,dict(sha=head,force=False))
    else:x=api('POST',PREFIX+'/git/refs',dict(ref='refs/heads/'+BRANCH,sha=head))
    if x['object']['sha']!=head:raise ValueError('ref mismatch')
    return dict(repo=REPO,branch=BRANCH,head=head,commits_uploaded=len(commits),exact_objects=True)


def main():
    user=api('GET','/user')
    if user['login']!='jieruiz':raise ValueError('unexpected GitHub identity')
    mode=sys.argv[1]
    if mode=='push':
        result=publish();save('PUSH.json',result);print(json.dumps(result))
    elif mode=='pr':
        prs=api('GET',PREFIX+'/pulls?state=all&head=rayggxia-workspace:'+BRANCH)
        args=dict(title='架构检查台：模块数据流、采样周期、存储与证据的可视化审计',
            body=(OUT/'PR_BODY.md').read_text(encoding='utf-8'))
        if prs:pr=api('PATCH',PREFIX+'/pulls/'+str(prs[0]['number']),args)
        else:pr=api('POST',PREFIX+'/pulls',dict(**args,head=BRANCH,base='pbit-tlm-attention-details-20261016',draft=False))
        result=dict(number=pr['number'],url=pr['html_url'],head=pr['head']['sha'],state=pr['state'],draft=pr['draft'])
        save('PUBLICATION.json',result);print(json.dumps(result))
    elif mode=='comment':
        x=api('POST',PREFIX+'/issues/104/comments',dict(body=(OUT/'ISSUE_UPDATE.md').read_text(encoding='utf-8')))
        print(json.dumps(dict(url=x['html_url'])))
    elif mode=='verify':
        head=git('rev-parse','HEAD').decode().strip();remote=api('GET',PREFIX+'/git/ref/heads/'+BRANCH)
        if remote['object']['sha']!=head:raise ValueError('remote head mismatch')
        result=[]
        for p in ['architecture_tlm/inspector/model-inspector.html','architecture_tlm/inspector/build.py',
                  'architecture_tlm/inspector/CHECK_REPORT_ZH.md','architecture_tlm/unified_v6/model.py',
                  'architecture_tlm/checks/test_observation_hooks_v6.py','work/jieruiz/104/HANDOFF.md',
                  'progress/jieruiz/STATUS.md',
                  'architecture_tlm/inspector/results/observed_v3/qwen_L2048_seed0_sc_screen_rejection_observed.json']:
            oid=git('rev-parse',head+':'+p).decode().strip();b=api('GET',PREFIX+'/git/blobs/'+oid)
            raw=base64.b64decode(b['content'])
            if raw!=git('show',head+':'+p):raise ValueError('published bytes mismatch')
            import hashlib
            result.append(dict(path=p,blob=oid,sha256=hashlib.sha256(raw).hexdigest()))
        save('REMOTE_VERIFY.json',dict(head=head,files=result));print(json.dumps(dict(head=head,files_verified=len(result))))


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');main()
