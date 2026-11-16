# Qwen3-4B 联合权重 FFN 采样预算评测方案

生效日期为 2026-11-16。此页是 [Issue #254](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/254) 本轮的远端执行清单。已有联合检查点直接用于推理评测，训练步数为 0。首批仅用部署 seed **101**，每组完成后立即回传。旧 ABCD 评测及原始记录沿用[历史清单](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/60592f4d373dd2a53d9d78daaac04d21e9424040/qwen3/evaluation/paper_quality_20261111/REMOTE_AGENT_PLAN_ZH.md)留档。

## 配置

| ID | FFN 前级 `T_x` | FFN 后级 `T_AND` | 后级每格独立抽样 | 执行 |
| --- | ---: | ---: | ---: | --- |
| `joint_16_32` | 16 | 32 | 1 | 复用现有 B 组，同 seed、权重、数据与计分协议 |
| `joint_32_64` | 32 | 64 | 2 | 首批，seed 101 |
| `joint_64_64` | 64 | 64 | 2 | 首批，seed 101 |
| `joint_64_128` | 64 | 128 | 4 | 首批，seed 101 |

- 所有新组固定 Qwen3-4B 后训练版对应的 B 组检查点。加载 T64 FFN 导出与配套公共权重，再覆盖联合适配 `main` 的 144 个 Q/K/V/O 投影。T64 交付清单 SHA-256 为 `187fa827daa5e162b0753ffd4b2687c11a17eea289193cdead614c8a722556ff`。`main` 权重 revision 为 `eb9ad683d6e8f859d01081955dda4d46f864208b`，对应权重文件 SHA-256 为 `678c6dcf47578dcdf154021afb73689c44842860553085320921f20887ca5829`。执行方从已有授权存储获取，并核对 B 组加载顺序、张量身份、W8/PoT 编码和校准。分词器与基线 revision 固定为 `Qwen/Qwen3-4B@1cfa9a7208912126459214e8b04321603b3df60c`。
- FFN 前级把 R8 域均分为 `T_x` 个区间，每组 64 个输入共享该组分层随机字。后级固定 4×2×4 共 32 个 `g/σ(g)/u` 联合分层格，逐格使用表中次数的独立抽样，AND 事件计数沿原归约进入 Wd。前后级分别使用自己的采样分母。沿用 B 组的随机流实现、共享与种子派生规则，并在日志记录实际采样路径。
- Attention 全部固定 `r32 / K128 / recent32 / S64`。近期 32 项计入 K，四个 Q 头共享候选。计分路径沿用 S12/F4 分数量化、整数 max-gap、U8/F4 LUT 地址、floor-P8、赢家保持 S64、burn 0、初始槽 0 和全零保持。输入不足 K 时处理有效位置。
- 未计分前缀用原生准确 Attention，FFN 在前缀及 decode 都用指定配置。多选续串沿用缓存逐 token 计分，首个答案 token 的预测也走指定的 decode 路径。逐层核对 36 层覆盖、实际 `T_x/T_AND` 与 Attention `S`。
- 关键配对为 32/64 对 64/64（比较前级预算），以及 64/64 对 64/128（比较后级预算）。16/32 提供原部署质量参考。以同题结果计算准确率差，不同任务各自保留分母。

## 正式任务清单

每个新配置、每个部署 seed 完成下表 **9 项**。八项下游任务共 **39,160 题**。GSM8K 从本轮调度清单移除，既有结果留在历史记录。

| 任务 | 固定测试范围 | 主指标 |
| --- | --- | --- |
| PIQA | validation 1,838，0-shot | `acc_norm` |
| HellaSwag | validation 10,042，0-shot | `acc_norm` |
| WinoGrande | validation 1,267，0-shot | `acc` |
| BoolQ | validation 3,270，0-shot | `acc` |
| ARC-Easy | test 2,376，0-shot | `acc_norm` |
| ARC-Challenge | test 1,172，0-shot | `acc_norm` |
| MMLU | 57 科 test 共 14,042，固定每科 5-shot | 按题数加权 `acc`，另存分科 |
| LAMBADA OpenAI | 英文 test 5,153，0-shot | 末词 `acc` |
| WikiText-2 | 原文，窗口 2048、步长 1024，292 窗、299,077 个唯一目标 | PPL 和 mean NLL |

PIQA、HellaSwag 和两项 ARC 同时返回 `acc` 和 `acc_norm`。保持 B 组冻结的 Harness、数据版本、提示模板、few-shot 例子及顺序、计分边界和题目 ID。MMLU 按实际题数归约。LAMBADA 以官方末词准确率为主指标。

WikiText-2 使用原文 teacher forcing，匹配已冻结的窗口坐标、BOS、计分掩码和目标数。原文 SHA-256 为 `173c87a53759e0201f33e0ccf978e510c2042d7f2cb78229d9a50d79b9e7dd08`，完整计分 token 序列 SHA-256 为 `8557ef42be22a592e5f1704026fedbedc937b484e52f517add9f478adc0de20f`。先累加所有窗口的 NLL 和计分目标数，再计算 mean NLL 与 `exp(mean NLL)`。更换执行环境时先复核原始 BF16 的匹配参考。若 16/32 的现成记录缺少匹配清单或逐题覆盖，只补对应的基线缺项。

## 排程与交付

1. **首批只提交 seed 101。** 核对权重和 tokenizer、数据哈希、任务表及三个采样配置。完成小样本门禁后提交 3 组 × 9 项全量评测，可在任务和分片维度并行。任一配置的单 seed 完成后立即回传，三组齐全时发首批总表。
2. **首批回传后再扩 seed。** 支持部署 seed 101、102、103。根据首批结果和资源，优先给进入论文比较的配置补 102 和 103。报告每个实际完成的 seed 及其样本均值、样本标准差，明确区分单 seed 和三 seed。与 16/32 比较时，只对实验组和基线均完整的同 seed 作配对。它们是部署随机种子，训练权重始终相同。
3. **回传覆盖和复现证据。** 在 Issue #254 给出作业号、源码提交和冻结快照、三组权重及配置文件的 SHA-256、依赖和完整命令。逐题输出保留题目 ID、候选分数、主指标标记和完成掩码。逐窗 WT2 保留坐标、NLL 和有效目标数，附 36 层采样审计、分片合并记录和结果文件 SHA-256。ARC-Easy 128 题小测、失败分片和部分分片保留原标记。
4. **首批验收看全量覆盖。** 每组核对上述题数、题目与分片无缺漏或重复，并提交逐任务分数及相对 16/32 的差值。对比 32/64、64/64、64/128 时使用同一套题和指标，报告下降项。大型原件保存在既有共享存储，GitHub 留汇总与校验索引。
