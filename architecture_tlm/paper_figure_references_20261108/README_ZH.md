# p-bit LLM 论文 Fig.1 至 Fig.10 的原图参考与绘制方案

日期：2026-11-08。对应用户白板中的图序；**Fig.8 按用户补充意见保持留空**。以下页码均为从 PDF 首页起算的物理页码，不是会议论文集页码。链接中的 `#page=` 可直接定位参考页；图号以所列 PDF 版本为准。

这组图可以沿着“p-bit 能做什么 → 整机怎样组织 → Attention 怎样实现及为何成立 → FFN 怎样实现 → 局部收益 → 模型质量 → 整机收益”的顺序展开。最值得借鉴的是原图的信息组织、放大层级和实验呈现；绘制内容、数据和结论仍使用本项目的实现与结果。

## 1 白板内容与推荐原图速查

白板 Fig.3 的编号字迹较潦草，按其所在位置及“att 具体结构”识别为 Attention 结构图；Fig.4 识别为进一步解释拟合/实现 Softmax 的原因。Fig.9 的第二个模型名有划改，不据此固定模型版本。左侧 benchmark、GPU、NIST 等为额外备忘，不能自动当成某张图已确定的内容。

| 我们的图 | 白板主题 | 优先打开的参考原图 | 最适合借鉴的内容 |
|---|---|---|---|
| Fig.1 | p-bit 介绍，并说明与 LLM 的联系 | [Pervaiz 等，Fig.1，p.1][pbit]；[SCIM，Fig.2，p.2][scim2] | 输入控制概率、随机时间序列、平均响应；数值到比特流再到运算的桥接 |
| Fig.2 | 芯片二维架构；随机源、Attention、FFN、数据流/I/O、存储 | [SOFA，Fig.11，p.7][sofa11]；[Tender，Fig.6，p.7][tender6]、[Fig.8，p.8][tender8] | 存储和计算同图；整机—阵列—单元三级放大；带编号的数据搬运路径 |
| Fig.3 | Attention 具体结构；Ising Softmax 与 PV 采样 | [LeOPArd，Fig.4，p.5][leopard4]；[SparQ，Fig.5，p.5][sparq5]；[Softermax，Fig.4，p.4][softermax4] | 筛选前端、索引/FIFO、非线性、V 访问及归约后端的接口 |
| Fig.4 | 解释概率机制为什么能得到 Softmax | [Ising SoftMax，Fig.3，p.2][ising3]；[Softermax，Fig.3，p.3][softermax3] | 公式变换和小例子对应；状态/能量与目标概率对应；渐进解释 |
| Fig.5 | Attention 对照与结果；面积、能量、时间、采样/筛选参数 | [Softermax，Fig.5，p.6][softermax5]；[LeOPArd，Fig.11，p.10][leopard11]；[Ising SoftMax，Fig.4，p.3][ising4] | 相同任务的能量随长度变化；相同基线下的分项与消融；采样误差收敛 |
| Fig.6 | FFN 结构；电路、p-bit、计数/截断、分层采样 | [DS-CIM，Fig.2，p.3][dscim2]、[Fig.6，p.4][dscim6]；[FIGNA，Fig.6–7，p.4][figna7]；[ASCEND，Fig.4，p.3][ascend4] | 共享源—阵列—计数器；采样空间示意；格式转换和非线性局部放大 |
| Fig.7 | FFN 对数字 MAC、数字 CIM、脉动阵列的结果 | [SCIM，Fig.9，p.7][scim9]；[DS-CIM，Fig.7，p.6][dscim7]；[FIGNA，Fig.17，p.12][figna17] | 完整成本分解；随机源/计数器不省略；面积与能量/性能的折中 |
| Fig.8 | **留空** | **不选参考文献，不另定主题** | 保留用户当前安排 |
| Fig.9 | Qwen 等模型的 PPL、任务准确率 | [LeOPArd，Fig.6，p.8][leopard6]；[Ising SoftMax，Fig.5，p.3][ising5]；[SparQ，Fig.1，p.1][sparq1]；[Tender，Fig.9，p.10][tender9] | PPL 与准确率分子图；基线—替换方案配对；质量与预算的联系 |
| Fig.10 | 跨模型整机功耗、面积、时间 | [Tender，Fig.10–11，p.11][tender10]；[FIGNA，Fig.13，p.10][figna13]、[Fig.15，p.11][figna15] | 同一模型下多方案并列；共享图例；面积/能量分解中包含存储 |

