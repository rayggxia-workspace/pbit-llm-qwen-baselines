> 已发布：[PR #42](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/42)，待审、未合并。当前正文见PR_BODY_CURRENT.md；以下为原待发布草稿，权限/发布状态仅指当时时点。

# docs: plan Attention p-bit value validation and RNG architecture experiments

Attention当前只有概率筛选的数字实现和理想Ising宏，尚未证明物理p-bit相对数字电路的收益。本变更核查主要原文、现有随机源/消费路径，制定常规数字硬算、online融合、数字IID/systematic与原生概率/类别模块的公平仿真实验计划。

Refs #33，负责人@amlink1219。目标rayggxia-workspace/pbit-llm-qwen-baselines；分支task/33-attention-value-plan，拟base pbit-tlm-attention-details-20261016 @3553996。上传前重新核目标与当前base。

正式计划及配置在architecture_tlm/；623行计划矩阵、11项文献/归档回执、源SHA和交接在work/amlink1219/33/；个人进度在progress/amlink1219/STATUS.md。三个输出契约分别比较，短S与稳态诊断分开；串行Ising必须先估时，8K本轮仅成本stress，基础PPL与后续扩seed预算分开。

实际验证：UTF-8/LF、JSON/CSV、623个唯一case、24个不可行筛选点、8K成本标签、引用/链接、来源SHA及Git暂存/提交字节核验。独立技术审查完成，Zotero新增4/复用7、9项带托管PDF；2附件待补。验证明细见VALIDATION.json。

没有运行新的GPU模型、PPL、训练、RTL/DC/PT、TLM或服务器作业；未更改既有算法/默认配置，不接管Issue19/22/30/32。无论文原件、权重、数据、工艺库、凭据或大轨迹上传。

当前push=false，本文是待创建PR正文；分支未上传、PR未创建，Projects缺read:project待同步。Issue33只同步真实本地阶段，不因计划写成就关闭实验验收。
