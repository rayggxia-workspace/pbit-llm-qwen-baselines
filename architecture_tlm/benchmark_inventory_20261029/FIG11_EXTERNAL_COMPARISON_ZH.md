# Fig.11 外部工作对比与归一化方案

2026-11-15。本文审计与本稿接近的整机 decode、异构推理和局部算子工作，优先使用作者论文、会议终稿及会议资料。`NR` 表示已核对的原始资料中未找到该口径。吞吐倒数、流量下界和重计价均标为计算值。芯片实测、布局后 PPA、宏校准后的系统仿真和 GPU 实测在表中分别注明。

**正文建议**。Fig.11 保留当前四方案的共同平台对照。旁边放一张简表给代表性外部工作实报值、条件和证据范围。额外做一组共同任务重放，优先挑选同模型的 EdgeCIM。加一行同节点的 SoulMate 硅参考，按原文注明带外存时延和片上能量的边界。CELLA、RCW-CIM 作为额外参考，取得详情后再考虑重放。SOFA、Sanger 等放到 Attention 子图或局部对照表。外部结果保留其原生工作点，定量加速结论来自同口径实验。

## 1. 整机、近整机与平台参考

| 工作与证据 | 实际覆盖和工作量 | 工艺、频率和存储 | 实报速度、能量、面积 | Fig.11 怎么用 |
|---|---|---|---|---|
| **本稿 Fig.11**，TLM，片上原语/宏计价 | Qwen3-4B、Llama-3.2-3B-Instruct、DeepSeek-LLM-7B-Chat；batch 1，已缓存 2,048 token。单步从 token ID 查表到全词表 LM head，计入流式 greedy argmax 时序代理。 | 28 nm TT、0.9 V、25 °C、250 MHz；832 KiB SRAM；LPDDR5-derived 8533，峰值 136.4606 GB/s；16 KiB DMA；外存 `4 pJ/bit` 事务估算。 | P-bit 为 51.133/43.929/98.985 ms/token，片上 15.268/12.414/26.527 mJ/token，含外存估算为 188.432/151.771/317.782 mJ/token；计价片上面积 6.480 mm²。 | 片上面积与能量均限已计价模块，详见 §2.1 和封存报告。 [封存报告](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/eaf1ddcc56742c4c9f51899ecefb120574aeb5eb/architecture_tlm/process_28nm/results_20261111/REPORT_ZH.md) |
| **EdgeCIM**，2026 预印本 v2，解析模拟器、宏校准与局部 RTL 验证 | Qwen3-4B 和 Llama 3.2-3B 均有结果。batch 1，128 输入 token、128 输出 token，单报 decode。覆盖 QKV 投影、Attention、输出投影和 FFN。全词表 LM head 和模拟器所用 checkpoint revision 未明确。INT4/INT8，按模型和精度搜索配置。 | 65 nm HSPICE 计算单元、CACTI 6.0 缓冲。16 通道 LPDDR5X，约 273 GB/s 峰值。固定配置另测 204.8/136.5/68.3 GB/s。系统名义时钟 NR。 | Table III：Llama 3.2-3B INT4 **139.3 output tok/s**，B1 倒数约 **7.18 ms/token**。Qwen3-4B 见 Fig.12。面积 18.4–103.6 mm² 为各 DSE 组合范围，44.66 mm² 为另一个共用配置，均排除外存控制器。Fig.13 的五模型范围分两种能源边界，片上 54.79–181.05 token/J、含外存 10.34–37.67 token/J。 | **优先外部系统对照**。约 2× 峰值带宽、更窄精度、短缓存以及不同面积约束都需披露。取同一模型、同一配置的原始三项，别把 139.3 tok/s 配上别的配置面积和能耗。 [§IV-A / §V，Table III、Fig.12–13](https://arxiv.org/html/2604.11512v2#S5) |
| **CELLA**，VLSI 2025，28 nm 数字 CIM 芯片 | 区分 prefill 和 decode，prefill 采用 MAC 模式，decode 为权重索引及动态 KV 筛选。具体输出序列、batch、LM head 和系统能量边界待原表核查。 | 28 nm，当前可核实会议页未给这两个数字对应的时钟、外部 DRAM 通道和带宽。 | 标题公布 **1.78 ms prefill 响应，31.32 tok/s decode**，后者吞吐倒数 31.93 ms/output token。工作点面积与整句总 J/token 暂留 NR。 | **优先的同节点硅参考**。收到原稿后先核每个工作点的模型、上下文、计量边界、存储和面积。 [作者机构论文页](https://computer-arch-dev.hkust.edu.hk/publication/vlsi25-cella/) · [会议 C17-3](https://www.vlsisymposium.org/wp-content/uploads/VLSI2025_Advanceprogram0606-3.pdf) |
| **SoulMate**，ISSCC 2026，实测 SoC | Llama3.2-1B（1.15B）、上下文约 1,024，MXFP6/MXFP4；分别报 prefill TTFT 与 decode TPOT，LM head NR。 | Samsung 28 nm FDS，25–250 MHz、0.58–0.82 V、约 3.9 MB SRAM。DDR3 接口，带宽 NR。 | Fig.31.5.6–7：**60.8 ms TPOT（含外存访问）**，**27.1 μJ/output token（排除外存访问）**；20.25 mm² 整颗 die，含 RISC-V 与接口。 | 同节点、同最高频率的原生硅参考。表里分别标注两个指标的测量边界，比较面积时注明整 die 与本稿计价片上区域的差异。 [作者原文，Fig.31.5.6–7](https://ssl.kaist.ac.kr/SoulMate/ISSCC2026_31.5_SoulMate.pdf) · [ISSCC 会议信息](https://static1.squarespace.com/static/6130ef779c7a2574bd4b8888/t/69a9c050c62f5720adbc05eb/1772732500368/ISSCC2026PressKit.pdf) |
| **RCW-CIM**，2026 预印本，22 nm CIM 硅实现，系统测试边界未完整公开 | Llama2-7B，INT4 权重、INT8 activation、FP16 非线性；报 prefill 和 decode，4.2 ms 与 26.87 tok/s 的 batch、实际 cache 长度、LM head NR。 | TSMC 22 nm、0.8 V、100 MHz、256 KB CIM macro；双 DDR5-6400。若两条有效数据宽度各 64 位，推导峰值 102.4 GB/s，原文未在该点列物理数据位宽和实际流量。 | **26.87 tok/s**（吞吐倒数 **37.22 ms/output token**）、4.2 ms prefill。42.3 TOPS/W 为核算子效率；完整 J/token 和整芯片总面积 NR。 | 优先的近规模低批量参考。只列原生速度和已报告配置，不能用 TOPS/W 补出 J/token。 [§III、Table II](https://arxiv.org/html/2604.27384v1#S3) |
| **Kelle**，MICRO 2025，系统仿真、逻辑综合、存储估计 | 端到端评估，Fig.16 区分 prefill 与 decode。Llama 3.2-3B、Llama2-7B 等用于 §8 的子比较。主任务 batch 16，输入 128/512/1,024/512，输出 512/2,048/5,120/8,192；另有 batch 扫描。LM head 未明确。 | 45 nm NanGate 逻辑 1 GHz，SRAM/eDRAM 用 65 nm Destiny；2 MB 权重 SRAM + 4 MB KV eDRAM + 256 KB activation eDRAM；16 GB LPDDR4，64 GB/s，CACTI 7。 | 片上 9.5 mm²、DRAM 面积模型 16 mm²，设置列片上 6.52 W 与 DRAM 11.74 W。Fig.13 相对同面积 Original+SRAM 报 3.94× 性能、4.46× 能效。未找到对应 B1/2K 的原生绝对 TPOT 与 J/token。 | 可列原生资源和相对值，或复现其 KV 策略后放进同一架构后端；整篇平均与单步 TLM 各有工作量。 [§8、Fig.13–16](https://arxiv.org/html/2510.16040v1#S8) |
| **OPAL**，DAC 2024，RTL 综合、存储估计 | Llama2-70B 的生成时间，混合低位权重与激活，硬件覆盖线性和 Attention 等计算；batch、上下文、LM head NR。 | 65 nm Synopsys DC，SRAM 用 CACTI；512 KB global buffer + 2 KB softmax buffer；外部 DRAM 型号、带宽和计价，以及核时钟 NR。 | §5.2 低精度例 **1.98 s/生成 token**。Table 3 的 W4A4/7 为**单个核**，0.929 mm²、335.85 mW；Fig.8 的能量柱由 core、存储访问、存储漏电组成，冷暖权重及外部 DRAM 能量边界未充分披露。 | DAC 同类架构叙述值得引用。能耗和面积仅按原文范围报告。 [§5.2、Table 3](https://arxiv.org/html/2409.05902v3#S5.SS2) · [Fig.8](https://arxiv.org/pdf/2409.05902v3#page=6) |
| **HSA**，ISLPED 2025，逻辑后布局、外存估算 | RetNet-1.3B，W4A8，长输入/短输出 750/50 与短输入/长输出 50/750。模型与 Attention 型 Transformer 不同。 | TSMC 28 nm、500 MHz；DDR5 51.2 GB/s，32 pJ/byte（4 pJ/bit）；0.636 mm²、0.108 W 为芯片范围。 | Table I 138.3/37.6 tok/s 的分子是输入+输出 token。Table II 另报 **24.06 mJ/输出 token** decode 能量（含外部访问）。 | **最适合引用的共同平台比较先例**。Table II 用统一工作量和外存条件重估对照设计，分别写原始和估计假设。 [§V、Table I–II](https://arxiv.org/html/2507.09010v1#S5) |
| **EdgeMM**，DAC 2025，后布局逻辑 + RTL/自建系统模拟 | SPHINX-Tiny 多模态模型，TinyLlama 1.1B 级解码骨干加视觉编码。Fig.11 有整体及各阶段，按平均输入/输出长度。batch、LM head、该结果的逐任务序列 NR。 | TSMC 22 nm、1 GHz；自家外存带宽须用自己的配置项核对，Table II 的 **336 GB/s GDDR6 是 RTX 3060 Laptop 对照**。 | 最高报 138 tok/s；112 mW 来自后布局报告。论文不同段落给不同 token/J 数字且边界难核，用作报告原生吞吐和配置，暂不转成可排名的 J/token。 | DAC 的不同阶段和实报平台对照排版值得参考，独列多模态。 [§V、Fig.10–13、Table II](https://arxiv.org/html/2505.10782v1#S5) |
| **CXL-PNM**，HPCA 2024，近存系统 | 单模块 Fig.10 为 OPT-13B、输入 64 / 输出 1,024，含 prefill 和生成。Fig.11 为 OPT-66B 多设备服务，LM head 计费 NR。 | Table I/II：目标 7 nm、1 GHz、1.0 V，周期模型经 FPGA 校验；63 MB 寄存器文件、1 MB DMA；单模块 LPDDR5X **512 GB、1.1 TB/s**，8 组各约 136 GB/s。该速率在模块内部，CXL 主机侧链路另计。 | 单模块 **42.68 tok/s**、平均运行功率 77.1 W、约 0.55 output tok/J（约 **1.82 J/token**），面积 NR。多设备相对 GPU 服务结果另列。 | 原生近存平台参考。短输入加生成的窗口和单步 decode 有差异，8 设备的聚合吞吐也单列。 [作者机构摘要](https://experts.illinois.edu/en/publications/an-lpddr-based-cxl-pnm-platform-for-tco-efficient-inference-of-tr/) · [原始论文全文，§VII–VIII](https://github.com/Clin0212/PIM-PNM-LLM-Inference/blob/main/An_LPDDR-based_CXL-PNM_Platform_for_TCO-efficient_Inference_of_Transformer-based_Large_Language_Models.pdf) |
| **RS-LPU**，ISSCC/JSSC 2026，55 nm ReRAM-on-logic 原型 | Llama2-7B 等，权重压缩、堆叠与 adaptive parallel speculative decoding。分母应是被接受的最终输出 token。 | 55 nm 逻辑与堆叠 ReRAM。会议公布 56 mm² 加速器 die、22 mm² ReRAM die；具体运行点的 die 数、时钟、内外带宽按原表逐点核对。 | 会议资料列 Llama2-7B **17.82 tok/s、123.41 mJ/token** 的一个工作点。论文标题 **14.08–135.69 tok/s** 是跨工作点范围。 | 另一类存储系统与推测解码的硅证据，按原生边界独立一行。 [ISSCC Session 31.1](https://static1.squarespace.com/static/6130ef779c7a2574bd4b8888/t/69a9c050c62f5720adbc05eb/1772732500368/ISSCC2026PressKit.pdf) · [JSSC 论文](https://doi.org/10.1109/JSSC.2026.3718555) |
| **嵌入式 FPGA DDR 极限**，实测部署 | Zynq KV260 跑 Llama2-7B 低位权重 decode。 | FPGA，不折算成 ASIC mm²；4 GB、64 位、2400 MT/s DDR4，理论 19.2 GB/s。 | 约 5 output tok/s，作者报约 85% 带宽理论上限。论文可作为不同 DDR 接口下带宽诊断先例。 | 原生端侧参照，资源列使用 LUT/BRAM/DSP。 [作者论文](https://arxiv.org/abs/2502.10659) |

## 2. 局部、prefill 和外部工作范围核对

| 工作 | 做了哪段，工艺和外存 | 实报指标与可比范围 |
|---|---|---|
| **SOFA**，MICRO 2024 | 动态稀疏 Attention 覆盖 QKV 生成与 Attention 流程优化。§V-D 比较的是 LLaMA-7B 的 137 GOP Attention 问题，统一 128 乘法器、1 GHz。TSMC 28 nm；DC、Verilator、CACTI、Ramulator；片上 316 KB，外存 16 通道 HBM2。59.8 GB/s 为功耗估算所用流量点。 | **45 ms** 是该 Attention 工作量。Tables III/IV 片上 5.69 mm²、0.95 W，另有接口 0.53 W、DRAM 1.92 W。用 Fig.5 的匹配 Attention 层或同 137 GOP 工作量对照。采用固定 v1 PDF，不混用其他版本表格。 [v1 PDF，§V、Tables II–IV](https://arxiv.org/pdf/2407.10416v1) |
| **Sanger**，MICRO 2021 | BERT、GPT-2、BART 的稀疏 Attention。UMC 55 nm **500 MHz**，后布局，512 KB Q/K/V/output SRAM，HBM 128 GB/s 假设。 | 16.9 mm²、2.76 W、529 GOP/s 有效 Attention 吞吐。原版频率与后续论文的共同频率重估分开。 [§7、Tables 2/4](https://liqianglu-zju.github.io/files/conference/2021/MICRO_2021_Sanger.pdf#page=9) |
| **SpAtten**，HPCA 2021 | 40 nm 片上、392 KB SRAM；普通版 HBM2 512 GB/s，另有 1/8 带宽 64 GB/s 变体。注意原生 Attention 与 SpAtten-e2e 不同，后者复用硬件做 FC/FFN；GPT-2-Medium 初始 992 token、生成 32。 | Table II 18.71 mm²（无外存）、8.30 W（含外存）。Table IV e2e 25.75 ms FC + 2.13 ms Attention 为指定工作量的两段，二者除以 32 约 0.871 ms/输出 token，仍需标注只计两段。FC FLOP 量与 decoder block 规模吻合，词表头未在原文该表明确计入。 [§VI、Tables II/IV](https://arxiv.org/pdf/2012.09852#page=9) |
| **LeOPArd**，ISCA 2022 | QK、Softmax、PV 的 Softmax Attention，不覆盖完整 LLM FFN。65 nm TSMC GP、后布局、800 MHz，HP 单 tile K 48 KB、V 64 KB；外部 DRAM 带宽 NR。 | Table 2 有 3.47 mm²、574.1 GOP/s、519.3 GOP/J，均为 HP 单 tile。65→40 nm 给 Dennard 和 Stillmaker–Baas 两套估计，同时配齐缓冲并有不同位宽版本。 [§5.1、Table 2](https://par.nsf.gov/servlets/purl/10394500) |
| **DOTA**，ASPLOS 2022 | 区分单独 Attention 与整个 Transformer，GPT-2/WikiText-103 评估含长度 4K，用逐 token GEMV 的架构支持和可匹配 TPOT 的完整工作量分别看。22 nm/1 GHz，DC、CACTI 与自建仿真；外存带宽 NR。 | 2.746 mm² 逻辑 + 1.690 mm²/2.5 MB SRAM；逻辑约 3.02 W。未披露与本稿匹配的输出 token、缓存长度和词表头计费。 [§4.4、§5.1、Table 2、Fig.12](https://par.nsf.gov/servlets/purl/10357543) |
| **A³ / ELSA / Energon / DTATrans / FACT** | SOFA 的 Attention 相关组。A³、ELSA 为 40 nm/1 GHz；Energon 仿真为 45 nm/1 GHz，边缘 LPDDR3 25.6 GB/s、服务器 HBM1 256 GB/s。DTATrans 40 nm/1 GHz，有整模型推理与 Attention-only 两组。FACT 优化 QKV/Attention/FFN，公开结果的匹配 decode 边界待核。 | A³ 大参考设计 2.082 mm² 与缩小实测核心不同。ELSA 单核约 1.255 mm²，含片上 K/V/Q/output RAM 为 2.147 mm²；Energon edge 4.20 mm²、2.7 W，server 8.62 mm²、10.6 W，功率含接口和内存。DTATrans/FACT 的 SOFA 归一值需标明 SOFA 137 GOP Attention 工作量。 [A³ Table I](https://users.cs.duke.edu/~lkw34/papers/ham-a3-hpca2020.pdf) · [ELSA Table I](https://taejunham.github.io/data/elsa_isca21.pdf) · [Energon Tables III–V](https://arxiv.org/pdf/2110.09310#page=9) · [DTATrans](https://doi.org/10.1109/TCAD.2022.3181541) · [FACT](https://doi.org/10.1145/3579371.3589057) |
| **FusionCIM**，2026 预印本 | LLaMA3-8B 的长序列 Attention；28 nm/400 MHz，CIM 模型、CACTI、DC/PrimeTime。IP CIM 64 KB、OP CIM 128 KB 每宏，外存实测 GB/s NR。 | 4K 序列时较其 DCIM 基线 1.98× 速度、约 3.85× 能量优势，29.4 TOPS/W、2.03 TOPS/mm² 对应论文 Attention 系统边界。适用于匹配局部路径。 [§IV、Tables I/II、Fig.6–9](https://arxiv.org/html/2604.25317v1#S4) |
| **AccelCIM**，DAC 2026 | 28 nm CIM 阵列生成与数据流建模，含仿真、综合与阵列布局；§4.4 给 Qwen3-0.6B 与 Llama3-8B 的 LLM 案例。 | Table 3 中 216.552/886.272 ms 属于 TTFT/prefill 结果，面积是相应阵列范围。可参考宏面积建模和 prefill，Fig.11 decode 分母不适用。 [§4.4、Table 3](https://arxiv.org/html/2604.17692#S4.SS4) |
| **3D-CIMlet**，DAC 2025 | 芯粒仿真：40 nm ReRAM/eDRAM 等组合存参数及动态激活。GPT-2 128/1,024 token，还有 BERT-base 和 DeiT。 | Fig.4 用 latency/energy per inference，Fig.5 用 NoC/NoP，重点是芯粒配置及通信；该图未给与本稿同一 token 和外存服务边界的三元组。 [作者终稿，§III–IV Fig.4–5](https://engineering.purdue.edu/NanoX/assets/pdf/2025_DAC_3D-CIMlet_AAM.pdf) |
| **Edge-LLM / P-DAC / OutlierCIM / Selective KV Accessing**，DAC | Edge-LLM 的系统能效关注 LLM 调优，P-DAC 以光学 DAC 替换、BERT/DeiT 为例。OutlierCIM 与 Selective KV Accessing 是相关量化/筛选设计，公开入口当前不足以审核完整批量、DRAM 与绝对整机三元组。 | 用作方法和近年 DAC 背景。需要补两篇原文的 setup、scope、PPA 表再入定量表。 [Edge-LLM §5](https://www.haoranyou.com/publications/pdf/2024DAC_EdgeLLM.pdf) · [P-DAC 原文](https://oscarlab2022.github.io/paper/dac25_pdac.pdf) · [OutlierCIM](https://doi.org/10.1109/DAC63849.2025.11132578) · [Selective KV Accessing](https://doi.org/10.1109/DAC63849.2025.11133377) |
| **S²ANTA / SANTA++**，GPU 软件评估 | S²ANTA Table 3：Llama 8B、RTX 6000 Ada，batch 6，30k 输入，2,048 输出/请求，prefill 保持稠密且单计。SANTA++ Table 5：RTX 5090 Laptop，Qwen2.5-7B-Instruct 第 14 层 Attention，32,768 缓存，batch 1。 | S²ANTA decode 80.97/82.36 s/batch，相当于 **6.589/6.702 ms/aggregate output token**，固定同步 batch 的每请求平均生成间隔约 **39.54/40.21 ms**。SANTA++ 107.33→63.52 μs 是局部 attention 算子。GPU 软件无可比 ASIC 面积。 [S²ANTA Table 3](https://arxiv.org/html/2605.01910#S3.SS5) · [SANTA++ Table 5](https://arxiv.org/html/2609.35629#S4) |

### 2.1 逐项核对首尾边界

下表审计引用的**速度点**实际能确认覆盖哪些阶段。`计入` 表示计时或配套实现可查，`图示` 表示在模型/系统流程中出现而计时分账未单列，`NR` 表示资料未披露。能量与面积各用独立的范围标记，即使与时延来自同一张表。

| 工作与时间点 | Token ID → embedding 查表 | Decoder blocks | 末层归一化 | LM head（词表投影） | Token 选择 / host | Prefill 与运行窗口 |
|---|---|---|---|---|---|---|
| **本稿 Fig.11** | 计入。每步读取一行 BF16 embedding | 计入。全部层，含 QKV、Attention、`W_O`、FFN、残差、层内 norm 及 KV 操作 | 计入。独立 `final_norm` | 计入。全词表 BF16 GEMV 时序和读权重 | `lm_head` 内计流式 greedy argmax 的时序代理和比较次数，无逐 token 的数值生成或 host 输出计时。单独 argmax PPA 未拆出 | 每个点是 B1、2K 已有 KV 的一次模型步。另有 prefill 估算，图中仅使用 decode 运行点。 [全模型执行与审计](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/eaf1ddcc56742c4c9f51899ecefb120574aeb5eb/architecture_tlm/process_28nm/cross_models_20261110/run.py) · [流式选择时序](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/eaf1ddcc56742c4c9f51899ecefb120574aeb5eb/architecture_tlm/sram1216_20261106/250MHz/vendor_attention/ordinary_pool.py#L99-L110) |
| **EdgeCIM v2** 139.3 tok/s | 背景介绍提到 embedding。模拟路径是否真正查表 NR | 计入。投影、Attention、`W^o`、FFN，含层内辅助算子 | NR。计入层内 normalization | NR。§III-C.3 的 `W^o` 是 Attention 输出投影，随后进入 FFN | NR。Jetson 的流式输出实测和 EdgeCIM 的解析仿真分开 | 128 输入 token 建立起始 KV，仅计后续 decode。 [§III-C.3–4、§V](https://arxiv.org/html/2604.11512v2#S3.SS3.SSS3) |
| **OPAL** 1.98 s/token | NR | 硬件流程明确给单个重复 decoder block，包括 Attention 与 FFN | NR。图示的是块内 layer normalization | NR | NR | §5.2 引用生成一个 token 的估计，未分列 prefill。 [§4.1 Fig.5](https://arxiv.org/html/2409.05902v3#S4.SS1) · [§5.2 Fig.8](https://arxiv.org/html/2409.05902v3#S5.SS2) |
| **Kelle** Fig.13/16 | NR | 系统评估覆盖预填和生成主流程 | NR | NR | NR | Fig.13 是整请求相对结果。Fig.16(b) 分列 P/D 能量，没有匹配 B1 的绝对时间。 [§8.1、8.3.5](https://arxiv.org/html/2510.16040v1#S8.SS1) |
| **CELLA / RCW-CIM** 标题/主表 | NR | CELLA 说明权重 MAC、KV 选择；RCW-CIM 说明权重更新和块内非线性 | NR。RCW-CIM 说明 grouped RMSNorm，未指明模型最后一次 norm | NR | NR | 两者分别给 prefill 与 decode；这些点的细分时间缺失。 [CELLA 作者机构摘要](https://researchportal.hkust.edu.hk/en/publications/cella-a-28nm-compute-memory-co-optimized-real-time-digital-cim-ba/) · [RCW-CIM §II-D、III](https://arxiv.org/html/2604.27384v1#S3) |
| **SoulMate** 60.8 ms TPOT | NR。微调相似度图中的 embedding 属于另一条路径 | 流程图有 Transformer Decoder、Attention、KV 管理 | NR | NR | 图示输出序列及片上 RISC-V I/O 管理，未分账 host 和 token 选择 | TPOT 含 DDR3 访问，27.1 μJ/token 的 decode 能量排除外存访问。 [Fig.31.5.1–7](https://ssl.kaist.ac.kr/SoulMate/ISSCC2026_31.5_SoulMate.pdf#page=3) |
| **HSA** Table I/II；**EdgeMM** Fig.11/Table II | NR。EdgeMM 的图像 embedding/投影与文本 token 查表分开 | 两者覆盖自回归骨干，HSA 为 RetNet，EdgeMM 为多模态 decoder + 视觉路径 | NR。HSA 有层内 RMSNorm/RoPE | NR | NR | HSA Table I 输入和输出均计；Table II 另有 decode 能量。EdgeMM 同时报阶段和整体。 [HSA §IV–V](https://arxiv.org/html/2507.09010v1#S5) · [EdgeMM §V](https://arxiv.org/html/2505.10782v1#S5) |
| **CXL-PNM** Fig.10 | 图示 | 图示。计时覆盖 sum/prefill 与 gen | NR | 图示，两阶段都画出 LM Head | 图示输出 token 及供 host 用的通知/API，计时/能量中的 CPU 部分 NR | Fig.10 合计 prefill 与生成。77.1 W 的表述是 CXL-PNM device 范围。 [原论文 §II-B Fig.1、§VI–VIII Fig.10](https://github.com/Clin0212/PIM-PNM-LLM-Inference/blob/main/An_LPDDR-based_CXL-PNM_Platform_for_TCO-efficient_Inference_of_Transformer-based_Large_Language_Models.pdf) |
| **S²ANTA** Table 3，GPU 完整生成路径 | 配套代码中计入 | 配套代码中计入 | 配套代码中计入 | 配套代码中计入 | 配套代码的 decode 计时中有逐步 `argmax` 与生成循环；最终文本解码在计时外。表未给功耗或面积 | 稠密 prefill 单计，首个输出用 prompt 末位置 logits。公开实现中 `N` 次选 token 对应 `N−1` 次后续逐 token forward。 [论文 §3.5](https://arxiv.org/html/2605.01910#S3.SS5) · [模型前向](https://github.com/OPUSLab/SANTA/blob/main/tutorial_code/runtime_common.py) · [计时循环](https://github.com/OPUSLab/SANTA/blob/main/tutorial_code/hf_generate_bridge.py) |

S²ANTA 的阶段判定使用现行公开参考代码。引用 Table 3 的精确数值时沿用论文给出的分母，代码核查用于说明边界，不断言当前分支与当时实验的提交完全相同。

对 EdgeCIM 可补一项合理性检查。§V-A 跨模型报告的最大权重流量为 3.63 GB/token，接近 Qwen3-4B 在 INT8 下 36 个 decoder blocks 的矩阵裸权重约 3.633 GB。若按 INT8 扫完整一遍非驻留词表头，还增加约 0.389 GB。上限正好接近块权重具有提示意义，无法从这项跨模型统计确定头部的压缩、驻留、数制或计时范围，因此表中继续记 `NR`。 [EdgeCIM §V-A](https://arxiv.org/html/2604.11512v2#S5.SS1)

## 3. 将指标归一到同一工作量和硬件条件

### 3.1 先确认分子、分母与模型质量

每个数据点记下模型 revision 和 tokenizer、精度和实际权重/KV 字节、任务质量、稀疏/采样预算、模型层数、是否计算词表头、是否含采样器及 host、初始 cache、生成长度、batch、设备数。对比架构设计时保留同一种模型与质量目标；对比算法-硬件联合设计时允许各自精度和筛选，报告同一质量基线下的 Pareto 点。跨模型按参数量线性缩放会漏掉 GQA/MHA、不同词表的 LM head、KV 长度和稀疏流量。

| 可比端点 | 同条件的输入、输出与计费规则 |
|---|---|
| **Decoder blocks** | 预置相同的 BF16 hidden row 与 KV/cache 初态。计时从第一层依赖开始到最后一个 residual；显式包含各层的投影、Attention、FFN、层内 norm 及相应访存。单独运行，禁用边界之外的 embedding/LM head 预取。只有外部论文或可复现实现能证明到这个端点，才报匹配倍率。 |
| **至末层 norm 或词表头** | 至末层 norm 的区间从 token ID 输入到最后一个 normalized hidden row。至完整词表头时，再计同一 `H×V` 词表、词表精度/分块及读权重，注明输出是物化 logits 还是只走流式 greedy 选择。现有 `without_lm_head_stage` 属于原有时间表的同执行前缀，可展示尾部贡献。 |
| **选出并返回文本 token** | 统一 logits/选择方式、实际输出 token、host/I/O 和计时位置。报告含 prefill 的 TTFT、decode TPOT、单位输出能量。若外部方案把尾段放在 host，把 host 路径作为共同配置接回，并对不同范围的面积独立标注。 |

接入局部 Attention 或 FFN 时，把替换单元放入同一执行图，在相同边界交接张量、做格式转换和搬运、重放 DMA/DRAM 与计算重叠。只有已验证完全串行且共享资源及缓冲状态一致的阶段，才适合直接加减其独立时延。完整头部在两方都启用且均用同一实现时，可另列“共同尾部”的对照行，同时保留各自原生值。

- `T_E2E`、`TTFT`、单请求平均 token 间隔与集群 `output tok/s` 分开。一次同步解码步产出 `B` 个输出时，`aggregate tok/s = B / T_step`；只有 B1、同一窗口时，`ms/token = 1000 / output tok/s` 才等于单请求时间。常规服务 TPOT 使用 `(T_E2E − TTFT)/(N_out − 1)`，按每请求时间计算，再按原协议汇总。分母包含输入 token 的吞吐不能换成该 TPOT。 [vLLM 指标文档](https://docs.vllm.ai/en/latest/benchmarking/cli/)
- Attention/FFN 结果用同一层、同组头形状/上下文、同 K 和 V 路径、同精度及同输出质量的 `μs/层` 或 `nJ/query`、`nJ/vector`。如果已测基线的独占阶段占比为 `p`，所有非该段时间和重叠方式保持相同时可给 Amdahl 估算 `S_all = 1 / [(1−p)+p/S_stage]`。如果优化同时改变外存事务、调度重叠或 host 任务，重放完整依赖链来得到整机变化。

### 3.2 共同带宽和频率下重放

1. 把每个方案拆成阶段级依赖、计算域周期、SRAM bank 访问、DMA 排队与外存读写事务，以及必要的固定延迟。相同模型、相同缓存窗口下运行同一 DRAM 后端，外存类型、数据宽度、通道/频率、页策略、刷新、排队容量、返回链路与仲裁共同配置。采用项目原生事务时序后端，异构近存方案单独记录 die 内部带宽和跨芯片总线。共同平台比较可以用 IO 限速实验，真实更换 DRAM 时再用对应几何与器件时序。
2. 在目标 PVT 的 STA/宏时序支持下对计算域应用 `C/f`，外存时钟、固定延迟、SRAM 及跨时钟路径分别更新。使用 `Σ` 或 `max` 的串行/理想并行近似须写清每一段依赖；总时延用原始/目标两次记录对比。整机周期计数已经包含可能的外存等待，不能把它视为纯计算周期乘以频率比例。
3. 无法重放但有**同一资源总线的真实事务量**时，可以报 `t_mem,min = D / BW_peak` 和 `BW_wall = D / T`。固定这份流量，前者是传输时间下界，后者是按整个观测窗口计算的交付带宽。读写共用数据总线时加总读写；独立且可并行的物理资源分别求下界后取瓶颈。将提前预取列入同一观测窗口或说明初始驻留。`BW_wall/BW_peak` 表示达峰比例，也可能被多余流量推高。报告 K/V、权重、其他字节及容量命中有助解释。 [Roofline §2](https://www2.eecs.berkeley.edu/Pubs/TechRpts/2008/Archive/EECS-2008-134.pdf) · [LLMCompass §IV-C、Fig.8](https://www.cl.cam.ac.uk/~ey204/teaching/ACS/R244_2024_2025/papers/LLMCOMPASS_ISCA_2024.pdf)
4. **示例先例**。EdgeCIM v2 固定 DSE 后的配置，把 273 GB/s 降至 204.8/136.5/68.3 GB/s 时，报告延迟为原来的 1.14×/1.45×/2.38×，这些不是指定模型的标量换算系数。HSA Table II 将参考架构放在同一 RetNet 工作量、DDR5 51.2 GB/s 与同数据移动单价下估算。Voyager 的基准方法则要求相同工作量、工艺和规模/面积，并验证实现与映射。 [EdgeCIM §V-A](https://arxiv.org/html/2604.11512v2#S5.SS1) · [HSA §V-B](https://arxiv.org/html/2507.09010v1#S5.SS2) · [Voyager 基准方法](https://doi.org/10.1098/rsta.2024.0514)

### 3.3 能量对齐与重新计价

- 用同一时间窗内的能量或积分功率除以输出量。`E_token = ∫P(t)dt/N_output`，只在功率确为同一窗口平均值时用 `P_avg / rate`。GPU TDP、峰值算子 TOPS/W、芯片功率和带外存的输出吞吐不能混用。
- 保留 `E_chip`、`E_PHY/ctrl`、`E_DRAM` 和 `E_host/links` 的覆盖标志。主场景可用统一动作价格 `E_DRAM,traffic (mJ/token) = 8 × D (GB/token) × ε (pJ/bit)`。若明细齐全且使用相同定义，另算读、写、刷新、待机、激活与 I/O 开销，多接口按接口汇总。若外部原文只给总能量且无法拆出外存与芯片，就无法可信地统一其外存单价。上下文、scheduler 或存储改变时，重新获取事务和运行时间；只换每 bit 单价可直接重计价。
- 图表并列 `E_on-chip` 和 `E_on-chip + E_DRAM,traffic`，物理整机能量仅在电源边界覆盖时使用。片上数字动态能量使用统一 PVT 的每次动作价，漏电用该运行时间另算。PIM/ReRAM/NAND 的驻留权重及 die 内访问是方案特点，原生比较按实际总成本和容量。用不同物理边界消掉其成本会得到不同问题。

### 3.4 面积与工艺

- **第一选择是共同 PDK、宏库和实际频率约束下重新综合/布局或重计价**。数字面积、SRAM 容量和端口、控制器/PHY、随机或模拟宏、其他 die 分项给值，同一边界对照。固定共同缓冲/带宽与固定共同面积是两组有用实验，两者的资源约束需明确。完整设计保留每个方案真实 native 面积和面积组成。
- 当只有公开数字逻辑面积且有工艺与电压信息时，DeepScaleTool 或 Stillmaker–Baas 可提供单列**逻辑面积敏感性估计**。DeepScaleTool 原版支持 130/90/65/45/40/32/28/22/14/10/7 nm，没有 55/5/4 nm 插点。用作者的方向系数和证据点；Stillmaker–Baas 的示例公式有作者勘误。SRAM 用目标工艺/端口宏库或校准模型，PHY/模拟/随机器件和 3D 存储另有各自证据。缺拆分的总面积保留原生值。和本项目 65→55 面积的 `0.81` 项目口径无关。 [DeepScaleTool §III–IV](https://arxiv.org/pdf/2102.10195) · [Stillmaker–Baas 与作者勘误](https://vcl.ece.ucdavis.edu/pubs/2017.02.VLSIintegration.TechScale/)
- **先例范围**。SOFA 给 28 nm/1 V 的带假设面积和能效，并统一局部算子规模；LeOPArd 同时列两种 65→40 nm 折算和原生配置，并尽量配齐局部 buffer。两例可引用作透明缩放说明。LLMCompass 按数字逻辑、SRAM、控制器及模拟 PHY 分开估计，并对已知芯片面积校准。 [SOFA §V](https://arxiv.org/pdf/2407.10416v1) · [LeOPArd §5.1](https://par.nsf.gov/servlets/purl/10394500) · [LLMCompass §III-D](https://www.cl.cam.ac.uk/~ey204/teaching/ACS/R244_2024_2025/papers/LLMCOMPASS_ISCA_2024.pdf)

## 4. 用 Fig.11 的结果做一遍可核对的换算

采用十进制 GB。`D` 来自含 LM head 的 DRAM 访问字节或等价的封存 `4 pJ/bit` 项。右列改变能量单价，时序列仍为 136.4606 GB/s 原生时序。下界计算假定事务量固定，未对低带宽运行重新模拟。

| 模型与方案 | 封存时延 ms/token | D GB/token | 峰值带宽下界 ms/token | 窗口平均 GB/s | 能量 4 → 6.6 pJ/bit，mJ/token |
|---|---:|---:|---:|---:|---:|
| Qwen3-4B BF16 Dense | 111.120 | 8.347 | 61.168 | 75.118 | 299.199 → 472.818 |
| Qwen3-4B W8 + SparQ | 85.450 | 5.417 | 39.700 | 63.399 | 193.167 → 305.851 |
| Qwen3-4B P-bit | 51.133 | 5.411 | 39.655 | 105.831 | 188.432 → 300.989 |
| Llama 3.2-3B P-bit | 43.929 | 4.355 | 31.913 | 99.134 | 151.771 → 242.353 |
| DeepSeek 7B P-bit | 98.985 | 9.102 | 66.699 | 91.951 | 317.782 → 507.098 |

- Qwen3 的 P-bit 与 W8 + SparQ 流量差约 **0.11%**，两者峰值下界约 39.7 ms，实际时延差却是 **34.32 ms**。这证明总流量差不足以解释时延差。要定位来源，再看计算、发包之间空闲、DMA/SRAM 等待以及与外存重叠的区间。
- 同一对照下，Qwen3 P-bit 的片上能量由 **19.808 降至 15.268 mJ/token（−22.9%）**。统一以 4 pJ/bit 计算时，含外存能量只降 **2.45%**，改用 6.6 pJ/bit 时降 **1.59%**。表内若只能取得某篇论文的片上指标，仅在片上列对照。四方案片上计价面积为 6.450/6.370/6.399/6.480 mm²，支持本项目近面积对照。
- Qwen3 P-bit 若保持 5.411 GB/token，时钟提高到 500 MHz，整机直接减半得到 25.57 ms，低于 **39.65 ms** 传输下界。当前流量、外存接口都固定时，将其他成本降到零也最多 **1.29×**。在 64、102.4、256 GB/s 假设下，固定流量对应的下界分别 **84.55、52.85、21.14 ms**。这些数字适合画虚线下界，不能当作预测的柱高。
- LM head 的**后缀增量**在现有三个 P-bit 模型里分别占 **14.7%、20.7%、10.2%** 解码时间。前缀包括 embedding、全部 decoder blocks、final norm，并保留最后一层已预取的 **64 KiB** 词表权重及原平台面积。严格做 decoder blocks 对照时应重新调度去掉两个端点。有些运行入口的 `include_head=false` 同时关掉 `final_norm`，需分设选项。 [项目封存报告](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/eaf1ddcc56742c4c9f51899ecefb120574aeb5eb/architecture_tlm/process_28nm/results_20261111/REPORT_ZH.md) · [数据 JSON](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/eaf1ddcc56742c4c9f51899ecefb120574aeb5eb/architecture_tlm/process_28nm/results_20261111/SUMMARY.json)

| 本稿 P-bit，B1/2K | 输入 embedding 权重一行 | 全词表 BF16 GEMV 权重 | 至末层 norm 的原执行前缀 ms | LM-head 后缀 ms | LM-head 后缀能量，片上 / 含外存（mJ） |
|---|---:|---:|---:|---:|---:|
| Qwen3-4B | 5,120 B | 777,912,320 B | 43.594 | 7.538 | 2.644 / 27.535 |
| Llama 3.2-3B | 6,144 B | 788,004,864 B | 34.838 | 9.091 | 2.750 / 27.964 |
| DeepSeek 7B | 8,192 B | 838,860,800 B | 88.924 | 10.061 | 2.947 / 29.788 |

表中权重字节是逻辑矩阵尺寸，后缀外存字节还需扣掉已经完成的 64 KiB 预取。绑定输入 embedding 与输出头只共享存储地址和容量。一次查一行与每步扫词表的工作量相差约为词表尺寸，不能把两者合并成单次查表。三个模型的片上后缀能量包含按既有账本计价的执行期间成本，面积仍是同一个物理配置。

## 5. 实施步骤与正文排版

1. **先做有数据支撑的同平台实验**。在四方案共同的 Qwen3-4B 或 Llama-3.2-3B-Instruct、batch 1、2K 已缓存 token 上，复用现有 28 nm、250 MHz、832 KiB 主配置。用对应权重复核 PPL/任务质量，TLM 另用同形状和候选轨迹重放工作量。外存跑 64、102.4、136.4606、256 GB/s 场景，先作固定容量/映射的带宽敏感性，再验证所选的实际 DRAM 时序。每运行记录分阶段权重/KV/其他字节、计算活跃与停等、DRAM service、队列、水位/重叠、时序及同边界能量。各时钟只改有可行 STA 支持的域。4.0 和 6.6 pJ/bit 作为统一价格敏感性，在论文中给出具体外存模型的标定来源或把价格保留为假设。
2. **外部首选 EdgeCIM**。先向公开作者资料核对 Fig.12 同一点的真实面积、PVT/频率、head、输入输出格式、内存价与调度执行细节。复现原条件 128 输入/128 生成、batch 1、原省略/包含模块、273 GB/s，复现误差以原数据粒度和来源列出。我们在这组条件下重放同一缓存轨迹，从 128 到 255 而非只跑一步；再把可复现的 EdgeCIM 样式映射和本方案一道接入 136.4606 GB/s 的共同后端、相同模型和 head 边界。如精度策略不同，同报质量；如不能取得原始轨迹，标 `our reconstruction` 并披露假设，强结论使用可匹配的部分。后续比较 28 nm CELLA 或 RCW-CIM 时，如模型不同，才补一个共同的 Llama2-7B 任务与相同精度/质量、同缓存，验证模型授权及项目 Instruct/后训练要求，不能拿 DeepSeek-7B 直接顶替。
3. **正文布局**。Fig.11 是相同平台的 2×2。邻近 Table X 控制为 `Work | Model, B/ctx | Scope / Evidence | Node / f | DRAM GB/s | ms/output token | mJ/output token | Chip area mm²`，占一张通栏表。选 EdgeCIM、SoulMate、CELLA 或 RCW-CIM、Kelle、OPAL 里已核实的结果。功耗预算和流量下界放对照说明或带宽敏感性小图。Table X 中标记 `measured`、`post-layout + modeled`、`simulation` 以及 `estimated`，LM head 或外存能量不明用 `NR`。取得匹配重放方案后，新增一张小图 `Decode latency vs. external bandwidth`，共用模型、质量目标及接口条件，实线是执行结果，细虚线是 `D/BW_peak`。归一倍率标清共同条件下的基线分母。

本轮给出原始证据复核、单位换算与同条件重放方案，数值示例基于已有封存数据。相关局部比较见同目录的 [SOFA 与八项 ASIC 专题](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/ec3e697101844af8aa5673020eba4b60e32b7712/architecture_tlm/benchmark_inventory_20261029/SOFA_ASIC_COMPARISON_ZH.md)。