## 2 Fig.1 p-bit 原理及它在 LLM 中的位置

**首选 Pervaiz 等的 Fig.1（p.1），辅以 SCIM Fig.2（p.2）。** 前者把 p-bit 的端口、随机输出和平均响应放在一起；后者将随机数生成、概率编码及基本随机运算连接起来，适合向体系结构读者交代信号含义。

建议画成三个相连的小面板：

1. **可控概率：** 标出数字输入、目标概率，以及同一输入下的 0/1 时间序列。用一条平均概率曲线解释 p-bit；区分 0/1 概率与 ±1 平均值，避免直接把 tanh 纵轴标为概率。
2. **怎样计算：** 分别画“概率事件参与乘加/非线性”和“条件概率采样产生索引”。用小于十位的比特流示例即可，避免在引言中放大规模电路。
3. **怎样用在 LLM：** 在简化的 decoder block 中高亮 Attention 与 FFN，标出数字保留路径以及两处概率计算的输出去向。

白板中的 LFSR 可以在第一面板内画成数字仿真实现的一个来源。物理 p-bit 与 LFSR 不宜被画成同一个器件；如果论文尚未采用某种物理单元的实测成本，可用抽象概率端口，避免让引言图提前固定器件方案。

**版式：** 优先单栏至约 1.5 栏宽，保留直观时间序列；复杂随机源共享网络放 Fig.2/6。

## 3 Fig.2 整机架构与数据流

**主参考 SOFA Fig.11（p.7）与 Tender Fig.6（p.7）；存储路径参考 Tender Fig.8（p.8）。** SOFA 将外存、SRAM、计算引擎和控制器放在一张总图中；Tender 的 Fig.6 采用系统、阵列和 PE 的连续放大，Fig.8 则展示带索引的数据供给过程。

建议我们的图包括：外部 DRAM 与控制/DMA、共享 banked SRAM、公共数字计算池、FFN 概率阵列、Attention 筛选/采样/PV 单元、随机服务，以及调度控制。粗实线表示数据，细虚线表示控制，用单独颜色表示随机服务；同一 SRAM 或数字池只画一个物理实例，再标逻辑用途。

图的下侧附一条 token 的阶段带，例如 QKV → 筛选/QK → 概率采样/PV → O → FFN；只把实际能重叠的传输和计算画成重叠。lm_head 由同一硬件资源执行时，可以用阶段标签表示，不能因为它没有独占算子就从执行范围中消失。

采用“总图＋两个局部放大”的双栏布局。白板所说的二维芯片图可画成**架构示意**；没有 floorplan/P&R 支撑时，模块矩形的面积比例不要暗示真实 die 版图。具体 SRAM 容量、核数、工艺和频率待最终基线冻结后填入。

## 4 Fig.3 Attention 结构与选择性 V 访问

**LeOPArd Fig.4（p.5）最适合学硬件组织；SparQ Fig.5（p.5）最适合学索引和矩阵访问的表达；Softermax Fig.4（p.4）适合学非线性单元的局部放大。** 三者分别突出前后端队列、按索引 gather 和共享归一化状态。

建议主干沿左至右展开：

`Q/K 输入 → 粗筛选 → 候选索引/FIFO → 精细 QK/分数准备 → Ising/概率采样 → 样本索引 → V gather/局部缓存 → PV 累加 → 输出`

