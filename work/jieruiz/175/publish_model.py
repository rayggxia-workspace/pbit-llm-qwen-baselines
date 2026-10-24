# -*- coding: utf-8 -*-
import base64,hashlib,json
import github as g
assert g.api('GET','/user')['login']=='jieruiz'
dependency=g.api('GET',g.PREFIX+'/pulls/174')
print('dependency',dependency['state'],dependency['head']['sha'],flush=True)
r=g.push();print('pushed',r['head'],flush=True)
report=(g.ROOT/'qwen3/results/smurf_swish_20261024/model/REPORT_ZH.md').read_text(encoding='utf-8')
body='''固定g数制、把真实尺度写入SiLU目标的状态机已完成Qwen3-4B模型试测。所有4/8状态候选均明显劣化；保留精确SiLU表的条件均值控制有接近参考的配置，FSM条件均值已严重偏离，不能只归因采样不够。详见下表。

Refs #175，依赖PR174。保留此前51组函数探针，新增128份后缀计分/118唯一配置、8个同轮BF16和三seed。Slurm2898/2902每片13测试通过，封存SHA及36层覆盖核验；2894编译预检失败原件保留。不是完整WT2，没有训练或RTL/PPA；前级恢复仍参考算术。代码/数制/随机过程/系数及原件索引已归档。

'''+report
p=g.api('PATCH',g.PREFIX+'/pulls/176',dict(title='Swish FSM：固定g尺度真实Qwen3测试与三路方案对照',body=body))
paths=g.git('diff','--name-only',g.BASE+'..HEAD').decode().splitlines()
cache={}
def tree(sha):
    if sha not in cache:cache[sha]=g.api('GET',g.PREFIX+'/git/trees/'+sha)['tree']
    return cache[sha]
verified=[]
for path in paths:
    b=g.git('show','HEAD:'+path);cur=g.git('rev-parse','HEAD^{tree}').decode().strip()
    for part in path.split('/'):
        obj=next(x for x in tree(cur) if x['path']==part)
        if obj['type']=='tree':cur=obj['sha']
    assert obj['sha']==g.git('rev-parse','HEAD:'+path).decode().strip() and obj['size']==len(b)
    if len(b)<64000:
        raw=g.api('GET',g.PREFIX+'/git/blobs/'+obj['sha']);assert base64.b64decode(raw['content'])==b
    verified.append(dict(path=path,bytes=len(b),sha256=hashlib.sha256(b).hexdigest(),git_blob=obj['sha']))
comment='已完成并推送固定g数制FSM模型试测，128份/118唯一配置封存核验、三seed、36层覆盖、13项服务器预检均通过。所有候选质量明显劣化，非线性近似偏差是主要问题之一，结果和失败证据均保留。报告：qwen3/results/smurf_swish_20261024/model/REPORT_ZH.md。提交 '+r['head']+'；PR176待审未合并。STATUS/HANDOFF/长期备忘录已同步；无运行中本任务或新定时。Projects缺read:project待维护者同步。'
r.update(pr=p['html_url'],pr_number=176,merged=False,verified_files=verified,
    dependency_head=dependency['head']['sha'],verification='Git blob SHA and size all files; raw bytes below64KB',
    issue_comment=g.api('POST',g.PREFIX+'/issues/175/comments',dict(body=comment))['html_url'])
g.save('MODEL_PUBLICATION.json',r)
print(json.dumps({k:r[k] for k in ('head','pr','merged','issue_comment')},ensure_ascii=False),flush=True)
