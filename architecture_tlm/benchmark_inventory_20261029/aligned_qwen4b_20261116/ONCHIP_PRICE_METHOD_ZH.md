# Fig.11 片上能量估算与覆盖口径


## 论文正文与表注

下方采用 LaTeX，引文键可与论文现有参考文献库合并。正文适用于 Fig. 11 对应的外部对比表。

### Manuscript paragraph

```latex
\paragraph{Cross-architecture estimates.}
Following prior comparisons based on published accelerator configurations~\cite{wang2024sofa,chen2025hsa}, we map one Qwen3-4B decode step at batch size one with 2,048 tokens in the KV cache to selected architectures. We use published mappings or released simulators, retain each evaluated weight and KV-cache precision, and use a common full-vocabulary BF16 output projection and token-selection stage where these stages are modeled. The common timing scenario assumes 250\,MHz and 80\% of the 136.46\,GB/s peak LPDDR bandwidth. We report per-operator overlap and serial cases for computation and transfers~\cite{bazzi2026edgecim}. We estimate on-chip energy as $\sum_j n_j e_j$, where $n_j$ is the modeled count of MACs, array service cycles, or SRAM accesses and $e_j$ is the corresponding component energy cost~\cite{wu2019accelergy,li2025h2llm}. Following cross-node comparisons such as Oltron~\cite{xue2024oltron}, we apply rounded DeepScaleTool switching-energy ratios only to separately identifiable digital logic (0.37 for 65-to-28\,nm and 0.58 for 45-to-28\,nm)~\cite{sarangi2021deepscale}. We estimate DRAM transfer energy separately using 4\,pJ per transferred bit~\cite{chen2025hsa,quinn2025iks}. Table~\ref{tab:arch-benchmark} states the source and component coverage of each estimate.
```

### Table note

```latex
\emph{Author-reported} values retain the original workload and hardware settings. Values read from plots are marked as approximate. \emph{Estimated on-chip subtotal} covers only the listed components under the common Qwen3-4B workload. \emph{Technology-scaled core estimate} covers only the specified digital logic after workload and process scaling. \emph{This work (TLM)} covers the full modeled decode from embedding through output-token selection. A dash denotes an unavailable value. Undisclosed stages are marked separately. DRAM energy covers model-data transfers. Background and refresh energy are outside this accounting boundary. Total energy is shown where the on-chip and DRAM estimates cover the same full decode step.
```

### Citation keys

