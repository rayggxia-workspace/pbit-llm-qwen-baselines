2026-10-28后续：用户已明确授权并完成本工艺成熟BF16 PPA，最新结果见[BF16单元/N64](../bf16_ppa_20261028/results/REPORT_ZH.md)与[INT8经典划分](../bf16_ppa_20261028/INT8_CLASSIC_ZH.md)。以下文献调研保留其原阶段语境。

# BF16数字矩阵对照

当前阅读入口为[第二轮文献核对](LITERATURE_RECHECK_ZH.md)：已找到28nm BF16输入/FP32累加阵列的后布线功耗估算，以及65nm BF16脉动阵列对照，不再将“未找到完整证据”作为当前结论。

- [归一值、原件与SHA索引](LITERATURE_RECHECK.json)，[重算脚本](literature_recheck.py)。
- [首轮调研与旧RTL诊断](REPORT_ZH.md)，[首轮条件预算](ESTIMATE.json)，保留原版本及其限制。

本目录仍未产生新的BF16本工艺PPA；文献参考不等于55nm同条件验证。真实发布状态见work/rayggxia/204/bf16_baseline/PUBLICATION.json及后续文献回执。
