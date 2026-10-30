# pJ级、小面积p-bit采样单元：实测证据、Extropic假设与本项目选择

调研日期：2026-10-30。范围为室温、可电控概率的采样单元；“便宜”首先指合格输出的能耗、面积与服务速率，不代表已核实采购价格。本文是文献与原始附件核查，没有新流片、Spectre、RTL、PPL或工艺PPA实验。仓库状态按本次固定快照读取；文献结果保留原工艺，不套用本项目面积×0.81规则。

## 1. 可以确认什么

**有pJ级的真实CMOS采样器，也有很小的真实p-bit原型。最接近“pJ且小”的公开候选是65nm SPAD方案；常规低压CMOS方案能耗证据更直接，但已发表实例的面积较大。Extropic的小随机源有芯片依据，其Z1/LLM能效数字仍属于模型推算。**

- **优先复核的小单元：**Whitehead等2024年的65nm SPAD/VRSC，作者表3列出1 pJ/flip、81 μm²、最高50 MHz。有雪崩高压、偏置和光照条件，尚不能把这一行等同于可直接移植的完整阵列宏。[R01]
- **低压CMOS实测基准：**Jeon与Lim 2026年的180nm噪声p-bit，1.8 V、50 MHz更新、6.95 pJ/bit、6551 μm²，支持32档概率。其数字包含本地随机源、比较和概率控制核心，网络/权重和FPGA另计。[R02]
- **Extropic值得认真看：**其补充材料展示约3×3 μm²的片上RNG和可调概率电路；主文给出约100 ns的实测相关衰减。小型随机单元不是凭空假设。其超低能耗、规模化连接和完整模型收益需要分层判断。[R04][R05]
- **sMTJ可列为器件合作路线：**2026年已有完整CMOS集成单元，但“3T+1MTJ”“裸器件ns翻转”和“完整单元fJ、ns、低变异”还不是同一条实测证据。[R07][R08]

## 2. 本文比较的输出到底是什么

| 输出/任务 | 所需能力 | 不足以证明什么 |
|---|---|---|
| 无偏原始bit | P(1)约0.5，明确时间和跨路相关性 | 不能直接替代8位均匀随机数或可调Bernoulli采样器 |
| Bernoulli(p) | 指定p后输出0/1，给出概率误差、动态输入建立时间和输出负载 | 只有p=0.5通过NIST，不能证明所有p的准确性 |
| sigmoid/tanh p-bit | 输入局部场I，均值近似sigmoid/tanh；可能连续演化 | 输入已给定的核心面积不包含形成I所需的权重、求和和偏置电路 |
| 耦合网络的有效样本 | 正确联合分布、收敛/混合、有效样本量及读出 | 单元翻转率不等于整网独立样本率 |

还要区分：一次物理翻转、一次时钟更新、一个随机字、一个可用独立bit、一轮Gibbs sweep、一个最终模型样本。它们不能共用未说明的“sample”分母。

## 3. 逐项证据与可用性

NR表示本轮所读原文没有给出可用于此比较的同口径数值，不代表该领域从未报道。

