# p-bit LLM 推荐文献原文阅读总结与设计建议

核对日期：2026-10-18。对应 Issue [#26](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/26)，负责人 `jieruiz`。

本文件对应用户指定的 `PBIT_LLM_RECOMMENDED_READING_ZH_20261018.md`，按原清单顺序覆盖全部17项。原清单保持不变；其仓库交付见 [PR #24](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/24)。本次阅读检查了可取得原文的方法、架构图、主要评估和限制，而不是只整理题名与摘要。下文将“原文核实”和“对本项目的判断”分开；建议不代表已经实现或测得收益。

## 1. 先给出结论与访问情况

**17项中，16项取得了全文或完整官方技术资料；1项仍只能读到摘要：第14篇 Stochastic Nanomagnets as Current Digitizers for Efficient Probabilistic Machine Learning。** APS要求授权，MIT官方页只有摘要；本次未找到可正常取得的作者公开全文。因此不对它的具体电路、采样数或能效作全文级判断。[APS入口](https://journals.aps.org/prapplied/abstract/10.1103/s86j-5jcr)、[MIT介绍](https://www.rle.mit.edu/stochastic-nanomagnets-as-current-digitizers-for-efficient-probabilistic-machine-learning/)

p-PIM 的部分网页/PDF入口出现验证码，但通过官方 Europe PMC 取得主文XML及补充材料，已核实关键图和补充实验；不属于全文缺失。FIGNA使用用户本地IEEE全文。SANTA清单链接是v1，本次另读了用户本地v2，以下关于整模型decode的数字明确来自v2，不能混用版本、章节和表号。

综合这些原文，我对当前路线的判断是：**继续研究随机FFN有价值，但最有希望的是短流、就地编码、共享与精确归约的组合；Attention更应优先让采样减少真实KV读取。要求整个网络始终保持0/1，并不自动带来更好的能效。** 原生p-bit器件参与激活/读出的路线值得保留，不过它与普通PRNG加比较器的数字随机乘法需要分别评估。

| # | 文献/资料 | 本次访问 | 已验证到什么层级 | 对我们的主要价值 |
|---|---|---|---|---|
| 1 | uGEMM，ISCA 2020 | 全文 | 算子、RTL综合、小型MLP | 条件更新、流式乘加、动态操作数 |
| 2 | SASCHA，CASES/TCAD 2022 | 全文 | 综合、调度模型、经训练CNN | 随机乘法配精确二进制累加 |
| 3 | DS-CIM，DATE 2026 | 全文 | 版图后宏、CNN/LLM误差注入 | 双流二维采样、SRR、SRAM与复用 |
| 4 | p-PIM，Advanced Science 2026 | 主文＋补充 | 器件/FPGA硬件在环、SPICE预测 | 原生随机器件与非线性融合 |
| 5 | SANTA，arXiv 2605.01910 | v1全文＋本地v2 | LLM质量、GPU内核及v2整模型decode | 在读取V前完成选择，分块并行采样 |
| 6 | Extropic Z1T / Z1T-0 | 官方全文＋代码/配置 | 模型发布、硬件映射及效率估算 | 为连接度与tanh重新设计模型 |
| 7 | VLSI 2024事件相机SCIM | 全文 | **12nm芯片实测** | 原位SNG、共享、ADC-less读出 |
| 8 | SC-CNN / BISC后续，2020 | 全文 | 综合、CNN精度搜索/微调 | 混合表示、确定性流与存储组织 |
| 9 | Dither computing，ARITH 2021 | 全文v2 | 理论、数值和小型网络 | 确定性主体加随机余量 |
| 10 | P2LSG，ASP-DAC 2024 | 全文v2 | 发生器综合、标量/图像测试 | 低成本低差异序列 |
| 11 | ICCAD 2018低差异计算 | 全文 | 多维乘法数值实验、综合 | 一维表示与二维乘积覆盖的区别 |
| 12 | tubGEMM，2024预印本 | 全文v1 | 精确整数算子、后综合PPA | 无RNG的temporal-unary对照 |
| 13 | ASTRA，GLSVLSI 2025 | 全文 | 光器件/电路/架构模拟、OPT-350质量 | 光学乘法加电荷域归约 |
| 14 | Current Digitizers，PR Applied 2025 | **仅摘要** | 摘要称器件与MNIST验证，细节未核实 | 可能降低模拟CIM的ADC开销，待全文 |
| 15 | FIGNA，HPCA 2024 | 用户本地全文 | 综合功耗、SystemC、语言模型数值 | BF16/INT混合数字基线与转换摊销 |
| 16 | NeuPIMs，ASPLOS 2024 | 全文 | NPU/DRAM联合模拟、GPU基线 | 数据布局、资源并行与批间调度 |
| 17 | LLMCompass，ISCA 2024 | 全文 | GPU/TPU校验的时延与面积模型 | 分块搜索、存储层次与校准方法 |

“全文可读”不等于完整复现。未公开的种子、设计文件、工艺条件，以及未测的整机边界仍按各节注明。本次没有运行新的PPL、训练、RTL或PT。

## 2. 优先六项：读到了什么，怎样用于我们

### 2.1 uGEMM: Unary Computing Architecture for GEMM Applications

ISCA 2020。[作者全文](https://jsm.ece.wisc.edu/docs/wu-isca2020.pdf)、[UnarySim](https://github.com/diwu1990/UnarySim)。核对重点：§IV、Fig.3–4、§V/Table V–VI、§VI/Fig.10；作者PDF第4–7、9–12页。

**原文核实。** uMUL-IS从第二路流估计概率，uMUL-ST使用预装二进制值；Sobol发生器在第一路有效位到达时才推进，再执行AND。这与两路独立IID流直接AND不同。缩放/非缩放加法器还需要计数、状态和饱和处理，非缩放输出也有范围限制。共享发生器要求相应条件更新同步。硬件为45nm综合；其MLP的98.6%是相对8位基准的准确率比例，绝对准确率为94.7%，不是LLM结果。

**对本项目的判断。** 它值得用于建立动态QK的逐周期参考，但应完整移植“何时更新、保留什么状态、如何读出”的协议。不能只拿一个AND替换乘法，再假定其短流精度自然成立。我们应继续保留宽二进制部分和作为对照，避免流式非缩放输出的饱和掩盖FFN误差。

### 2.2 SASCHA – Sparsity-Aware Stochastic Computing Hardware Architecture for Neural Network Acceleration

CASES/TCAD 2022。[作者全文](https://nanocad.ee.ucla.edu/wp-content/papercite-data/pdf/j72.pdf)。重点：§IV-A、§V–VII，Fig.10–13、18及Table II；PDF第3、6–11页。

**原文核实。** GEO先OR再计数，GEO+取消OR而精确统计乘积位；共享种子对经过乘法误差选择。架构离线平衡稀疏权重组，以异步调度和带索引的部分和合并减少空算。非切片使用64拍；位切片的高/低部分使用64/8拍。CNN训练包含剪枝和随机误差；硬件为28nm综合、CACTI和调度模型，面积表不含存储，并假设带宽足够。

**对本项目的判断。** **随机乘法＋精确计数是一条有明确文献依据的路线，不能因为存在加法树就判定方案失败。** 真正应检查的是短流能否抵消计数器、转换和存储成本。其90%级权重稀疏收益不适用于未经剪枝的稠密LLM；我们也不能继承“带宽足够”的假设。调度标签、索引、合并和回写都要进入事务与PPA。

### 2.3 DS-CIM: Digital Stochastic Computing-In-Memory Featuring Accurate OR-Accumulation via Sample Region Remapping for Edge AI Models

DATE 2026。[公开全文v1](https://arxiv.org/html/2601.06724v1)。另核用户本地7页PDF，重点§III-A–D、§IV-B及Fig.2、4–6、Table II–III。

**原文核实。** SRAM存二进制权重，激活和权重分别与两个随机轴比较，跨行共享。SRR右移并重映射乘积区域，使组内事件互斥；对OR4/16/64，激活与权重均右移，分别丢弃各自1/2/3位低位。因此它解决的是重映射后的OR碰撞，仍有量化和有限采样误差。64个输入上下文复用廉价MAC与权重/SNG，提高吞吐；单向量串行采样不会自动缩短64倍。论文还采用4拍缓存后更新宽累加器。

版图后40nm宏与LLM评估是两层证据。LLaMA-7B使用FP8到INT8对齐及256拍误差注入；平均准确率从66.0%到62.6%或58.8%，未报告WT2 PPL。64拍3566.1 TOPS/W是归一化宏峰值，不能作为8位完整LLM系统能效。[原文§IV–V](https://arxiv.org/html/2601.06724v1)

**对本项目的判断。** 简单OR2/4/8不是SRR的复现。下一步应将普通OR和带重映射OR分开，并明确丢低位、符号修正、二维序列与共享条件。其SRAM单元/计算线经过定制；“普通SRAM读出后接逻辑”是另一种实现，需要自己的读能量、保持方式和布线成本。缓存累加是否省能也应以我们的PT为准，不能直接套论文的21.8%。

### 2.4 Hardware Acceleration of Stochastic Neural Networks Enabled by Bit-Cell Level Co-Design of Magnetic Tunnel Junctions（p-PIM）

Advanced Science 2026，DOI 10.1002/advs.78111。[主文入口](https://pmc.ncbi.nlm.nih.gov/articles/PMC13626169/)、[官方全文XML](https://www.ebi.ac.uk/europepmc/webservices/rest/PMC13626169/fullTextXML)、[官方补充包](https://www.ebi.ac.uk/europepmc/webservices/rest/PMC13626169/supplementaryFiles)。重点：主文架构及实验图，补充S1–S5、Table S1–S4。

**原文核实。** MP-SMC把稳定磁存储、随机磁器件和比较结合；阵列利用XNOR、列求和及随机激活完成随机神经网络。64×64硬件在环实际由单个sMTJ时间复用并结合FPGA实现，256拍/4位MNIST为96.52±0.15%。补充S2.3使用数字加法树和实测曲线LUT模拟列累加/激活；S5的器件数据按100Hz采样后缓存复用。FPGA的50MHz不是器件以50MHz输出独立样本的实测。SPICE用预测工艺模型，能效/面积边界不含完整偏置、路由、I/O和控制。

**对本项目的判断。** 它支持“让器件直接承担概率变换”的研究方向，但不能证明LLM已可用或完整阵列已集成。我们的器件模型应有独立样本间隔、自相关、输入到概率曲线、偏置/读出成本；单报一个p-bit能量不足以接入TLM。sigmoid型激活也不自动等于SiLU，更不等于整个SwiGLU。

### 2.5 Stochastic Sparse Attention for Memory-Bound Inference（SANTA）

2026预印本。[清单v1](https://arxiv.org/html/2605.01910v1)、[本次交叉核对v2](https://arxiv.org/html/2605.01910v2)、[官方代码](https://github.com/OPUSLab/SANTA)。本地v2日期2026-06-03，27页。重点§2–3.6、§5及附录；以下表号取v2。

**原文核实。** 基础方法按softmax分布抽取V行，gather后平均，仍先算QK。独立分层具有方差不增保证；systematic只用一个随机偏移，但没有一般方差减少保证。`prop`先存标量分数/块质量、全局分配预算、再并行读取选中V；`flash`使用各块固定预算，最后按质量合并，省同步但浪费样本。[方法](https://arxiv.org/html/2605.01910v2)

v2 §3.5/Table 3新增整模型decode：RTX6000 Ada、BF16 Llama-3.1-8B、batch6、约30k提示、生成2048token，`prop`128样本/`flash`2048样本，decode分别加速1.229/1.250倍；prefill保持准确。约1.5倍则是注意力内核口径。§5/Table 7–9明确GQA并集：一例K访问从每头67.5%变为组内97.9%，共享代表query降到84.7%；联合PV采样后V可降到10.8%。这是特定模型质量实验，不是通用比例或ASIC能耗实测。[v2实验](https://arxiv.org/html/2605.01910v2)

**对本项目的判断。** 这是最应立即落实到Attention调度中的文章。顺序应为“形成选择信息→产生地址→合并/去重→读选中V→累加”，不能先读完整V再模拟采样。prefill、decode分别统计；K特征筛选和V行选择也分别统计。我们自己的Ising/筛选路径还需要证明分布、混合时间和有效样本数，不能继承SANTA的独立采样保证。

### 2.6 Extropic Z1T / Z1T-0

2026官方技术发布，非同行评审论文。[技术说明](https://extropic.ai/writing/z1t/)、[固定版本配置](https://huggingface.co/Extropic-AI/Z1T-0/blob/b5c244cee26b7f4e613b9ddbe83e83b2962ab2e1/config.json)、[固定版本组件](https://github.com/extropic-ai/sparse-transformers/blob/8c0f7e66cfea794f70e81fcf289e179d9f58ed0d/research/z1t/components.py)。重点：encoding、model architecture、performance and efficiency estimates。

**原文核实。** 模型用稀疏tanh-linear、Dynamic Tanh和GCA；代码对应AFT-conv系的局部卷积、历史累计与门控，不走标准QK-softmax。HF发布配置为4层、宽12288、序列256、fan-in4，效率示例则为4层、宽512、上下文1024；两者不同。[配置](https://huggingface.co/Extropic-AI/Z1T-0/blob/main/config.json)、[组件](https://github.com/extropic-ai/sparse-transformers/blob/main/research/z1t/components.py)

官网当前估算同时列出不同边界，必须分开读：

| Z1T官方示例边界 | 估计能量/token | 含义 |
|---|---:|---|
| 仅Z1采样部分 | 8.74 nJ | 少数稀疏tanh算子 |
| Z1＋已计FPGA工作，排除词表读出/芯片间搬运 | 294.52 nJ | 官网14–139倍H100比值采用这个边界 |
| 再加入FPGA最终logits读出 | 约136.4 µJ | 说明稠密词表层可能主导总账 |

这些是理论/模型估算，未计所需并行Z1芯片数。数百至数千倍对应仅Z1层的比较；不能称为已实测的完整LLM千倍收益。[官网效率估算](https://extropic.ai/writing/z1t/#sec-efficiency)

**对本项目的判断。** 需要修正“官网所有估算都排除读出”的过度概括：它确实补充了含读出的数值，只是宣传表的倍率仍排除它。公开JAX前向是稀疏浮点求和、tanh等，未执行有限样本Gibbs循环；运行公开模型不等于验证物理p-bit。最值得借鉴的是为连接度和概率更新重新训练模型；若保留原Qwen/Llama，不能照搬其稀疏度和tanh替换。当前主线与另开重训模型路线可并存，前者更适合验证计算替换，后者研究原生p-bit表达能力。[固定组件代码](https://github.com/extropic-ai/sparse-transformers/blob/8c0f7e66cfea794f70e81fcf289e179d9f58ed0d/research/z1t/components.py)

## 3. 其余十一项：用于补齐哪些设计问题

### 3.1 A 278–514M Event/s ADC-Less Stochastic Compute-In-Memory Convolution Accelerator for Event Camera

VLSI Technology and Circuits 2024。[两页全文](https://nanocad.ee.ucla.edu/wp-content/papercite-data/pdf/c128.pdf)。两页及Fig.1–6、Table 1均核对。

**原文核实。** 6位二进制权重驻留SRAM，原位SNG生成正负流；循环移位序列提供多组窗口，每个权重/SNG复用给32个MAC。乘积经wired-OR和正负计数器读出，6位输出64拍。12nm芯片实测，6×6位非事件模式系统/宏为46/86 TOPS/W；事件模式、稀疏与提前终止的峰值是另一边界。

**项目判断。** 它是“无需存4096拍比特流，权重就地产生流并跨输出复用”的实物证据。定制原位SNG和计算线不能用普通SRAM宏零成本替代；OR精度、事件稀疏与提前终止也不能直接套到稠密SwiGLU。

### 3.2 Bitstream-Based Neural Network for Scalable, Efficient, and Accurate Deep Learning Hardware（SC-CNN / BISC后续）

Frontiers in Neuroscience 2020，DOI 10.3389/fnins.2020.543472。[开放全文](https://pmc.ncbi.nlm.nih.gov/articles/PMC7793640/)。重点§3/Fig.2–3、§4.3–4.6及§5/Table 1–2。

**原文核实。** 确定性MUX-FSM从二进制输入生成流，权重控制运行时长，上下计数器读出；相同权重的路径可共享FSM/倒计数。lane-major SRAM可删输入MUX/寄存器，却需逐拍读SRAM。逐层精度搜索含微调：AlexNet为8–10位，GoogLeNet为13位，不能简化为统一8位。ImageNet只评前1万张；硬件综合，存储能耗并非研究重点。

**项目判断。** 混合表示值得借鉴；删寄存器后增加的SRAM访问必须补回总账。ReLU相关半范围优化不适用于有负值的SiLU。其效果也不等于无微调替换预训练LLM。

### 3.3 Dither computing: a hybrid deterministic-stochastic computing framework

ARITH 2021。[v2全文](https://arxiv.org/html/2102.10732v2)。重点§III–IV、VI–VIII；PDF第4页Table I、第5页Fig.7及第6–8页实验。

**原文核实。** 用确定性脉冲表示主体，随机扰动表示余量；在特定编码、排列和独立性条件下实现无偏及均方误差 `O(1/N²)`。乘法两侧格式不对称，多级计算需要重编码；舍入方法仍有低位乘法器和索引状态。验证含矩阵、小型MNIST/Fashion-MNIST网络，没有LLM或芯片能效。

**项目判断。** 与“分层短流、只随机边界余量”思想相近，但不是我们的现有实现证明。应与同精度数字随机舍入比较，并计入重编码。经过非线性后，无偏输入估计也不保证输出无偏。

### 3.4 P2LSG: Powers-of-2 Low-Discrepancy Sequence Generator for Stochastic Computing

ASP-DAC 2024。[v2全文](https://arxiv.org/html/2309.05235v2)。重点§III–V、Table I–III/V及Fig.4–5。

**原文核实。** 按 `2^k` 基数分组与重排计数器位，形成Van der Corput序列，并可并行产生多个序列点。双流AND仍依赖二维覆盖；128拍乘法表的MAE为P2LSG 0.88%、Sobol 0.45%。两路8位发生器45nm综合为163µm²、16.05µW，不包含完整GEMM。应用为标量与图像，非LLM。

**项目判断。** 是本地PRNG的低差异候选，适合比较“共享计数器＋不同接线”。必须验证64/128拍前缀、双操作数联合分布与64路共享协方差，不能只看每路全周期均匀；功率也需在55nm重新提取。

### 3.5 Deterministic Methods for Stochastic Computing using Low-Discrepancy Sequences

ICCAD 2018，DOI 10.1145/3240765.3240797。[作者全文](https://mriedel.ece.umn.edu/wiki/images/1/1f/Najafi_Lilja_Riedel_Deterministic_Methods_for_Stochastic_Computing_using_Low-Discrepancy_Sequences.pdf)。重点§3–4、Fig.3–4、Table 2–3。

**原文核实。** 用Sobol多维序列、周期控制/旋转保证联合配对，短前缀近似读出。其双8位乘法完整精确周期仍为65536拍，128拍两种Sobol方法的MAE约0.451%。序列方法有额外状态和面积；论文以面积×时延作为能耗代理，未验证神经网络质量。

**项目判断。** 它直接解释了为什么“随机数只有256种，256拍应该足够”并非双流乘法的一般结论。但这也不是所有8位乘法都必须65536拍：二进制/位串行乘法、单边固定权重、输入相关编码是不同算法。我们的判断应落在具体协议和LLM误差，而不是只数随机字的取值数。

### 3.6 tubGEMM: Energy-Efficient and Sparsity-Effective Temporal-Unary-Binary Based Matrix Multiply Unit

2024预印本。[v1全文](https://arxiv.org/html/2412.17955v1)。重点§II–IV、Fig.2–3、Table I–V。

**原文核实。** 一侧时间展开，另一侧二进制，每拍累加两倍值、末拍修正奇数，执行无RNG的精确整数GEMM。外积推进，时长受当前最大幅度影响；8位有符号单乘最坏约64拍，完整GEMM还要推进归约维。N5 PPA来自后综合和活动估计，完整存储子系统尚未包含。

**项目判断。** 这是短流方案必须面对的确定性对照：便宜的一位控制乘法未必需要随机性。须同位宽、阵列和存储边界重做比较。它与uGEMM原文的45nm库名/特殊溢出配置也有比较口径差异，不能直接把跨论文倍率当作同库复现。

### 3.7 A Light-Speed Large Language Model Accelerator with Optical Stochastic Computing（ASTRA）

GLSVLSI 2025，DOI 10.1145/3716368.3735299。[机构全文](https://api.mountainscholar.org/server/api/core/bitstreams/5393ef9a-acdf-4548-a718-f05f5df3e3f9/content)。重点§3–4、Fig.3–6、Table 1–3。

**原文核实。** 定点操作数转成确定性TCU流，一侧使用位位置相关编码；光学AND/NAND完成乘法，PCA/PCA′电荷积分，最终ADC和数字减法读出。8位含符号配置用128脉冲，并非物理p-bit。结果来自器件/电路/架构模拟；OPT-350的Guanaco BLEU为FP32 18.07、INT8 17.79、INT8＋SC 17.49，没有WT2 PPL或7B质量验证。

**项目判断。** 最有价值的是让归约发生在电荷域、降低读出频率，以及行列共享转换器。收益不能归因于AND本身，电荷积分/ADC也不能在纯数字TLM中免费替代计数器。其128脉冲不是通用双8位独立流精确乘法的证明。

### 3.8 Stochastic Nanomagnets as Current Digitizers for Efficient Probabilistic Machine Learning

Physical Review Applied 24, 044012，2025，DOI 10.1103/s86j-5jcr。[APS摘要](https://journals.aps.org/prapplied/abstract/10.1103/s86j-5jcr)、[MIT摘要](https://www.rle.mit.edu/stochastic-nanomagnets-as-current-digitizers-for-efficient-probabilistic-machine-learning/)。**全文未取得。**

**仅摘要可核实。** 三端SOT驱动sMTJ作为模拟电流到随机数字输出的接口，目标是替代传统交叉阵列ADC；摘要提到partial-sum与MNIST验证。无法据此确认阵列分块、采样数、校准、外围成本或完整能效。

**项目判断。** 值得补全文，尤其看partial-sum和读出误差是否适配我们。如果采用普通SRAM加纯数字计数，此文的ADC替代价值不会自然出现。取得全文前，不将其数字写入能耗模型。

### 3.9 FIGNA: Integer Unit-Based Accelerator Design for FP-INT GEMM Preserving Numerical Accuracy

HPCA 2024，DOI 10.1109/HPCA57654.2024.00064。[论文标识](https://doi.org/10.1109/HPCA57654.2024.00064)。本次使用用户本地14页IEEE全文；重点§III-B/D/E、Fig.9–11、§IV-B。

**原文核实。** 在向量入口按最大指数预对齐，再用整数MAC、宽累加及int2fp；不同子向量在FP32合并。BF16×INT8且采用FP32累加时，对齐表示为34位；两组7位有效块加2位位置可压缩传递，但乘法仍是15位有符号值×INT8，不是无损BF16→INT8。硬件为**28nm** DC/PrimePower；SystemC统计运算/访存/时间，内存采用单次能量模型；模型数值验证含BERT/OPT/BLOOM。

**项目判断。** 这是比“BF16 GPU整卡”更有辨识力的数字ASIC对照。转换应按向量摊销，宽部分和尽量保留到最终读出，再与残差接口转换一起核算；不能只比较INT8乘法器和AND门。原文并未证明我们的A8量化无损。

### 3.10 NeuPIMs: NPU-PIM Heterogeneous Acceleration for Batched LLM Inferencing

ASPLOS 2024。[作者全文](https://jongse-park.github.io/files/paper/2024-asplos-neupims.pdf)、[代码](https://github.com/casys-kaist/NeuPIMs)。重点§5–8、Fig.8–13、Algorithm 1、Table 5。

**原文核实。** NPU处理GEMM，DRAM PIM处理Attention GEMV；新增双row buffer和命令通道支持二者并行，按序列长度分配通道、交错子批。K与V布局不同，延迟估计依赖物理映射。评估耦合ONNXim与DRAMsim3。内存功耗使用Micron模型，并假设PIM all-bank计算功率为普通读取的4倍；增加row buffer背景功耗。按论文所列内存功耗边界，其1.8倍功率/2.4倍速度推得约25%能量减少；这是模型估算，不能作为包含完整NPU功耗的整机实测。

**项目判断。** 同一token的依赖不能通过画流水线消失，跨head/跨请求并行也需要独立资源、端口和缓存。batch1不能自动得到大批量子批交错收益。我们可以学它的映射与调度证据，但自定义SC/Ising命令的能量仍需自己的PT/电路模型，不能由普通DRAMPower自动给出。

### 3.11 LLMCompass: Enabling Efficient Hardware Design for Large Language Model Inference

ISCA 2024。[作者全文](https://augustning.com/assets/papers/llmcompass-isca-2024.pdf)、[代码](https://github.com/PrincetonUniversity/LLMCompass)。重点§III-A–D、Fig.4–6。

**原文核实。** 在全局/本地缓冲间递归分块，搜索映射、广播合并、部分和驻留、归约与双缓冲；阵列周期调用SCALE-Sim，其他算子单独建模。对GPU/TPU的验证中，算子平均误差10.9%，prefill/decode整体平均4.1%。面积模型使用CACTI及芯片资料；不是现成的p-bit能量或DRAM命令级模型。

**项目判断。** 值得借鉴“搜索多种合法调度，再用实机/RTL校验”的工作方式。不能把它的误差范围当我们新ASIC的保证。当前TLM应补容量、端口、重复传输、队列和背压约束，并为SC、转换、采样、Ising各自提供经验证的算子模型。

## 4. 把论文合起来后，哪些认识需要更新

### 4.1 把四类不同的“随机/比特流计算”分清

| 路线 | 随机性/时间序列做什么 | 保留的主要成本 | 代表资料 |
|---|---|---|---|
| 数字随机乘法 | 用一位事件估计乘积 | SNG、共享布线、归约、时间累加、重编码 | SASCHA、DS-CIM |
| 确定性/混合unary | 用时长或排列编码数值，随机余量可选 | 计数、比较、状态、最坏周期 | Dither、SC-CNN、tubGEMM |
| 随机地址选择 | 抽取要读的向量，直接减少读取 | 分布生成、索引、去重、稀疏gather | SANTA |
| 原生概率器件/网络 | 输入决定状态概率，承担非线性或采样 | 建立/混合、相关性、输入配置、读出、耦合 | p-PIM、Z1T |

这是本次归纳，不是四类收益已经在我们模型上测得。物理tanh p-bit与均匀随机字＋比较器不能按同一种能量、同一种独立样本率处理。论文里的确定性unary也可以研究，但应诚实命名，不把无RNG对照当作物理随机器件的优势。

### 4.2 为什么取值只有256种，IID仍可能需要超过256拍

以我们常用的无符号幅度门限协议为例：8位门限字 `r∈{0,…,255}`，`b=1[r<a]`，则一位输出的均值为 `a/256`。完整遍历一次门限，能精确表示这个**一维、给定量化值**；它不消除量化和尺度裁剪误差。

双流乘法还要求两个门限的**联合覆盖**：

`平均(1[rA<a] AND 1[rW<w]) ≈ (a/256)×(w/256)`。

若只遍历两路完全相同的门限，左边变成 `min(a,w)/256`，并不是乘积；两路各自均匀仍然不够。完整笛卡尔覆盖有256×256个点。低差异、条件更新、相关编码可以用短前缀取得更好近似，甚至改变算法，但必须说明具体构造。[uGEMM](https://jsm.ece.wisc.edu/docs/wu-isca2020.pdf)、[ICCAD 2018](https://mriedel.ece.umn.edu/wiki/images/1/1f/Najafi_Lilja_Riedel_Deterministic_Methods_for_Stochastic_Computing_using_Low-Discrepancy_Sequences.pdf)

因此，4096不是随机计算的物理要求，也不是一个应保留的默认最优值。正确问题是：**对给定编码、共享、序列和真实FFN分布，达到可接受完整PPL需要多少拍，是否胜过同精度确定性电路。** 固定权重＋单边流、双边AND、OR重映射、确定性TCU应分别回答，不能共享一个“8位所以128/256拍足够”的结论。

### 4.3 精确计数可以保留，但不能只优化乘法门

SASCHA的GEO+说明精确归约有研究依据；DS-CIM/光学ASTRA则说明，收益很大时常常同时改变了归约、存储、转换和复用。我们应同时比较三条路径：

1. 位平面压缩器/并行计数＋共享时间累加，保持给定比特事件的准确和。
2. 小组OR＋组间准确累加，明确碰撞误差；若做SRR，另计右移与修正。
3. 同量化参考的确定性位串行/temporal-unary/整数MAC。

缓存几拍后更新大累加器，只是把宽寄存器切换换成局部缓冲与小计数器；是否省能取决于翻转、位宽、时钟、泄漏和复用。我们已有RTL/PT与新短流模块应继续按同一频率、相同有效工作量比较，本文件不生成新的节能百分比。

### 4.4 FFN调度不能忽略SwiGLU和输出投影的依赖

本项目的目标函数仍是 `g=Wg·x，u=Wu·x，z=SiLU(g)×u，y=Wd·z`。这里的建议是：输入x在g/u两投影间复用；g/u可在确有双计算资源时并行，或在同一阵列上分时。某段z必须等该段g/u的归约、尺度恢复与SiLU完成后才可用；Wd按段接收z并保存部分和，最后完成输出与残差接口转换。

能否形成tile级流水取决于Wd对输入维的完整归约、片上容量和端口，不等于所有阶段同拍开始。应搜索“g/u分时或并行、z分块缓存、Wd部分和驻留”的组合，计算利用率与存储读写。若非线性前后反复转BF16再量化，需要单列转换成本。若改为全流式近似SiLU，则应作为另一算法重新测完整PPL；上述论文没有替我们证明这一点。

### 4.5 Attention需要按实际地址而非逻辑稀疏率计能耗

SANTA与NeuPIMs共同提示：K和V是不同访问问题。K筛选的摘要可能需要更新/读取，GQA头并集可能使大部分K仍被读取；PV可以先抽少量token地址，再读对应V。即使逻辑选择很稀疏，burst、bank映射、缓存行和重复请求仍影响实际字节量。

当前模型应分别给出：筛选摘要流量、入选K流量、分数/归一化流量、V请求及去重后地址、DRAM实际burst字节、局部累加与输出。prefill/decode、GQA/MHA和上下文长度分别报告。Ising路径另记更新次数、自相关和有效样本数；若高概率状态反复出现，可合并V读取，但合并后的计数权重不能丢。

### 4.6 能效倍率必须固定同一个比较边界

| 层级 | 应回答的问题 | 不能替代什么 |
|---|---|---|
| 数值/模型 | 相同权重、数据、协议下PPL/任务质量如何 | 小型MNIST不能替代LLM完整PPL |
| 电路/宏 | 相同位宽、工艺、频率、活动下PPA如何 | 宏TOPS/W不能替代模型J/token |
| 系统/调度 | 同工作负载下时延、访存、能量如何 | 操作数比例不能直接变成实测能耗 |
| 对GPU | 同模型、质量、batch、上下文、阶段，且边界匹配 | 不把GPU整卡与仅AND阵列比较后称整机倍率 |

我们应采用 `总能量=算子动态能量+存储/互连动态能量+运行时间×背景/泄漏功率` 的总账。DRAMPower/DRAMSys负责所选器件和命令轨迹的内存部分，不自动包含新型CIM、转换、PRNG或Ising。PT提供具体算子，校准CACTI提供SRAM探索，事务调度决定访问次数与时间；各项边界和不确定性都要记录。

## 5. 建议的下一轮工作，按优先级排列

以下是阅读后的建议清单，本次未启动这些实验。

| 优先级 | 要做的对照/补充 | 输出什么才算有结论 |
|---|---|---|
| 1 | 固定权重短流：IID、分层/低差异、枚举、确定性低位/位串行对照 | 同模型版本、文本SHA、未改BF16重测、完整WT2滑窗PPL、≥3种子；逐投影误差分解 |
| 2 | 统一FFN tile及外围接口比较 | 同工艺/时钟/读出范围的PT：源、比较、归约、缓存累加、转换、SiLU/乘积；给J/tile和面积，不只门数 |
| 3 | 对齐Attention访问与采样依赖 | dense与PV/筛选/Ising各自的地址trace、GQA并集、burst/去重、prefill/decode延迟及J/token |
| 4 | 比较普通SRAM外挂计算与定制CIM | 先写清端口、位线/感放/保持方式、权重驻留及读频率，再决定哪些需要定制电路仿真 |
| 5 | 双流与SRR独立验证 | 门限二维覆盖、短前缀、相关性/seed、偏移和低位误差；随后真实FFN向量及PPL |
| 6 | 原生p-bit路线作独立研究 | 实测概率曲线、相关时间、有效样本率、配置/读出能量；重训模型与保留Qwen路线分开 |

我会据此采用更严格的设计检查顺序：先画数值依赖和读写地址，再确定资源/容量与合法重叠，最后代入经校准的能量。收益先在算子、再在完整模型和系统上分别验证。这样可以直接防止再次出现“逻辑PV采样了，但完整V已经读完”或“假定并行却没有独立端口”的问题。

## 6. 版本、证据与复用说明

- 阅读依据为原清单17项，不新增训练或硬件结果。模型/分词器/语料/种子字段对这次文献任务不适用；后续实验仍需遵循仓库复现规则。
- SANTA本地v2 PDF SHA-256：`19be9065451d31a6f646ec31e1e8caee0a7ea6694780808ddfef236b48b70ffc`；DS-CIM本地PDF：`6f736516b0534d81e3c0a08eb3822674b827c344e8051353a02ebfeab6ef9aef`；FIGNA本地PDF：`d4bfd00ab334a744be0d89d6ce3d792254e5afd7c70c4c6a16830b0bf7b1e072`。
- 其余下载字节、公开URL、章节/页码、图表核查与访问失败/替代入口见仓库 `work/jieruiz/26/SOURCE_EVIDENCE.json`。原文PDF、受许可资料和长图像只保留在本地阅读目录，Git提交摘要和索引。
- 仓库正式入口为本文件；用户资料目录 `pbit_llm_master_report_20261012/` 保留同字节副本。文件散列和交接在 `work/jieruiz/26/`；原推荐清单未改。
- Current Digitizers仍缺全文。取得全文后优先补其partial-sum组织、器件相关时间、ADC替代边界和外围能量；本次不把摘要推测写成已读结论。
