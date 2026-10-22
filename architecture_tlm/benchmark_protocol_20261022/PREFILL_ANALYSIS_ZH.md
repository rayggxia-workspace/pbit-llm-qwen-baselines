# Prefill 的文献处理方式与 p-bit LLM 端到端评估边界

日期：2026-10-22。专项负责人：amlink1219。接续 [Issue98](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/98)，原 Issue 负责人 rayggxia 保持。

阅读与仓库核对基线：`pbit-tlm-attention-details-20261016@eb317e4f6fb1b0d8844887401f3275f128ef8a83`。本文补充[统一 benchmark 报告](README_ZH.md)，文献版本与逐项位置见 [PREFILL_EVIDENCE.json](PREFILL_EVIDENCE.json)。

**结论：完整请求的端到端评估必须计入 prefill，但不要求 prefill 一定使用概率 Attention。建议第一版采用数字密集 prefill Attention，再在 decode 使用 QK 筛选与有限采样；联合 FFN 继续明确其在两个阶段的替换范围。** 这是待评审的实现分工，不是已切换的架构默认、已批准的质量阈值或新增 PPA 结果。

## 1. Prefill 包含什么，为什么不能省略

Prefill 对输入 prompt 做一次完整模型前向：embedding、各层归一化、Q/K/V 投影、RoPE、因果 Attention、输出投影、残差及 FFN，生成各层 KV cache，并通常得到第一个输出 token 所需 logits。它不是单纯把既有 KV 写进存储器。

