# -*- coding: utf-8 -*-
import base64,hashlib,json
from pathlib import Path
import github as g

assert g.api('GET','/user')['login']=='jieruiz'
dependency=g.api('GET',g.PREFIX+'/pulls/174')
print('dependency',dependency['state'],dependency['head']['sha'],flush=True)
assert dependency['head']['sha']=='bec546d4d4313bf9d818288a2c7764403f49cded', 'Review new dependency before publishing'
result=g.push();print('pushed',result['head'],flush=True)
body='''复现SMURF状态机机制并核验固定W8接口。4状态、P8整数比较、从复位开始64次IID更新的MAE为0.04405；独立打乱的32层输入为0.03399。原论文图9仅0～1且未给Swish完整参数，本PR是独立重建，不声称精确重现其0.033。

51组函数探针覆盖32/64/128拍、2/4/8/16状态、初始化/顺序和正负固定尺度。给出逐条流MAE及有限时长Markov均值/二阶矩对照。固定W8可以保留，但位平面须带权、符号与尺度归约，不能直接作为等权输入或分别做非线性。S64负分支系数量化全零等限制如实保留。

验证：8项功能/统计测试通过；51组结果manifest及解析RMSE核对通过；图表已检查。执行ba7ff03d，配置/源码/输入/结果SHA在MANIFEST。没有Qwen PPL、训练、RTL/PPA或新GPU任务，未证实优于已有分层AND路径。依赖PR174，仅新增独立模块及报告，不改旧执行快照。

Refs #175。报告：qwen3/results/smurf_swish_20261024/REPORT_ZH.md。'''
prs=g.api('GET',g.PREFIX+'/pulls?state=open&head=rayggxia-workspace:'+g.BRANCH)
if prs:p=prs[0]
else:p=g.api('POST',g.PREFIX+'/pulls',dict(title='Swish短流状态机：51组重建与固定W8位平面接口核验',head=g.BRANCH,base='task/173-and-direct-wd',body=body,draft=False))
result.update(pr=p['html_url'],pr_number=p['number'],state=p['state'],merged=False)
paths=g.git('diff','--name-only',g.BASE+'..HEAD').decode().splitlines()
verified=[]
for path in paths:
    b=g.git('show','HEAD:'+path)
    a=g.api('GET',g.PREFIX+'/contents/'+path+'?ref='+result['head'])
    assert a['sha']==g.git('rev-parse','HEAD:'+path).decode().strip()
    assert a['size']==len(b)
    if a.get('content') and len(b)<100000:
        assert base64.b64decode(a['content'])==b
    verified.append(dict(path=path,bytes=len(b),sha256=hashlib.sha256(b).hexdigest(),git_blob=a['sha']))
result['verified_files']=verified
try:
    project=g.api('POST','/graphql',{'query':'query { repository(owner:"rayggxia-workspace", name:"pbit-llm-qwen-baselines") { issue(number:175) { projectItems(first:20) { nodes { id project { title } } } } } }'})
    result['project_query']=project
except Exception as e:result['project_query_error']=str(e)
comment='''本地函数级实现与51组结果已推送 %s，待审未合并。8项测试、有限时长Markov二阶矩与manifest验证通过，源码/配置/结果均可追溯。4状态64拍IID MAE0.044052，32层乱序变体0.033992；原文仅正半轴且参数不全，不能称精确复现0.033。固定W8仍适用，但原始位平面不可直接等权喂FSM。没有Qwen PPL/训练/RTL/PPA，也未改Slurm2891。个人STATUS/HANDOFF及长期备忘录已同步。看板状态以PUBLICATION.json实际查询为准，未擅自创建看板项。'''%p['html_url']
c=g.api('POST',g.PREFIX+'/issues/175/comments',{'body':comment});result['issue_comment']=c['html_url']
g.save('PUBLICATION.json',result)
print(json.dumps({k:result[k] for k in ('head','pr','state','merged','issue_comment')},ensure_ascii=False),flush=True)
