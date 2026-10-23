# Issue157 当前执行与交接

更新时间：2026-10-23T23:54:08+08:00。唯一目标 `rayggxia-workspace/pbit-llm-qwen-baselines`；认证 `amlink1219`；分支 `task/157-sparq-qwen3`；[PR163](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/163) draft/open/未合并，堆叠依赖PR147@357db588。

## 当前结果

最新独立复核：[REVIEW_ZH.md](../../../../qwen3/sparq/results/8d60abe4e7c5/reviews/checkpoint_001/REVIEW_ZH.md)。结论 `partial_verified`；完整anchor为299077目标、PPL11.537160499310174，执行形状与cached不同；配对完整质量尚未完成时不作全WT2/任务结论。原始完成分片和下载SHA在同目录raw/，每次独立报告保持原快照。源清单内文件已从固定Git提交逐SHA重建并复核；大权重未重新下载。

54次GPU基准已完成：RTX5090、context2048/decode128，dense47.8444、SparQ14.3296 token/s。PyTorch参考代码未实现稀疏HBM kernel，此结果不是ASIC速度。原快照GPU功率null：裸UUID未加GPU-前缀使遥测未启用；修复已另测12项CPU辅助测试，须另冻结测量补充，不能修改运行中原源或把新测量伪装成原8d60结果。

## 正在运行

GPU **2878**、CPU依赖2877已完成。固定执行提交 `8d60abe4e7c5c245c8f5f87b7f66e49e23ae0eea`；模型 `Qwen/Qwen3-4B@1cfa9a7208912126459214e8b04321603b3df60c` 后训练版，原FFN。主机 `Weican_Chen@10.129.164.156:21570`，已核个人根 `/home/Weican_Chen/projects/sparq-qwen3-issue157`。

- 不变源：`source-8d60abe4e7c5`；结果：`results/8d60abe4e7c5`；日志：`logs/full-2878.out`、`.err`。
- 环境：`env-v2/bin/python`，Torch2.7.1+cu128、TF4.51.3、lm_eval0.4.8；模型10文件、5语料已核SHA。
- 开始2026-10-23 23:33:19，时限12h。恢复先查`scontrol show job 2878`和本人三台队列；监控断连不等于作业结束，不重放提交。
- 固定命令：`python -B -m qwen3.sparq.run --root /home/Weican_Chen/projects/sparq-qwen3-issue157 --phase full --batch 32 --ppl-chunk 32 --task-chunk 256 --diagnose-document-batching`，在原source目录内运行；不能在登录节点直接执行。
- PPL WT2窗口2048/步长1024，292窗，batch32；正式MC逐题/choice_batch4，全PIQA1838、ARC-Easy2376、HellaSwag10042，每256题原子落盘。分片256不是跨题batch。

## 验证和负结果

CPU2877最终51项真实TF测试+10项benchmark辅助通过；GPU2874原native/dense logits逐bit相同、检查开关逐bit相同。当前2878 preflight正式门禁通过，batch32峰22.94GB。原跨题batch在2876失败；2878完整候选诊断记录多个任务超.02 nats/target，最大ARC-Easy dense .413066864。正式串行评分不采用该优化；没有放宽门限。独立报告保留所有失败项。

最初环境失败、GPU门禁失败及各版日志分别在staging_failures/、gpu_preflight/、batch_gate_failure/；历史回执不代替当前作业状态。

## 下一步及边界

1. 保持2878运行；下载完成JSON，核envelope/TRANSFER/source，运行`python -m qwen3.sparq.report <下载目录> --output <新目录> --source-root <原固定源>`，完整SUMMARY和全部目标/题目/正式门禁齐全才标complete。
2. 当前唯一GPU结束并核三台本人队列后，在新冻结测量源上补GPU板级功率；记录原质量identity和新测量SHA，功率不可用仍置null。
3. [EDA_HANDOFF_ZH.md](../../../../architecture_tlm/sparq_baseline/EDA_HANDOFF_ZH.md)已上传且[通知@jieruiz](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/157#issuecomment-6368752572)。完整SparQ RTL顶层/库表征/STA尚未实施，ASIC面积功率真实延迟null；不沿用旧FFN物理值。
4. GitHub Projects只读查询缺read:project；不改账号权限。Zotero后台未运行，复用现有SparQ PDF和待导入/精读补充任务，不声称入库、不打开窗口。

Issue116/123继续暂停，不访问他人home/工艺库，不上传权重/凭据；最多一个GPU任务。源码、日志及中间失败证据均保留，不删除唯一文件。
