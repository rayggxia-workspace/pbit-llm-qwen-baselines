# amlink1219 项目进度

更新时间：2026-11-03，北京时间。本人GitHub：amlink1219（75301230）。

本页记录本任务的进度；其他尚未合并任务的状态以各自Issue、PR和交接为准，不接管原负责人工作。

## Issue234：SparQ粗阶段赢家保持采样方案

- 任务：[Issue234](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/234)。
- 分支：`task/234-sparq-coarse-sampling`；base：`main@639ffc28a8409e19f330413a0635f95939c20621`。
- 独立工作目录：`workspace_projects/cs234`，仅检出任务所需目录。
- 正式文档：`qwen3/sparq/proposals/pbit_sampling_selector_20261103/PLAN_ZH.md`。
- 范围：优先复用WH从粗分数采样，32近期＋224唯一非近期；对比有放回去重与mask适配，明确GQA混合、P8支持、cap和成本。独立小网不进入首轮。
- 已完成：文档初稿、两份独立数学/成本审阅；数字IID收费和P8条件化/空支持处理已补充。
- 验证：本地文本/链接/差异和Git blob检查完成情况见`work/amlink1219/234/VALIDATION.json`；没有模型、训练、Slurm、RTL或EDA实验。
- 发布：[PR235](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/235)已创建，正式方案提交`2eee5845c8cf566a76fbf5b5f63861d0d6962880`；5文件已逐字节远端读回一致，PR待审、未合并。
- 不修改Issue220既有13组矩阵、SparQ默认、他人STATUS或冻结结果。
- 下一步：交付MD和PR；未来实验须先落实PPL容差、候选补满要求、运行环境与任务分工，本轮未提交。
- Projects看板：本轮未执行看板写入，待有权限的维护者同步。

恢复入口：`work/amlink1219/234/HANDOFF.md`。没有运行中的本任务作业。
