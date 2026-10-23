# Issue139：SANTA++ 对照与 GQA 采样耦合补充

2026-10-23，amlink1219；沿用 `task/139-qwen3-gqa-literature` / PR140。基线 `6966739a5223680888bf0315f7bb4f73423a1ae6`；前次文献提交 `b1086fc3aae700ee2531814151e88ecfaea68912`。PR 实际状态以实时 GitHub 回执为准，本轮不合并。

正式报告：`architecture_tlm/qwen3_gqa_literature/SANTAPP_GQA_COUPLING_ZH.md`。已读 Zotero 原 PDF、核对 Issue84/PR85 已合并及 Issue9 的既有共享 U 方案；不重做已交付精读、不把共享随机数作为新发现。新增固定 K 共同 Gumbel 的单头分布/校正、期望加权并集界及投影方差反例，经独立审阅。文献/本项目代码、数学分析和未做实验明确分开。

解析算例：在本目录运行 `python -X utf8 analytic_examples.py`，输出应与 `ANALYTIC_EXAMPLES.json` 数值一致；使用标准库精确分数，无模型、随机采样或远端计算。它不构成通用命题的机器证明。原文来源与文件 SHA 见 `MANIFEST.json`。

未做：生产代码改动、模型替换/下载、SANTA++ 完整复现、Qwen3-4B 质量、跨头有限精度噪声实现、suffix 更新、周期后端新接合、STA/PPA、全领域查新。没有本任务计算作业。Issue116/123 继续暂停，其他成员的 Base 基线/EDA 任务不接管。

下一步候选（需后续实施任务）：先做相同固定状态的 independent/shared Gumbel 对照，观察并集字节和投影后误差，再决定是否值得进行完整模型评测。旧 Bernoulli 合成例仅省约 1.4pp，不预设显著收益。

Zotero：已有 F6DJ2FX7/W7DTMLYE 复用，原件 SHA 核验；未启动 UI、未改条目或原笔记。新增设计笔记尚未写回，待办位于本机 `outputs/santapp_design_20261023/ZOTERO_NOTE_PENDING.json`，恢复后核验官方后台接口与条目身份，避免重复笔记。前次 12 篇待导入仍按原交接，不算本次已导入。

本机新增 helper、只读数据库核验及 API 回执保留 `outputs/santapp_design_20261023/`，不上传个人库内容、PDF全文或凭据。仅上传明确文件清单；保留前次 MANIFEST 及其所指文档原字节。本轮发布最终 SHA、远端文件回读与 PR 状态见该 outputs 目录的 `PUBLICATION.json`。Projects 上次查询缺 read:project；本轮未申请权限或同步看板，不影响 Issue/PR 文件交付。
