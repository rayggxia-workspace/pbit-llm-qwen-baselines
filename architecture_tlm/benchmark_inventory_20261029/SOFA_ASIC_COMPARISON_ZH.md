# SOFA 的比较方式与八项相关 ASIC：评估场景、硬件边界及本项目适用性

整理日期：2026-11-06。负责人：rayggxia；关联 Issue #98。本文是文献整理，没有新增模型、TLM、RTL 或 EDA 实验。

**结论：这些工作可以用于相关工作和分层对照，但不是八个统一的 LLM decode 整机基线。优先参考 SpAtten-e2e 和 Energon 的生成阶段方法；SOFA 的 45 ms 是归一化 Attention 工作负载时间，不能直接与我们的完整 decode 步比较。**

## 1. 文件范围与证据规则

本专题接续已有 [benchmark 总清单（PR213 固定版本）](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/759b6c0ffd506ca4d7ff17a1bc0eae45c9b3db67/architecture_tlm/benchmark_inventory_20261029/README_ZH.md)，放在同一目录。不修改该任务作者的 README、STATUS 或分支；PR213 在本次核实时仍 open、未合并。本专题可独立阅读，不依赖 PR213 先合入。

证据按以下含义使用：

- **原文核实**：本次研究已阅读对应原文/作者材料的相关段落；不是复现实验。
- **SOFA 转录**：来自 SOFA Table II 的对手配置，不表示逐篇独立复核了该数值或重建了该硬件。
- **算术推导**：用已公开数字复算，明确列公式；不是论文直接给出的新实测数据。
- **NR-本轮未核**：当前没有取得足够的全文证据；不等于原论文没有报告。
- **建议**：本项目可采用的比较设计，不代表已经实施、质量预算已经批准，或文献架构已经接入我们的模拟器。

SOFA 固定为用户提供的 arXiv **2407.10416v1**（2024-07-15），16 页。原 PDF SHA-256：

`c720d90c88c1d6bda65bc800a361b7283fe6f7bb3f19a87e80124a034b59a176`

仅发布本总结和小型校验/交接，不上传原 PDF。网页 HTML 与该 PDF 存在差异：例如 Table II 的 ELSA latency，上传 PDF 为 **522 ms**，本次网页 HTML 显示 **252 ms**；本文以该 PDF 为准，不混用版本。

## 2. SOFA 做了什么，主要解决哪个阶段