该顺序须按最终实现核对；若筛选与精算有复用，画共享硬件和模式切换，不平白复制两套阵列。PV 放大框重点画清：样本是否重复、重复样本如何累计、V 是否缓存、未命中如何发起读取、反压如何传回。旁边放一个 4～8 个 token 的 K/V 矩阵小例子，用相同颜色标出“选中的位置”与“实际读取的数据”。

借鉴 SparQ 的矩阵着色方法，不意味着把它的 top-k 后精确 Softmax 或均值补偿照搬给我们。我们的图应明确：哪些步骤仍为数字精算，哪些输出是采样索引，以及是否直接融合 PV 而不显式输出整行概率。

**版式：** 双栏主数据通路，下面一排小矩阵示例；数学推导交给 Fig.4。

## 5 Fig.4 Softmax 概率机制与公式的对应

**首选 Ising SoftMax Fig.3（p.2），辅以 Softermax Fig.3（p.3）。** 前者把 logits、状态能量和分布放在同一框架中；后者适合学习“每一步变换都明确改变了什么”的呈现方式。

建议三个面板：

- **目标：** 从三个 logits 的小例子出发，给出目标类别概率，避免从完整 Transformer 开始推导。
- **实现：** 写出本项目实际采用的条件更新式、状态编码和抑制/反馈关系，用箭头对应 Fig.3 中的具体硬件端口。若采用全局反馈，必须用实际更新方程说明，不能用参考文献的另一套耦合矩阵替代。
- **输出：** 将目标概率、实际状态占比、有限采样得到的类别频数并列。若包含无效、多热或保持状态，明确它们如何读出或转换成一个类别。

稳态公式、有限时间混合、有限样本误差是三个不同问题。示意图可解释前者，实测收敛放 Fig.5；不要仅凭重叠的三根柱就声称任意短采样长度均精确等价于 Softmax。也不要把“归一化 sigmoid”与 Softmax 的关系省略成未经证明的等号。

**版式：** 公式不多时单栏，状态映射与采样例子较多时双栏；面板标题直接说明“目标—更新—读出”。

## 6 Fig.5 Attention 的局部收益与参数选择

**主参考 Softermax Fig.5（p.6）和 LeOPArd Fig.11（p.10）；收敛画法参考 Ising SoftMax Fig.4（p.3）。** 可增加 SparQ Fig.4（p.3）作为筛选质量的备选，尤其是其 top-k agreement 随筛选维度变化的曲线。

建议用三至四个子图回答不同问题：

| 子图 | 建议横纵轴/分组 | 要回答的问题 |
|---|---|---|
| (a) 局部能量与时间 | 横轴上下文长度，纵轴 mJ/query 与 μs/query 分开画；相同 Attention 边界 | 采样、稀疏访问的收益是否随长度变化？ |
| (b) 成本分解/消融 | 相同基线下堆叠筛选、QK、概率前端、随机服务、V 访问、PV 和控制成本 | 节省来自哪里，新增成本在哪里？ |
| (c) 采样收敛 | 横轴样本数 S，纵轴 TV/KL 或 PV NMSE；多 seed 误差带 | 有限样本下分布/输出误差怎样变化？ |
| (d) 筛选预算 | 横轴 r/k 或实际读取字节，纵轴候选覆盖质量或 PV 误差 | 筛选成本与有效信息保留怎样折中？ |

只选最终最需要解释的三项也可以。白板 Fig.5 还写到 PPL，建议保留一个质量约束说明或指向 Fig.9；完整模型 PPL 主图不在两个位置重复。面积、延迟、能量分别标单位，功率 mW 不替代完成同一 Attention 任务的能量。

Ising SoftMax 参考图中的高精度收敛来自其特定 ensemble 仿真，不能当成我们单次有限样本硬件的误差证据。有限样本的 PV NMSE、稳态分布偏差与模型 PPL也不能互换。

