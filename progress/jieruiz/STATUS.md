# jieruiz 项目进度

更新时间：2026-10-17（Asia/Shanghai）；实际 GitHub 登录 jieruiz。

| 项目 | 当前状态 |
|---|---|
| 当前任务 / 负责人 | [Issue #9](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/9)，筛选＋PV 的 K 读取分析；@jieruiz |
| 正式仓库 | rayggxia-workspace/pbit-llm-qwen-baselines |
| 分支 / PR base | task/9-screen-k-traffic → pbit-tlm-attention-details-20261016 |
| 基线提交 | 9608c0d06cf8b421cbbd348aca4fc84c5990aae7 |
| 独立目录 | a_P_BIT/tmp/screen-k-traffic-issue9-20261017/ |
| 当前阶段 | 已推送；[PR #10](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/10) 待审，未合并 |
| 成果 | [正式分析](../../architecture_tlm/SCREEN_K_TRAFFIC_ANALYSIS_ZH_20261017.md)、审计工具与结果、原始校准字节归档 |
| 实际验证 | 原选择器重建两组记录一致；补充MHA/GQA区别；旧LLaMA-1 7B筛选3种子×32层候选与组并集逐项相等；没有新推理。其他检查见 work/jieruiz/9/ |
| 未运行 | 没有模型推理、训练、新 BF16/PPL、新 DRAMSys、RTL或DC/PT；不把合成输入作为真实模型稀疏率 |
| 限制 | 组级共同预算、v6 PV＋筛选、摘要压缩均为后续候选；共享随机数仅计算理论期望，未启用 |
| 待同步 | Projects 缺 read:project，看板待权限补齐；Issue/PR正常同步 |
| 交接 | [HANDOFF](../../work/jieruiz/9/HANDOFF.md) |

前序 Issue #1/PR #2 治理、#3/PR #4 架构审计、#5/PR #6 DRAM/DS-CIM、#7/PR #8 FFN/后处理均保留原分支待审。本任务没有覆盖其工作树。
