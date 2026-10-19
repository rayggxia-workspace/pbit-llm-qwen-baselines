# p-bit LLM 架构推荐阅读清单

更新日期：2026-10-18。

建议先精读 **uGEMM、SASCHA、DS-CIM、p-PIM、SANTA 和 Extropic Z1T**。它们分别回答通用随机矩阵运算、精确累加与调度、随机源与存算阵列共同设计、原生随机器件、减少注意力访存，以及重新设计模型这六个问题。后面的文章用于检查具体设计选择和建立对照。

选择范围不限于固定权重：既包括 FFN 的权重矩阵，也包括注意力中动态的 Q/K/V；既考虑随机乘法，也考虑让随机源直接承担激活、采样或读出。以下是按本项目需要筛选的阅读路线，并非 DAC 论文全集。

## 一、优先精读的六篇

| 顺序 | 文献 | 首先要弄懂什么 | 验证范围 |
|---|---|---|---|
| 1 | uGEMM，ISCA 2020 | 两个操作数都变化时，随机乘法与累加怎样组成 GEMM | RTL 综合、算子及小型神经网络 |
| 2 | SASCHA，CASES / TCAD 2022 | 为什么随机乘法可以配精确二进制累加；稀疏调度怎样产生收益 | 综合、访存/调度模型、CNN |
| 3 | DS-CIM，DATE 2026 | 两个共享 PRNG、采样区域重映射、OR 累加和权重复用如何配合 | 版图后电路评估、模型误差注入 |
| 4 | p-PIM，Advanced Science 2026 | 随机器件是否能同时参与权重编码、列求和和神经元激活 | 器件硬件在环与电路模型、MNIST |
| 5 | SANTA，2026 预印本 | 随机采样怎样在读取 V 之前减少访问 | LLM 质量实验、GPU 注意力内核 |
| 6 | Extropic Z1T，2026 官方技术发布 | 模型怎样适应 p-bit 的连接与概率更新机制 | 模型发布、芯片映射及能耗估算 |

### 1. uGEMM：先建立完整的随机 GEMM 概念

**完整题名：** *uGEMM: Unary Computing Architecture for GEMM Applications*，ISCA 2020。