## 7 Fig.6 FFN、计数器和分层采样结构

**主参考 DS-CIM Fig.2（p.3）与 FIGNA Fig.6–7（p.4）；分层示意参考 DS-CIM Fig.6（p.4），非线性局部放大参考 ASCEND Fig.4（p.3）。** 它们分别提供源与阵列的层级、格式转换路径、采样空间示意和真值/逻辑对应的画法。

建议一张双栏图分成以下部分：

1. **SwiGLU/FFN 数据路径：** 标出 gate/up、非线性与逐元素乘、down，说明同一物理核何时复用。用颜色区分 BF16、幅值码/符号、随机事件、多位部分和。
2. **阵列局部：** 画输入保持/概率编码、共享随机服务的实际扇出、驻留权重、逐列选择/归约、公共计数与跨 K 恢复。固定 W8 的主方案必须在此看出“权重保留多位码”，不能照搬双侧随机 SNG。
3. **计数和截断：** 画本拍事件和、累计状态、清零/使能、输出；明确所谓饱和究竟是数值饱和、位宽截断还是分段累计。位宽标注用最终证明/RTL接口，不凭整齐随意取 8 位。
4. **分层采样小例子：** 用数轴或格子展示层号、层内随机偏移和访问顺序。线性阶段与非线性阶段的采样空间分别标注，避免让读者以为每一级都采用相同二维网格。

DS-CIM 的 Fig.6 是互斥区域重映射；我们的分层采样不应仅因都画格子就写成同一机制。ASCEND 的 Fig.4 对应 GELU，适合借鉴“函数/真值表—逻辑块”的表达，不能直接换成 Qwen 的 SwiGLU 后声称功能相同。FIGNA 的格式转换可帮助说明接口，但不代表我们已经具备其数值精确性。

## 8 Fig.7 FFN 对数字基线的局部比较

**主参考 SCIM Fig.9（p.7）、DS-CIM Fig.7（p.6）；折中散点图参考 FIGNA Fig.17（p.12）。** SCIM 分别展示 SNG、计数和运算的成本；DS-CIM 将功率/面积分开分解；FIGNA 用散点表达缓存资源改变后的能效—面积效率关系。

与现有 [Fig.7 比较计划](../fig7_ffn_comparison_20261107/PLAN_ZH.md)衔接，推荐保留：

- **单位工作能量：** GU 与“非线性→Wd”分别成组，使用相同完整 DOT/帧定义；放量化数字 MAC、数字 CIM、成熟脉动阵列、BF16 背景与我们。
- **面积—完成时间散点：** 每个点是同一完整任务，注明物理核数；等面积/等吞吐匹配用不同点形，并给出匹配方式。
- **分项：** 源/SNG、非线性、权重选择、归约/计数、保持/门控、格式转换及局部存储按覆盖边界展示；面积和能量各自成图。
- **少量匹配消融：** 前/后端共享、门控、分层减采样。没有同输入同边界对照的历史结果，不拼成累计节能瀑布图。

如果版面紧，前三项比挤满采样/位宽/工艺/阵列规模的扫描更重要。SCIM Fig.9 的 1-bit 归一化和不同精度折算只用于理解其图；我们应按完整有用运算计量，不把 T 次采样另算成 T 倍有效 MAC。参考图中的倍数也不能作为我们的性能结果。

## 9 Fig.8 留空

用户已经明确“暂时留空，先整理其余九张”。本文件不为 Fig.8 安排随机质量、存储调度或任何其他主题，后续若补主题，再单独核对参考。

## 10 Fig.9 模型 PPL 与任务准确率

**主参考 LeOPArd Fig.6（p.8）与 Ising SoftMax Fig.5（p.3）；质量—预算曲线参考 SparQ Fig.1（p.1），参数敏感性参考 Tender Fig.9（p.10）。** LeOPArd 对 PPL 使用独立面板，Ising 论文并列了两类模型质量指标；SparQ 则在同一任务上将质量与数据流量联系起来。

