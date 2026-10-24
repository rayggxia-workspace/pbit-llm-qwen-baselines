"""Narrow, explicit publication/merge steps for the user-authorized Issue179."""
import argparse
import base64
import concurrent.futures
import hashlib
import json
from pathlib import Path
import subprocess
import github as g

def checked_identity():
    u=g.api('GET','/user')
    assert u['login']=='jieruiz',u['login']
    r=g.api('GET',g.PREFIX)
    assert r['permissions']['push']
    return dict(login=u['login'],repo=r['full_name'],permissions=r['permissions'])

def publish():
    identity=checked_identity()
    result=g.push()
    head=result['head']
    local=g.git('ls-tree','-r','--long',head).decode().splitlines()
    tree={x['path']:x for x in g.api('GET',g.PREFIX+'/git/trees/'+head+'?recursive=1')['tree']}
    paths=g.git('diff','--name-only',g.BASE,head).decode().splitlines()
    verified=[]
    for line in local:
        metadata,path=line.split('\t',1)
        if path not in paths:continue
        _,kind,sha,size=metadata.split()
        assert kind=='blob' and tree[path]['sha']==sha and tree[path]['size']==int(size),path
        verified.append(dict(path=path,blob=sha,bytes=int(size)))
    assert len(verified)==len(paths)
    result.update(identity=identity,verified=verified)
    g.save('PUBLICATION.json',result)
    body=(g.OUT/'PR_BODY.md').read_text(encoding='utf-8')
    pr=g.api('PATCH',g.PREFIX+'/pulls/180',dict(body=body))
    g.save('PR_FINAL.json',pr)
    print(json.dumps(dict(head=head,verified_files=len(verified),pr=pr['html_url'])))

def merge():
    identity=checked_identity()
    head=g.git('rev-parse','HEAD').decode().strip()
    p=g.api('GET',g.PREFIX+'/pulls/180')
    if p['merged']:
        assert p['head']['sha']==head
        g.save('MERGE.json',dict(already_merged=True,merge_commit_sha=p['merge_commit_sha'],pr=p))
        print('already merged',p['merge_commit_sha']);return
    assert p['state']=='open' and not p['draft'] and p['base']['ref']=='main'
    assert p['head']['sha']==head and p['head']['ref']==g.BRANCH
    assert p['mergeable'] is True and p['mergeable_state']=='clean',(p['mergeable'],p['mergeable_state'])
    branch=g.api('GET',g.PREFIX+'/branches/main')
    assert branch['commit']['sha']==g.BASE,'main changed; rebase/review before merge'
    checks=g.api('GET',g.PREFIX+'/commits/'+head+'/check-runs')
    statuses=g.api('GET',g.PREFIX+'/commits/'+head+'/status')
    reviews=g.api('GET',g.PREFIX+'/pulls/180/reviews')
    decisions={}
    for review in reviews:
        if review['state'] in ('APPROVED','CHANGES_REQUESTED','DISMISSED'):
            decisions[review['user']['login']]=review['state']
    assert 'CHANGES_REQUESTED' not in decisions.values(),decisions
    assert all(c['status']=='completed' and c['conclusion'] in ('success','neutral','skipped') for c in checks['check_runs']),checks
    assert all(s['state']=='success' for s in statuses['statuses']),statuses
    g.save('MERGE_PRECHECK.json',dict(identity=identity,pr=p,branch=branch,checks=checks,statuses=statuses,reviews=reviews))
    merged=g.api('PUT',g.PREFIX+'/pulls/180/merge',dict(sha=head,merge_method='merge',
        commit_title='Merge PR #180: unify latest fixed-scale stochastic FFN TLM'))
    g.save('MERGE.json',merged)
    assert merged.get('merged'),merged
    print(json.dumps(merged))

def receipt():
    p=g.api('GET',g.PREFIX+'/pulls/180');assert p['merged']
    main=g.api('GET',g.PREFIX+'/branches/main')
    merge=g.api('GET',g.PREFIX+'/git/commits/'+p['merge_commit_sha'])
    head=g.git('rev-parse','HEAD').decode().strip()
    assert p['head']['sha']==head
    assert head in [x['sha'] for x in merge['parents']]
    assert merge['tree']['sha']==g.git('rev-parse',head+'^{tree}').decode().strip()
    result=dict(repo=g.REPO,pr_url=p['html_url'],merged_at=p['merged_at'],
        head=head,merge_sha=p['merge_commit_sha'],main_sha=main['commit']['sha'],same_tree=True)
    g.save('MERGE_VERIFIED.json',result)
    print(json.dumps(result))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=('publish','merge','receipt'))
    {'publish':publish,'merge':merge,'receipt':receipt}[p.parse_args().action]()