| 方案与原文 | 原文给出的能耗/功率 | 面积 | 速度与概率控制 | 证据与我们的判断 |
|---|---|---|---|---|
| **65nm SPAD/VRSC，2024** [R01] | **1 pJ/flip**，作者表3口径 | **81 μm²**，作者表3；不是整个系统 | 最高50 MHz；概率/温度可调 | 有流片与测量。表2击穿电压9.7/11 V；光照与偏置参与优化，不能假定最高速点完全依靠暗计数。优先核查小面积候选。 |
| **180nm噪声CMOS，2026** [R02] | **6.95 pJ/bit**，50%输出、1.8 V；派生核心功率347.5 μW | **6551 μm²**，活动核心 | 150 MHz时钟实现50 MHz更新；5位/32档控制 | 流片实测；含噪声源、CDS、校准比较器、本地控制/时序。中心固定码测能耗；芯片间概率最大偏差达14.08个百分点。系数存储、求和和系统接口另计。 |
| **180nm混沌CMOS，2025** [R03] | **4.26 pJ/bit**、212.9 μW、1.8 V | **28800 μm²**，单混沌振荡器 | 50 Mb/s；配合8位CDAC设概率 | 单振荡器实测；不要把其数值扩成包含8位概率设定/FPGA的整机能耗。能耗可参考，但面积不适合直接作为高密度阵列首选。 |
| **Extropic实物RNG与DTCA模型，2026** [R04] | 约**400 aJ/bit的RNG设计值**；**2 fJ/conditional update**为DTCA单元模型 | 实物RNG约**3×3 μm²**，补充图S10 | 实测可调概率；相关衰减约100 ns | 图S9给简化电路，实际需补鲁棒性电路。面积/波形有实物依据，超低能耗和全网成本属于设计/PDK模型；权重、邻接线、时钟、外部接口须分别核对。 |
| **Extropic Z1T的Z1预算，2026** [R05] | **13 fJ/sample**为理论芯片估计 | 本报告未给可比的Z1单元完整宏面积 | 模型按50 MHz采样、每层32次等设置 | 这是后续系统预算，不是上一行9 μm²单元的全部指标在同一硅片上同时实测。原文排除dense logits和芯片间数据移动，芯片数量也未建模。 |
| **CMOS集成3T-1MTJ，2026预印本** [R07] | 实测约52–55 μW；**4.9 fJ/flip属于预测点** | 3T+1MTJ为结构计数；可移植完整单元版图面积NR | 最快实物平均dwell约68.9 μs；预测点1 flip/ns | Fig.4明确区分已集成实测与绿色P4预测。是重要集成进展，不能以P4作为已测fJ/ns单元。 |
| **130nm CMOS+sMTJ，2026预印本** [R08] | 同口径完整E/sample NR | 测试片5.2×3.6 mm²含多种结构；单元完整面积NR | 完整单元输出0–1.8 V；多数sMTJ的dwell在ms量级 | 有单片集成。含cascode、可变阈值级和逆变器，不能套用3T结构或用整片面积除150当作p-bit面积。 |
| **sMTJ与数字p-bit对比，2024** [R09] | LFSR p-bit约145 fJ、Xoshiro p-bit约293 fJ；sMTJ约2 fJ为引用估计 | 5150/11546个晶体管与约4器件当量的比较 | 数字估算采用1 GHz输入活动等条件 | ASAP7综合/HSPICE，不是该7nm芯片实测；32位PRNG、256×32位LUT的具体设计不是所有数字随机源的下界。 |
| **130nm ASIC+VCMA-MTJ，2025正式版** [R11] | 裸MTJ写脉冲约0.43 pJ、读约1.3 fJ；原型ASIC+控制板395 mW，RNG板9 mW | 1143个逻辑p-bit的设计区占用约3.11 mm²；非裸MTJ单元面积 | 裸器件10 ns写脉冲；系统有控制/访问瓶颈 | 不是0.43 pJ的完整可调p-bit；板级数值还排除外部脉冲源。逻辑更新使用随机调度和16位随机数/LUT等步骤。 |
| **CT-FET同片p-bit/突触，2026** [R10] | 文中器件/电阻/栅相关平均功率约1.25 μW；完整更新E NR | 同片器件和阵列实现；完整p-bit宏面积NR | +10.7 V、−9.6 V各100 μs，再读100 μs | 共集成有价值；仍有外部比较器、门极驱动和慢周期。μW不能直接改写为pJ/bit。 |
| **暗计数pgSPAD，2025** [R12] | 同口径完整E/bit NR；减少雪崩次数是机制，不是已测pJ数 | 0.35 μm工艺64×64器件阵列；完整服务宏面积NR | 本次demo为kHz量级，概率可由周边栅电压调整 | 可减少光源依赖；大网络结果为器件校准后的仿真。不要移入65nm VRSC的50 MHz或1 pJ指标。 |
| **biristor，2024** [R13] | 582 nW@4.4 V；原文明确**排除比较器** | 器件结构简单，但完整可移植p-bit单元面积NR | 串电阻+比较器形成可调概率输出 | 测量与CMOS兼容性有依据；“几百nW”尚不足以证明高速、完整外围的pJ采样。 |
| **440-spin混合信号CMOS，作者稿2025** [R14] | 本轮作者稿未给可采用的完整每更新能耗 | **0.44 mm²/440 spins**；算术摊销约1000 μm²/spin | 65nm；电流求和、tanh、DAC和比较器 | 随机数实际来自LFSR/PRBS。是有意义的数字/混合对手，不应归为本征热噪声随机源。期刊版2026的摘要确认440 spins和0.44 mm²，细节以本轮读到的作者稿为限。 |

两点补充：

1. **约3.6 nJ/flip的量级核查。**仅把[R07]最低实测功率52 μW与最快dwell 68.9 μs作乐观交叉组合，P×τ约3.58 nJ；这不是同一工作点的实测能量，也不是独立样本能量。它说明为什么不能把该原型的集成成功等同于预测的4.9 fJ/flip。
2. **裸器件小，不等于完整p-bit小。**磁性器件面积、晶体管数量、光电二极管光敏区、模拟处理电路和整个服务宏是不同边界。表中保留作者边界，没有把缺失外围填0。

