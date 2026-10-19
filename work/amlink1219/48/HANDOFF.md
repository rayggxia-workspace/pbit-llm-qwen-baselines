# Issue48 联合 Attention PPL 交接

负责人amlink1219；分支task/48-attention-joint-ppl；独立目录workspace_projects/aj48。PR base为task/35-attention-e01，明确依赖其输入身份核验代码；既有PR不自动合并。正式代码experiments/attention_joint_ising。

用户已授权执行概率QK筛选→候选QK→有限时间Ising→V累加，并扫描采样数。当前阶段为实现/验证准备，尚未提交本任务服务器作业。并行sampler、adapter、evaluator各在aj48s/aj48a/aj48e独立分支实现，根仅cherry-pick明确提交，不共享未提交文件。

2026-10-19服务器第一次SSH连接超时，第二次恢复。实际核验Weican_Chen、/home/Weican_Chen、本人队列空、gpu5090分区up/idle；目标个人目录/home/Weican_Chen/projects/attention-joint-issue48。仅复用本人既有venv、原模型和数据；尚未因队列空就直接在登录节点计算。

先读README_ZH.md的计分/随机/预算契约，核最新Issue48/33/35/37及成员STATUS。模型数据核验复用Issue35已记录的同一原权重、tokenizer、WT2与token SHA，不读取历史报告中的其他用户服务器目录。

下一步：完成并审查三个模块，冻结完整Git源和fixture，CPU Slurm preflight通过后再GPU preflight复现原BF16及真实24层smoke。按其耗时在单GPU顺序跑34项后缀PPL；之后仅对有依据的S做少量完整cached WT2确认。每步保存不可变snapshot、submission intent/job ID、首终态、成果SHA；连接中断先查作业，不重复提交。

历史原manifest继续按对应旧commit验证。本任务新成果单列，原模型/校准/旧140项/其他成员FFN任务不改。Projects缺read:project/project scope待同步，不把Issue/PR更新冒称看板已同步。
