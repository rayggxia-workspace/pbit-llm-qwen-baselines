# -*- coding: utf-8 -*-
import base64,concurrent.futures,hashlib,json
import github as g
assert g.api('GET','/user')['login']=='jieruiz'
head=g.git('rev-parse','HEAD').decode().strip()
ref=g.api('GET',g.PREFIX+'/git/ref/heads/'+g.BRANCH)
assert ref['object']['sha']==head
paths=g.git('diff','--name-only',g.BASE+'..HEAD').decode().splitlines();cache={}
def tree(sha):
    if sha not in cache:cache[sha]=g.api('GET',g.PREFIX+'/git/trees/'+sha)['tree']
    return cache[sha]
verified=[];root=g.git('rev-parse','HEAD^{tree}').decode().strip()
for path in paths:
    data=g.git('show','HEAD:'+path);cur=root
    for part in path.split('/'):
        o=next(x for x in tree(cur) if x['path']==part)
        if o['type']=='tree':cur=o['sha']
    assert o['sha']==g.git('rev-parse','HEAD:'+path).decode().strip() and o['size']==len(data)
    verified.append(dict(path=path,bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),git_blob=o['sha']))
def raw(v):
    for attempt in range(3):
        try:
            r=g.api('GET',g.PREFIX+'/git/blobs/'+v['git_blob']);b=base64.b64decode(r['content'])
            assert hashlib.sha256(b).hexdigest()==v['sha256'];return v['path']
        except Exception:
            if attempt==2:raise
critical=[v for v in verified if v['path'] in (
    'qwen3/smurf_swish/model_core.py','qwen3/smurf_swish/model_kernel.py',
    'qwen3/smurf_swish/model_tables.py','qwen3/smurf_swish/model_run.py',
    'qwen3/smurf_swish/model_config.json','qwen3/results/smurf_swish_20261024/model/REPORT_ZH.md')]
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:raw_verified=list(pool.map(raw,critical))
body='固定g数制FSM模型试测已完成并推送。128份/118唯一配置封存SHA、三seed、36层覆盖、每片13项预检通过。BF16=13.5660；最好实际FSM128 PPL=1757.8026，对应期望623.0503。固定g精确SiLU表期望有接近参考的配置，故本次失败不能只归因缩放或采样不够。所有失败记录保留。报告：qwen3/results/smurf_swish_20261024/model/REPORT_ZH.md。提交 '+head+'；PR176待审未合并。全部改动文件远端Git blob/长度核验，六个核心文件原字节回读。上一轮逐文件回读网络断开，没有重跑实验；本回执补齐核验。STATUS/HANDOFF/长期备忘录已同步；无本任务运行中作业或新增定时。Projects缺read:project待同步。'
c=g.api('POST',g.PREFIX+'/issues/175/comments',dict(body=body))
p=g.api('GET',g.PREFIX+'/pulls/176');assert p['head']['sha']==head
result=dict(head=head,pr=p['html_url'],state=p['state'],merged=p['merged'],
    verified_files=verified,raw_verified=raw_verified,issue_comment=c['html_url'],
    verification='Every changed path: remote Git blob and length; six core files raw bytes.',
    earlier_verification_failure='RemoteDisconnected on optional raw read; push and PR update had succeeded.',
    projects='read:project permission missing; pending maintainer synchronization')
g.save('MODEL_PUBLICATION.json',result)
print(json.dumps({k:result[k] for k in ('head','pr','state','merged','issue_comment')},ensure_ascii=False),flush=True)