## 4. Extropic究竟做了什么，有哪些依据

### 4.1 最接近可以复现的公开电路

[R04]补充K与图S9不是只有理想Bernoulli黑盒：一个亚阈值CMOS逆变器产生高斯噪声，后面四级逆变器逐渐将其数字化，控制电压调节输出偏置。这个**简化示例约10个MOS**；作者明确说真实电路还要增加对工艺变化和漂移的鲁棒性处理。简化电路的约75 aJ/bit基于每节点800 aF等假设，不能拿来给我们自己的比较器定价。

图S10给出封装测试芯片和显微照片，标注每个RNG约3×3 μm²。主文报告可调sigmoid形状与约100 ns的相关衰减。与此同时，主文的制造变异能耗散点来自PDK仿真；Methods的2 fJ单元能耗是随机源、偏置、局部通信和时钟的建模和。实测信号经过额外放大缓冲链后才送到示波器；亚阈值小核心接入我们标准逻辑和指定负载时，读出、必要电平转换与驱动必须另算。[R04]

[R06]另外公开了CMOS高斯随机源的测量与物理模型，并有原始数据入口。这能支撑“CMOS噪声可被工程化利用”；它是模拟随机源研究，不能单独充当完整Bernoulli/LLM加速器的PPA验收。

### 4.2 对Z1T结论应怎样表述

[R05]承认使用X0相似p-bit实验来支撑后续Z1能耗估计。它给出的13 fJ/sample、Z1T每token能耗和速度是系统模型的一部分。其成本边界排除了dense logits与Z1–FPGA数据移动，且假设模型并行铺开但没有计算所需芯片数量。

因此，**小型CMOS随机源有实物依据；“我们也可获得相同能耗、50 MHz有效独立采样以及完整LLM收益”需要我们自己的电路与系统验证。**13 fJ不是可以不加条件填进TLM的实测常数。DTCA的2 fJ、Z1T的13 fJ和RNG核心约0.4 fJ也不应相互替换。

## 5. 对p-bit for LLM的具体含义

### 5.1 先固定接口，才能选器件

本项目至少有三种不同需求：

- **给数字随机服务供种子。**较慢的物理源可以通过缓冲与合格调理给PRNG补种；下游高速输出仍需承担PRNG、分发和相关性验证成本。物理源速度不等于整个数字服务吞吐。
- **给随机乘法/短流直接供随机阈值。**需要明确每拍多少路、每路几位、允许哪些共享/重放。一个50/50 p-bit只产生一个二值状态；组合成多位均匀数还要验证联合分布和时间相关性。
- **直接实现sigmoid/tanh条件采样。**可以省部分数字非线性，但必须把概率/局部场变成合格的电压或电流。器件的自然sigmoid、目标Bernoulli(p)、有限码精度与数字随机比较的映射可能不同，需要校准或硬件感知训练。

不要把某个论文的10位输入、32位随机数、大LUT数字p-bit，强行当作本项目简单三/五位随机阈值端口的最低数字成本；也不要用裸物理bit的价格覆盖多位阈值生成。[R09]

### 5.2 采样能量应该怎样计

建议把服务边界写成：

`E_usable = (E_entropy + E_bias_or_DAC + E_readout + E_clock + E_conditioning + E_distribution + E_buffer + E_calibration_amortized) / N_usable`

其中电源升降压损失、持续静态电流和等待时间进入相应分项；按需使用时不能仍按峰值翻转率摊销静态功耗。原生耦合p-bit算子还须单列权重存储、局部场求和、反馈和调度。

对固定输入、近似平稳序列，有限N时均值方差的相关性修正为：

`tau_int(N) = 1 + 2 * sum_{k=1}^{N-1} (1-k/N) * rho(k)`

`N_eff = N / tau_int(N)`

这里N_eff针对所估计的观测量，并非对任意下游任务的通用认证。大N、指数自相关rho(k)=exp(-k*Delta/tau)时，tau_int近似为`(1+rho(1))/(1-rho(1))`。例如**假设**tau=100 ns、每20 ns读取，修正约10.03；这只是说明过采样不能免费制造独立样本，不是给Z1实测套上的10倍惩罚。[R04]的原型相关时间与后续Z1估计必须分开。

### 5.3 一个有边界的面积/功率量级

下表只做“1024个副本、每个副本按作者所列50 MHz事件速率活动”的线性算术，排除阵列外围与互连，不保证事件独立，亦不是我们的55nm PPA预测。

