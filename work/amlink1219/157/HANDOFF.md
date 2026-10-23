# Issue157 当前执行与交接

更新时间：2026-10-24T00:16:33+08:00。唯一目标 `rayggxia-workspace/pbit-llm-qwen-baselines`；认证 `amlink1219`；分支 `task/157-sparq-qwen3`；[PR163](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/163) 待审、未自动合并，依赖 PR147@357db588。

## 已核验结果

最新独立复核：[REVIEW_ZH.md](../../../../qwen3/sparq/results/8d60abe4e7c5/reviews/ppl_complete_20261024/REVIEW_ZH.md)，结论 `partial_verified`。

- cached dense：292/292 窗，299077 个目标；完整 PPL=11.5381534；完整核验=True。
- cached sparq：292/292 窗，299077 个目标；完整 PPL=10.7979258；完整核验=True。
- 向量化 BF16 anchor：292/292 窗，PPL=11.5371605，完整核验=True；执行形状与 cached 不同。
- piqa/dense：0/1838 题，已验子集 acc=待定, acc_norm=待定；完整核验=False。
- piqa/sparq：0/1838 题，已验子集 acc=待定, acc_norm=待定；完整核验=False。
- arc_easy/dense：0/2376 题，已验子集 acc=待定, acc_norm=待定；完整核验=False。
- arc_easy/sparq：0/2376 题，已验子集 acc=待定, acc_norm=待定；完整核验=False。
- hellaswag/dense：0/10042 题，已验子集 acc=待定, acc_norm=待定；完整核验=False。
- hellaswag/sparq：0/10042 题，已验子集 acc=待定, acc_norm=待定；完整核验=False。

尚未完整核验：piqa/dense、piqa/sparq、arc_easy/dense、arc_easy/sparq、hellaswag/dense、hellaswag/sparq、最终 SUMMARY。

GPU benchmark 完整核验=True；NVIDIA GeForce RTX 5090，context2048/decode128：native 47.8418 token/s，dense 47.8444 token/s，sparq 14.3296 token/s。功率：本次已核源码调用方传入裸 UUID，而采样器要求 GPU- 前缀，导致采样未启用；不是另一块 GPU 或 NVML 缺失的证据。。这是原 FFN 的 Python 全模型参考计时，不是优化稀疏 kernel 或 ASIC 速度/能耗。后续计量修复须另冻结、另存补充，不能替换原质量快照。

## 调度证据和恢复入口

GPU 2878 最近保存的 Slurm 状态 **RUNNING**，ExitCode=0:0，观测文件时间 2026-10-23T16:14:22+00:00。这是保存的调度证据；监控断连或文件缺失不证明作业结束。

固定执行提交 `8d60abe4e7c5c245c8f5f87b7f66e49e23ae0eea`；后训练 `Qwen/Qwen3-4B@1cfa9a7208912126459214e8b04321603b3df60c`，原 FFN。CPU 依赖 2877 历史终态见回执，不能代替当前 GPU 状态。

- 个人远端根 `/home/Weican_Chen/projects/sparq-qwen3-issue157`；不变源 `/home/Weican_Chen/projects/sparq-qwen3-issue157/source-8d60abe4e7c5`；结果 `results/8d60abe4e7c5`；日志 `logs/full-2878.out`、`.err`。
- 环境 `env-v2/bin/python`，Torch2.7.1+cu128、TF4.51.3、lm_eval0.4.8；模型10文件及语料已登记 SHA。本次只重建并核固定源码，不重新下载权重。
- 命令 `python -B -m qwen3.sparq.run --root /home/Weican_Chen/projects/sparq-qwen3-issue157 --phase full --batch 32 --ppl-chunk 32 --task-chunk 256 --diagnose-document-batching`，只能在原 Slurm 分配中运行，不能在登录节点直接执行。
- WT2 2048/1024；正式 MC 逐题/choice_batch4，每256题分片落盘；分片大小不是跨题 batch。
- 本检查点下载清单为 `reviews/ppl_complete_20261024/TRANSFER.json`；raw/TRANSFER 是可更新的最新下载索引，每版原件按检查点保存。报告、输入哈希、调度终态和日志均按检查点冻结。

## 验证和负结果

正式 document_batch=1；preflight passed=True。跨题候选 present=True、passed=False；失败项=[{"task": "piqa", "mode": "dense", "maximum": 0.043265106636681594, "threshold": 0.02}, {"task": "piqa", "mode": "sparq", "maximum": 0.032665827996371424, "threshold": 0.02}, {"task": "arc_easy", "mode": "dense", "maximum": 0.4130668640136719, "threshold": 0.02}, {"task": "arc_easy", "mode": "sparq", "maximum": 0.21209144592285156, "threshold": 0.02}, {"task": "hellaswag", "mode": "dense", "maximum": 0.04170358808955825, "threshold": 0.02}, {"task": "hellaswag", "mode": "sparq", "maximum": 0.02695267952402078, "threshold": 0.02}]。候选失败完整保留；正式逐题/choice_batch4 不采用该优化，不放宽门限。

历史 CPU/原生 logits 门禁、环境失败与候选失败回执保留，不把历史调度记录当作当前执行状态。

## 下一步及边界

1. 继续只读核调度状态并归档新完成分片；没有新观测时不推断作业终态。 只有完整 SUMMARY、全部目标/题目和正式门禁通过才标 complete。
2. 当前本人 GPU 作业结束并核本人队列后，才可另冻计量源补板级功率。补测关联原质量 identity 和新测量 SHA，不能混写原 `8d60abe4e7c5` 结果。
3. [EDA_HANDOFF_ZH.md](../../../../architecture_tlm/sparq_baseline/EDA_HANDOFF_ZH.md)已交接并通知 jieruiz；完整 SparQ RTL/STA 尚缺，物理 ASIC 面积、功率、真实延迟为 null。
4. Projects 与 Zotero 的限制、待办保留在回执，不声称待同步/待入库已完成。Issue116/123 继续暂停，不访问他人 home/工艺库，不上传权重/凭据，不自动合并或重复提交作业。
