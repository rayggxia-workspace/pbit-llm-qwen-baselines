# 最新：诊断完成，PPL部分结果与后续运行

时间：2026-10-21T07:12:29.385386+00:00；Issue78/PR79，jieruiz，未合并。

- 数值执行源0c0d8978908e9232cb94b75ac301a8254f834645保持不变；分析源344498a6d1867cb637d6d0955a37a9c283357251。9项本地/远端CPU合同通过（6采样+3汇总）。
- CPU Slurm2600已完成405项合成配置/控制记录，2601本次CPU BF16和SDPA包装NLL一致通过；2608已完成42行真实Qwen分数的48项重放记录。真实NPZ只在服务器，不上传。
- 128目标后缀BF16 PPL20.212326；CTMC S64三seed23.245402/23.527614/22.704328，均值23.159115、SD0.418371。全同步κ12目前两seed129.479031/82.224259；不能用两seed均值冒充三seed完成，也不等于完整WT2。
- 已发布的部分SUMMARY对应5/18完成、13pending；后续2602数组继续。六路CPU并发（每项4核、不用GPU），节点64核中原GPU任务约32核，仍留空闲；scontrol对已结束3/4返回finished、pending5-17更新成功，实际ArrayTaskThrottle6已核验，不是全部更新失败。无原作业取消/快照改写。
- 2609为afterany:2600:2602:2608的服务器自动汇总，完成后写outputs/0c0d897.../collected/RESULTS_ZH.md及SUMMARY.json，不需要本地持续在线。不要重交18项。
- 真实分数最大位置目标质量29.91%，CTMC29.87%，全同步87.55%，块64 44.62%，块16 31.71%，块4 30.63%；κ12/16几乎相同。稀疏使能1/8均值接近但地址重复约67%（CTMC约23%）；不宣称同等有效样本数。详细DIAGNOSTICS_ZH.md。
- κ建议仅为平衡泄漏起点：512候选κ12，约2K候选κ16；tanh输入系数要除2并做器件标定。当前PPL候选最多512，2K只做合成压力，不把它说成2K全候选PPL。

正式成果：qwen/results/ising_broadcast_20261021/；原件路径/字节/SHA见ARTIFACT_MANIFEST.json。原始模型JSON留个人服务器（逐段NLL、全24层执行审计、输入revision/文件SHA/环境/源码），小型诊断原件按-byte校验后入Git。当前无RTL/PT/PPA或训练。

下一步：读取2602各JSON和错误日志、2609终态，不仅看队列消失。确认18配置各3seed；失败null保留。取回collected两个派生文件及最终artifact manifest，重放collect.py并逐字节核验后更新同一报告/PR79/Issue78/STATUS和记忆。若需要扩大质量验证，当前128目标只能初筛，另记配置，不覆盖此快照。Projects缺read:project仍待同步。

以下为较早时点的交接记录：

# Issue78 全局广播与伪异步更新

2026-10-21；jieruiz；task/78-ising-broadcast；base e4990c15b40f664cea7f9db43175b68347ce588b；目标rayggxia-workspace/pbit-llm-qwen-baselines。

独立稀疏目录：C:/Users/86134/Documents/a_P_BIT/tmp/ising-broadcast-issue78-20261021。已读根记忆0/1/7/12、远端README/AGENTS/两位成员STATUS、Issue37及最新open任务；Issue76为其他成员训练设计，保持分离。原Issue73作业2585仍运行，不取消或重交。

已完成：有限κ方程、全同步/随机分块/稀疏使能NumPy行为模型、合法输出等待、无兜底cap；6项CPU数学/转移/边界测试通过。平坦输入发现全同步2周期振荡；原固定spacing4会只读空状态，故新路线增加独立随机间隔读出，并保留逐阶段非法率。

尚未完成：远端合成诊断与模型CPU PPL、任务分支推送/PR；不得把本地脚本写成已执行结果。计划个人服务器项目`/home/Hongjie_Zeng/projects/pbit-qwen-ising-broadcast-20261021-issue78`，独立不可变snapshot；只读复用既有权重/数据/标定，不复制模型。

准备按Slurm提交CPU诊断、CPU BF16/SDPA门禁和afterok的18配置PPL数组。128目标固定后缀只做初筛，所有24层scored decode替换，原FFN和多token前缀准确；不等于完整WT2。

下一步：封存执行SHA与source包；提交后在本文件追加真实job ID、路径、哈希。核对JSON终态，失败保留null PPL，不用分布指标估造PPL。至少3seed记录，κ选择区分平衡泄漏与动态偏差。Projects历史缺read:project，待有权限后同步；Issue78保持open至PR验收。

## 真实提交与发布（2026-10-21）

执行源0c0d8978908e9232cb94b75ac301a8254f834645，31个Git blob封存为81,056字节包；SHA256 6a33d8c84c56e2b00131b8ec2fcf7a4dd8afac5b6fe10338728fca2939e12fa5。源码和未来修复不可混写。快照位于个人项目snapshots/<SHA>，结果outputs/<SHA>。

CPU Slurm2600诊断、2601 BF16/SDPA门禁已RUNNING；2602_[0-17]%2依赖2601。首次远端日志6项测试通过，诊断进行中；PPL尚pending。提交原件SUBMISSION.json、EXECUTION_SOURCE.json。

分支已推送正式workspace；草稿PR79已创建并关联本聊天，待结果核验，未合并。Issue78已同步。Git默认OpenSSL TLS失败，使用单命令http.sslBackend=schannel且http.proxy=推送成功，没有修改全局Git设置。
