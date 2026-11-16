# Qwen3-4B 联合权重采样预算评测交接

负责人 `rayggxia`，跟踪 [Issue #254](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/254) 和 [PR #255](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/255)。执行分支为 `task/254-qwen3-paper-quality`，目标分支为 `main`。

- [2026-11-16 远端执行方案](../../../qwen3/evaluation/paper_quality_20261111/REMOTE_AGENT_PLAN_ZH.md) 是本轮入口。权重固定在联合训练 B 组，复用已有 16/32，新增 FFN 32/64、64/64、64/128，Attention 固定 K128/S64。
- 首批只排部署 seed 101，回传单 seed 全量后再按优先级补 102/103。范围为 39,160 道下游题和 299,077 个 WT2 目标。GSM8K 从本轮清单移除。
- 本轮交付为远端执行方案。执行方下一步核对权重与 tokenizer、数据和计分协议，提交门禁及首批 Slurm 作业，并在 Issue 回传权重、冻结源码和作业清单。
- [2026-11-11 原 ABCD 交接](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/60592f4d373dd2a53d9d78daaac04d21e9424040/qwen3/evaluation/paper_quality_20261111/REMOTE_AGENT_PLAN_ZH.md) 保留历史任务定义和计分来源。已有结果与原始分片继续留档。
