# -*- coding: utf-8 -*-
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT.parents[1]
submission=ROOT/'work/jieruiz/175/MODEL_SUBMISSION.json'
r=json.loads(submission.read_bytes())
if not any(a['job']=='2898_[0-3]' for a in r['attempts']):
    r['attempts'].append(dict(job='2898_[0-3]',commit='462d4fe168fbb7168a5cd742ec1270f02f6ce466',
      source_sha256='f50ebe7c4b00a7c599bd86fedb677f9c3eddcf5c7bdc28b369a67759ef12180c',
      snapshot='snapshot-462d4fe1',status='submitted_preflight_pending',logs='logs/2898_[0-3].log',
      planned_physical_results=64,results='results/shard0..3',max_walltime_hours=3))
submission.write_bytes((json.dumps(r,indent=2)+'\n').encode())
note='''## Issue175：固定g数制FSM进入模型试测（2026-10-24）

用户明确要求实际测试FSM以减少g分档。新模块qwen3/smurf_swish/model_*，固定G=8/16、幅度P8＋符号，无在线max或g逐值选档。真实G写进SiLU目标；有限T状态占用拟合，theta0=0、复位0，无预热；逐拍R8输入更新→状态系数比较→独立u比较AND→固定W8 Wd，仅最终整数统计恢复。负输出单位Sf=.5或G另测，不保证可拟合。u沿用TRAIN固定四档，前级x固定四档共享64 T=K64；准确Attention。四组(G,N,Sf)=(8,4,.5)/(8,8,.5)/(16,8,.5)/(8,8,8)，各含BF16及LUT均值/FSM64和128均值/实际64和128，概率三seed，64份后缀计划。IID FSM基线，未混称分层；模型前级恢复仍FP32参考，非整链bittrue/PPA。

Slurm2894四片均在CUDA编译预检失败，模型未启动；uint32随机键类型已修复，新冻结462d4fe168fbb7168a5cd742ec1270f02f6ce466、Slurm2898_[0-3]已提交。源包SHAf50ebe7c4b00a7c599bd86fedb677f9c3eddcf5c7bdc28b369a67759ef12180c，原失败快照保留。当前无封存新模型结果；本机7项通过、3项CUDA待服务器。个人目录pbit-qwen3-smurf-model-20261024-issue175，MODEL_SUBMISSION.json含准确快照/作业/日志，健康任务不重交。无新定时。

负责人jieruiz，task/175-smurf-swish，tmp/smurf-swish-20261024，沿用Issue175/PR176待审未合并；新发布以MODEL_PUBLICATION.json为准，Projects缺read:project待同步。完成时核对complete/documents/sidecar SHA、36层全前缀、同轮BF16和1024目标位置一致，再汇总；不是完整WT2，不用函数MAE冒充PPL。

'''
canonical=BASE/'tmp/project-memory-issue28-20261018/PROJECT_MEMORY_ZH.md';mirror=BASE/'PROJECT_MEMORY_ZH.md'
assert canonical.read_bytes()==mirror.read_bytes()
old=canonical.read_text(encoding='utf-8');data=note+old if not old.startswith(note) else old
for p in (canonical,mirror,ROOT/'PROJECT_MEMORY_ZH.md'):p.write_bytes(data.encode('utf-8'))
for p in (ROOT/'progress/jieruiz/STATUS.md',ROOT/'work/jieruiz/175/HANDOFF.md'):
    old=p.read_text(encoding='utf-8')
    if not old.startswith(note):p.write_bytes((note+old).encode('utf-8'))