多个输入 token 可以并行计算，线性投影与 FFN 通常形成矩阵乘，Attention 可以分块复用 K/V。Decode 每次追加一个 token，通常更依赖权重与 KV 带宽；实际瓶颈还取决于 batch、上下文、数制、驻留容量与调度。长上下文 prefill 的 Attention 计算量也可能显著，不能把“prefill 偏计算、decode 偏带宽”当成所有配置的固定结论。[LLMCompass §II-B、IV](https://arxiv.org/html/2312.03134v1#S2.SS2)

需要区分三种边界：

| 名称 | 计入范围 | 能回答的问题 |
|---|---|---|
| Attention 算子 | 给定 Q/K/V 后的筛选、QK、归一化/采样及 V 聚合，具体算子边界须声明 | 局部算子是否更快、更省能 |
| 完整模型 decode | 每步 embedding、全部层、最终 norm、lm_head、选词，以及 cache 增量；初始 cache 可以已存在 | 生成阶段每步成本是否改善 |
| 完整请求 | 输入处理/prefill、请求内准备、阶段交接和全部输出；设备级与服务级起止点分别说明 | 用户一次完整请求的时间、能量与部署代价是否改善 |

完整模型的单步 decode 结果不能直接改称完整请求结果。若不包含排队、tokenizer 或网络，应称“设备执行端到端”，并保证对照边界相同。

## 2. 先从现有 Zotero 论文库查到的直接参考

本节直接读取既有个人库托管 PDF；没有重新建立 Zotero 库或修改用户条目。PDF 原件不随报告上传，条目键、附件 SHA-256 和页码在证据文件中记录。页码均指 PDF 页序。

### 2.1 SANTA++：dense prefill 后构建代表 key，decode 复用

[SANTA++ v1](https://arxiv.org/html/2609.35629v1)，本库条目 `F6DJ2FX7`，PDF 第 1–4、8 页及附录 D/E：

- 对 prompt 做 dense prefill，使用 RoPE 后的 key 为每层、每 KV head 构建 parent groups 与 teams，保存真实成员 key 代表、组大小和成员索引。
- 构建在 prefill 后执行一次，后续 query 评分代表 key 并抽取 teams；生成的新 token 构成另行准确处理的 suffix。一次性准备成本通过后续输出摊销。
- GPU Table 5 的 **1.69×** 是完整 Attention 算子的速度比；**prefill、team 构建、cache packing、输入准备和 workspace 分配均在计时之外**。该数值不是完整模型 decode 或完整请求速度比。

与我们最相关的是“prefill 生成缓存并准备筛选元数据，decode 重用”的分工。我们的块摘要不是其真实 key 代表与重要性校正，不能把两种算法当作相同实现，也不能直接继承其质量/速度结论。[§2.2、§4、附录 D/E](https://arxiv.org/html/2609.35629v1#S4)

### 2.2 PD-Swap：两个阶段使用不同 Attention 数据通路

[PD-Swap，DAC 2026](https://doi.org/10.1145/3770743.3804245)，本库条目 `569GPQSN`，PDF 第 1、5–6 页：

- FPGA 上保留共用的表查找三值线性层和权重缓冲模块；Attention 区域在 token 并行的 prefill 引擎与 KV 带宽导向的 decode 引擎之间切换。
- 每请求有阶段切换成本；作者把重配置与最后一层 prefill Attention 之后仍需执行的算子重叠，并分析未隐藏开销。
- 同时给出 prefill TTFT 与 decode 吞吐；这是特定 FPGA/模型实现的证据，不是可直接用于我们的 ASIC 参数。

启发：两阶段不必共用完全相同的数据通路，但必须核算共用与专用资源、切换和调度。

### 2.3 Token-Picker：prompt 阶段重用 KV，generation 阶段按需访问

[Token-Picker，DAC 2024](https://doi.org/10.1145/3649329.3655953)，本库条目 `EHFQ826N`，PDF 第 2、4 页：prompt 阶段把 K/V 放入片上缓冲，跨 query 复用；generation 阶段保留当前 query，按 chunk 从 DRAM 取 KV，并执行概率估计和筛选。不能把后者的逐 query 访问模式直接当成高效 prefill 调度。

## 3. Benchmark 原有 16 篇如何处理 prefill

以下保留原 [PAPERS.json](PAPERS.json) 的 16 个 ID。另三篇库内补充不混入原矩阵。表中“未明确披露”是本次检查的证据限制，不等于作者一定没有实现。

| ID / 文献 | Prefill 处理及原文位置 | 可用于我们的结论与限制 |
|---|---|---|
| `opal` — [OPAL v3](https://arxiv.org/html/2409.05902v3#S5.SS2) | §5.2、Fig.8 主要核算生成单个 token 的能量、面积和延迟 | 可以参考量化/算子硬件；未给出足够的完整请求 prefill 核算 |
| `monde` — [MoNDE](https://jaewoong.org/pubs/dac24-monde.pdf) | §4 区分 MoE encoder 与 autoregressive decoder 的 GPU/NDP 卸载 | encoder/decoder 不是 decoder-only 模型的 prefill/decode，不能直接套用其两组吞吐 |
| `unicaim` — [UniCAIM v1](https://arxiv.org/html/2504.07479v1#S3.SS1) | §III-A：prefill 基于累计 Attention 分数做一次静态裁剪；decode 做逐步静态/动态裁剪。§III-B 硬件重点针对 decode | 有明确前缀缓存准备策略；电路级 Attention 指标不自动覆盖完整模型和请求 |
| `mba` — [MBA](https://doi.org/10.1145/3770743.3803981) | 本库 PDF §6–7、Fig.7/8：计算图考虑两个阶段，分析 prefill TTFT、buffer eviction 与 decode | 可参考两阶段缓冲/权重调度；峰值、完整推理和缓冲消融指标仍需分开 |
| `kelle` — [Kelle](https://saiqianzhang.com/gallery/Kelle_Camera_Ready.pdf) | §2.1、§7.1、§8.3.5、Fig.16：prefilling 和 decoding 均管理 KV；按阶段分解能量并扫描输入/输出长度 | 长输入短输出下 prefill 可主导总能量，不能一律把 decode 能效排名扩展到整请求 |
| `attacc` — [AttAcc](https://scale.snu.ac.kr/papers/2024-04-Conference-ASPLOS-AttAcc.pdf) | §2.2 称 prefill 为 Sum；§5.2 将 Sum 全部算子放在 xPU，并将生成 KV 拷入 AttAcc；Gen 的 Attention 放到 PIM | 明确的数字 prefill＋专用 decode 分工。文中后续分析重点为 Gen，具体图的 end-to-end 是否含 Sum 仍须按计时边界判断 |
| `neupims` — [NeuPIMs v3](https://arxiv.org/html/2403.00579v3#S4) | §2.1、§4：summarization 交给独立 NPU，NeuPIMs 的 NPU＋PIM 处理 generation | 支持异构分工；不能只核算 PIM 就把独立 NPU 的成本视为零 |
| `cent` — [CENT v3](https://arxiv.org/html/2502.07578v3#S7) | §6、§7.1–7.3：不用 GPU，两个阶段均由自身系统执行；主要配置 512 输入＋3584 输出，计入整机比较 | 作者报告 GPU 在 prefill 的能效更高、CENT 在 decode 更高；总体收益依赖工作负载配比 |
| `anda` — [Anda v1](https://arxiv.org/pdf/2411.15982v1) | §VI-A 的系统比较主要针对可替换的 FP–INT GEMM；batch=1 | 不是两个阶段的完整 LLM 请求账本；不能仅由其 GEMM 加速复原 TTFT |
| `llmcompass` — [LLMCompass v1](https://arxiv.org/html/2312.03134v1#S5.SS1) | §II-B 定义两个阶段，§III-C 分别验证，§V-A 将完整延迟定义为 prefill＋生成 | 适合参考阶段拆分和输入/输出长度扫描；其性能/面积框架不自动补齐我们的能量数据 |
| `splitwise` — [Splitwise](https://www.microsoft.com/en-us/research/wp-content/uploads/2023/12/Splitwise_ISCA24.pdf) | §IV-C、§VI-A、Fig.11/14/15：prompt 与 token 阶段在不同机器执行；显式核算 KV 传输，用逐层异步传输重叠 prefill | 外部数字 prefill 可行，但传输、两侧设备和调度成本必须计入 |
| `dscim` — [DS-CIM v1](https://arxiv.org/html/2601.06724v1) | §V 为随机 CIM 宏的硬件评估及模型质量验证 | 没有足够明确的完整请求 prefill/decode 分项账本；不能把宏 TOPS/W 直接当请求能效 |
| `artemis` — [ARTEMIS](https://arxiv.org/pdf/2407.12638) | 实验覆盖多类 Transformer 的映射、执行与质量，未找到明确的自回归请求两阶段核算协议 | 有 SC/模拟累加参考价值；不能据其模型执行加速推定我们 TTFT 或 decode 性能 |
| `scarlet` — [SCARLET](https://www.bu.edu/peaclab/files/2026/03/SCARLET_CameraReady.pdf) | §IV-D、Fig.7 分别评估 prefill 与 generation 的平均 decoder 层延迟 | 两阶段均考虑；该图是层级结果，不能直接称为完整请求总时间 |
| `hsa` — [HSA v1](https://arxiv.org/html/2507.09010v1) | §IV-A 混合阵列支持 MMM/MVM；§V、Fig.8 分析两个阶段能量/延迟 | 可参考阶段数据流切换；token 指标包含输入和输出，硬件主模型为 RetNet1.3B，不能混接另一个 Llama 质量点 |
| `santa` — [SANTA / S²ANTA v2](https://arxiv.org/html/2605.01910v2#S3.SS5) | §3.5、Table3 保持 dense prefill，仅在 decode 替换；明确列出两阶段时间。部分其他质量实验同时替换两阶段 | 性能实验与质量实验范围要逐组绑定，不能认为全文共用同一 prefill 策略 |

本次对库内 SANTA v1 附件和在线 v2 分开记录；以下 Table3 数字只来自 v2，不能写成已在本机重跑。以上文献含 GPU 软件测量、FPGA 实现、综合和架构仿真等不同证据层级，彼此不构成同工艺同质量的硬件排行榜。

## 4. 一个可复算例子：计入 prefill 后加速比会下降

S²ANTA v2 §3.5 / Table3：Llama-3.1-8B-Instruct、RTX6000 Ada、BF16、约 30K 输入、batch6、每请求 2048 输出，9 批平均；prefill 均保持 dense。

| 方法 | Prefill，s/batch | Decode，s/batch | 两阶段合计，s/batch |
|---|---:|---:|---:|
| FlashAttention-2 | 56.69 | 101.22 | 157.91 |
| S²ANTA-flash，S=2048 | 56.61 | 80.97 | 137.58 |

- Decode 比值：`101.22 / 80.97 = 1.2501×`。
- 两阶段合计比值：`157.91 / 137.58 = 1.1478×`。
- 表内 `8.237 ms/output token` 是 `101.22 / (6×2048) ×1000`；不是每请求相邻输出间隔。

以上是论文数字的算术复核；两阶段合计仍限于论文所测设备执行范围，不补称服务排队或网络均已计入。[原表](https://arxiv.org/html/2605.01910v2#S3.SS5)

## 5. 我们当前已有结果的真实边界

在本次核对的集成提交中，[unified_v6/README_ZH.md](../unified_v6/README_ZH.md) 明确：覆盖完整 decoder 的单 token decode，包含 embedding、全部层、最终 RMSNorm、lm_head 和贪心选词；初始 KV 和筛选摘要已存在，**不包含 prefill、摘要首次构建和 TTFT**。[RESULTS_ZH.md](../unified_v6/RESULTS_ZH.md) 的 52 项情景沿用这个边界。

因此目前这些数字应继续称为“完整 decode 的条件架构估计”。不能把它们与一个含 prompt 处理的完整请求计时直接相比，也不能把新增文献分析写成已经补做了 prefill 仿真。

项目既有联合质量协议在[项目备忘录](../../PROJECT_MEMORY_ZH.md)中区分：多 token prefill Attention 保留原 SDPA，分层随机 FFN 在 prefill/decode 均替换，目标位置通过单 token 路径审计。新赢家/校正拒绝采样器的成本结果不能自动继承旧理想 CTMC 的完整 PPL。

实时协作核对：Issue96/PR103 为统一 TLM/随机接口，Issue107 为周期、访存与数字模块 RTL 审计，Issue78 为采样器质量。本文只补充文献与评估边界，不修改它们的实现、活动默认或运行任务。PR106 的频率报告仍独立待审；本文不依赖其合并。

## 6. 建议第一版怎样分工

### 6.1 Prefill Attention 保留密集数字实现

采用分块、融合/在线 Softmax、GQA 复用的数字 Attention。输入矩阵乘、因果 mask、数制、片上 tile 与 SRAM 容量、KV 写入均明确；不强制物化完整概率矩阵，也不逐 query 重复读取全部 KV 来制造较差数字对照。

每层 RoPE 后的 K 生成时，构建现有 QK 筛选所需块摘要；保存其位宽、布局、按 KV head 共享关系及元数据。优先评估与 KV 写入重叠的流式构建，但须证明端口/带宽允许；否则保留未隐藏时间。Decode 新 K 到来时，更新未满块和新增块，并单独记录费用。

这不是采用 SANTA++ 的分组/校正算法；摘要语义仍以本项目实际筛选器为准。

### 6.2 Decode 使用当前概率 Attention 候选

比较“概率块筛选→候选 QK→有限时间采样→V 累加”，并明确每个点究竟采用理想 CTMC、赢家保持还是校正拒绝。配置加载、随机源启动/供给、预热、更新、观测、合法性处理、索引和 V 读取必须进入对应成本。已经在 prefill 完成的摘要首次构建不得每 token 重复收费，也不得完全漏掉。

### 6.3 FFN 维持独立、明确的两阶段比较

联合方案延续固定 W8、多档幅度与分层门限的既有行为参考，明确 prefill/decode 都替换；Attention-only 消融保持原 FFN。数字 prefill Attention 不等于把 prefill 的 FFN 也改回 BF16。

Prefill 的 FFN 要用多 token 矩阵乘调度核算权重复用、编码/采样共享、部分和和缓冲。不能只拿 decode 的单 token FFN 时间乘输入长度，也不能直接把观测数当矩阵或网络层周期。

至少保留三类对照：原 BF16 全数字；固定 W8 数字 FFN＋数字 Attention；分层随机 FFN＋数字 prefill Attention＋概率 decode Attention。这样才能分辨量化、随机 FFN 和概率 Attention 各自的作用。实际执行前冻结配置和质量门槛。

### 6.4 面积与外部卸载

若片上保留数字 prefill 引擎，其面积、存储和漏电进入系统边界。共享 MAC/SRAM 只计一次，专用模块另计；不能把两个阶段的面积相加，也不能因模块在 decode 关闭就删除其面积。

若 prefill 放在 GPU/NPU，报告应称异构系统；明确设备是否常驻、模型副本、KV 复制、互连、同步以及两侧能量。阶段传输可以与计算重叠，但仅扣除调度证明确实隐藏的延迟，不能删除传输能量。

## 7. 建议补齐的评估记录

本节为待实施协议，不是本轮已执行实验；不设新的已接受 PPL 阈值。

| 项目 | 必需记录 |
|---|---|
| 输入条件 | 模型/权重/tokenizer/语料版本与 SHA，batch，输入/输出长度，精度，固定 token 重放或闭环生成，EOS 策略 |
| Prefill | 全模型时间与能量；Attention/FFN 分解；KV 写入、块摘要 cold-build、额外索引/布局/缓冲；峰值 SRAM、物理 DRAM 字节 |
| 阶段交接 | 配置/种子加载、DMA、重排、cache flush、同步和未隐藏等待；共享资源与双时钟约定 |
| Decode | 全模型逐步时间、上下文增长、候选及 GQA 并集、实际采样更新/观测与源等待、KV 增量和能量 |
| 完整请求 | 同一边界的 TTFT、TPOT、E2E、请求 J/output token、平均功率；模块/芯片/板卡边界分别标注 |
| 质量 | 匹配原模型控制；随机方案至少三 seed；每个被计分目标、每层实际执行路径；PPL/任务协议与硬件配置绑定 |

若请求到达为 `a`，第一个输出时间为 `t1`、第 G 个为 `tG`：

```text
TTFT = t1 - a
TPOT = (tG - t1) / (G - 1)          # G > 1
E2E  = tG - a
E_request = E_prefill + E_request_setup + E_decode
request_J_per_output = E_request / N_output
```

能源阶段须互斥记账，后台/主机/存储能量按已声明边界分摊，不能重复。延迟按实际关键路径统计，不能把所有资源 busy time 相加。通常 prefill 已产生首 token 所需 logits；若实现额外重算最后一个 prompt token，应计入该次真实工作，不把 G 与 G−1 个后续间隔混用。

输入/输出长度先沿用主报告的待评审组合：128/512、2048/128；Qwen 另加 8192/128，batch1/4，并补充随输出长度增加的摊销曲线。不得把超出某模型原上下文上限的压力情景当作质量结论。

质量方面，整窗 teacher-forcing 可能全部走多 token prefill 而绕过 `q_len==1` 的概率 Attention。应在实际单 token cached 路径上记录各层调用和计分覆盖；同时报告保留数字 prefill 的质量范围。局部算子误差与准备成本的复算不能代替完整模型 PPL。

## 8. 本次交付与后续待办

本次完成：库内附件与 benchmark 16 篇的阶段处理核对；版本和位置记录；SANTA 数值复算；集成 TLM 边界核对；可评审的分工和记账建议。来源与验证散列见个人任务目录的 manifest。

本次没有新增训练、模型推理、PPL、服务器作业、TLM 执行、RTL 综合或功率测量。模型/数据 revision、随机种子和运行精度等新实验字段不适用，不能用文献配置补成我们的实验记录。

后续先评审 prefill 计算资源、FFN 两阶段调度、摘要流式构建和卸载边界，再由相应实现任务建立完整请求仿真。当前未知的 prefill 延迟/能量/面积保持未标定，不以零或旧宏系数填补。
