"""Read current collaboration state before revising the remote-agent handoff."""
import base64, concurrent.futures, json
from publish import api, PREFIX, OUT, ROOT

paths={'user':'/user','pr161':PREFIX+'/pulls/161','issue159':PREFIX+'/issues/159',
       'comments159':PREFIX+'/issues/159/comments?per_page=100',
       'pr147':PREFIX+'/pulls/147','pr153':PREFIX+'/pulls/153',
       'pr160':PREFIX+'/pulls/160','issue158':PREFIX+'/issues/158',
       'comments158':PREFIX+'/issues/158/comments?per_page=100',
       'integration':PREFIX+'/branches/pbit-tlm-attention-details-20261016'}
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    data=dict(pool.map(lambda x:(x[0],api('GET',x[1])),paths.items()))
assert data['user']['login']=='jieruiz'
out=OUT/'remote_agent_v2';out.mkdir(exist_ok=True)
base=data['integration']['commit']['sha']
for path in ['README.md','AGENTS.md','progress/jieruiz/STATUS.md']:
    r=api('GET',PREFIX+'/contents/'+path+'?ref='+base)
    (out/('LATEST_'+path.replace('/','__'))).write_bytes(base64.b64decode(r['content']))
summary=dict(login=data['user']['login'],integration=base,
    prs={k:dict(head=data[k]['head']['sha'],base=data[k]['base']['ref'],state=data[k]['state'],merged=data[k]['merged']) for k in ['pr161','pr147','pr153','pr160']},
    issue=dict(state=data['issue159']['state'],title=data['issue159']['title']),
    comments=[dict(user=c['user']['login'],created=c['created_at'],body=c['body']) for c in data['comments159']],
    baseline_issue=dict(state=data['issue158']['state'],body=data['issue158']['body']),
    baseline_comments=[dict(user=c['user']['login'],created=c['created_at'],body=c['body']) for c in data['comments158']])
handoff=api('GET',PREFIX+'/contents/work/jieruiz/158/HANDOFF.md?ref='+data['pr160']['head']['sha'])
(out/'BASELINE_158_HANDOFF.md').write_bytes(base64.b64decode(handoff['content']))
(out/'PREFLIGHT.json').write_bytes((json.dumps(summary,ensure_ascii=False,indent=2)+'\n').encode())
print(json.dumps(summary,ensure_ascii=False))