来源：[SOFA v1 PDF](https://arxiv.org/pdf/2407.10416v1)、[HTML](https://arxiv.org/html/2407.10416v1)，重点 §I、§III–V、Fig.6、Fig.11–21、Table II–IV。

SOFA 面向 **large-scale token parallel processing（LTPP）**，原文特别指出 prefill 同时处理整个上下文，适合高 token 并行度。它优化的是“预测重要 QK 对 → 选择 → 按需计算 KV → 稀疏 QK/Softmax/PV”的跨阶段数据流。硬件一次组织 128 路 query，并通过跨 query 复用 K/V 降低访存。

| 机制 | 主要做法 | 对本项目的启示 |
|---|---|---|
| DLZS | 用 leading-zero / 对数近似、移位和加法降低预测成本；不同预测阶段选择转换的操作数 | 筛选精度应与预测本身的转换、算术、访存成本一起评估 |
| SADS | 分段搜索/筛选与局部 top-k；硬件采用 16-to-4 排序核，并裁掉不必要比较 | 不必为了获得候选集合，对全部候选做完整排序 |
| SU-FA | 利用排序提供的最大值信息，减少分块融合 Attention 的重复缩放与非线性；硬件校正最大值预测误差 | 可以优化非线性的调用次数；不能把它理解为已经消除了 exp/div |
| RASS | 按多 query 共享的 KV ID 安排乱序执行，配 ID buffer、FIFO 和 FSM | 共享数据复用必须有具体调度和缓冲成本；单 query decode 未必能获得相同收益 |

**范围限制：**SOFA Table III 的面积/功耗模块包含预测、排序、KV generation、SU-FA、SRAM、调度；没有独立列出完整 FFN、全模型投影和 lm_head 的完整生成路径成本。其“end-to-end”表述应结合该 Attention 加速流程理解，不能自动扩展成完整 LLM 请求的 TTFT/TPOT。

prefill、encoder inference、decode 要分别记录。BERT 整序列推理与 LLM prefill 都存在多 query 并行，但因果掩码、输出需求及 KV cache 后续使用不同，不能直接改名为同一基准。

## 3. SOFA 的 benchmark 和质量比较

以 PDF Fig.18/19 可见标签统计，共 **20 个模型—任务组合**：

| 模型 | 图中任务 | 组合数 |
|---|---|---:|
| BERT-base | MRPC、RTE、SST-2、STS-B、SQuAD、QNLI | 6 |
| BERT-large | 同上 | 6 |
| GPT-2（规模未明确） | WikiText-2 | 1 |
| PVT | ImageNet-1k | 1 |
| BLOOM（见下方版本问题） | WikiLingua、Wiki-raw | 2 |
| Llama-7B | WikiText-2、WinoGrande | 2 |
| Llama-13B | WikiText-2、WinoGrande | 2 |
| 合计 | | **20** |

方法段另有“八项 GLUE”的表述，与主图标签并不完全对应。BLOOM 在正文写 1.7B，图中及部分长度描述写 1.3B，应在引用时保留这个不一致。最大序列长度：BLOOM 约 2K，Llama-7B/13B 约 4K；BERT 不同任务为 256/384/512；PVT 为 3192。

SOFA 在剪枝后做任务相关 fine-tuning，分别约束 0%、1%、2% 的任务质量损失。原文举例为 SQuAD F1、RTE accuracy。**这些百分比不能统一解读为 PPL 增加百分比，也不是 DAC/体系结构会议规定的容许误差。**v1 没有提供足以逐项复现这 20 项质量差值的完整原始分数和 PPL 计分协议。

它也没有给出可将所有性能图统一解释为 batch=1、固定 prompt/输出长度、带 KV cache 的完整 decode TPOT 协议。图中用了 Llama 并不自动补齐这个协议。

## 4. SOFA 实际采用三种比较

### 4.1 与 A100/TPU 的软件及软硬件比较

- GPU 基线为 A100 上的 PyTorch 实现；在测量边界前后同步。
- 先测 idle，再重复执行工作负载；通过 nvidia-smi 取总功率，动态功率按 total−idle 计算。
- 比较 dense、低复杂度预测 LP、LP+FlashAttention、LP+FlashAttention-2，以及 SOFA 的架构估计。
- 0%/1%/2% 质量损失档下，报告平均加速 **6.1×/7.2×/9.5×**，能效提升 **49.8×/57.6×/71.5×**。
- 在 2% 档，9.5× 是相对其 dense GPU 基线；相对 LP+FA2 GPU，论文报告约 **3.01×**。

这些倍率不等于我们的 Qwen 完整 decode 倍率。其硬件增量消融不能解读为“实际改造 A100 并实测新增电路”。CPU/GPU 的软件栈、计费边界和 idle 处理也应随数字一起引用。

### 4.2 内部机制消融

SOFA 比较传统预测/排序/FA，逐步加入 DLZS、SADS、SU-FA、RASS/tiling，并分开报告：

1. 算术复杂度；
2. Attention 与 QKV+Attention 的计算量；
3. 访存量；
4. 性能与能效；
5. 不同任务质量预算下的取舍。

论文报告 RASS 相对普通动态稀疏减少平均约 23% 访存，结合 SU-FA 与 tiled dataflow 后总降幅约 79%。这些是各自基线下的结果，不应把两个百分比相乘或累加后再算一次收益。

**适合我们借鉴：**同一个数字后端中逐项加入筛选、采样、随机 FFN、共享随机源和访存优化，保持每一项的额外资源与质量配置可追溯。

### 4.3 与八项 ASIC 的归一化比较

Table II 汇集原论文/作者采用的不同实现，再折算部分能效和面积效率；§V-D 另按统一乘法器数量和频率估算 Attention 工作量的时延。**它不是把八个完整 RTL 在同一工艺、同一 Qwen trace、同一 DRAM 上重新综合和运行。**

## 5. SOFA 的跨 ASIC 表到底怎样折算

### 5.1 能效与面积效率

Table II 脚注将标注项目折算到 **28 nm、1.0 V**，按原文符号：

`s = Tech / 28 nm`

`f ∝ 1/s²`

`power(core) ∝ (1/s) × (1.0/Vdd)²`

它引用自己的参考文献 [61]、[65]；**不是明确使用 DeepScaleTool 的流程。**该脚注符号和适用对象较简略，不能据此声称任意工艺的实际最高时钟均服从该关系，更不能直接缩放 DRAM、模拟 p-bit、PHY、封装和整个系统能量。

本文只记录 SOFA 的做法，不把其规则指定为本项目主比较标准。本项目已有的原始工艺面积 ×0.81 规则仍是独立用户口径，不适用于这些外部论文，也不自动作用于功率或时延。

### 5.2 时延：137 GOP、128 个乘法器、1 GHz

SOFA §V-D 选用 **Llama-7B 的 Attention 部分 137 GOP 工作量**，将对手统一到 **128 个乘法器、1 GHz** 后估算。可将其 FACT 示例重写为：

`R_norm = R_report × (128 / N_multiplier) × (1 GHz / f_report)`

`T_est = 137 GOP / R_norm`

FACT 在其示例中为 928 GOP/s、512 个乘法器、500 MHz：

`R_norm = 928 × (128/512) × (1000/500) = 464 GOP/s`

`T_est = 137/464 s = 295.26 ms ≈ 论文所列 296 ms`

137 GOP 和报告吞吐都经过取整，不能要求最后小数严格相等。

**可用之处：**给出某个统一 Attention 工作量下的容量/有效吞吐参考。

**不能支撑的结论：**

- 296 ms 是 FACT 运行完整 Llama-7B 的实测每 token 时间；
- SOFA 的 45 ms 是完整模型 decode TPOT；
- 等乘法器就是等面积、等功耗、等带宽；
- 固定工作量/有效 GOPS 已覆盖不规则访存、同步、布局、控制和质量差异；
- 将随机 AND、计数器与数字 MAC 都归一成“同样 128 个乘法器”即可公平比较。

### 5.3 Table II 对照配置的忠实摘录

**下表均为 SOFA v1 PDF Table II 的转录，不是八篇原论文 PPA 的独立复验。**工艺/频率/面积列是该表列出的配置；Latency 是其归一化 Attention 时间。不要把最后一列与前几列拼成未经说明的原生配置运行结果。

| 工作 | Table II 工艺 | 频率 | 表列面积 mm² | 归一化 Attention latency ms |
|---|---:|---:|---:|---:|
| A³ | 40 nm | 1 GHz | 2.08 | 622 |
| ELSA | 40 nm | 1 GHz | 1.26 | 522 |
| Sanger | 55 nm | 500 MHz | 16.9 | 241 |
| DOTA | 22 nm | 1 GHz | 4.44 | 448 |
| Energon | 45 nm | 1 GHz | 4.20 | 477 |
| DTATrans | 40 nm | 1 GHz | 1.49 | 652 |
| SpAtten | 40 nm | 1 GHz | 1.55 | 382 |
| FACT | 28 nm | 500 MHz | 6.03 | 296 |
| SOFA | 28 nm | 1 GHz | 5.69 | 45 |

特别注意缩小配置：SpAtten 的 1.55 mm² 对应其 **SpAtten1/8** 类比较配置，不是原文完整 SpAtten 的约 18.71 mm²；Energon 的 4.20 mm² 对应 edge 配置，原文 server 为约 8.62 mm²。不能用小版本面积配大版本性能。

此外，Table II 的 comp saving 明确扣除 prediction computation；其 effective GOPS 含跳过计算的收益，并不必然等于实际执行的算术吞吐。不同质量损失、稀疏率和缺失 IO 的条目也不是严格等条件排名。

## 6. SOFA 的仿真依据与 DRAM 边界

### 6.1 电路与架构工具

| 层级 | SOFA 方法段所述证据 | 能支撑什么 / 尚不能推断什么 |
|---|---|---|
| 算法 | PyTorch/Hugging Face、剪枝后 fine-tuning、DSE | 任务相关质量与配置选择；不等于无训练通用替换 |
| 逻辑 PPA | RTL、Synopsys DC、TSMC 28 nm | 逻辑综合估计；方法段没有据此证明完整 P&R/CTS/芯片实测 |
| 时钟 | 报告综合关键路径 <1 ns，据此使用 1 GHz | 有实现依据的目标；不是任意模块默认一拍 |
| 周期 | Verilator 提取各阶段实际周期，再建自研 cycle-level simulator | 模块时序与系统模拟的混合层级；不等于全模型门级仿真 |
| SRAM | CACTI 的功耗、面积及读写带宽 | 宏模型估计；不能替代具体 SRAM 编译器和布线收敛 |
| DRAM | Ramulator 模拟外存行为；IO 能量按引用方法估计 | 有时序后端；此方法段没有明确声明使用 DRAMPower |
| 活动输入 | 方法段未披露完整“真实模型张量→VCD/SAIF→功率分析”链条 | 不能只凭使用 DC 就声称真实激励签核功耗 |

Table III：片上 Token SRAM 192 KB、Weight SRAM 96 KB、Temp SRAM 28 KB，总计 **316 KB**；外存配置写为 **HBM2、16 HBM channels @2 GHz**。核心面积 **5.69 mm²**、核心功率 **949.85 mW**。本专题不将上述通道写法自动换算成某个未给出的持续带宽。

### 6.2 “Core+IO”其实包含外部 DRAM

由 SOFA Table IV：

| 项目 | 功率 | 本文解释 |
|---|---:|---|
| Core | 0.95 W | 含其 Table III 所列片上模块 |
| Memory interface | 0.53 W | 外存接口 |
| DRAM | 1.92 W | 外存 |
| Overall | **3.40 W** | 三项合计 |

DRAM/接口功率按 **59.8 GB/s** 估计。Table II 的 SOFA “IO=2.45 W”在数值上恰好等于 **0.53+1.92 W**，即其 IO 列在这一行合并了接口与 DRAM：

`24423 GOP/s ÷ (0.95+2.45) W ≈ 7183 GOP/J`

所以 **7183 GOPS/W 是该边界下含 DRAM 的 device 能效；25708 GOPS/W 是 core 能效。**不能拿我们的含外存能量与其 0.95 W 核心数字直接比。

可由表中数字进一步推导（不是原文直接列出的器件参数）：

`DRAM: 1.92 W / (59.8×10^9 byte/s×8) ≈ 4.013 pJ/bit`

`interface: 0.53 W / (59.8×10^9×8) ≈ 1.108 pJ/bit`

`DRAM fraction: 1.92/3.40 ≈ 56.47%`

这说明我们采用约 4 pJ/bit 并不因数值本身就比 SOFA 异常保守；仍需逐项对齐读写流量、实际带宽、背景/刷新能量、接口是否另计，以及该参数对应哪种外存。不能直接把这个反推值迁移成另一 LPDDR/HBM 型号的实测参数。

## 7. 八项 ASIC 是否评估 decode，能否与我们比较

### 7.1 场景与范围总表

| 工作 | 核实的 benchmark / 场景 | decode 证据 | 硬件/计时边界与比较建议 |
|---|---|---|---|
| **A³，HPCA 2020** [A3] | MemN2N/bAbI、KV-MemN2N/WikiMovies、BERT-base/SQuAD v1.1 | **不是现代 LLM 的连续生成 decode 基准**；单 query 注意力或 QA 响应不等于完整生成一步 | 主要 Attention 运算；适合候选筛选、近似点积、PV 的局部比较 |
| **ELSA，ISCA 2021** [ELSA] | BERT/RoBERTa/ALBERT-large 的 SQuAD/RACE 等，SASRec/BERT4Rec 推荐 | 本次核实的实验没有我们的 LLM decode 协议 | 主要 Self-Attention；可比低成本相似度预测、精度/候选保留，不直接比整机 J/token |
| **Sanger，MICRO 2021** [SANGER] | BERT，以及 GPT-2/BART 的 GLUE 等推理；包含 SQuAD/CLOTH 长上下文任务 | **未见清楚的 prompt→连续生成 N token 协议**；GPT-2/BART 用于下游推理不能据名称认作 decode 测试 | 稀疏 SDDMM/SpMM、可重构阵列、预处理与 QKV 映射；可参考稀疏实现和质量消融 |
| **DOTA，ASPLOS 2022** [DOTA] | BERT-large/SQuAD、LRA 的图像/文本/检索、GPT-2/WikiText-103，后者描述为 4K 序列 | 作者材料明确讨论 decoder 的顺序 token、GEMV 与带宽限制；**具体 prompt/生成长度、TPOT 协议未核实** | 不应归类为“完全不支持 decode”；也不能把所有长序列结果认作 TPOT。包括完整 Transformer 架构与 Attention/端到端性能分列，值得参考数字对照 |
| **Energon，TCAD 2023** [ENERGON] | BERT-base/SQuAD、GPT-2/WT2、ViT-B/L 的分类；GPT-2 初始 992 token、生成 32 token | **明确有生成阶段测试**，§V-B 写明跟随 SpAtten 的 992+32 方案 | 主要核是 Attention 协处理器；§VI-A 另有 TPU-style+Energon 完整系统，必须分开引用 |
| **DTATrans，TCAD 2023** [DTATRANS] | 动态 token 混合精度、精度补偿 | **NR-本轮未核**：全文评估段未取得，不能确认生成协议 | 可列相关工作；不得仅凭 SOFA 表格或 BERT/GPT-2 摘要描述填成已核 decode 基线 |
| **SpAtten，HPCA 2021** [SPATTEN] | BERT-base/large；GPT-2-small/medium，在 WT2/WT103/PTB/One-Billion Word；初始 992 token、生成 32 token | **明确有生成阶段测试**；Fig.3 说明 KV 拼接/单 query，并分别讨论 summarization/generation | **优先参考**。主核 Attention 与支持 FC/FFN 的 **SpAtten-e2e** 分开；30 benchmark 的平均倍率不等于 GPT-2 decode 单项倍率 |
| **FACT，ISCA 2023** [FACT] | QKV、Attention、FFN 联合优化；具体完整 benchmark 表本轮未取得 | **NR-本轮未核**：不能确认其具体 decode 测试协议，也不能断言没有 | 联合优化范围值得读全文；当前仅作候选对照与 SOFA 转录，不把其面积/时延直接当完整 Qwen decode |

本表中的“未核实”是证据状态，不是对论文做了/没做的最终否定。DOTA 本次用作者学位论文第 5 章核实架构与评估描述；未把它未经核对地当成会议 PDF 的逐字同版副本。

### 7.2 最值得借鉴的两个工作

**SpAtten / SpAtten-e2e。**原文 §V-B 将乘法阵列复用到 FC/FFN，权重以 INT8 或 INT12 存在 DRAM，并指出生成阶段 FC/GEMV 是 memory-bound。Table IV 的 GPT-2-Medium 示例，FC latency 25.75 ms、Attention latency 2.13 ms，FC 占 **92.4%**。这是该表自己的覆盖范围，不能据此给我们补上未核实的 lm_head/采样成本。

它直接说明：降低 Attention 成本后，整机可能转由权重读取与线性层主导。可借鉴其“Attention 专用结果”和“复用计算资源后的端到端结果”分别报告，而不要只引用最大的局部加速比。

**Energon。**主要结果比较 Attention 协处理器；§VI-A 用 SCALE-Sim 模拟 TPU core，并联合 Energon 自研模拟器评估完整系统，其他投影/FC/FFN 仍由 TPU 执行。论文报告平均端到端时延改善约 **1.21×**、吞吐改善约 **1.55×**，两者含义不同。

其内存模型原文明确采用 Ramulator，能量段还写明 DRAMPower；这与 SOFA 方法段只明确写 Ramulator+引用 IO 方法的证据强度不同，不能互相代填。Energon-edge 配 2-channel LPDDR3-1600、25.6 GB/s，server 配 HBM-1.0、256 GB/s。相关 TOPS/时钟/系统边界应随配置引用。

### 7.3 电路/模拟层级的可参考证据

| 工作 | 本次核实的实现/模拟链 | 使用时应保留的限制 |
|---|---|---|
| A³ | Chisel→Verilog、DC/TSMC40nm、自研周期模型；另有缩小 test chip 的功能验证 | 测试芯片缩小到 MemN2N 规模，不证明表中所有模型的性能/功耗均为硅实测；CPU/GPU 能量比较采用 TDP 假设 |
| ELSA | 本专题已核实 workload/Attention 范围；完整实现流程不在本轮重审范围 | 不把 SOFA Table II 的转录误写成已逐项复核的工艺/DRAM模型 |
| Sanger | Chisel→Verilog、DC/UMC55nm、Innovus 布局布线；cycle-accurate 模型，假定128 GB/s HBM | 500 MHz 有相应实现流程依据；未因“用了 Innovus”就补称完整 CTS/活动功耗签核 |
| DOTA | RTL、DC/TSMC22nm、CACTI、自研模拟器；作者材料写明同 ELSA 对照时匹配数制/资源/工艺并重综合 | 不能用“自研模拟器”推出只有算量估计；具体完整请求/KV协议仍需会议原文进一步核对 |
| Energon | Chisel→Verilog、DC/FreePDK45nm、CACTI、Verilator→周期模型、Ramulator/DRAMPower；完整系统联合 SCALE-Sim | Attention 核与 TPU+协处理器整机配置和收益分开 |
| DTATrans | NR-本轮未核 | 不根据 SOFA 引用表补造工具链或 decode 测试 |
| SpAtten | SpinalHDL→RTL、Verilator、Genus/TSMC40nm、CACTI、Ramulator HBM2；浮点非线性部分还引用外部 FMA/FPU 成本 | 属于混合粒度估算，不能声称所有浮点模块都在同一40nm库完整实现 |
| FACT | NR-本轮未核；只记录 SOFA 转录配置和作者题名范围 | 未核实的综合/P&R/DRAM时序/完整生成协议保留空白 |

SpAtten Table I 的完整配置为 HBM2、16×128-bit channels@2 GHz，每 channel 标为32 GB/s，即表述峰值合计512 GB/s。该配置与 SOFA 表中缩小的1/8对照不能混用。同理，Energon 的异构系统吞吐可以利用多输入交错，不能等同单请求 TPOT。

## 8. 我们应如何采用这些比较方式

### 8.1 三层结果，而非把八篇原始数字放在一起排名

| 层次 | 推荐对照 | 需要对齐的边界 | 主要指标 |
|---|---|---|---|
| **整机主表** | 本项目优化数字基线、p-bit FFN-only、Attention-only、联合方案 | 同模型/revision、质量协议、PVT、近等面积、SRAM/外存、调度优化机会、完整模块覆盖 | decode-step latency、连续生成TPOT、mJ/token、面积、DRAM占比 |
| **外部架构重建/映射** | 优先 SpAtten-e2e；Energon 完整系统；DOTA/FACT 待补足协议 | 在同一个Qwen负载/存储预算上重建；标明 reproduced/adapted，区别论文原值 | 同质量和资源条件下的系统收益、带宽/面积敏感性 |
| **Attention机制表** | SpAtten、Energon、Sanger、A³、ELSA；SOFA用于多query场景 | Q/K/V形状、MHA/GQA、候选与采样预算、精度、SRAM、物理burst、控制成本 | 核心latency/energy、K/V字节、筛选成本、误差/模型质量 |
| **跨论文背景表** | 八篇及SOFA的原始/归一化数值 | 清楚注明原值、来源、归一规则、局部/系统及缺项 | 工艺、频率、面积、峰值/有效吞吐；不直接得出Qwen TPOT胜负 |

我们的数字对照不能默认将所有浮点/非线性操作收费为“一拍”，也不能默认物化整张概率矩阵。应使用已验证流水/II、在线融合归一化、GQA共享与可实现调度，同时为随机源、编码、计数归约和不规则读取收费。

### 8.2 生成指标的最低记录项

1. **阶段：**encoder、prefill、decode、speculative verification分别标注；prefill不计入的结果不能叫完整请求时延。
2. **负载：**准确模型/后训练属性、B、prompt长度、计时起点KV长度、生成token数、EOS规则、head/KV-head数量、精度。
3. **覆盖：**QKV/O、RoPE、KV追加、QK/Softmax/PV、RMSNorm/残差、FFN、lm_head、选token是否计入。
4. **存储：**SRAM容量/端口、权重驻留、外存型号/通道/持续带宽、预取/重叠及背景/PHY成本。
5. **质量：**同一套配置对应完整模型PPL/任务指标；各seed；不把已有其他采样数/编码的PPL移植过来。
6. **证据：**功能、综合、STA、功率分析、后布局、宏模型、周期/事件模型、硅实测分列；未知项不能填0。

对固定 B 个同步请求、每个生成 G 个token：

`平均每步时间 = T_decode / G`

`总输出吞吐 = B×G / T_decode`

`全批次每输出token摊销时间 = T_decode/(B×G)`

第三项不是单个请求的 TPOT。若使用用户可见的首末token定义，应明确以 `(t_last−t_first)/(G−1)` 计间隔；模拟器的固定上下文单步则命名为“decode-step latency at L”，不能直接称完整生成实测 TPOT。

### 8.3 建议优先做的图表

- 一张对照配置表：数制、PVT、频率、面积、SRAM、外存、B/L/G及覆盖。
- 一张质量—成本曲线：采样数/筛选预算对应完整PPL、时间、片上与含外存能量。
- 一张联合消融图：优化数字→筛选→概率Attention→随机FFN→共享随机源/调度；每一步含新增开销。
- 一张流量/瓶颈图：权重/K/V/中间结果的物理字节与等待，区分逻辑裁剪率和真正DRAM节省。
- prefill与decode分别报告；SOFA类多query复用收益不外推到B1单query。

上述是研究建议，本轮没有启动这些实验。

## 9. 目前还缺哪些原文证据

| 待补项 | 为什么重要 | 补齐后才能作出的判断 |
|---|---|---|
| FACT 完整正文及评估表 | 目前不能确认具体模型/任务、生成协议、完整成本和DRAM边界 | 是否适合作为完整decode重建对照，而非仅引用SOFA表值 |
| DTATrans 完整正文 | 动态token精度不自动意味着验证过缓存decode | 原始benchmark、prompt/G/B、性能范围与工具链 |
| DOTA 会议版评估/decoder协议细节 | 作者材料能证明支持decoder，但4K LM评估不自动定义TPOT | 报告的LM时延到底覆盖多少生成步/哪些算子 |
| SOFA 各项原始质量分数与计分协议 | 0/1/2% loss跨任务不能直接换算PPL | 严格同质量预算比较 |
| 各对手的完整系统成本/缺失IO | SOFA表中部分IO为“-”，而面积和性能还可能来自缩小版本 | 含DRAM/接口的公平能量或面积效率比较 |

本文件是可更新的证据索引。未核实项后续拿到原文再补，不把综述摘录、模型名称或“end-to-end”字样替代实验协议。

## 10. 原始来源入口

- **[SOFA]** Huizheng Wang et al., *SOFA: A Compute-Memory Optimized Sparsity Accelerator via Cross-Stage Coordinated Tiling*, arXiv:2407.10416v1；后续会议为 MICRO 2024，但本文固定 v1。[PDF](https://arxiv.org/pdf/2407.10416v1) / [HTML](https://arxiv.org/html/2407.10416v1)。主要位置：§I、§V-A–D、Fig.18–21、Table II–IV。
- **[A3]** Tae Jun Ham et al., *A³: Accelerating Attention Mechanisms in Neural Networks with Approximation*, HPCA 2020。[作者原文](https://arxiv.org/pdf/2002.10941)。主要位置：§VI，workload/性能/测试芯片。
- **[ELSA]** Tae Jun Ham et al., *ELSA: Hardware-Software Co-design for Efficient, Lightweight Self-Attention Mechanism in Neural Networks*, ISCA 2021。[作者PDF](https://seonghoonseo.github.io/files/pdf/research/2021-isca-elsa.pdf)。主要位置：§V-A及Fig.10/11。
- **[SANGER]** Liqiang Lu et al., *Sanger: A Co-Design Framework for Enabling Sparse Attention using Reconfigurable Architecture*, MICRO 2021。[作者PDF](https://liqianglu-zju.github.io/files/conference/2021/MICRO_2021_Sanger.pdf)。主要位置：§6.2、§7.1–7.2、Table2、Fig.8。
- **[DOTA]** Zheng Qu et al., *DOTA: Detect and Omit Weak Attentions for Scalable Transformer Acceleration*, ASPLOS 2022。[会议原文入口](https://par.nsf.gov/servlets/purl/10357543) / [DOI](https://doi.org/10.1145/3503222.3507738)。本轮全文入口超时，架构/评估细节另核自[作者学位论文第5章](https://escholarship.org/content/qt0jp411vn/qt0jp411vn_noSplash_5eafb43a40df2162459837d4a907d562.pdf)，重点§5.1.4、§5.2.1；不是声称两版逐字一致。
- **[ENERGON]** Zhe Zhou et al., *Energon: Toward(s) Efficient Acceleration of Transformers Using Dynamic Sparse Attention*, TCAD 2023。[作者预印本](https://arxiv.org/pdf/2110.09310) / [DOI](https://doi.org/10.1109/TCAD.2022.3170848)。主要位置：§V-A/B、Table I/III–V、§VI-A。
- **[DTATRANS]** Tao Yang et al., *DTATrans: Leveraging Dynamic Token-Based Quantization With Accuracy Compensation Mechanism for Efficient Transformer Architecture*, TCAD42(2),509–520,2023（在线2022）。[作者机构记录](https://faculty.sjtu.edu.cn/hezhezhi/en/lwcg/519421/content/216015.htm) / [DOI](https://doi.org/10.1109/TCAD.2022.3181541)。本轮全文评估段未取得。
- **[SPATTEN]** Hanrui Wang et al., *SpAtten: Efficient Sparse Attention Architecture with Cascade Token and Head Pruning*, HPCA 2021。[作者原文](https://arxiv.org/pdf/2012.09852) / [官方代码](https://github.com/mit-han-lab/spatten)。主要位置：Fig.3、§V-A/B、Table I–IV、SpAtten-e2e。
- **[FACT]** Yubin Qin et al., *FACT: FFN-Attention Co-optimized Transformer Architecture with Eager Correlation Prediction*, ISCA2023。[作者目录](https://yubin-qin.github.io/publications/) / [DOI](https://doi.org/10.1145/3579371.3589057)。本轮ACM全文访问受限；未用非原文综述填补decode结论。

版本说明：除SOFA用户PDF外，其余在线原文未在本任务归档完整字节；链接/段落反映2026-11-06阅读状态，不宣称具有同等强度的本地SHA固定版本。既有 benchmark 总清单的37项原始记录保持其原有时间与来源边界。