建议：

| 面板 | 内容 | 呈现方式 |
|---|---|---|
| (a) 模型 PPL | 未改动参考、FFN-only、Attention-only、联合方案 | 每个模型独立小图或分组；给原始 PPL，可另标相对变化 |
| (b) 下游任务 | 实际完成的 ARC-E/PIQA 等，精确注明 acc 或 acc_norm | 配对点/分组柱；变化以百分点标注，多 seed 给误差 |
| (c) 可选预算曲线 | 少量 S/k 设置与质量的关系 | 固定另一参数，避免把多变量混成一条因果曲线 |

同一模型的 BF16 与随机替换方案使用同 revision、文本/任务和计分协议。不同模型的绝对 PPL 不适合排成统一优劣榜；准确率、PPL、Self-BLEU 也不共用数值纵轴。参考论文里存在 Base 模型，不改变本项目新实验优先后训练/Instruct 版的要求。

白板中 Qwen 后面的模型名被划改，图例先保留“第二个实际完成评估的模型”；不擅自确定为 Llama-1/2，也不将尚未完成的质量结果填进去。

## 11 Fig.10 整机跨模型时间、能量、功率和面积

**主参考 Tender Fig.10–11（p.11），分解方式参考 FIGNA Fig.13（p.10）和 Fig.15（p.11）。** Tender 用相同模型次序展示性能和能效；FIGNA Fig.15 将计算、片上存储与外存能量区分开。其 Fig.13 是逻辑面积分解，不含 SRAM；Fig.17 的面积效率才明确包含 SRAM。我们的整机面积应另列 SRAM，不能照抄 Fig.13 的边界。

建议主图用四个面板：

1. **完整 decode 时间：** ms/step 或请求 TPOT，注明 batch、上下文长度和计时范围；不同 batch 不能悄悄改用全批 tokens/s 的倒数。
2. **完整 decode 能量：** mJ/step 或 J/output-token，与时间使用相同范围；堆叠 FFN、Attention/公共数字部分、SRAM、DRAM/接口等已计成本。
3. **平均功率：** 用相同时间窗口的 E/T，分芯片与包含外存的系统；不能把某算子的峰值功率填进整机平均栏。
4. **面积：** 分计算、随机/控制和 SRAM 等。若同一 ASIC 运行多个模型，面积只随硬件配置变化，不按模型画出不同“模型面积”；可单列硬件配置小面板。

同资源数字/概率方案作为一组，真实 GPU 对照作为另一组，标注各自工艺和测量/估计层级。GPU 无对应同边界面积时保留面积为空，不拿封装/板卡面积比较核心面积。100MHz 与 250MHz 的不同 PVT 版本也应分别标注，不能画成单纯频率扫描。

若本轮只有 Attention 加速器的参考图，可以借它的画法，但我们的“完整 decode”必须由实际系统结果提供，包括最终采用的 lm_head、格式转换与存储边界；不能把模块节省倍数直接外推为整机倍数。

**版式：** 四个对齐的小面板，至少时间和能量共享图例；优先保留绝对值，归一化结果作为辅助。DRAM占比高时保留它，在同图上另用芯片小计标注显示局部改进。

## 12 优先阅读顺序与绘图统一

如果只先打开六页：SOFA p.7（总架构），SparQ p.5（筛选和 gather），Ising SoftMax p.2（概率原理），DS-CIM p.3（随机计算阵列），SCIM p.7（局部成本），Tender p.11（跨模型结果）。随后用 FIGNA p.11 补整机能量分解。

统一颜色建议：蓝色表示数字矩阵计算，橙色表示概率计算，紫色表示随机服务，绿色表示存储；图例含义跨图保持。结构图用实线数据/虚线控制，结果图用点形或纹理区分方案，以便黑白打印。每张结果图只保留一个主要问题，避免同一颜色在 Fig.5 代表模型、到 Fig.7 又代表硬件类型。

