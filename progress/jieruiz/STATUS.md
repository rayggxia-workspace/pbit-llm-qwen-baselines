# jieruiz项目进度

更新时间：2026-10-17（Asia/Shanghai）；已通过本机凭据核实GitHub身份jieruiz。

| 项目 | 当前状态 |
|---|---|
| 本任务 | [Issue #5](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/5)：DRAM功耗核实与DS-CIM权重供给；负责人@jieruiz |
| 目标仓库 | `rayggxia-workspace/pbit-llm-qwen-baselines` |
| 分支 / base | `task/5-dram-dscim-audit` → `pbit-tlm-attention-details-20261016` |
| 基线提交 | `9608c0d06cf8b421cbbd348aca4fc84c5990aae7` |
| 独立目录 | `a_P_BIT/tmp/dram-dscim-issue-5-20261017/` |
| 成果 | [专题报告](../../architecture_tlm/DRAM_POWER_AND_DS_CIM_WEIGHT_REVIEW_ZH_20261017.md)、核心功耗profile/预检查工具、独立计价辅助工具 |
| 当前阶段 | 已推送；[PR #6](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/6)待审；未合并 |
| 验证范围 | 13项测试通过；4份既有统计重计价残差≤1.67e-16J；16文件范围/37个链接/成果SHA-256核对通过。没有新PPL/完整DRAMSys或PT |
| 辅助与交接 | [HANDOFF](../../work/jieruiz/5/HANDOFF.md)、[源清单](../../work/jieruiz/5/source_evidence.json)、[成果manifest](../../work/jieruiz/5/manifest.json) |
| 限制 | 新profile是厂商限值核心情景，I/O/实际器件选择/完整timing尚未认证；不覆盖旧输入和历史结果 |
| 待同步 | Projects缺read:project；Issue/PR正常同步，看板待权限补齐 |

Issue #1/PR #2治理、Issue #3/PR #4架构审计仍保留原任务分支。下一步应具体确定FFN权重驻留接口，再开展实现/工艺表征；本次未宣称已实现DS-CIM宏。