| 作者单元口径 | 1024副本的核心面积 | 按所列速率的核心功率 | 用途 |
|---|---:|---:|---|
| SPAD：81 μm²、1 pJ/flip、50 MHz | 0.082944 mm² | 51.2 mW | 表明小面积pJ单元的潜在阵列量级；高压/光照/外围仍须补 |
| 噪声CMOS：6551 μm²、6.95 pJ/bit、50 MHz | 6.708224 mm² | 355.84 mW | 低压CMOS完整本地核心的较保守文献参照 |
| 混沌振荡器：28800 μm²、4.26 pJ/bit、50 Mb/s | 29.4912 mm² | 约218.1 mW | 显示pJ级并不自动等于面积便宜；4.26为舍入能耗 |

不把Extropic的9 μm²实物面积与13 fJ后续估计拼成第四个“已测阵列”点。不把上述外部65nm面积乘0.81。

## 6. 建议给我们项目保留的三条路线

1. **近期架构基线继续使用有实价的数字服务，同时单列物理种子入口。**让当前数字随机/分层方案承担真实操作和分发成本，按Issue95的接口保留替换能力。物理源供种子和直接逐拍采样分开验收。
2. **纯CMOS物理p-bit的优先研究对象：噪声节点＋读出/概率控制。**以Extropic图S9作为机制原型、[R02]作为较完整低压测量基准；对自己的工艺、输出负载和概率范围重新做噪声瞬态、PVT/失配、功率积分与面积。既有Issue152/184仍由原负责人推进，本调研不启动或接管那些仿真。
3. **另列SPAD小面积路线与sMTJ器件路线。**SPAD先确认工艺可用性、雪崩偏置和暗场实际速度；sMTJ先取得适配工艺的器件分布及读出验证。两者都适合条件化预算和后续器件合作，不直接取代现有主预算。

若现在必须在架构探索中给物理采样器一个数，建议做0.1/1/10 pJ每合格输出的**假设敏感性扫描**，并独立扫描服务率、面积、相关性/有效率与外围。0.1 pJ是探索目标；1 pJ有SPAD文献支点；10 pJ接近较完整CMOS单元量级。三者都不自动成为本工艺实测或已批准默认值。既有数字实价是共同对手，扫描要回答多少成本以内能赢，而不是先假定它一定能赢。

## 7. 下一轮真正能缩小不确定性的验收项

| 项目 | 最小应交付证据 |
|---|---|
| 输出合同 | 输入电压/概率码、更新率、动态建立时间、有效负载、输出逻辑电平 |
| 能耗 | 所有核心电源与偏置支路的积分，固定/变化概率、活动/等待、校准成本分开 |
| 面积 | 噪声核心、比较/锁存、DAC/参考、校准、分发和耦合各自版图或同工艺综合依据 |
| 统计 | 多概率点与多器件/种子、时间戳、ACF、跨路相关、概率误差、漂移和有效样本量 |
| 系统映射 | 每个LLM模块实际要多少位/路/拍；FIFO、共享、重放、等待和额外存储 |
| 数字对照 | 相同概率/精度/质量目标、相同可用吞吐与输出负载下的数字成本 |

NIST测试和单点50%校准可以作为诊断，不能代替这些合同，也不能单独证明IID或LLM质量。单元指标合格后才有依据更新完整算子和端到端预算。

## 8. 原始来源与阅读依据

