# Issue92 小型p-bit筛选网交接

2026-10-22；负责人amlink1219（75301230）；目标rayggxia-workspace/pbit-llm-qwen-baselines（1420564659）。

## 当前状态

实际服务器训练已完成，Slurm2741 COMPLETED/ExitCode0:0，没有本任务运行中作业。论文级优势尚未成立：49参数4→8→1网在层0/12/23的holdout遗漏质量为6.173%/4.493%/37.082%，原max4为4.552%/3.319%/32.298%；网的预算略高仍更差。BCE下降只能说明训练流程能优化首轮代理目标。完整学生PPL/Ising联合/PPA没有执行，正式Attention默认未改。

任务分支task/92-pbit-gate-pilot，独立目录workspace_projects/gt92；PR base为pbit-tlm-attention-details-20261016，初始83e15289434af50fc09c35e699d8b39965389d98。上传/PR状态以本目录PUBLICATION.json最终回执为准；本文件首次编写时尚待上传，不能由训练完成推断已经发布/合并。

## 执行与成果

- 冻结执行源码53c24f28eb24d25f0edffc4e45354dab6cd86154。最终CPU2740的16项测试通过；先前CPU2738环境/SHA门禁通过、CPU2739为增加分母诊断前快照的16项检查。
- 主服务器Weican_Chen@10.129.164.156:21570，规范home /home/Weican_Chen；RTX5090分区gpu5090、job-name cwc、单GPU+4CPU、12G主机内存请求。无备用GPU作业；备用155的可选完整探测超时后，轻量squeue恢复成功，终态/提交前检查分别保留，不把超时当空队列。
- 不可变快照/home/Weican_Chen/projects/pbit-gate-pilot-issue92/snapshots/53c24f28eb24d25f0edffc4e45354dab6cd86154。
- 远端成果/home/Weican_Chen/projects/pbit-gate-pilot-issue92/outputs/gpu_pilot-53c24f28eb24。
- NPZ 8557506字节，SHA256 5a531bed5bfbfc688db272384857ee369985ef9761d58023fec4b0fbb3f7f249，位于该成果根capture/dataset.npz。模型/原始语料/NPZ未上传Git，仍在本人已授权服务器。
- 正式代码experiments/pbit_gate_pilot_20261022；小型报告/逐epoch日志/JSON小网参数/原字节调度记录qwen/results/pbit_gate_pilot_20261022。54个小文件传回并逐SHA验证，ARTIFACT_INDEX和MANIFEST保留完整源位置、输入版本与散列。
- 配置32/8/8文章、0/12/23层、head0/6/13、3query位置、3训练seed、3评估seed×16draw、100epoch。验证选checkpoint，holdout从未调参；总45.90秒、训练评估30.05秒。

## 恢复和下一步

1. 先读取远端最新README/AGENTS/PROJECT_MEMORY、Issue92和关联PR、所有成员STATUS，核对本人的认证身份和权限；别重交已完成2741。
2. 从结果README/RESULTS.json检查负结果、真实预算、PV与容量。当前可变mask约35%–40%超过512 token，不能直接塞进512宏，也不能按预算均值代替缓冲上限。
3. 若用户继续，另行冻结直接质量/PV目标、相同规模确定性控制及新的独立留出协议；本次holdout已经看过，后续调参不能继续把它当独立测试。先做新的局部训练对照，再决定完整PPL接入，不直接改现有正式默认。
4. 复用已核个人venv /home/Weican_Chen/projects/pbit-qwen-sigmoid-20260929/.venv/bin/python，不安装到共享/系统环境。所有算力操作经Slurm，先核队列与allocation。完整环境及原命令在RUN/ENVIRONMENT，README给出sbatch环境接口。
5. PR待审时不合并、不关闭Issue。看板若read:project不足，保留待同步，并以PUBLICATION.json实际响应为准。

没有待恢复训练，没有另行下载数据或在登录节点运行训练。辅助脚本和完整本机传回档位于DAC资料根outputs/gate_pilot_20261022；正式成果不依赖这些本机临时脚本即可解释和复现。
