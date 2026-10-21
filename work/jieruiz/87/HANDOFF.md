# Issue87 交付回执：PR88草稿已上传、未合并

2026-10-22；jieruiz；task/87-parallel-sampler-tlm。科学交付head8687c1d8124af192e82ec13aa3dbe12ccaa240b7已推送workspace，PR88草稿开放未合并；两个采样器、公共接口、中文说明、结果报告及验证文件6份远端原字节SHA已读回核验，详见work/jieruiz/87/REMOTE_VERIFY.json和PUBLICATION.json。

18新＋10旧检查通过，执行f6c6bd8；30三seed合成模块＋2单层decode连通完成。全宽候选一次读取、随机源后端未定；未知完整能量/面积null，不冒充PPL/PT/DRAMSys或实际源结果。下一步填源/数字模块成本或做真实模型质量与调度验证，现阶段等待PR评审；Issue87保持open，不自动合并。看板本轮未写，沿既有权限限制待同步；Issue73/78作业不改。

以下为此前阶段记录，待发布描述不代表当前阻塞：

# Issue87 全候选并行采样器 TLM 交接

2026-10-21；负责人jieruiz；分支task/87-parallel-sampler-tlm；base为集成分支pbit-tlm-attention-details-20261016@5b26c80c28ab22383f12ab31046dd723ca985abb。独立稀疏目录tmp/parallel-sampler-issue87-20261021。目标仅rayggxia-workspace/pbit-llm-qwen-baselines。

## 当前完成及验证

- 用户要求每轮候选全部同时采样，随机源后端不决定。已实现WinnerHoldSampler和CorrectedRejectionSampler、后端无关源接口、全宽服务、明确计数/仲裁/反馈/回压及活动账本。
- 正式设计说明architecture_tlm/PARALLEL_SAMPLERS_V5_ZH.md；源码parallel_sampler_v5.py、winner_hold_tlm_v5.py、corrected_rejection_tlm_v5.py、screen_parallel_tlm_v5.py、run_parallel_sampler_v5.py；配置configs/parallel_sampler_v5.json。
- v4仅增加factory/输入准备/工作空间三个扩展点，旧默认不变。没有改Issue37的比较脚本、他人STATUS或运行任务。
- 执行代码f6c6bd8215c2d702ab42e6a3078f64e0888cade8。18个新测试＋10个旧v4测试通过；30项三seed合成模块事务、两个单层完整decode情景完成。正式结果architecture_tlm/results/parallel_sampler_v5_20261021，RESULT_VERIFY/VALIDATION及日志在本目录。原执行JSON按UTF-8/LF封存并逐SHA核验。
- 未选择PRNG/DAC/物理源，未知完整能量/面积为null；已知参数化小计不冒充完整PPA。没有新模型PPL/训练、服务器/Slurm/PT或真实DRAMSys运行。

## 接续步骤

1. 先核对Issue87/相关PR与本目录发布回执；PR78/86是数值证据依赖，不把PR86本地V-MSE当完整模型PPL。Issue37归amlink1219，此次不接管。
2. 在仓库根运行VALIDATION.json里的四条命令；输出目录须为空，不能覆盖封存结果。collect_results.py仅核验/派生报告，可重建RESULTS_ZH.md。
3. 源阵列、计数/按秩树、零单多检测、偏移更新和寄存器需要后续PT/源服务数据；填energy_pJ/area之前明确互斥边界，不能重复计整宏与子模块。
4. 固定全宽读取，每查询N/ N−1有偏通道；公平随机接口分别预留ceil(log2N)/24位最大需求。模块实例按查询串行；不含免费多头并行。拒绝的per_candidate与shared_scalar改变前端成本，不改变理想样本律，测试覆盖。
5. 新的全模型质量评测需显式实施decode路径和层覆盖，Slurm与不可变快照规则继续；本次不重跑已有90QKV结果或Llama健康任务。

## 发布与限制

本地实现、验证和结果完成；任务分支推送/PR/远端SHA以PUBLICATION.json及Issue87最终回执为准。尚未合并。看板未操作，沿既有read:project受限状态待同步，本轮未重新探测权限。

最初未提交的本地原型示例已逐文件SHA核验压缩至project_archives/parallel_sampler_issue87_20261021/prototype_before_f6c6bd8.zip，SHA256为1c6ae1c9367f4e67634283fc68c5d31c4ee35e0187d11f3e7a7edaf24503bb51（36文件，195131字节）；恢复清单为同目录RECOVERY_INDEX.json。核验后原型目录已回收。不是服务器封存或新的科学结果，正式结果以本目录manifest和执行f6c6bd8为准；当前稀疏checkout约数MiB，不保留多套完整副本。
