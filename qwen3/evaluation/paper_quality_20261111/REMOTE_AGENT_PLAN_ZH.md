# Qwen3-4B 论文四组质量评测交接

评测执行方请在 [Issue #254](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/254) 回执可用检查点、执行代码提交和首批任务。先跑原版，再跑实际联合采样。并行核对 100M BF16 控制权重和同权重确定性适配。此交接只含四组。

## 四组配置

| ID | 检查点 | FFN | Attention | 交付范围 |
| --- | --- | --- | --- | --- |
| `original_bf16` | `Qwen/Qwen3-4B@1cfa9a7208912126459214e8b04321603b3df60c`，后训练版 | 原生 BF16 | 原生稠密 SDPA | 八项全量准确率、GSM8K、同协议完整 WT2 参考 |
| `joint_sampled` | 项目已交付的 T64 FFN 导出及配套公共权重，覆盖联合适配版 `main` 的 144 个 QKVO 投影 | GU 前级分层 T16，后级 g/sigmoid/u 三路 4×2×4 联合分层 T32，事件计数送 Wd | SparQ K128，Ising 赢家保持 S64 | 完整 WT2、八项全量准确率、GSM8K。先 seed 101，正式结果补 102、103 |
| `continued_bf16_100m` | FFN 训练方同预算 **100M 有效监督 token** 的全模型 BF16 控制检查点 | 确定性 BF16 | 稠密精确 | 优先独立复跑完整 WT2，再补八项全量准确率、GSM8K |
| `joint_deterministic` | 与 `joint_sampled` 使用完全相同的检查点组合、分词器和校准 | 两处有限抽样改为条件均值，保留对应编码、裁剪、量化和边界 | 同一 SparQ K128 筛选规则，数字 Softmax 对候选内全部有效 V 做精确加权 | 完整 WT2 一次 |

`main` 是联合适配权重的交付名称。通过项目已有授权的模型存储取得 T64 和 `main` 的冻结版本，记录二者 revision、实际文件 SHA-256、加载后张量映射及公共参数归属。两条联合配置使用同一份身份清单。C 组使用训练方实际交付的 100M 检查点；如缺权重，请在 Issue 记录缺项并推进其他组。100M 对齐的是 FFN 训练阶段预算，联合权重额外的 QKVO 适配另记。

## 联合配置的执行合同

- B、D 共用 SparQ 的 r32、K128、recent32（计入 K）、四个 Q 头共享一组候选和有效位掩码。保留筛选算法及数制，允许因前层激活变化而产生不同候选地址。上下文不足 K 时只处理有效位置。
- B 的计分 Attention 采用 signed S12/F4 分数量化、整数 max-gap、U8/F4 LUT 地址与 floor-P8 阈值，赢家保持 S64、burn 0、初始槽 0、全零保持。首轮使用已验证的软件随机前向及其独立流；记录 FFN／Attention 源、seed、共享方式和消费顺序。Philox 软件参考按该名称标注。
- D 的前级使用条件平均输入计数（码值 q∈[0,256]，期望为 T×q/256）；后级使用相同 4×2×4 格及编码下的条件平均联合 AND 计数（逐格求三路命中概率乘积再相加），沿原 W8/PoT 权重、符号、满幅、非线性边界和归约口径进入 Wd。审计前后两级实际随机调用均为零。若沿用已有浮点 Wd 均值诊断实现，回传中注明与采样组的归约及舍入差异。Attention 仍由相同筛选器选择候选，在共同精确 QK 分数边界计算 Softmax 和完整加权 PV。B 与 D 的差异覆盖两处部署前向变化，包括 PV 权重与数制。
- 对 B、D，未计分前缀沿用原生准确 Attention；FFN 前缀及 decode 都用各组指定 FFN 路径。多选续串使用缓存逐 token 计分，让首个答案 token 的预测也走目标 decode 路径。A、C 建立同口径 cached SDPA 对照。分别核对 36 层及各计分目标的覆盖，记录短历史有效长度、回退次数和计分掩码。

## 数据与评分

| 任务 | 固定测试范围 | 论文主指标 |
| --- | --- | --- |
| PIQA | validation 1,838，0-shot | acc_norm |
| HellaSwag | validation 10,042，0-shot | acc_norm |
| WinoGrande | validation 1,267，0-shot | acc |
| BoolQ | validation 3,270，0-shot | acc |
| ARC-Easy | test 2,376，0-shot | acc_norm |
| ARC-Challenge | test 1,172，0-shot | acc_norm |
| MMLU | 57 科 test 共 14,042，固定每科 5-shot | 按题数加权 acc，另保存分科 |
| LAMBADA OpenAI | 英文 test 5,153，0-shot | acc，末词计分 |
| GSM8K | main test 1,319，固定 5-shot | 最终数值答案 Exact Match，真实自回归生成 |
| WikiText-2 | 原文，窗口 2048、步长 1024，292 窗、299,077 个唯一目标 | `exp(总 NLL / 总计分 token)` |

八项准确率合计 39,160 题。PIQA、HellaSwag 和 ARC 同时保存 acc 与 acc_norm。多选按同一模板对候选续串打分，沿冻结 Harness 版本定义归一化；WinoGrande 按候选前缀语义做预检。GSM8K 用统一非 thinking 协议，正式测试前以开发样本固定模板、few-shot 顺序、解码方式、生成上限、停止条件和答案提取规则。记录实际超预算和解析失败。固定任务数据、样例、顺序和解析器后再全量执行。

WT2 原文 SHA-256 为 `173c87a53759e0201f33e0ccf978e510c2042d7f2cb78229d9a50d79b9e7dd08`，计分使用的完整 token 序列 SHA-256 为 `8557ef42be22a592e5f1704026fedbedc937b484e52f517add9f478adc0de20f`。普通文本 teacher forcing，保持原窗口坐标、BOS 与计分掩码。换执行环境先核验未改动的 BF16 参考。联合 WT2 如已在相同检查点、随机源、seed 和目标覆盖下封存，可复用，避免重复作业。短后缀和小样本预检单独记录。

## 执行顺序与回传

1. 锁定依赖、模型、数据及计分配置，完成少量开发样本预检。A 的全量任务可先开始。联合配置检查 B 实际抽样、D 零抽样与模型计分路径覆盖。
2. B 的 seed 101 先完成所需全量任务，复核覆盖和结果后按同一配置补 102/103。每个 seed 保留独立逐题及逐窗结果。C 组请训练方交付 100M 控制权重、有效训练 token 账本、实际训练包与排重回执的 SHA，以及原 WT2 评估记录。
3. 回传汇总表及逐题文件（样本 ID、候选分数或生成答案、正确标记）、逐窗 NLL/目标数/坐标、各层计分覆盖、完整命令、源代码提交、配置/模型/分词器/数据/结果 SHA-256、环境和 Slurm 回执。B 报告每 seed、均值及样本标准差；确定性配置一次。大型原件按项目共享存储约定归档，GitHub 放小型汇总与校验索引。
4. 请在 Issue 回帖列出每组已完成项、封存证据链接和仍缺的输入。原版与联合结果用于主图，续训数字结果用于说明训练收益，同权重确定性结果进入 WT2 消融。比较 PPL 时同时回传 mean NLL。

已有 [联合评测及 FFN 条件均值诊断](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/252)、[历史联合 PPL 范围](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/242) 和 [论文评测清单背景](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/250) 可作为实现与报告参考。
