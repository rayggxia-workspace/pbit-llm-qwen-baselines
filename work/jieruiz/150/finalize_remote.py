"""Verify published scientific files, update existing PR/Issue; never merge."""
import base64
import hashlib
import json
from pathlib import Path
from publish import api, git, save, ROOT, OUT, PREFIX, BRANCH

assert api('GET','/user')['login']=='jieruiz'
head=git('rev-parse','HEAD').decode().strip()
assert api('GET',PREFIX+'/git/ref/heads/'+BRANCH)['object']['sha']==head
paths=['experiments/qwen_static_multiscale_20261023/'+n for n in
       ('static_core.py','test_static_core.py','run_static.py','collect_static.py','README_ZH.md')]
paths += ['qwen/results/static_multiscale_20261023/'+n for n in
          ('REPORT_ZH.md','SUMMARY.json','SUMMARY_ZH.md','SELECTED.json','SELECTED.sha256.json','RAW_INDEX.json')]
paths += ['work/jieruiz/150/HANDOFF.md','progress/jieruiz/STATUS.md','PROJECT_MEMORY_ZH.md']
verified=[]
for path in paths:
    oid=git('rev-parse',head+':'+path).decode().strip()
    remote=api('GET',PREFIX+'/git/blobs/'+oid)
    payload=base64.b64decode(remote['content'])
    assert payload==git('show',head+':'+path)
    verified.append(dict(path=path,blob=oid,sha256=hashlib.sha256(payload).hexdigest()))
save('REMOTE_VERIFY.json',dict(scientific_head=head,files=verified,verified=True))
pr=api('PATCH',PREFIX+'/pulls/153',dict(body=(OUT/'PR_BODY.md').read_text(encoding='utf-8')))
if pr['draft']:
    result=api('POST','/graphql',dict(query='mutation($id:ID!){markPullRequestReadyForReview(input:{pullRequestId:$id}){pullRequest{id isDraft}}}',variables=dict(id=pr['node_id'])))
    assert not result.get('errors'), result
pr=api('GET',PREFIX+'/pulls/153')
assert not pr['draft'] and not pr['merged'] and pr['state']=='open'
issue=api('GET',PREFIX+'/issues/150')
body=issue['body'].replace('- [ ]','- [x]')
body += '\n\n完整交付见PR #153及`qwen/results/static_multiscale_20261023/REPORT_ZH.md`；所有实验和证据核验完成，Issue保持open等待评审/合并。Projects无read:project待同步。'
api('PATCH',PREFIX+'/issues/150',dict(body=body))
comment=api('POST',PREFIX+'/issues/150/comments',dict(body=(OUT/'ISSUE_UPDATE.md').read_text(encoding='utf-8')))
receipt=dict(scientific_head=head,pr=153,url=pr['html_url'],draft=pr['draft'],state=pr['state'],merged=pr['merged'],
             verified_files=len(verified),issue_comment=comment['html_url'],project_board='blocked: read:project unavailable',
             experimental_status='21 full WT2 + 12 selection + 4 holdout complete; no pending jobs')
save('FINAL_PUBLICATION.json',receipt)
save('PUBLICATION.json',dict(number=153,url=pr['html_url'],head=pr['head']['sha'],state=pr['state'],draft=pr['draft']))
print(json.dumps(receipt))
