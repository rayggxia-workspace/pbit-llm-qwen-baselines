# Issue84 / PR85交接

- 更新时间：2026-10-21T12:10:56.373304+00:00；负责人jieruiz。
- 目标仓库：rayggxia-workspace/pbit-llm-qwen-baselines；身份由GitHub /user核实。不是旧个人origin。
- 分支：task/84-santapp-novelty；base：pbit-tlm-attention-details-20261016@5b26c80c28ab22383f12ab31046dd723ca985abb。
- 工作目录：C:/Users/86134/Documents/a_P_BIT/tmp/santapp-novelty-issue84-20261021。为稀疏worktree；不需要补全历史模型/原始事务数据。
- 科学报告head：ad92485c9f98cc50fdb706f620c96d681fb339e9，已上传。PR：https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/85 ，草稿开放未合并；Issue84待审不关闭。收尾元数据随后一个提交更新同PR。

## 已完成

1. 核实本地/远端规则、基线、本人身份、Issue和开放PR；为同范围文献核查建立Issue84。
2. PDF正文/附录A–F方法、质量/逻辑读取/GPU演示范围核查；PDF第2/7/13/28页渲染检查。
3. 报告和8个项目源SHA索引、预算/配对PPL等10项核查。报告SHA96f123e75e48212956fc50f740956310b06d61d5e95766b625f7976548834f05。
4. 正式报告architecture_tlm/research_readings/SANTAPP_V1_NOVELTY_ZH_20261021.md；TASK、REMOTE_CHECK、SOURCE_MANIFEST、VALIDATION、PR_BODY及PUBLICATION在本目录。
5. 根阅读备忘录与Issue28 canonical原有增量完整保留，仅追加本任务记录；当前两者同字节SHA 998f1954fbcac31d5fce18100be9d5bc9965746486c6017b9cada60a87aa6e67。本分支只在基线备忘录后增加本任务，不混入其他未集成任务。

## 验证与命令

- pypdf提取身份/文本，Poppler pdftoppm渲染并检查；PDF原件不进Git。提取/渲染仅在本地tmp/pdfs/2609_35629_review。
- 本地prepare84.py使用git show/rev-parse读取冻结源，不运行模型。VALIDATION.json是算术/文件核验，不是模型质量验证。
- git diff --cached --check通过；仅本任务明确文件提交。GitHub Git Data API逐blob、tree、commit与本地SHA相同再更新非force任务分支；科学数据未改写。

## 边界与后续

报告是相对论文与已读近邻的判断，不是全领域穷尽查新。SANTA++的代表选组/校正/GQA共享是现有机制；我们的潜在新贡献还需真实key对照、适配实际选择律的校正、p-bit与数字采样同质量PPA、长上下文任务。不能把已有短题全保留K当筛选验证，不能将局部8位驱动TV当全模型PPL。

本次没有新推理/训练、Slurm、RTL/PT、TLM或默认算法修改；不接管Issue37/78或服务器评测。没有运行中本任务作业。Projects本轮未写，沿既有权限限制待同步。下一步读取Issue84/PR85最新变化后评审文档；如启动算法实验，使用相应独立Issue/分支，不改冻结执行快照。

PR待审保留此最小目录，合并后按生命周期规则回收；不新增全量副本，不删除原始实验历史。
