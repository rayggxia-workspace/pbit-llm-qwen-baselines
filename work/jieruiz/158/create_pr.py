"""Create/recover this task's draft PR only; never merge."""
from publish import api, PREFIX, BRANCH, save

assert api('GET', '/user')['login'] == 'jieruiz'
existing = api('GET', PREFIX + '/pulls?state=open&head=rayggxia-workspace:' + BRANCH)
if existing:
    assert len(existing) == 1
    pr = existing[0]
else:
    pr = api('POST', PREFIX + '/pulls', dict(title='Qwen3-4B非Base：独立BF16基线与13项概率架构迁移',
        head=BRANCH, base='task/144-qwen3-stochastic', draft=True,
        body='关联#158。用户指定Qwen/Qwen3-4B，固定revision1cfa9a7208912126459214e8b04321603b3df60c，经hf-mirror准备；依赖PR147@357db588但不改Base代码/结果。新目录qwen3/posttrained，原算法W8/B4/T32/K32、max4、拒绝128/赢家1024保持；先新模型原生完整BF16两次精确重放，再13项4096目标后缀。原文teacher-forced PPL不使用聊天模板/思考生成，不自动跑完整概率WT2。\n\n本地5合同测试/compileall/diff通过；服务器包和44源SHA验证、提取快照5合同检查后CPU下载和GPU afterok任务，实际ID/状态以HANDOFF为准，尚无新PPL。完整旧基线评分源码原字节复用，只换模型配置；token和TRAIN校准从新模型独立生成。CPU/GPU门槛、结果归档和独立SHA/计分验证尚待完成。\n\n与Issue157 SparQ分工评论6367526124，本任务仅原架构，向其提供只读准备manifest，不覆盖其目录/作业。一个GPU、原venv只读、权重不上传。Projects待read:project权限；不合并/不关闭Issue。'))
assert pr['head']['ref'] == BRANCH and pr['base']['ref'] == 'task/144-qwen3-stochastic'
save('PR.json', dict(number=pr['number'], url=pr['html_url'], draft=pr['draft'], head=pr['head']['sha']))
print(pr['html_url'])