| Suggested key | Source and use |
|---|---|
| `wang2024sofa` | Huizheng Wang et al., *SOFA: A Compute-Memory Optimized Sparsity Accelerator via Cross-Stage Coordinated Tiling*, MICRO 2024. §V-D uses published hardware parameters to estimate latency for the same 137 GOP Llama-7B attention workload. [Paper §V-D](https://arxiv.org/html/2407.10416v1#S5.SS4) · [DOI](https://doi.org/10.1109/MICRO61859.2024.00093) |
| `chen2025hsa` | Chun-Ting Chen et al., *Hybrid Systolic Array Accelerator with Optimized Dataflow for Edge Large Language Model Inference*, ISLPED 2025. Table I identifies post-layout, estimated, and technology-scaled results. Table II uses 32 pJ/byte for its DDR5 scenario, equivalent to 4 pJ/bit. [Paper §V](https://arxiv.org/html/2507.09010v1#S5) |
| `bazzi2026edgecim` | Jinane Bazzi et al., *EdgeCIM: A Hardware–Software Co-Design for CIM-Based Acceleration of Small Language Models*, 2026. Eqs. (1)–(3) relate compute and memory time for serial and overlapped tile schedules. [Paper §III-C](https://arxiv.org/html/2604.11512v2#S3.SS3) |
| `wu2019accelergy` | Yannan Nellie Wu, Joel S. Emer, and Vivienne Sze, *Accelergy: An Architecture-Level Energy Estimation Methodology for Accelerator Designs*, ICCAD 2019. Uses runtime action counts and per-action component energies. [Paper](https://d1qx31qr3h6wln.cloudfront.net/publications/ICCAD_2019_Accelergy.pdf) · [DOI](https://doi.org/10.1109/ICCAD45719.2019.8942149) |
| `li2025h2llm` | Cong Li et al., *H²-LLM: Hardware-Dataflow Co-Exploration for Heterogeneous Hybrid-Bonding-based Low-Batch LLM Inference*, ISCA 2025. §7.1 uses distinct MAC, SRAM, and memory I/O costs sourced from synthesis, compilers, and prior reports. [Paper §7.1](https://chenzhangsjtu.github.io/files/2025-H2_LLM_ISCA25.pdf#page=10) |
| `xue2024oltron` | Chenhao Xue et al., *Oltron: Software-Hardware Co-design for Outlier-Aware Quantization of LLMs with Inter-/Intra-Layer Adaptation*, DAC 2024. §5.1 uses DeepScaleTool in the comparison with OliVe and OLAccel. [Paper §5.1](https://chenzhangsjtu.github.io/files/2024-DAC.pdf#page=5) · [DOI](https://doi.org/10.1145/3649329.3656221) |
| `sarangi2021deepscale` | Satyabrata Sarangi and Bevan Baas, *DeepScaleTool: A Tool for the Accurate Estimation of Technology Scaling in the Deep-Submicron Era*, ISCAS 2021. Fig. 3 is the source of the approximate switching-energy ratios used here. [Paper Fig. 3](https://vcl.ece.ucdavis.edu/pubs/2021.05.ISCAS.DeepScale/2021.05.ISCAS.DeepScale.pdf#page=3) |
| `quinn2025iks` | Derrick Quinn et al., *Accelerating Retrieval-Augmented Generation*, ASPLOS 2025. §6.1 uses 4 pJ/bit as a reference LPDDR cost for retrieval and describes scaling to 16 nm. [Paper §6.1](https://arxiv.org/html/2412.15246v1#S6.SS1) |

LPDDR 参数引用 IKS §6.1。它对 LPDDR 采用过相同的 4 pJ/bit 参考值，应用是 RAG 检索，并另述了向 16 nm 的换算。HSA 与 IKS 提供单位计价的先例。本项目的 4 pJ/bit 属于固定传输能耗假设，文中可写成 *assumed DRAM transfer energy*。 [IKS，ASPLOS 2025 §6.1](https://arxiv.org/html/2412.15246v1#S6.SS1)

### 现有表中片上能量的来源标记

单位为 mJ/token。标记对应具体数值。同一行的时延、面积和能量可能采用不同来源或不同范围。

| 表注标记 | 适用片上能量 | 覆盖 |
|---|---|---|
| This work (TLM) | P-bit **15.27**，同配置数字控制在同一行备注 | Qwen3-4B 完整建模 decode。 |
| Author-reported | SoulMate **0.0271** | 原报 Llama-3.2-1B 片上 decode 能量。 |
| Author-reported, plot read | EdgeCIM **约 18**；OPAL **约 1,900** | EdgeCIM 为原报 65 nm、Qwen3-4B INT4 的片上估算，片上口径按版本间同模型数值交叉判断。OPAL 为原报 65 nm、Llama2-70B 的 core 和片上存储（含漏电）。 |
| Estimated on-chip subtotal | BitMoD W3 **31.34**（另一计价 24.25）；Tender W4 **8.34**；EVA W2 **58.15**（串行 FC 估算约 70.88）；M-ANT W4A8KV4 **7.02** | 统一 Qwen3-4B 工作量下的已计模块小计，包含共有 BF16 词表头。未计模块因架构而异，详见逐篇说明。 |
| Estimated on-chip subtotal | OASIS **约 12**；Harmonia **约 1.18** | 统一 Qwen3-4B 工作量。OASIS 只计线性 GEMV，Harmonia 只计线性和 QK/PV 峰值算术代理。 |
| Technology-scaled core estimate | Kelle **约 1.13**；OPAL **约 12.4**（备注） | 统一 Qwen3-4B 工作量下的局部估算。Kelle 折算 INT8 线性 RSA；OPAL 折算计算核心。SRAM、eDRAM、漏电与外存按各自边界处理。 |

其余外部行在片上能量栏留空。论文表中使用上下标时可令同一行的原报面积、重估时延和片上小计各自带标记。嵌入、词表投影与输出选择是否有计价，以逐项公开证据为准。

### 比较的合理性

- **适用的结论。** 工艺折算、模块事件计价及在共同工作量下解析重估都有公开先例。外部表适合展示各设计的量级和覆盖范围。主图的节能结论由同一套 TLM 和存储配置下的本项目数字对照支撑。对 W8 + K 筛选，片上能量从 19.81 降至 15.27 mJ/token（约 **23%**），计入外存传输的模型总量从 193.17 降至 188.43 mJ/token（约 **2.5%**）。 [本项目封存 TLM](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/01a2fb1d13018d381e012630ea1be442e85bdd26/architecture_tlm/process_28nm/results_20261111/REPORT_ZH.md)
- **调度与活动会改变排名。** BitMoD W3 在同为 1,024 PE 的两个排列下，从 64×16 的 **130–144 ms/token** 变为 256×4 的 **39–53 ms/token**。相对本项目的 51.13 ms/token，排序随映射和重叠假设改变。其两种片上计价约 24–31 mJ/token，反映两种事件价格假设。Tender 的峰值等效 MAC 单价没有完整重建 B1 空闲阵列、FIFO 和静态成本。片上小计仅给出已计模块的量级，误差方向取决于利用率和所用单价。 [共同设定快估](QUICK_BENCHMARK_ZH.md) · [Tender Table V](https://arxiv.org/html/2406.12930v1#S5.SS3)
- **等面积、等质量和同库 PPA 需要各自证据。** 外部场景统一工作量和名义时钟/带宽，保留不同的权重和 KV 精度、PE 布局及片上存储条件。外部计价映射使用 Qwen 张量形状与事务量，无对应的新 Qwen 检查点或质量评测。即便两个设计都标为 28 nm，仍可能有不同 PDK、电压及工艺角。4 pJ/bit 计算传输部分，背景/刷新及板级分项没有统一计价。跨工作量、跨工艺的局部值宜按项标注，正文中的倍数只用于相同覆盖和控制条件的结果。

## 估算细节

同条件形状为 Qwen3-4B、batch 1、已缓存 2,048 个 token、36 层。每输出一个 token，decoder 线性层有 3.633316 G MAC，QK 与 PV 合计 0.603980 G MAC。表中外部快估用共有的 BF16 全词表 head（输入输出及已计控制的片上代价 2.5983 mJ），各方法保留自己的权重和 KV 位宽；OASIS、Harmonia 和 Kelle 的局部数字保留各自列明的算子范围。LPDDR 136.46 GB/s、80% 有效带宽用于共同时间场景。外存一列是访问字节数乘 8 和 4 pJ/bit，未计单独待机/背景，也不代表板级能量。各版本的时延与读写边界另见同目录的快估。 [工作负载与快估](QUICK_BENCHMARK_ZH.md) · [EVA 与 M-ANT 工作负载](EVA_MANT_ESTIMATE_ZH.md)

## 能量单位与工艺

器件与数据通路可拆开时，对译码事件分别计价。片上估算用“有用 MAC 数 × 单价”或“阵列服务拍 × 每拍价格”，再叠加已识别的 SRAM 访问、独立数字算子和共享 head。原报吞吐、原报功耗、计算域和内存域只有在相同工作点下才能直接组合。用原报功率反推一次操作或一拍能量时，先除以原报工作频率或峰值操作率，目标时钟负责把拍换成时间。基本活动价转用假设同等切换活动和接近原始电压。若把等待拍也计价，应额外计该时间的驻留功耗。峰值效率和 B1 下的数组闲置开关开销都有不确定性。

DeepScaleTool 原文第 3 页 Fig. 3 是对逻辑切换能量的跨节点趋势。按图估读，65→28 nm 的目标/原工艺能量比例约 **0.37**，45→28 nm 约 **0.58**。本文只把它乘在明确拆出的数字算术代理上；原报 SRAM、eDRAM、漏电、DRAM、I/O 和工艺各有独立的模型。比例为取整后的读图值，28 nm 也可能是与本项目不同的 PDK、VDD 或工艺角。面积栏继续沿用各行指明的范围和节点。 [Sarangi 和 Baas，ISCAS 2021 Fig. 3](https://vcl.ece.ucdavis.edu/pubs/2021.05.ISCAS.DeepScale/2021.05.ISCAS.DeepScale.pdf#page=3)

## 各论文的估算

- **BitMoD**。沿用作者阵列模型 64×16 下的拍数。W3 默认价格为 0.84 pJ/PE/拍，代入 30.74 M 拍、1024 PE，再加 SRAM 和共有 head，得到 31.34 mJ。替代价格取同论文 Table X 的 tile 功率 (39.36\,\mathrm{mW}/1\,\mathrm{GHz}/64=0.615\,\mathrm{pJ}/\mathrm{PE}/\mathrm{cycle})，得到 24.25 mJ。W6 34.69–45.05 mJ。范围是同一映射的两个计价场景。作者代码收集 Linear（包含模型中采用 Linear 的词表头）、QK/PV，不独立计 embedding、norm、softmax 或最后的 token 选择。当前共同模型使用项目 BF16 head 代替其头部映射。 [原文 §IV–V](https://arxiv.org/html/2411.11745v1#S5.SS3) · [作者形状收集](https://github.com/abdelfattah-lab/BitMoD-HPCA-25/blob/e445a5f31100a5057b4c5c4373da223ce95f1c3b/bitmod_sim/llm_shape_profile.py#L17-L26) · [作者 QK/PV 模型](https://github.com/abdelfattah-lab/BitMoD-HPCA-25/blob/e445a5f31100a5057b4c5c4373da223ce95f1c3b/bitmod_sim/pe_array.py#L78-L123)
- **Tender**。28 nm 文中阵列含累加器，1.09 W @ 1 GHz / 4096 MAC/拍得到峰值等效 0.266 pJ/MAC。线性阵列约 0.97 mJ，QK/PV 按本项目 BF16 增量价 3.152 pJ/MAC 计约 1.90 mJ，SRAM 权重和 KV 有效载荷按一次片上写读约 2.87 mJ，另加共享 head 得 **8.34 mJ**。用 1.09 W 直接充满整个生成窗口会假定全部 PE 一直以峰值活动，B1 利用率、门控、FIFO、控制和静态成本未完整重建。 [Tender 原文 Table V](https://arxiv.org/html/2406.12930v1#S5.SS3) · [项目 BF16 FMA 标定](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/01a2fb1d13018d381e012630ea1be442e85bdd26/architecture_tlm/process_28nm/250MHz/BINDINGS.json)
- **EVA**。作者含实数据的系统实验运行每个模型的首个 Transformer block。当前用作者 FC 模型把活动扩至 252 个 FC 运算，采用 6.070 nJ/FC 服务拍及各 SRAM 动态访问，再加共用 BF16 attention 3.00 mJ 和 head 2.60 mJ。80% 外存效率下，W2/W3/W4 的重叠估算为 **58.15 / 83.51 / 108.86 mJ**，只将 FC 计算与搬运串行计拍时约 **70.88 / 102.56 / 134.24 mJ**。独立 RMSNorm、残差、FFN 激活及完整物理互连的能量仍未补齐。 [EVA §VI](https://arxiv.org/html/2605.24144#S6) · [作者模型](https://github.com/dbw6/Eva/blob/main/simulator/methods/vqarray.py#L13-L171) · [作者配置](https://github.com/dbw6/Eva/blob/main/simulator/configs/methods/eva.yaml) · [项目 dense attention](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/01a2fb1d13018d381e012630ea1be442e85bdd26/architecture_tlm/attention28_digital_estimates_20261109/RESULTS.json)
- **M-ANT**。用 P³-LLM Table VIII 报告的 M-ANT PE 价格 0.40 pJ/MAC，按 4.2373 G MAC 得 1.69 mJ。SRAM 权重和 KV 约 2.73 mJ，再加共享 head，得到 **7.02 mJ**。SRAM 与 Tender 统一用每 16 B 读 10.36 pJ、写 10.73 pJ，head 流量在 head 内独立计价。PE 的原始 PVT 未在引用表中单列，片上驻留、静态、转换和控制未完整计价。 [M-ANT 原文](https://arxiv.org/html/2502.18755v1#S7) · [P³-LLM Table VIII](https://arxiv.org/html/2511.06838#S6)
- **OASIS**。从原文 4,096×4,096 GEMV 中 1% outliers 的场景读出 2,304 个 reduction 周期，用 Table II 的 16 个 MAC tree 和每个 0.254 W，再根据 Fig. 18 reduction 占比 33.1% 回算这个 GEMV 的片上能量。按 Qwen 投影和 FFN MAC 估 **约 12 mJ/token**，假设相似的利用率和 outlier 分布。注意力、词表头和其他控制均不在此数。表中另列的外存包含 KV 与 head，两个值不可写成端到端总能量。 [OASIS 原图与表](https://arxiv.org/pdf/2507.23035v4#page=12)
- **Harmonia**。28 nm 原文 M8W4 与 M8M8 的峰值为 8,176 与 4,088 GOPS/W，以两 ops/MAC 推算 Qwen 线性和 QK/PV 的有用算术约 **1.18 mJ/token**。论文 B1 线性阶段的理论行利用率只有 12.5%。此代理不包含闲置切换、SRAM、其他向量运算和 head。 [Harmonia §V](https://arxiv.org/html/2602.04595v3#S5)
- **Kelle**。6.52 W 片上功率中取 RSA 的 17%，以 4.13 INT8 TOPS 计 Qwen 线性工作量，得 **1.95 mJ/token @ 45 nm** 峰值算术代理。乘 0.58 后为 **约 1.13 mJ/token @ 28 nm**。原文另外建模的 SRAM、eDRAM、SFU、控制、重计算及外存保留在原文范围。 [Kelle §8](https://arxiv.org/html/2510.16040v1#S8)
- **OPAL**。修正上一版对 Fig. 8(a) 的描述，原图纵轴为绝对 **J/token**。65 nm、Llama2-70B W4A4/7 的 core + 片上存储能量图读约 **1.9 J/token**，其中 core 约 **0.63 J/token**。仅对 core 取 Qwen/Llama2 层内线性 MAC 比 3.633/68.451，再乘 0.37，得到 **约 12.4 mJ/token @ 28 nm**。这里假定核心以线性矩阵工作为主，原报上下文及完整词表边界未披露。片上存储访问与漏电未折算。表内保留原报片上值，共同规模估计放在备注。 [OPAL Fig. 8(a)](https://arxiv.org/pdf/2409.05902v3#page=6)
- **EdgeCIM**。v2 PDF Fig. 12(a,c) 可读 Qwen3-4B INT4 约 105 token/s 与 20 mm²。v2 Fig. 12(b) 的图面没有该模型，能量改读 v1 Fig. 9(b)，INT4 约 55 token/J（18 mJ/token），INT8 约 25 token/J（40 mJ/token）。片上口径由 v1 的 Llama3.2-1B 值与 v2 §V-C 明示的片上值吻合交叉判断，两者远高于同文含 DRAM 的范围。外存与合计均无匹配数值。当前保留原生 65 nm SRAM-CIM，缺少逻辑和存储分项。 [EdgeCIM v1 Fig. 9](https://arxiv.org/pdf/2604.11512v1#page=6) · [EdgeCIM v2 Fig. 12](https://arxiv.org/pdf/2604.11512v2#page=9) · [EdgeCIM v2 §V-C](https://arxiv.org/html/2604.11512v2#S5.SS3)

正文能量主图可用本项目、同工艺、同位宽及同生成边界的数字对照。外部表保留片上子系统估计、原生实测和作者完整性。BitMoD/Tender/EVA/M-ANT 的“已计片上 + DRAM”可用于定位差异，权重和 KV 位宽更低带来的 DRAM 收益与概率计算本身的能效分别解释。报告同量化/输出质量设置时仍需相应质量数据。

复算使用 `python price_onchip.py ONCHIP_PRICE_ESTIMATE.json`。脚本读取同目录的已锁定时延/流量输入，JSON 保留未舍入的中间量。此次为分析计价及论文图读，未运行新的模型推理、RTL、PPA 或外存仿真。