- **[R01]** Whitehead, Oh, Theogarajan. *CMOS Single-Photon Avalanche Diode Circuits for Probabilistic Computing*. IEEE JXCDC 10, 49–57 (2024). [DOI](https://doi.org/10.1109/JXCDC.2024.3452030)，[机构作者稿](https://escholarship.org/content/qt38h7m5pc/qt38h7m5pc.pdf?t=sms9hq)。依据正文SPAD/电路设计、V节与表2/3；作者稿表3在PDF第22页。全文工具可读，本机直接下载403，未编造PDF哈希。
- **[R02]** Jeon, Lim. *A Noise-Based CMOS Probabilistic Bit for Combinatorial Optimization Problems*. Electronics 15(12), 2510 (2026). [原文](https://www.mdpi.com/2079-9292/15/12/2510)。依据出版社原文的电路描述与测量第4节、图15/16、表1/2；直接下载受限，数值通过出版社索引正文交叉核对。
- **[R03]** Lee et al. *Correlation free large-scale probabilistic computing using a true-random chaotic oscillator p-bit*. Scientific Reports 15, 8018 (2025). [原文](https://doi.org/10.1038/s41598-025-93218-8)。读取PDF正文与测量/实验设置；4.26 pJ、28800 μm²均限于单混沌振荡器口径。
- **[R04]** Jelinčič et al. *An efficient probabilistic hardware architecture for diffusion-like models*. npj Unconventional Computing 3, 30 (2026). [主文](https://doi.org/10.1038/s44335-026-00075-3)，[补充材料](https://media.springernature.com/original/springer-static/esm/art:10.1038%2Fs44335-026-00075-3/MediaObjects/44335_2026_75_MOESM1_ESM.pdf)。读取主文RNG测量与Methods能耗模型、补充E/K；视觉核对S9/S10，补充PDF第25/26页。
- **[R05]** Extropic. *Z1T: Sparse Transformer-Like Models for Probabilistic Hardware* (2026-09-04). [官方报告](https://extropic.ai/writing/z1t)。依据Performance and efficiency estimates及其排除项；保存本次公开HTML字节哈希。
- **[R06]** Freitas et al. *Taming nonequilibrium thermal fluctuations in subthreshold CMOS circuits*. Phys. Rev. Applied 25, 034061 (2026). [原文](https://doi.org/10.1103/5l2z-3f1h)，[开放正文](https://harvest.aps.org/v2/journals/articles/10.1103/5l2z-3f1h/fulltext)，[原始数据说明](https://doi.org/10.5281/zenodo.18636981)。读取随机源模型、能耗/相关时间定义及实验设置；没有下载7.1GB原始数据或独立重放测量。
- **[R07]** Zhang et al. *Experimental Demonstration of an On-Chip CMOS-Integrated 3T-1MTJ Probabilistic Bit—A P-Bit* (2026预印本). [作者稿](https://arxiv.org/abs/2604.05191)。读取测量、Fig.4与预测假设；视觉核对PDF第8页。
- **[R08]** Yoon et al. *CMOS-integrated superparamagnetic tunnel junction-based p-bit* (2026预印本). [作者稿](https://arxiv.org/abs/2604.14446)。读取完整单元结构、芯片结构与sMTJ测量；没有把独立裸器件ns文献当成本片实测。
- **[R09]** Singh et al. *CMOS plus stochastic nanomagnets enabling heterogeneous computers for probabilistic inference and learning*. Nature Communications 15, 2685 (2024). [原文](https://doi.org/10.1038/s41467-024-46645-6)。读取Fig.4、ASAP7/HSPICE与随机质量相关讨论；2 fJ来自其引用估计，本文不将其升级为实测。
- **[R10]** Park et al. *CMOS compatible probabilistic computing hardware with cointegrated reconfigurable p-bits and synapse arrays*. Nature Communications 17, 5110 (2026). [原文](https://doi.org/10.1038/s41467-026-71906-x)。读取p-bit操作时序、外部比较器、功率与4节点硬件/20节点仿真边界。
- **[R11]** *An integrated-circuit-based probabilistic computer that uses voltage-controlled magnetic tunnel junctions as its entropy source*. Nature Electronics 8, 784–793 (2025). [正式版](https://doi.org/10.1038/s41928-025-01439-6)，[2024预印本](https://arxiv.org/abs/2412.08017)。分别读取并保留版本；文中主要数值已在正式版System design中核对。
- **[R12]** Sajal et al. *Probabilistic Bits Using Perimeter-Gated Single Photon Avalanche Diodes*. IEEE Electron Device Letters 46(8), 1417–1420 (2025). [原文](https://doi.org/10.1109/LED.2025.3577944)。读取既有托管全文，区分阵列测量、kHz演示和大网络仿真。
- **[R13]** Kim et al. *Fully CMOS-Based p-Bits with a Bistable Resistor for Probabilistic Computing*. Advanced Functional Materials 34, 2307935 (2024). [原文](https://doi.org/10.1002/adfm.202307935)。读取既有托管全文的电路、Table1与比较器功率排除项。
- **[R14]** Jhonsa et al. *A CMOS Probabilistic Computing Chip With in-situ Hardware Aware Learning* (2025作者稿). [作者稿](https://arxiv.org/abs/2504.14070)。读取3页作者稿的LFSR/PRBS与电流模式实现。[2026期刊版元数据/摘要](https://ieeexplore.ieee.org/document/11503224/)的DOI为10.1109/JXCDC.2026.3689506，标题/作者列表有所变化；本次不声称已逐项核完期刊全文。

随附[PAPER_CATALOG.json](PAPER_CATALOG.json)、[SOURCE_MANIFEST.json](SOURCE_MANIFEST.json)与[VALIDATION.json](VALIDATION.json)。来源清单区分下载原字节哈希与仅工具可读来源，不上传原论文、工艺资料、私人Zotero状态或认证信息。本文不依赖二手评论来确定技术数值。Zotero维护在本机另留复用核对与可恢复待办，未完成写入不视为收录完成。
