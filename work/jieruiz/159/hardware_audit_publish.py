"""Publish Issue159 correction; exact objects, no merge or job changes."""
import hashlib
import json
from pathlib import Path
import sys
import publish as p

p.BRANCH = 'task/159-hardware-forward-contract'
p.BASE = 'd6d33995754fcdcea99286e4ce43f91647aa231a'
D = p.ROOT/'qwen3/training/sc_qat_20261023'
ENTRY = '''## 2026-10-24 Issue159：硬件前向纠错

用户明确要求从电路出发。确认旧训练清单及近期固定尺度PPL仍使用FP32 g/u、SiLU与乘积；x/z A8不等于非线性量化。任意实数W scale、恢复/跨tile累加亦待统一。已有FP32数字RTL/PPA只证明其自身路径，不能代替随机非线性证据。FP32已降为诊断oracle，部署前向必须先冻结有限位宽/缩放/舍入/随机响应与流相关性契约。训练主权重/优化器/反向可保留浮点。W4/6/8和57项计划保留但不可启动部署验收；3项门禁测试通过，无新训练/PPL/RTL/PPA，无作业取消。

负责人jieruiz，Issue159，分支task/159-hardware-forward-contract，base d6d33995，复用tmp/qwen3-qat-plan-issue159-20261023；旧PR161已合并，新纠错PR见work/jieruiz/159/HARDWARE_PUBLICATION.json。正式审计qwen3/training/sc_qat_20261023/HARDWARE_FORWARD_AUDIT_ZH.md；交接REMOTE_AGENT_START_HERE_ZH.md，必填HARDWARE_CONTRACT.example.json。发布不代表远端Agent已修改训练，需执行任务回传计划/实现SHA；Projects未同步。不修改历史封存证据，不覆盖其他成员。

'''

def prepend(path):
    data=path.read_bytes()
    if ENTRY.splitlines()[0].encode() not in data:
        path.write_bytes(ENTRY.encode()+data)

if sys.argv[1]=='prepare':
    for rel in ('PROJECT_MEMORY_ZH.md','progress/jieruiz/STATUS.md','work/jieruiz/159/HANDOFF.md'):
        prepend(p.ROOT/rel)
    root=p.ROOT.parents[1]
    canonical=root/'tmp/project-memory-issue28-20261018/PROJECT_MEMORY_ZH.md'
    mirror=root/'PROJECT_MEMORY_ZH.md'
    assert canonical.read_bytes()==mirror.read_bytes(), 'Concurrent memory change; reconcile first'
    prepend(canonical)
    mirror.write_bytes(canonical.read_bytes())
    p.save('HARDWARE_VALIDATION.json',dict(date='2026-10-24',tests_passed=3,
        test_command='python -B -m unittest discover -s qwen3/training/sc_qat_20261023 -p test_hardware_gate.py -v',
        scan_manifest_sha256=hashlib.sha256((D/'SCAN_MANIFEST.json').read_bytes()).hexdigest(),
        scope='design-only gate, not hardware validation',new_gpu_or_rtl_tests=False,
        matched_model_or_data='not applicable: no new model execution'))
elif sys.argv[1]=='publish':
    assert p.api('GET','/user')['login']=='jieruiz'
    result=p.push()
    body='''旧训练交接把FP32 g/u、SiLU与乘积当成部署训练契约，与目标随机非线性电路不符。本次将其降为诊断oracle，新增硬件前向缺口审计、必填格式/响应契约和启动门禁，保留W4/6/8及原57项条件扫描。

关联Issue #159，接续已合并PR #161。审计涵盖任意权重scale、有限累加/恢复、随机非线性及现有FP32 RTL/TLM的边界；不改历史实验或他人任务。

验证：3项设计门禁测试通过；57项清单生成与跨位宽一致性通过；缺失硬件契约时启动拒绝；git diff --check通过。未实现新硬件前向，未运行GPU训练/PPL、RTL或PPA。Projects待维护者同步，不自动合并。'''
    prs=p.api('GET',p.PREFIX+'/pulls?state=open&head=rayggxia-workspace:'+p.BRANCH)
    args=dict(title='纠正Qwen3训练前向：FP32非线性仅作参考，增加硬件契约门禁',body=body)
    pr=p.api('PATCH',p.PREFIX+'/pulls/'+str(prs[0]['number']),args) if prs else p.api('POST',p.PREFIX+'/pulls',dict(**args,head=p.BRANCH,base='pbit-tlm-attention-details-20261016',draft=False))
    head=result['head']
    paths=p.git('diff','--name-only',p.BASE,head).decode().splitlines()
    checked=[]
    for name in paths:
        sha=p.git('rev-parse',head+':'+name).decode().strip()
        obj=p.api('GET',p.PREFIX+'/git/blobs/'+sha)
        import base64
        data=base64.b64decode(obj['content'])
        assert data==p.git('show',head+':'+name),name
        checked.append(dict(path=name,sha256=hashlib.sha256(data).hexdigest()))
    comment=p.api('POST',p.PREFIX+'/issues/159/comments',dict(body=body+'\n\n更正PR：'+pr['html_url']+'\n提交：'+head+'\n逐文件远端回读一致。远程执行仍需确认采用本次计划SHA；没有自动修改或取消远端训练。'))
    result.update(pr=pr['html_url'],number=pr['number'],state=pr['state'],merged=False,
        issue_comment=comment['html_url'],files_verified=checked,project_board_synced=False)
    p.save('HARDWARE_PUBLICATION.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='files_verified'},ensure_ascii=False))
