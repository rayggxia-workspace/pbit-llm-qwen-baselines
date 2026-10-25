# rayggxia 当前研究任务

更新时间：2026-10-25。GitHub连接器身份rayggxia已核验；正式仓库rayggxia-workspace/pbit-llm-qwen-baselines。

## Issue187：LLM架构模拟器与PPA证据综述

- 分支：task/187-simulator-survey；PR base：main@5273e5d9fdae811a714f1a278fee6e776c5675af。
- 工作目录：C:/Users/86134/Documents/a_P_BIT/tmp/simulator-survey-issue187-20261025，最小稀疏worktree。
- 当前阶段：本地研究完成、文档一致性检查通过，准备任务PR；发布结果由work/rayggxia/187/PUBLICATION.json及Issue回执记录，不把本地完成当远端完成。
- 成果：architecture_tlm/simulator_survey_20261025/README_ZH.md、REQUIREMENTS_ZH.md、EVIDENCE.md/.json/.csv、SOURCES.json；33条论文/工具证据、67个去重来源URL。
- 实际验证：build_and_check.py检查结构、JSON/CSV一致、相对链接/锚点、关键范围约束、UTF-8/LF、4份用户PDF SHA、SANTA batch公式复算；三条研究线独立复核转录，综合建议复核通过。
- 未运行：模型/PPL/训练、GPU/Slurm、TLM、RTL/EDA/PPA、论文artifact重跑。不是新的硬件实验，不新增数字run台账。
- 关系：接续Issue98的benchmark研究；只读PR183@0341b4ac与Issue186，保留unified_v6、不接管调度实现。
- 待办：PR审核验收；Projects权限/同步未验证。长期备忘录将在PR回执后以唯一维护副本追加，同步根镜像；保留该文件现有未提交改动。

## 历史任务入口

旧Issue98及95等状态以其原分支STATUS/HANDOFF及最新远端Issue/PR为准。本分支main基线没有rayggxia STATUS，故新增当前任务入口；未覆盖其他成员STATUS，也未修改已有实验。