原文：[作者 PDF](https://jsm.ece.wisc.edu/docs/wu-isca2020.pdf)；参考实现：[UnarySim](https://github.com/diwu1990/UnarySim)。

**重点阅读：** 乘法器 uMUL-IS / uMUL-ST、scaled / unscaled 加法器，以及随机序列发生器共享的条件。先跟踪一个乘积和一个点积，再看 GEMM 阵列；不同公开稿的章节编号可能不同。

uMUL-IS 面向两个变化的输入，uMUL-ST 利用静态操作数与条件更新。Sobol 序列和更新时机共同决定两个比特流的交集，不能把其机制简化成“随便产生两路随机流后 AND”。累加还需要并行计数及状态更新。发生器共享取决于输入和更新条件是否一致。[原文](https://jsm.ece.wisc.edu/docs/wu-isca2020.pdf)

**对我们的价值：** 同时理解 FFN 和动态 QK/PV 的算术边界；可以借鉴 UnarySim 建立逐周期数值参考。论文没有完整 LLM 或 DRAM 系统验证，接入我们的 TLM 仍需补充存储、供给与调度。

### 2. SASCHA：随机乘法不要求所有环节都成为随机流

**完整题名：** *SASCHA – Sparsity-Aware Stochastic Computing Hardware Architecture for Neural Network Acceleration*，CASES 2022 / TCAD 的 ESWEEK 专刊。

原文：[作者 PDF](https://nanocad.ee.ucla.edu/wp-content/papercite-data/pdf/j72.pdf)。

**重点阅读：** GEO / GEO+ / uGEMM 处理单元、bit-slicing、稀疏异步调度，以及评估方法中的综合与存储假设。

GEO+ 将随机乘法与完整二进制累加结合，减轻近似 OR 归约造成的误差。文章还联合考虑位切片、稀疏数据组织与调度；随机源共享受到计算路径及种子选择约束。CNN 实验、逻辑综合和存储模型共同支撑结果，收益随权重稀疏率变化。[原文](https://nanocad.ee.ucla.edu/wp-content/papercite-data/pdf/j72.pdf)

**对我们的价值：** 这是回答“必须把全部数都变成随机流吗”的关键文章。应特别检查精确累加带来的计数器、加法器和部分和成本；不能直接把高稀疏 CNN 的收益转移到未剪枝 Llama 的 SwiGLU。

### 3. DS-CIM：共享随机源必须与运算结构一起设计

**完整题名：** *DS-CIM: Digital Stochastic Computing-In-Memory Featuring Accurate OR-Accumulation via Sample Region Remapping for Edge AI Models*，DATE 2026。

原文：[公开全文 v1](https://arxiv.org/html/2601.06724v1)。

**重点阅读：** §III-A–D、§IV-B，尤其 Fig. 2、4–6；最后对照性能表与模型精度表的采样长度。

SRAM 存二进制权重，SNG 就地产生流。激活和权重分别使用 PRNGA、PRNGW 两个独立随机轴，跨行共享；重映射使同一 OR 组中的乘积事件互斥。CMR=64 复制廉价 MAC，让多个输入复用权重/SNG；其吞吐收益不能理解成一个输入向量的串行采样自动缩短 64 倍。分批累加还减少宽计数器的更新次数。[原文](https://arxiv.org/html/2601.06724v1)

**对我们的价值：** 学习联合设计相关性、累加和复用。互斥 OR 的准确性针对重映射后的量，并不消除右移量化误差。动态第二操作数还需要在线更新相关修正项。论文的版图后宏评估与 LLaMA 误差注入应分别看，不能合并成完整 LLM 芯片能效。

### 4. p-PIM：研究随机器件能否改变计算边界

**完整题名：** *Hardware Acceleration of Stochastic Neural Networks Enabled by Bit-Cell Level Co-Design of Magnetic Tunnel Junctions*，Advanced Science，2026，DOI：10.1002/advs.78111。

原文入口：[开放全文](https://pmc.ncbi.nlm.nih.gov/articles/PMC13626169/)；[PubMed](https://pubmed.ncbi.nlm.nih.gov/42814470/)；[期刊 DOI](https://doi.org/10.1002/advs.78111)。

**重点阅读：** MP-SMC 单元与 p-PIM 阵列图、随机权重产生、列电流求和、sMTJ 激活，以及实验和电路仿真的方法部分。

该路线把稳定磁存储、随机磁器件、比较与激活放在同一计算组织里：权重仍需编码，流经 XNOR/列归约后，再由随机器件产生非线性输出。器件硬件在环、FPGA 和电路预测模型分别承担不同验证任务；硬件在环采用时间复用器件，并非所有阵列单元均已集成实测。[论文入口](https://pubmed.ncbi.nlm.nih.gov/42814470/)

**对我们的价值：** 比单纯用 p-bit 替代 LFSR 更接近器件与算法共同设计。阅读时画清“什么信号进入器件、输出是什么、由谁累加”。MNIST 结果不能证明 SwiGLU 或完整 LLM 可直接替换，sigmoid 型器件也不能直接视为 SiLU。

### 5. SANTA：让随机性减少实际访存

**完整题名：** *Stochastic Sparse Attention for Memory-Bound Inference*，2026 预印本，arXiv:2605.01910v1。

原文：[公开全文](https://arxiv.org/html/2605.01910v1)；代码：[官方仓库](https://github.com/OPUSLab/SANTA)。

**重点阅读：** §2 的估计器和分层/系统采样、内核实现、质量实验、prefill 访问并集分析，以及 Bernoulli QK 扩展。

核心 PV 路径按注意力分布选择 V 的行，以 gather 与求和估计加权输出；V 可以保留普通数值格式。只有在取回 V 之前选定地址，才可能减少内存流量。基础 PV 路径仍承担形成注意力分布的成本，QK 稀疏扩展应单独核算。论文包含 LLM 质量和 decode 注意力内核实验。[原文](https://arxiv.org/html/2605.01910v1)

**对我们的价值：** 它说明随机性可以用于地址选择，而不必用于每一个标量乘法。TLM 需要追踪去重、GQA 组内并集、突发读取和采样器成本；prefill 的多查询并集可能削弱节省。注意力内核加速不能直接等同整模型加速。

### 6. Extropic Z1T：模型为 p-bit 架构作出什么改变

**资料名称：** Extropic Z1T / Z1T-0，2026 官方技术说明与模型发布；不是同行评审论文。

原文：[官方技术说明](https://extropic.ai/writing/z1t)；[模型卡](https://huggingface.co/Extropic-AI/Z1T-0)。

**重点阅读：** hardware encoding、model architecture、performance and efficiency estimates，以及模型卡中的规模和训练设置。

Z1 的 p-bit 更新、稀疏连接及映射约束参与了模型设计；Z1T 使用 DyT、GCA 等结构并重新训练。物理连接度与编码后的模型连接不能混为一谈。公开模型规模、训练任务和能耗估算边界都应保留；其效率估算对末端读出与主机/FPGA 数据传输有明确范围限制。[官方说明](https://extropic.ai/writing/z1t)、[模型卡](https://huggingface.co/Extropic-AI/Z1T-0)

**对我们的价值：** 如果允许重训，可以考虑让随机源参与神经元和连接结构，而不是仅逼近原模型的矩阵乘法。它不能直接证明原 Qwen/Llama 的无训练替换效果，也不能把估算倍率当作完整 LLM 的实测能效。

## 二、按具体设计问题继续读

### 7. VLSI 2024 SCIM：必须看的一篇实测芯片

**题名：** *A 278–514M Event/s ADC-Less Stochastic Compute-In-Memory Convolution Accelerator for Event Camera*，VLSI Technology and Circuits 2024。

原文：[作者 PDF，2 页](https://nanocad.ee.ucla.edu/wp-content/papercite-data/pdf/c128.pdf)。重点看第一页 SNG/阵列说明与第二页 Fig. 2–6。

12 nm 实测芯片把二进制权重留在 SRAM，原位生成随机流，一个权重/SNG 复用给多个 MAC。循环寄存器的位窗口用于产生多组流；符号分路、wired-OR 与计数器共同完成输出。这是检查“共享是否真的节省面积、读出是否昂贵”的直接材料。事件模式和普通 6b×6b 模式有不同能效，不能拿事件模式峰值对比稠密 LLM。[原文](https://nanocad.ee.ucla.edu/wp-content/papercite-data/pdf/c128.pdf)

### 8. SC-CNN / BISC：混合表示怎样降低转换成本

**题名：** *Bitstream-Based Neural Network for Scalable, Efficient, and Accurate Deep Learning Hardware*，Frontiers in Neuroscience，2020，DOI：10.3389/fnins.2020.543472。

原文：[开放全文](https://pmc.ncbi.nlm.nih.gov/articles/PMC7793640/)。重点看 §3.1、Fig. 2–3 和硬件优化部分。

利用输入流、二进制权重控制的运行时长和计数读出组织乘加，不要求两个操作数都使用独立随机流；同权重复用具有结构条件。文章还讨论确定性流与多位并行。实验面向 CNN，涉及 ReLU 的优化不能原样用于带负值的 SiLU。它是 BISC 路线的后续完整材料，不能把其全部结果归到 DAC 2017 原始 BISC-MVM 论文。[全文](https://pmc.ncbi.nlm.nih.gov/articles/PMC7793640/)

### 9. Dither Computing：为什么“确定性主体＋少量随机余量”值得比较

**题名：** *Dither computing: a hybrid deterministic-stochastic computing framework*，ARITH 2021。

原文：[全文 v2](https://arxiv.org/html/2102.10732v2)。重点看 §III–IV 的构造、§VI 操作数不对称、§VII–VIII 的舍入与矩阵乘法。

它用确定性部分表示主体，只随机处理余量；论文证明相应构造的均方误差可按 O(1/N²) 缩减，并讨论矩阵乘法中的舍入位置。这一结论有具体构造和假设，不能推广成任意相关随机流都具有该收敛率。其价值在于帮助建立低位确定性舍入、随机舍入与长随机流的公平对照；没有完整 LLM ASIC 验证。[原文](https://arxiv.org/html/2102.10732v2)

### 10. P2LSG：低成本序列发生器的组件对照

**题名：** *P2LSG: Powers-of-2 Low-Discrepancy Sequence Generator for Stochastic Computing*，ASP-DAC 2024。

原文：[全文 v2](https://arxiv.org/html/2309.05235v2)。重点看序列定义、多维构造与发生器硬件。

计数器、位分组与重排可产生低差异序列，适合对照我们“一个状态源＋多路排列”的成本和数值效果。这里的 low-discrepancy 不是物理真随机；标量运算和图像实验也不是 GEMM 或 LLM 结果。需要另行验证两个操作数的联合分布及共享后的点积误差。[原文](https://arxiv.org/html/2309.05235v2)

### 11. ICCAD 2018 低差异随机计算：补上二维误差理解

**题名：** *Deterministic Methods for Stochastic Computing using Low-Discrepancy Sequences*，ICCAD 2018，DOI：10.1145/3240765.3240797。

原文：[作者 PDF](https://mriedel.ece.umn.edu/wiki/images/1/1f/Najafi_Lilja_Riedel_Deterministic_Methods_for_Stochastic_Computing_using_Low-Discrepancy_Sequences.pdf)。重点看乘法所用的多维序列及误差实验。

这篇用于理解“用确定性序列执行随机编码算术”。双流 AND 的精度取决于联合采样点覆盖乘积区域的情况，不能只检查每一路 1 的比例或单维均匀性。对于我们的一源多路设计，应把短前缀点积误差纳入检查，而不只报告全周期分布。[原文](https://mriedel.ece.umn.edu/wiki/images/1/1f/Najafi_Lilja_Riedel_Deterministic_Methods_for_Stochastic_Computing_using_Low-Discrepancy_Sequences.pdf)

### 12. tubGEMM：必须保留的无随机源对照

**题名：** *tubGEMM: Energy-Efficient and Sparsity-Effective Temporal-Unary-Binary Based Matrix Multiply Unit*，2024 公开预印本，arXiv:2412.17955v1。

原文：[全文](https://arxiv.org/html/2412.17955v1)。重点看 temporal-unary-binary 表示、周期数、稀疏处理与阵列评估。

一个操作数按时间展开，另一个保留二进制；不依赖 RNG，面向准确整数矩阵运算。它很适合回答“简单乘法电路带来的收益，是否一定要通过随机性获得”。应与位串行整数方案一起作为硬件对照；不能把这种无 RNG 的 unary 方案标成 p-bit 的证据。[原文](https://arxiv.org/html/2412.17955v1)

### 13. ASTRA：动态矩阵与新器件结合的参考

**题名：** *A Light-Speed Large Language Model Accelerator with Optical Stochastic Computing*，GLSVLSI 2025，DOI：10.1145/3716368.3735299。

原文：[作者机构仓储 PDF](https://api.mountainscholar.org/server/api/core/bitstreams/5393ef9a-acdf-4548-a718-f05f5df3e3f9/content)。重点看 §3 的生成、光学乘法、电荷累加和共享，及 §4 的评估方法。

光学 AND 与电荷积分共同处理矩阵运算，支持动态操作数，适合参考 QK/PV 的映射。它采用确定性生成和位位置编码，不等同于物理 p-bit。结果来自器件/电路及体系结构模型；模型评估包含 OPT-350M 等，不能视为 7B 级完整 PPL 验证。[原文](https://api.mountainscholar.org/server/api/core/bitstreams/5393ef9a-acdf-4548-a718-f05f5df3e3f9/content)

### 14. 随机纳米磁体电流数字化：器件是否能替代昂贵的读出

**题名：** *Stochastic Nanomagnets as Current Digitizers for Efficient Probabilistic Machine Learning*，Physical Review Applied 24，044012，2025。

原文入口：[期刊 DOI](https://doi.org/10.1103/s86j-5jcr)；[MIT 官方介绍](https://www.rle.mit.edu/stochastic-nanomagnets-as-current-digitizers-for-efficient-probabilistic-machine-learning/)。

官方摘要介绍了三端 SOT 随机磁器件电流数字化，以及面向 MNIST 的部分和方案。其吸引力在于让随机器件承担电流数字化，而非只为常规数字乘法器提供随机字。这一路线可用于思考列求和后的接口，与目前“数字固定权重＋随机输入”是不同计算边界。[官方摘要](https://journals.aps.org/prapplied/abstract/10.1103/s86j-5jcr)

**建议下载全文。** 目前可核实题录、摘要与官方介绍；采样长度、外围电路、完整 PPA 和测试设置应以全文为准。

## 三、阅读时统一记录的八个问题

| 问题 | 应从论文中提取的内容 | 对我们设计的影响 |
|---|---|---|
| 什么量被随机化？ | 输入、权重、乘积、激活、舍入余量，还是地址 | 决定 p-bit 放置位置和数据格式转换 |
| 随机源是什么？ | LFSR、低差异序列、TRNG、可调概率 p-bit；初始化与更新 | 决定面积、功耗、重放与校准成本 |
| 哪些流共享？ | 同一乘积两边、同一点积内、不同输出列、不同输入/时刻 | 必须分别判断偏差、协方差和复用条件 |
| 怎样累加？ | OR、popcount、二进制部分和、电荷/电流、概率神经元 | 决定饱和、动态范围、计数器与读出成本 |
| 一次有效输出要几拍？ | 采样数、位切片、并行流数、流水线启动和排空 | 决定 TTFT、TPOT 与实际吞吐 |
| 数据是否真的少搬？ | 权重驻留层级、输入复用、部分和、KV、外部 DRAM 事务 | 区分算子节能与整机节能 |
| 模型质量怎样验证？ | 同模型原参考、量化参考、完整替换范围、PPL/任务分数、种子 | 避免用单层 MSE 或 CNN 准确率代替 LLM 质量 |
| 功耗面积包括什么？ | 随机源、时钟、SRAM、转换、控制、DRAM；综合/版图/实测 | 决定能否公平比较 |

“64 路能否共享一个 8 位随机字”没有脱离计算图的统一答案：同一乘积两侧、同一点积的不同项和不同输出之间，共享造成的后果不同。DS-CIM 甚至主动利用相关性形成互斥事件；uGEMM 则要求特定的序列更新关系。应先写出计算的联合分布和累加规则，再决定共享结构。

## 四、针对本项目的阅读路线与设计取舍

**继续优化现有 FFN：** uGEMM → SASCHA → DS-CIM → VLSI 2024 SCIM。读完后应能画出一个 tile 的完整路径：二进制数据驻留 → 序列/概率编码 → 乘法 → 归约 → 计数/读出 → 缩放/非线性，并逐项核算状态和周期。

**寻找更依赖 p-bit 特性的结构：** p-PIM → 电流数字化 → Extropic Z1T。重点判断器件是否同时替代非线性、读出或采样电路，以及是否需要重训；不要只比较 p-bit 与 LFSR 的随机字功耗。

**把收益扩展到整个 LLM：** SANTA → uGEMM 的动态输入路径 → ASTRA。先分开分析 prefill 与 decode，再检查 K/V 的实际读取。动态矩阵路线可以考虑，但不能沿用固定权重中的离线修正与长期驻留假设。

**验证随机性的必要性：** Dither → P2LSG / ICCAD 2018 → tubGEMM。至少保留低位数字计算、确定位串行、完整门限枚举和低差异短序列对照。它们分别检验收益来自低精度、时间展开、序列覆盖，还是随机器件本身。

对于单边门限、另一侧固定数值且精确线性累加的路径，完整覆盖 8 位门限可消除该离散表示的采样误差；双流 AND 则还需要满足二维联合计数条件。这是比较这些路线时的数学区别，不能把“256 个门限足够”泛化到所有随机乘法。

## 五、系统仿真与数字计算的三篇补充

下面三篇不提供随机乘法机制，但能帮助我们把模块收益变成可信的 LLM 架构评估。

### 15. FIGNA：混合精度接口与数字强基线

**题名：** *FIGNA: Integer Unit-Based Accelerator Design for FP-INT GEMM Preserving Numerical Accuracy*，HPCA 2024。

原文入口：[会议 DOI](https://doi.org/10.1109/HPCA57654.2024.00064)；[已有本地全文](C:/Users/86134/Downloads/FIGNA_Integer_Unit-Based_Accelerator_Design_for_FP-INT_GEMM_Preserving_Numerical_Accuracy.pdf)。已有中文细读记录见下一节。

重点读 §III 的整数阵列、共享指数与外围转换，及 §IV 的评估方法。它采用综合/功耗工具标定与 SystemC 统计，适合学习 FP–INT 边界如何计入成本。HBM 采用单位比特能量计费，与详细 DRAM 命令级功耗评估的范围不同。[原文入口](https://doi.org/10.1109/HPCA57654.2024.00064)

### 16. NeuPIMs：异构调度与 DRAM-PIM 系统评估

**题名：** *NeuPIMs: NPU-PIM Heterogeneous Acceleration for Batched LLM Inferencing*，ASPLOS 2024。

原文：[作者 PDF](https://jongse-park.github.io/files/paper/2024-asplos-neupims.pdf)；[官方模拟器](https://github.com/casys-kaist/NeuPIMs)。

重点读 §2.1、§4–7 和 §8。NPU 的 GEMM 与 DRAM-PIM 的 GEMV 通过子批交错协作；ONNXim、DRAMsim3 和 Micron 能量模型连接计算与存储评估，其中 PIM 命令的能耗另有假设。文章分析两阶段特征，核心设计与实验侧重批量 generation。它适合参考调度和功耗边界，但 DRAM-PIM 的计算命令不能直接代表我们的随机宏。[原文](https://jongse-park.github.io/files/paper/2024-asplos-neupims.pdf)

### 17. LLMCompass：存储层级、映射搜索与校准

**题名：** *LLMCompass: Enabling Efficient Hardware Design for Large Language Model Inference*，ISCA 2024。

原文：[作者 PDF](https://augustning.com/assets/papers/llmcompass-isca-2024.pdf)；[官方仓库](https://github.com/PrincetonUniversity/LLMCompass)。

重点读 §III、Fig. 5 与验证部分：计算图怎样映射到存储层级、怎样搜索分块、怎样用实机结果检查时延模型。它可作为数字路径和调度验证的参考；加入 p-bit 后，需要为新算子、吞吐与转换接口重新标定。论文的验证误差针对其指定硬件与工作负载，不是对任意新 ASIC 模型的精度承诺。[原文](https://augustning.com/assets/papers/llmcompass-isca-2024.pdf)

## 六、已有本地资料

下列文件是既有调研与设计记录，可与原文交叉阅读；它们不替代上述论文的方法和实验条件。

- 随机矩阵乘法与共享：[STOCHASTIC_MATMUL_RNG_SHARING_SURVEY_ZH_20261015.md](C:/Users/86134/Documents/a_P_BIT/pbit_llm_master_report_20261012/STOCHASTIC_MATMUL_RNG_SHARING_SURVEY_ZH_20261015.md)。
- 一个状态源供多路输入：[RNG32_TO_64_DESIGN_AND_PROOFS_ZH_20261015.md](C:/Users/86134/Documents/a_P_BIT/pbit_llm_master_report_20261012/RNG32_TO_64_DESIGN_AND_PROOFS_ZH_20261015.md)。
- 新器件与随机计算：[STOCHASTIC_COMPUTING_DEVICES_LLM_RESEARCH_ZH_20261013.md](C:/Users/86134/Documents/a_P_BIT/pbit_llm_master_report_20261012/STOCHASTIC_COMPUTING_DEVICES_LLM_RESEARCH_ZH_20261013.md)。
- prefill/decode 与 SANTA：[PREFILL_DECODE_ACCELERATOR_AND_SANTA_SURVEY_ZH_20261017.md](C:/Users/86134/Documents/a_P_BIT/pbit_llm_master_report_20261012/PREFILL_DECODE_ACCELERATOR_AND_SANTA_SURVEY_ZH_20261017.md)。
- 新器件的阶段覆盖：[EMERGING_DEVICE_PREFILL_DECODE_EVIDENCE_ZH_20261017.md](C:/Users/86134/Documents/a_P_BIT/pbit_llm_master_report_20261012/EMERGING_DEVICE_PREFILL_DECODE_EVIDENCE_ZH_20261017.md)。
- 数字混合精度对照 FIGNA：[FIGNA_FULL_PAPER_REVIEW_AND_PBIT_IMPLICATIONS_ZH_20261016.md](C:/Users/86134/Documents/a_P_BIT/pbit_llm_master_report_20261012/FIGNA_FULL_PAPER_REVIEW_AND_PBIT_IMPLICATIONS_ZH_20261016.md)。

这些本地报告在用户资料目录中，仓库阅读时应使用该目录的实际路径。新结构的后续实验应分别给出数值质量、模块 PPA 和完整系统结果，不能用清单中的任一宏峰值替代这三层验证。
