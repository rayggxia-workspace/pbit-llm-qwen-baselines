# Qwen3-4B 四组论文质量评测交接

- 负责人 `rayggxia`，跟踪 [Issue #254](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/254)。
- 独立分支 `task/254-qwen3-paper-quality`，基线 `main@206bf81f18ea88c4c625ce8d32edd18a58edd1cd`。本交接直接在 GitHub 独立分支发布。
- [四组执行清单](../../../qwen3/evaluation/paper_quality_20261111/REMOTE_AGENT_PLAN_ZH.md)。计划固定版本 [`60592f4d373d`](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/60592f4d373dd2a53d9d78daaac04d21e9424040/qwen3/evaluation/paper_quality_20261111/REMOTE_AGENT_PLAN_ZH.md)，Issue 中维护 PR 和执行回执。
- 交接验收核对四组 ID、39,160 道主任务题、1,319 道 GSM8K、299,077 个 WT2 目标与语料/分词 SHA。任务指标、随机路径、训练权重来源及回传要求见执行清单。
- 执行范围已统一。四组各跑完整十项，即八项全量准确率、GSM8K 真实生成、完整 WT2。原版、续训 BF16、同权重确定性各一遍，联合采样 seed 101、102、103 各一遍。
- 当前阶段为交接待回执。执行方请回传四组权重及代码身份和每组任务安排。训练方同步交付 C 组 100M BF16 检查点与训练清单。
- Projects 待维护者同步。
