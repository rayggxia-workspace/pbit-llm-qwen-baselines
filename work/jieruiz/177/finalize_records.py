# -*- coding: utf-8 -*-
"""Reconcile transient DDP status with sealed final evidence; no job changes."""
from pathlib import Path
import hashlib
import json

task=Path(__file__).resolve().parents[3]
workspace=task.parents[1]
replacements={
    '2908卡在NCCL初始化后已停止，2909使用本机socket进行隔离检查，最终状态待补。':
    '2908仅禁P2P在初始化等待后完成，2909本机socket也完成；按最终封存SHA核验，两卡参数一致，全部作业结束。',
    '附加DDP2907超时、2908初始化挂起后停止；2909本机socket隔离后三步通过，跨rank权重一致、冻结参数不变。全部作业结束。':
    '附加DDP2907超时；2908仅禁P2P在长初始化后已封存完成，2909本机socket隔离也通过，跨rank权重一致、冻结参数不变。全部作业结束。',
    'DDP2907默认NCCL超时、2908禁P2P仍初始化挂起后停止；2909以本机socket隔离配置三步通过':
    'DDP2907默认NCCL超时；2908禁P2P在长初始化后已封存完成（中途停止请求不覆盖最终完成证据），2909以本机socket隔离配置也三步通过',
    'DDP2907超时、2908手动停止初始化挂起；2909在socket隔离环境完成3步':
    'DDP2907超时；2908在长初始化后已封存完成，2909在socket隔离环境也完成3步',
}
files=[task/'progress/jieruiz/STATUS.md',task/'work/jieruiz/177/HANDOFF.md',
       task/'work/jieruiz/177/MEMORY_UPDATE_ZH.md',task/'PROJECT_MEMORY_ZH.md',
       workspace/'PROJECT_MEMORY_ZH.md',workspace/'tmp/project-memory-issue28-20261018/PROJECT_MEMORY_ZH.md']
for p in files:
    s=p.read_text(encoding='utf-8')
    for old,new in replacements.items():s=s.replace(old,new)
    p.write_bytes(s.encode('utf-8'))
assert (workspace/'PROJECT_MEMORY_ZH.md').read_bytes()==files[-1].read_bytes()==(task/'PROJECT_MEMORY_ZH.md').read_bytes()
base=task/'qwen3/training/stochastic_nonlinear/validation'
for name in ('results-2906','ddp-results-2908','ddp-results-2909'):
    d=base/name;m=json.loads((d/'COMPLETED.json').read_text())
    for n,digest in m['documents'].items():assert hashlib.sha256((d/n).read_bytes()).hexdigest()==digest,n
print('final sealed states and all document hashes reconciled')
