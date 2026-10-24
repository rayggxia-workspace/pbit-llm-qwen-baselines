import base64,json
from github import api,save,PREFIX,ROOT,git
me=api('GET','/user');assert me['login']=='jieruiz'
repo=api('GET',PREFIX)
pr=api('GET',PREFIX+'/pulls/174');issue=api('GET',PREFIX+'/issues/173')
assert pr['state']=='open' and not pr['merged'] and pr['head']['sha']==git('rev-parse','HEAD').decode().strip()
latest=api('GET',PREFIX+'/issues?state=open&sort=updated&per_page=25')
docs={}
for name in ('README.md','AGENTS.md'):
    obj=api('GET',PREFIX+'/contents/'+name+'?ref='+pr['head']['ref'])
    docs[name]=base64.b64decode(obj['content']).decode()
print(json.dumps(dict(login=me['login'],repo=repo['full_name'],pr174=dict(head=pr['head']['sha'],state=pr['state']),issue173=issue['body'],recent=[dict(n=x['number'],title=x['title']) for x in latest]),ensure_ascii=False))
save('MULTISCALE_REMOTE_CHECK.json',dict(login=me['login'],repo=repo['full_name'],pr_head=pr['head']['sha'],docs=docs,recent=[dict(n=x['number'],title=x['title']) for x in latest]))
api('POST',PREFIX+'/issues/173/comments',dict(body='用户授权接续：在原三流AND直连Wd上测试g/u固定多档二次幂编码，分别保留sigmoid真实输入尺度并在Wd部分和归约时按指数和移位对齐。复用同任务目录/分支，旧冻结快照与负结果不改；新增快照与同轮BF16、三seed、无有限采样均值对照。研究LUT/FSM/p-bit增益边界；不启动训练、不宣称新PPA。'))