**Fig.2、3、6 优先双栏**，因为需要显示数据路径和局部放大；Fig.1、4 优先紧凑。Fig.5、7、9、10 按子图数决定双栏，不为凑图号增加信息重复的面板。这里是绘图建议，不改动现有实验或论文模板。

## 13 文献版本与定位索引

下表标题、会议/期刊和图号用于快速复核。IEEE 正式版与 arXiv 版可能排版不同，下面页码均对应本次实际阅读版本。

| 文献 | 发表信息/阅读版本 | 本次主要参考位置 | 原文入口 |
|---|---|---|---|
| Probabilistic Computing with Binary Stochastic Neurons | BCICTS 2019；用户提供的 6 页 PDF | Fig.1 p.1，Fig.3 p.2 | [DOI](https://doi.org/10.1109/BCICTS45179.2019.8972719) |
| A 65-nm Digital Stochastic Compute-in-Memory CNN Processor With 8-bit Precision（SCIM） | JSSC 2025；作者公开的 13 页版 | Fig.2 p.2，Fig.9–10 p.7 | [作者 PDF](https://nanocad.ee.ucla.edu/wp-content/papercite-data/pdf/j83.pdf) |
| Softermax: Hardware/Software Co-Design of an Efficient Softmax for Transformers | DAC 2021；arXiv:2103.09301 的 7 页版 | Fig.3 p.3，Fig.4 p.4，Fig.5 p.6 | [论文](https://arxiv.org/pdf/2103.09301v1)、[作者机构的 DAC 记录](https://research.nvidia.com/publication/2021-12_softermax-hardwaresoftware-co-design-efficient-softmax-transformers) |
| SOFA: A Compute-Memory Optimized Sparsity Accelerator via Cross-Stage Coordinated Tiling | MICRO 2024；用户指定 arXiv:2407.10416v1，16 页 | Fig.6 p.5，Fig.11 p.7；表 III/IV p.11 为成本边界辅助 | [固定 v1 PDF](https://arxiv.org/pdf/2407.10416v1) |
| Accelerating Attention through Gradient-Based Learned Runtime Pruning（LeOPArd） | ISCA 2022；14 页版 | Fig.4 p.5（论文集 p.906），Fig.6 p.8（p.909），Fig.11 p.10（p.911） | [作者 PDF](https://cseweb.ucsd.edu/~hadi/doc/paper/2022-isca-leopard.pdf) |
| Tender: Accelerating Large Language Models via Tensor Decomposition and Runtime Requantization | ISCA 2024；15 页版 | Fig.6 p.7（论文集 p.1054），Fig.8 p.8，Fig.9 p.10，Fig.10–11 p.11 | [作者 PDF](https://jungi-lee.github.io/assets/pdf/isca24-tender.pdf) |
| FIGNA: Integer Unit-Based Accelerator Design for FP-INT GEMM Preserving Numerical Accuracy | HPCA 2024；用户提供的 14 页正式版 | Fig.6–7 p.4（论文集 p.763），Fig.13 p.10，Fig.15 p.11，Fig.17 p.12 | [DOI](https://doi.org/10.1109/HPCA57654.2024.00064) |
| SparQ Attention: Bandwidth-Efficient LLM Inference | ICML 2024；arXiv v6（2024-09-04），27 页 | Fig.1 p.1，Fig.4 p.3，Fig.5 p.5 | [PDF](https://arxiv.org/pdf/2312.04985v6)、[作者说明](https://graphcore-research.github.io/2024-07-17-sparq/) |
| ASCEND: Accurate yet Efficient End-to-End Stochastic Computing Acceleration of Vision Transformer | DATE 2024；用户 `71_pdf_upload.pdf`，6 页 | Fig.4 p.3，Fig.5–6 p.4；Fig.8 p.6 为参数扫描备选 | [会议公开 PDF](https://past.date-conference.com/proceedings-archive/2024/DATA/71_pdf_upload.pdf)、[arXiv](https://arxiv.org/abs/2402.12820) |
| DS-CIM: Digital Stochastic Computing-In-Memory Featuring Accurate OR-Accumulation via Sample Region Remapping for Edge AI Models | DATE 2026；7 页版，图号以用户正式 PDF 为准 | Fig.2 p.3，Fig.6 p.4，Fig.7 p.6 | [公开 PDF](https://arxiv.org/pdf/2601.06724)、[作者机构发表记录](https://researchportal.hkust.edu.hk/en/publications/ds-cim-digital-stochastic-computing-in-memory-featuring-accurate-/) |
| Energy-Efficient Parallel Ising SoftMax Engine for Transformer Attention Based on Asynchronous SOT-P-Bits | IEEE EDL 2026；用户提供的 4 页作者版 | Fig.2–3 p.2，Fig.4–5 p.3 | [DOI](https://doi.org/10.1109/LED.2026.3691358) |

本次核对了各参考图的原页；原 PDF 和截图仅作阅读缓存，不随文档上传。source/页数/文件 SHA-256 和逐图核对位置放在同目录小型 `SOURCES.json`，用于固定图号版本。本文件不产生新模型、训练、RTL、EDA 或 TLM 结果。

[pbit]: https://doi.org/10.1109/BCICTS45179.2019.8972719
[scim2]: https://nanocad.ee.ucla.edu/wp-content/papercite-data/pdf/j83.pdf#page=2
[scim9]: https://nanocad.ee.ucla.edu/wp-content/papercite-data/pdf/j83.pdf#page=7
[sofa11]: https://arxiv.org/pdf/2407.10416v1#page=7
[tender6]: https://jungi-lee.github.io/assets/pdf/isca24-tender.pdf#page=7
[tender8]: https://jungi-lee.github.io/assets/pdf/isca24-tender.pdf#page=8
[tender9]: https://jungi-lee.github.io/assets/pdf/isca24-tender.pdf#page=10
[tender10]: https://jungi-lee.github.io/assets/pdf/isca24-tender.pdf#page=11
[leopard4]: https://cseweb.ucsd.edu/~hadi/doc/paper/2022-isca-leopard.pdf#page=5
[leopard6]: https://cseweb.ucsd.edu/~hadi/doc/paper/2022-isca-leopard.pdf#page=8
[leopard11]: https://cseweb.ucsd.edu/~hadi/doc/paper/2022-isca-leopard.pdf#page=10
[sparq1]: https://arxiv.org/pdf/2312.04985v6#page=1
[sparq5]: https://arxiv.org/pdf/2312.04985v6#page=5
[softermax3]: https://arxiv.org/pdf/2103.09301v1#page=3
[softermax4]: https://arxiv.org/pdf/2103.09301v1#page=4
[softermax5]: https://arxiv.org/pdf/2103.09301v1#page=6
[ising3]: https://doi.org/10.1109/LED.2026.3691358
[ising4]: https://doi.org/10.1109/LED.2026.3691358
[ising5]: https://doi.org/10.1109/LED.2026.3691358
[dscim2]: https://arxiv.org/pdf/2601.06724#page=3
[dscim6]: https://arxiv.org/pdf/2601.06724#page=4
[dscim7]: https://arxiv.org/pdf/2601.06724#page=6
[figna7]: https://doi.org/10.1109/HPCA57654.2024.00064
[figna13]: https://doi.org/10.1109/HPCA57654.2024.00064
[figna15]: https://doi.org/10.1109/HPCA57654.2024.00064
[figna17]: https://doi.org/10.1109/HPCA57654.2024.00064
[ascend4]: https://past.date-conference.com/proceedings-archive/2024/DATA/71_pdf_upload.pdf#page=3
