# Qwen3 随机架构最终质量评估清单

日期：2026-11-08。负责人：rayggxia。接续 Issue250 / PR251 的 Fig.9 规划。

用户已确认测试集选择：**经典六项＋完整 MMLU＋LAMBADA，另做 GSM8K 生成任务与 WikiText-2 PPL**。本文件汇总最终清单和执行前需固定的评估口径；few-shot、生成预算及种子安排属于下文建议或待冻结项。本次仅整理文档，没有启动模型推理、训练、GPU/Slurm、TLM 或 EDA，也不代表以下任务已经跑完。

## 1 最终需要跑哪些

主准确率部分共八项，另有一项生成任务和一项语言建模任务。MMLU 的57个子科目合并作为一项完整基准。

| 用途 | 测试集 / Harness task | 覆盖能力 | 主报告指标 | 建议 shot | 正式数据范围 |
|---|---|---|---|---|---|
| 主准确率 | PIQA / `piqa` | 物理常识 | `acc_norm` | 0-shot | 完整 validation |
| 主准确率 | HellaSwag / `hellaswag` | 常识与事件后续理解 | `acc_norm` | 0-shot | 完整 validation |
| 主准确率 | WinoGrande / `winogrande` | 指代消解、语境理解 | `acc` | 0-shot | 完整 validation |
| 主准确率 | BoolQ / `boolq` | 阅读理解与是非问答 | `acc` | 0-shot | 完整 validation |
| 主准确率 | ARC-Easy / `arc_easy` | 基础科学知识与推理 | `acc_norm` | 0-shot | 完整 test |
| 主准确率 | ARC-Challenge / `arc_challenge` | 较困难的科学推理 | `acc_norm` | 0-shot | 完整 test |
| 主准确率 | MMLU / `mmlu` | 57学科的综合知识 | `acc`，按题数加权总分 | 5-shot | 57学科完整 test |
| 主准确率 | LAMBADA / `lambada_openai` | 利用整段语境预测末词 | `acc` | 0-shot | 完整 test |
| 生成补充 | GSM8K / `gsm8k` | 连续生成、多步数学推理 | 最终数值答案 Exact Match | 5-shot | 完整 test |
| 语言建模 | WikiText-2 raw test / 沿用项目完整滑窗入口 | 对预测概率分布变化的敏感性 | 完整滑窗 token PPL | 不适用 | 完整已校验 raw test |

PIQA、HellaSwag 和 ARC 同时保存 `acc` 与 `acc_norm`，主图预先采用上表指标，不能看过结果后再选更好的一种。MMLU 总分沿用固定 Harness 配置的题数加权聚合，分学科结果保留；不能把57个科目等权平均后仍标成同一个总分口径。

LAMBADA 固定为 `lambada_openai`；`lambada_standard` 是另一个任务版本，不混报。LAMBADA 的末词准确率与 WikiText-2 的全语料 PPL 分别展示，不能相互替代。

## 2 Tender 图中还有哪些需要补充

