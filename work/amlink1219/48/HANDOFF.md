# 当前接续点：正式作业2380运行中

2026-10-19；执行源11f1d6eea2776e201f2021081f8b0fbae2cc455e已推送PR49。CPU2362 COMPLETED/0:0（38测试），GPU2365 COMPLETED/0:0（原BF16完整PPL及同BF16 wrapper逐位一致）。GPU2331原失败留档，没有覆盖旧快照。

在本机资料根用Python313执行 outputs/attention_joint_ppl_20261019/monitor_compact.py sweep，只读检查2380；终态立即落本机terminal_sweep_2380.txt。完成后 collect_stage.py sweep 2380 回收本人目录的小型JSON，逐项SHA核验，再 summarize_results.py --source .../raw/sweep-2380 --output 新目录。不要重交已存在submission intent/receipt；SSH断开不等于作业停止。

冻结源位于本人服务器 /home/Weican_Chen/projects/attention-joint-issue48/snapshots/11f1d6eea2776e201f2021081f8b0fbae2cc455e；输出outputs/sweep-2380。34项注册见experiments/attention_joint_ising/registered_suffix_cases.json。完整WT2确认仅在曲线与耗时核验后注册少量案例，不把4096后缀称完整299077目标。Projects同步仍缺read:project/project scope。

以下保留历史准备/失败记录；“待提交/待门禁”等旧句已被上方当前状态替代。

# 首次门禁与诊断修订

CPU2327 COMPLETED/0:0；35测试及18源/模型/数据SHA通过。GPU2331 FAILED/1:0，原BF16完整精确复现11.652735，但短32target的manual FP32 vs原BF16 SDPA差异触发原.003门禁。参数/缓冲前后SHA一致；失败小型原件已SHA回收，不将该门禁失败称模型方案失败。

新修订新增同BF16 SDPA核心的wrapper控制及两次原SDPA重现，逐位hash全部计分logits。只有该严格接入检查通过后才跑正式曲线；manualFP32作为数值路径差异另报。所有pilot统一4段×8目标。当前38/38 CPU测试通过，待新CPU/GPU门禁，不覆盖旧fb032e0快照或2327/2331。

# Issue48 联合 Attention PPL 交接

负责人amlink1219；分支task/48-attention-joint-ppl；独立目录workspace_projects/aj48。PR base为task/35-attention-e01，明确依赖其输入身份核验代码；既有PR不自动合并。正式代码experiments/attention_joint_ising。

用户已授权执行概率QK筛选→候选QK→有限时间Ising→V累加，并扫描采样数。当前阶段为实现/验证准备，尚未提交本任务服务器作业。并行sampler、adapter、evaluator各在aj48s/aj48a/aj48e独立分支实现，根仅cherry-pick明确提交，不共享未提交文件。

2026-10-19服务器第一次SSH连接超时，第二次恢复。实际核验Weican_Chen、/home/Weican_Chen、本人队列空、gpu5090分区up/idle；目标个人目录/home/Weican_Chen/projects/attention-joint-issue48。仅复用本人既有venv、原模型和数据；尚未因队列空就直接在登录节点计算。

先读README_ZH.md的计分/随机/预算契约，核最新Issue48/33/35/37及成员STATUS。模型数据核验复用Issue35已记录的同一原权重、tokenizer、WT2与token SHA，不读取历史报告中的其他用户服务器目录。

下一步：完成并审查三个模块，冻结完整Git源和fixture，CPU Slurm preflight通过后再GPU preflight复现原BF16及真实24层smoke。按其耗时在单GPU顺序跑34项后缀PPL；之后仅对有依据的S做少量完整cached WT2确认。每步保存不可变snapshot、submission intent/job ID、首终态、成果SHA；连接中断先查作业，不重复提交。

历史原manifest继续按对应旧commit验证。本任务新成果单列，原模型/校准/旧140项/其他成员FFN任务不改。Projects缺read:project/project scope待同步，不把Issue/PR更新冒称看板已同步。
