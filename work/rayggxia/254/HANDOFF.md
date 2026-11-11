# Qwen3-4B 四组论文质量评测交接

- 负责人 `rayggxia`，跟踪 [Issue #254](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/254)。
- 独立分支 `task/254-qwen3-paper-quality`，基线 `main@206bf81f18ea88c4c625ce8d32edd18a58edd1cd`。本交接直接在 GitHub 独立分支发布。
- [四组执行清单](../../../qwen3/evaluation/paper_quality_20261111/REMOTE_AGENT_PLAN_ZH.md)。计划固定版本 [`69d9fb210ee1`](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/69d9fb210ee136a141bcbb52fdb7bd7353cb3e98/qwen3/evaluation/paper_quality_20261111/REMOTE_AGENT_PLAN_ZH.md)，Issue 中维护 PR 和执行回执。
- 交接验收核对四组 ID、39,160 道主任务题、1,319 道 GSM8K、299,077 个 WT2 目标与语料/分词 SHA。任务指标、随机路径、训练权重来源及回传要求见执行清单。
- 当前阶段为方案交付。执行方先回执权重和冻结代码可用性，A 原版先跑，C 等 100M BF16 控制权重交付。现有运行由各自任务继续跟踪。
- Projects 待维护者同步。