用户提供的表格来自 **Tender，ISCA 2024，Table VII，PDF第12页**。该表比较 OPT-6.7B / LLaMA-7B 上 FP32 与几种低精度数制，表注明确是 Harness zero-shot 任务；这不是体系结构论文统一规定的必测清单。[原文表VII和§VI-C](https://jungi-lee.github.io/assets/pdf/isca24-tender.pdf#page=12)

| 表中项目 | 本项目决定 | 原因 |
|---|---|---|
| HellaSwag、WinoGrande、ARC-E、ARC-C | 正式必测 | 已被经典六项覆盖 |
| LAMBADA | 正式加入 | 补充整段上下文下的语言预测能力 |
| College CS、Int. law、Jurisprudence | 不另立三个必测项 | 分别是 MMLU 的大学计算机、国际法、法理学子科目，完整 MMLU 已覆盖 |
| WiC | 可选扩展，当前不列主清单 | 补充词义是否相同的二分类；对当前硬件贡献的证明优先级较低 |
| ANLI-r2 | 可选扩展，当前不列主清单 | 若强调语义推断或对抗鲁棒性，可预先加入；并非当前论文的必需项目 |

WiC 和 ANLI 可以加强能力覆盖，但不能因为某种随机方案在其上下降较小，才临时选择它们替换原定任务。接近随机猜测水平的参考准确率，其“变化很小”对能力保持的证明也较弱。

Tender 这张表的粗体是低精度方案间的比较。部分任务相对 FP32 下降明显，不能将其解释为本项目已获得同等精度损失预算。本项目仍报告自己同协议参考下的变化，不把外部模型的绝对准确率当作我们的验收门槛。

## 3 比较哪些模型和方案

主模型采用 **Qwen/Qwen3-4B 后训练版本**，不使用 Qwen3-4B-Base。官方模型卡说明 Qwen3-4B 经过预训练与后训练；不能仅凭模型名称是否含 Instruct 判断。[官方模型卡](https://huggingface.co/Qwen/Qwen3-4B)

优先完成两条主线：

1. **未改动 BF16 参考：** 在同一实验环境、同一准确模型 revision 和同一评估协议下重新核验。
2. **最终联合随机方案：** 使用拟用于论文的最终 FFN＋Attention 检查点、采样预算、筛选配置、源共享和前后处理。

若训练改变了权重，这两条主线说明的是最终方案相对原模型的整体质量变化；不能把差异全部归因于随机算术。需要隔离算术误差时，补充同一训练检查点的匹配精确/条件数值控制，并明确其与原始 BF16 模型的区别。数值控制本身也需要说明量化、算子精度及数值等价边界。

FFN-only、Attention-only 消融优先选已有 PIQA、ARC-E 和完整 WT2；需要解释复杂推理影响时补 GSM8K。先把主参考和最终联合方案的完整清单收齐，不要求每个候选配置都跑全部任务。

不同前端与随机源不能继承彼此结果：S12 与 FP32 max-gap、理想采样与实际有限精度采样、Philox 与 GF/共享随机源，以及不同筛选 K / 采样 S，均需按实际执行路径标注。算法数值结果不自动等于 RTL 有限状态实现的质量结果。

## 4 评估协议必须固定什么

### 4.1 模型、文本与工具版本

- 固定模型 ID、revision、权重文件/最终检查点与 tokenizer 的 SHA-256；保留模型后训练属性。
- 固定代码仓库及提交、执行补丁、环境、Harness commit、任务 YAML/模板与数据 revision/划分/样本顺序。下方 v0.4.8 链接用于核对指标定义，不表示本项目已经采用该版本。
- WikiText-2 使用项目已校验的 raw 文本及 SHA-256。保留空行恢复规则，不用普通换行拼接替换已有原文。
- PPL 记录窗口、stride、目标 token 覆盖、BOS、loss mask 和精度；不能把固定后缀 PPL 标为完整 WT2 PPL。
- 最终测试使用完整指定划分；256题筛选只作开发/预检，不能继承为完整测试集结果。参数调节使用训练/校准/开发数据，不在正式 test 上挑选配置。

### 4.2 提示、thinking 与生成设置

- 经典六项与 LAMBADA 建议 0-shot，MMLU 建议 5-shot；固定 few-shot 样例及顺序，原始任务模板和套 chat 模板的结果分开标注。
- 概率评分任务按固定模板运行，不自动插入思考文本。若不套 chat 模板，写明 `chat_template=none`，不要声称设置了只在 chat 模板中生效的 thinking 开关。
- GSM8K 建议固定为非 thinking 模式，并记录 chat 模板、特殊 token、`enable_thinking`、解码方式、停止条件及 `max_new_tokens`。原生 Harness 模板与聊天适配协议须明确选择，不能混合结果。
- 执行前冻结生成预算和答案提取规则。建议以固定 Harness `strict-match` 的最终数值 Exact Match 为主，另存 `flexible-extract` 便于诊断；不按结果挑解析器。
- 若采用确定性贪心生成，应注明这是用于控制生成噪声的项目协议，不宣称与 Qwen 官方采样评测完全一致。token 采样随机种子与电路/算术采样种子分别记录。
- 记录提示长度、上下文上限和超长处理。特别核对 MMLU 5-shot 与 GSM8K 提示是否超出当前验证过的上下文范围；不静默截断。截断、无效答案、超生成预算均保留计数。

### 4.3 随机计算路径覆盖

**多选题通常用候选答案 log-likelihood 评分，不等于进行一次自由生成。** 单纯跑通普通多 token forward，可能没有触发只在单 token decode 中启用的随机模块。

执行前审计并记录：

1. 哪些层、哪些模块启用随机替换；所有正式计分目标是否实际走过这些模块。
2. prefill 是准确还是随机，decode 是准确还是随机；FFN 与 Attention 可以有不同作用范围，需分别写明。
3. 若是 decode-only 方案，候选答案/目标 token 用缓存逐 token 评分；同一协议下建立 cached BF16/SDPA 控制，核对 logprob 与目标覆盖。
4. 只在答案 token 使用随机路径的结果标为“准确前缀＋随机答案评分”，不能声称随机 prefill 或完整请求全程替换。
5. 记录 batch、padding/mask、GQA、KV cache、随机流分配和每个 scored token 的调用计数；不同 batch 可能改变随机数消费顺序，不假定同 seed 必然逐抽样配对。

GSM8K 需要真实自回归生成，不能用 teacher-forced 标准答案的正确率替代。短上下文任务也不能单独证明长上下文 QK/KV 筛选有效；若论文提出长上下文质量收益，再配置独立长上下文验证，不在这份基础清单中默认新增。

## 5 种子、执行顺序与复用

仓库一般要求随机方案至少三个独立种子，并报告均值与离散程度；**已有任务中用户明确授权的单 seed 范围继续保留，不因本清单自动扩跑**。单 seed 结果只能标成该 seed 的结果，不补造跨 seed 误差条。

建议顺序：

1. 核验已有结果、运行中任务、检查点和 manifest，复用同版本同协议结果，避免重复提交健康作业。
2. 用少量开发样本核查加载、评分、随机路径、模板、长度及解析器；此为预检，不是最终准确率。
3. 在最终执行环境核验未改动 BF16，再完成最终联合方案的八项理解/预测任务和完整 WT2。
4. 用完全冻结的协议完成 GSM8K 生成评估。
5. 按已有授权补齐种子或少量消融；这一步不是本次文档请求对昂贵作业的新启动许可。

结果复用要求模型/检查点、模板、目标集合、算子/采样配置、精度、源模型与协议匹配。历史 Qwen2.5-0.5B、LLaMA Base 或旧 Qwen3 配置的结果只作历史证据，不能填入本轮 Qwen3 主表。

## 6 论文中怎样展示

- **Fig.9 主图：** 八项任务分别对比 BF16 参考和最终联合方案，显示准确率及下降的百分点；可按常识、问答、知识、语言预测分组。
- **配套表格/子图：** 单独展示 GSM8K Exact Match 与 WT2 PPL；量纲不同，不放到同一个准确率纵轴。
- **消融图：** 选择代表任务展示 FFN-only、Attention-only 和联合方案，分开解释训练收益和随机算术影响。
- 图注注明模型 revision/检查点、shot、指标、模板、随机作用阶段、种子数和采样预算；完整逐题结果和配置放可追溯索引。

准确率以百分数显示，差值用百分点：`Δacc_pp = 100 × (acc_candidate − acc_reference)`。PPL 另报绝对值和相对变化：`ΔPPL_rel = PPL_candidate / PPL_reference − 1`。二者没有通用换算关系。

多任务均值如需展示，先约定任务集合和聚合方法，不能混入 PPL；MMLU 总分与其57个科目不要重复计权。任务准确率不等于生成速度，PPA 与时延继续采用各自完整系统口径。

## 7 执行前仍需补齐的记录

本文件不填造未执行结果。正式执行 manifest 至少包括：

| 字段 | 要求 |
|---|---|
| 身份与源码 | Issue、负责人、仓库提交、执行快照及配置 SHA-256 |
| 模型 | 模型 ID/revision、后训练属性、权重/tokenizer/检查点 SHA-256 |
| 数据与协议 | dataset revision、split、样本 ID/顺序、提示模板、shot 与例子、Harness commit |
| 算子与随机 | 层范围、FFN/Attention配置、位宽/尺度、采样数、筛选预算、源/共享/seed |
| 执行范围 | prefill/decode、逐目标覆盖、上下文/截断、batch、缓存和精度 |
| 生成 | thinking、解码策略、token预算、停止条件、解析器和无效输出计数 |
| 结果 | 每题结果、正确数/总数、主/辅助指标、均值/离散程度（若适用）、日志和原件 SHA |

最终质量损失阈值未在本次对话中另行约定；采用这套测试集不等于已批准某个统一 PPL 或准确率下降预算。本次无硬件实验，工艺/PVT/频率/RTL/PPA字段不适用。

## 8 原始依据与相关入口

- [Tender，Table VII及§VI-C，PDF第12页](https://jungi-lee.github.io/assets/pdf/isca24-tender.pdf#page=12)：截图来源，zero-shot低精度方案比较。
- [DS-CIM，Table II，PDF第6页](https://arxiv.org/pdf/2601.06724#page=6)：经典六项任务的相关随机计算工作参考。
- [Harness PIQA配置](https://github.com/EleutherAI/lm-evaluation-harness/blob/v0.4.8/lm_eval/tasks/piqa/piqa.yaml)、[HellaSwag配置](https://github.com/EleutherAI/lm-evaluation-harness/blob/v0.4.8/lm_eval/tasks/hellaswag/hellaswag.yaml)、[ARC配置](https://github.com/EleutherAI/lm-evaluation-harness/blob/v0.4.8/lm_eval/tasks/arc/arc_easy.yaml)：`acc` / `acc_norm` 定义。
- [Harness MMLU聚合配置](https://github.com/EleutherAI/lm-evaluation-harness/blob/v0.4.8/lm_eval/tasks/mmlu/default/_mmlu.yaml)、[MMLU数据](https://huggingface.co/datasets/cais/mmlu)：完整学科覆盖与题数加权聚合。
- [Harness LAMBADA配置](https://github.com/EleutherAI/lm-evaluation-harness/blob/v0.4.8/lm_eval/tasks/lambada/lambada_openai.yaml)：`loglikelihood`、末词 `acc` 与独立任务版本。
- [Harness GSM8K配置](https://github.com/EleutherAI/lm-evaluation-harness/blob/v0.4.8/lm_eval/tasks/gsm8k/gsm8k.yaml)：生成式评估、5-shot与严格/宽松答案提取。
- [WiC任务定义](https://pilehvar.github.io/wic/)、[ANLI原项目](https://github.com/facebookresearch/anli)：两项可选扩展。
- [Qwen3-4B官方模型卡](https://huggingface.co/Qwen/Qwen3-4B)：后训练模型与 thinking/chat 模板行为。
- [逐图原图参考与实验缺口](README_ZH.md)：接续 Fig.9；Fig.8仍按用户意见留空。
- [综合benchmark协议任务Issue98](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/98)、[论文benchmark清单Issue213](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/213)：既有广泛调研，本文件仅细化当前 Qwen3 质量测试选择。
