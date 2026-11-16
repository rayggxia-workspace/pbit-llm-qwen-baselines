# LLM 加速器外部基准候选

2026-11-16。先保留论文报告的工作点，后续如开展同条件整机比较，再按所采用的实际实现与工作量测定。**未披露**指下表的核实来源没有给出该比较口径的数据。功耗和面积跟各自边界绑定。正式引用以[修订后的 benchmark 表](../LLM_HARDWARE_BENCHMARK_20261116.md)为准。

| 工作 | 原生工艺、时钟、外存 | 原生结果及边界 | 接入 Qwen3-4B 的条件 |
|---|---|---|---|
| **Harmonia v3，2026** | 28 nm，300 MHz、0.9 V，HBM2 256 GB/s、3.9 pJ/bit | 3.3812 mm²、300.60 mW 片上综合。Llama-3.1-8B B1 单 token 线性和 2K–16K Attention 分项；未披露绝对完整步。 | 原文参考。本项目未运行 Harmonia 或将其接入项目 TLM。 [原文 §IV–V、Fig.21](https://arxiv.org/html/2602.04595v3#S5) |
| **EdgeCIM，TCAD 2026** | 65 nm HSPICE/CACTI，外存 LPDDR5X 16 通道、273 GB/s；芯片统一工作频率未披露 | **直接评估 Qwen3-4B INT4/INT8**，B1、128 个已有 token／128 个生成 token。Fig.12 给吞吐、能效、面积。共享设计 44.66 mm²，边界排除 DRAM 控制器。Table III 的 **139.3 token/s（7.18 ms/token）属于 Llama3.2-3B INT4**。 | 第二个整机候选。锁定同一个物理配置，确认全词表头，补 28 nm CIM 宏和外围的面积及每次读写／位操作计价，重跑 2K。 [原文 §IV-A、§V-B/C](https://arxiv.org/html/2604.11512v2#S5) |
| **OPAL，DAC 2024** | 65 nm，RTL + CACTI；512 KB 全局、2 KB Softmax 缓存；生成比较未给可复用的实际外存时序 | Llama2-70B **1.98 s/token**，Fig.8 分列面积和能量。W4A4/7 单个 OPAL core 约 **0.929 mm² / 335.85 mW**。 | DAC 整机候选。锁定整机核数、外存及词表头，按 28 nm 库重价逻辑和 SRAM。 [原文 §5.2/Table 3](https://arxiv.org/html/2409.05902v3#S5.SS2) |
| **Tender，ISCA 2024** | 商用 28 nm，1 GHz，HBM2 + Ramulator | 64×64 阵列，计价核心 **3.98 mm² / 1.60 W** 峰值。B1、2048:1 输入输出；作者给归一化时延与能效。Table V 为 INT4 硬件。 | 第二个 28 nm 数字设计候选。需重建 B1 实际阵列占用、重定标和 float attention 路径。 [原文 §V、Table V](https://arxiv.org/html/2406.12930v1#S5.SS3) |
| **M-ANT，HPCA 2025** | TSMC 28 nm；DNNWeaver、CACTI；对照统一频率和外存带宽 | 1024 个 8-bit PE、32 个 RQU 合计核心 **0.302 mm²**；共享缓冲 512 KB 单列 **4.2 mm²**。线性和 Attention 对比分项给归一值。 | 可以与 Tender 用相同公共向量路径。生成质量与整步硬件时间需在统一工作量重放。 [原文 §VII、Table IV](https://arxiv.org/html/2502.18755v1#S7) |
| **Kelle，MICRO 2025** | 45 nm 逻辑 1 GHz；LPDDR4 16 GB、64 GB/s，CACTI 7 | 片上 **9.5 mm² / 6.52 W**、外存估计 11.74 W；主评估含 B16，另有 B1 Llama2-7B。 | 完整生成及缓存组织参考。移至 28 nm 需 eDRAM 宏或明确的 SRAM 对应变体，需确认全词表头。 [原文 §8.1、§8.3](https://arxiv.org/html/2510.16040v1#S8) |
| **RCW-CIM，2026 预印本** | TSMC 22 nm，100 MHz，双 DDR5-6400；两路均为 64 bits 时理论 102.4 GB/s | Llama2-7B W4A8、FP16 非线性，**26.87 token/s（37.22 ms/token）**。42.3 TOPS/W 属于计算指标；公开 Table II 未给对应完整功耗和面积。 | 数字 CIM 参考。移至 28 nm 需 RCW 宏和外围计价，并核对 Qwen 全步的外存 trace 与端点。 [原文 Table II、§III](https://arxiv.org/html/2604.27384v1#S3) |
| **CELLA，VLSI 2025** | 28 nm，数字 CIM | 作者机构报告 **31.32 token/s（31.93 ms/token）**与 1.78 ms prefill response；公开摘要不足以确定这一速度点的模型、外存和完整能量。 | 同节点原生速度参照。全文与对应运行点参数可用后再决定是否重建。 [作者机构原始条目](https://researchportal.hkust.edu.hk/en/publications/cella-a-28nm-compute-memory-co-optimized-real-time-digital-cim-ba/) |
| **AccelCIM，DAC 2026** | 28 nm，macro/array 后布局与周期仿真 | Qwen3-0.6B 8K、1 个 CIM core 为 **216.552 ms TTFT / 1.869 W / 2.916 mm²**。面积是阵列 floorplan，时间是 prefill TTFT。 | CIM 外围和存算阵列的建模依据。解码需重设 GEMV、分片、片上数据流和外存。 [原文 §4.1/4.4、Table 3](https://arxiv.org/html/2604.17692v1#S4) |
| **EdgeMM，DAC 2025** | TSMC 22 nm、1 GHz，异构 CPU＋SA＋数字 CIM，动态带宽分配 | 原文报告 **138 token/s** 的多模态流水／剪枝配置；**112 mW** 为后布局芯片报告。摘要／正文的能效表述不同。 | 对比 GEMM/GEMV 和调度分工，原生吞吐按其并发与多模态场景引用。 [原文 §V、Table II](https://arxiv.org/html/2505.10782v1#S5) |
| **SoulMate，ISSCC 2026** | Samsung 28 nm FDS、DDR3 | 20.25 mm² 实测 die。Llama3.2-1B 的作者表列 **60.8 ms/输出 token（含 DDR3）**与 **27.1 μJ/输出 token（外存除外）**。 | 同节点实测部署原生参照；保留芯片、模型和能量边界。 [作者 ISSCC 原文](https://ssl.kaist.ac.kr/SoulMate/ISSCC2026_31.5_SoulMate.pdf) |
| **ReRAM-on-Logic，ISSCC 2026** | 55 nm 逻辑与堆叠 ReRAM，专用推测解码 | 会方给 LLaMA2-7B **17.82 token/s、123.41 mJ/token** 的一个点，约 56 mm² 逻辑及约 22 mm² ReRAM 裸片分属不同层。 | 新器件实测参照。权重存储直接参与加速，迁入普通 LPDDR 会改变机制。 [ISSCC 会方资料](https://static1.squarespace.com/static/6130ef779c7a2574bd4b8888/t/69a9c050c62f5720adbc05eb/1772732500368/ISSCC2026PressKit.pdf) · [论文索引](https://xplorestaging.ieee.org/document/11409211/) |
| **SPARTA，2026 预印本** | 28 nm、1 GHz；HBM2，Ramulator2 验证 KV 事务 | **13.9 mm²、平均片上 1.40 W**。报告三值 LLM 的 prefill/decode 分项、TPOT 和带外存能量。 | 同时处理线性和 Attention 稀疏的参考，迁入同模型要验证三值训练、质量和稀疏率。 [原文 §V/Fig.18](https://arxiv.org/html/2610.34824v1#S5) |
| **Salca，2026 预印本** | TSMC 28 nm，核 500 MHz；单 HBM2、1 GHz，U280 活动校准 | **6.4 mm² / 0.933 W** 片上、约 9.85 W HBM；仅长上下文 decode attention 的选择、QK/Softmax/PV。 | P-Attention 的局部对照，以共同 Attention 输入、上下文和误差门槛重放。 [原文 §5.2/Table 5–6](https://arxiv.org/html/2604.24820v1#S5) |
| **SMOOTH，ISCA 2026** | 官方工件含 LLMCompass 扩展与 ASAP7 预测库，增量硬件评估对应存储管理逻辑 | 作者工件可复现内存管理对 TTFT/TTLT 的影响。硬件面积表的边界是新增逻辑开销。 | 优先用公开工件交叉检查调度与计时。移至 28 nm 时用目标库综合对应单元。 [作者工件](https://zenodo.org/records/20020344) |

## 图表采用口径

- **文献整机表**保留各论文原生精度、KV 策略、工作量及计价边界。Harmonia 只列原文结果。取得正式共同任务和硬件条件下的结果后，再计算整机倍率。
- **机制消融**保留 BF16 Dense、W8 Dense、W8 + Key Selection、P-bit 四行。若加外部硬件同数制消融，选择双方可支持的存储格式、量化张量和 KV 协议，给转换与缓存重定价。 [M-ANT 的质量对齐先例](https://arxiv.org/html/2502.18755v1#S7.SS1)
- **原生工作点表**先选 EdgeCIM 同模型、OPAL 同会议、SoulMate/CELLA 或 ReRAM-on-Logic 实测。注明模型、B、已有和生成 token、精度、芯片／外存计价边界。端点只到 Attention 的 Salca 放入 P-Attention 分项表。AccelCIM 的 216.552 ms 是 TTFT，适用于 prefill。
- **下一个重建**先选 EdgeCIM，正式取得共享或 Qwen 专用配置的每项 PPA 和全词表头路径。拿不到 CIM 宏的 28 nm 数据时，可同时做 Tender 作为纯数字外部对照，保留各自的资源和面积。 
