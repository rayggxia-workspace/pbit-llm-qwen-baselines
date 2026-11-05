# 逐篇论文与模拟器证据

核查日期：2026-10-25。共33个代表性条目；ACCELSIM、ASTRASIM为明确标记的工具家族，含多篇版本，不是33篇单独的LLM论文。

NR=本次核查范围未明确披露。最终全文未取得、补充材料未核全、仅核公开代码入口分别注明。论文结果是作者报告，本轮未重跑。

[综合结论](README_ZH.md) · [需求与验收](REQUIREMENTS_ZH.md) · [CSV](EVIDENCE.csv) · [JSON](EVIDENCE.json)

## 导航

| 条目 | 年份/会议 | 硬件/工具类别 | 时序与物理层级 |
|---|---|---|---|
| [FIGNA](#figna) | 2024 / HPCA | 数字ASIC | 操作/访问计数与系统延迟模型；RTL综合PPA；原文未明确cycle-accurate |
| [OPAL](#opal) | 2024 / DAC | 数字ASIC | 综合级模块PPA；系统性能模型粒度未充分披露 |
| [ANDA](#anda) | 2025 / HPCA | 数字ASIC | 周期级性能模型+活动驱动综合功耗 |
| [KELLE](#kelle) | 2025 / MICRO | 数字ASIC/eDRAM | 模块综合+存储模型+分析式调度；未明确整系统cycle-accurate |
| [AXCORE](#axcore) | 2025 / MICRO | 数字ASIC | 周期性能模型+RTL综合+软件质量 |
| [HSA](#hsa) | 2025 / ISLPED | 数字ASIC | 后布局模块/加速器仿真；外存参数模型 |
| [SPATTEN](#spatten) | 2021 / HPCA | 数字ASIC | RTL应用周期仿真+DRAM命令模拟+综合/文献PPA |
| [DSCIM](#dscim) | 2026 / DATE | 随机数字CIM | 定制宏布局后仿真+模型误差注入；没有完整LLM系统时序模型证据 |
| [UNICAIM](#unicaim) | 2025 / DAC | FeFET CAM/CIM | 器件/电路与算法混合；非完整ASIC周期级模型 |
| [NEUPIMS](#neupims) | 2024 / ASPLOS | NPU+HBM-PIM | NPU和DRAM周期模型；稳态服务抽样 |
| [ATTACC](#attacc) | 2024 / ASPLOS | GPU+HBM-PIM | 命令/周期模型+数字综合+存储模型 |
| [CENT](#cent) | 2025 / ASPLOS | GDDR6-PIM+CXL | 设备周期模型+功能检查+通信解析；混合粒度 |
| [PIMGPT](#pimgpt) | 2024 / npj Unconventional Computing | GDDR6-PIM+ASIC | 事件驱动周期模型，package/channel/bank状态机；ASIC综合 |
| [XFORMER](#xformer) | 2023 / IEEE TVLSI | ReRAM+SRAM CIM | 器件/宏电路/架构混合仿真 |
| [PCMALBERT](#pcmalbert) | 2025 / Nature Communications | 实测PCM+模拟数字系统 | 模拟MAC实测；整系统PPA混合估计 |
| [LLMCOMPASS](#llmcompass) | 2024 / ISCA | 通用加速器模型 | 分析式/分块时序；向量softmax/LN/GELU、all-reduce；不执行数值 |
| [ONNXIM](#onnxim) | 2024 / IEEE CAL | NPU模拟器 | 计算tile时序、DMA依赖、DRAM/NoC周期争用；无已核实数值功能后端 |
| [PYTORCHSIM](#pytorchsim) | 2025 / MICRO | NPU模拟器 | 功能执行与分块事件/周期时序解耦；softmax/转换/归约/融合 |
| [SCALESIM](#scalesim) | 2025 / ISPASS | 矩阵阵列模拟器 | 阵列周期与访问轨迹；非数值LLM执行 |
| [TIMELOOP](#timeloop) | 2019 / ISPASS | 映射/分析工具 | 循环、空间/时间映射、动作计数和吞吐/带宽约束；非事务全系统 |
| [ACCELERGY](#accelergy) | 2019 / ICCAD | 能耗估计框架 | 动作计数×energy/action；时间/事件由外部模型给出 |
| [ZIGZAG](#zigzag) | 2021 / IEEE TC | 映射/分析工具 | 循环/分层存储分析；非数值、非DRAM命令模型 |
| [ACCELSIM](#accelsim) | 2020 / ISCA2020 / MICRO2021；2.0为2026预印本 | GPU模拟器 | GPU指令/缓存/互连；数值与控制流来自取trace目标 |
| [ASTRASIM](#astrasim) | 2020 / ISPASS2020/2023；3.0为2026预印本 | 多设备系统模拟器 | 事件/资源层；ReduceOp可用给定周期 |
| [MBA](#mba) | 2026 / DAC | IGZO eDRAM ASIC | 行为/算子图时延能量模型；非明确周期级 |
| [ASCEND](#ascend) | 2024 / DATE | 随机数字ASIC | 综合级非线性模块面积延迟；加速器面积汇总；网络质量 |
| [ISINGSOT](#isingsot) | 2026 / IEEE Electron Device Letters | 物理p-bit+模拟系统 | 器件实测；分布/功能仿真；外围未整合 |
| [DRAMSYS](#dramsys) | 2022 / International Journal of Parallel Programming | DRAM时序后端 | 事件驱动TLM可保留周期级JEDEC约束；不是逐拍信号仿真 |
| [RAMULATOR2](#ramulator2) | 2023 / IEEE CAL | DRAM时序后端 | DRAM周期级；不包含完整NPU与电路PPA |
| [DRAMPOWER](#drampower) | 2013 / 官方工具；相关模型DSD2011/DATE2013/DAC2013 | DRAM能耗后端 | 命令和状态时间积分；不负责调度或合法性验证 |
| [VAMPIRE](#vampire) | 2018 / SIGMETRICS / POMACS | DRAM实测校准 | 命令+数据值/模块结构变化的经验模型 |
| [MEMINTEGRATION](#memintegration) | 2026 / arXiv预印本 | 模拟器集成验证 | 三视角：DRAM后端、CPU–内存接口、应用观察 |
| [SANTA](#santa) | 2026 / ICML | GPU软件/随机算法 | kernel与批生成实测；prefill保持dense |

<a id="figna"></a>
## FIGNA — FIGNA: Integer Unit-Based Accelerator Design for FP-INT GEMM Preserving Numerical Accuracy

HPCA，2024。类别：数字ASIC。

- **被模拟硬件**：新设计FP-INT GEMM ASIC；对照FP-FP Engine也重实现
- **目的**：降低混合精度乘法的浮点硬件成本
- **工具链**：自研SystemC；Synopsys Design Compiler、PrimePower；SRAM compiler
- **建模层级**：操作/访问计数与系统延迟模型；RTL综合PPA；原文未明确cycle-accurate
- **工艺/PVT**：28nm CMOS；电压/工艺角NR
- **频率/时基**：100MHz
- **能量/面积来源**：逻辑由DC/PrimePower；寄存器文件0.0625pJ/bit、SRAM0.1053pJ/bit；动态操作计数+漏电×时间
- **存储与DRAM**：HBM2 256GB/s、3.9pJ/bit；不是DRAM命令能耗模型
- **模型/场景**：128×128阵列；BERT输入128tokens；BLOOM/OPT自回归batch32；只评线性GEMM
- **代表结果及条件**：FP16-INT8对FP-FP Engine平均面积效率3.56×、能效1.55×
- **验证证据**：原文实现/综合流程；未找到与真实芯片/独立时序模型的误差数字
- **局限/不能推导的结论**：主TOPS/mm²只计逻辑，buffer sweep才含SRAM；不是全LLM、非后布局证据
- **原文定位**：本地用户PDF第9–12页（印刷768–771），§IV-B1/B2/B3、IV-C、IV-E
- **本轮访问核查范围**：用户全文PDF核读

原始来源：[来源1](https://doi.org/10.1109/HPCA57654.2024.00064)


<a id="opal"></a>
## OPAL — OPAL: Outlier-Preserved Microscaling Quantization Accelerator for Generative Large Language Models

DAC，2024。类别：数字ASIC。

- **被模拟硬件**：混合精度MxV/softmax专用ASIC
- **目的**：保留离群值、减少量化推理成本
- **工具链**：RTL（SRAM除外）+Design Compiler；CACTI；系统模拟器名称NR
- **建模层级**：综合级模块PPA；系统性能模型粒度未充分披露
- **工艺/PVT**：65nm；电压/角NR
- **频率/时基**：NR：已查§5.2和硬件表未给出
- **能量/面积来源**：DC逻辑功耗面积；CACTI存储含漏电；表3单核逻辑0.9293mm²、335.85mW
- **存储与DRAM**：512KB global buffer；每核2KB softmax buffer；外部DRAM配置/模型NR
- **模型/场景**：Llama2-7/13/70B、OPT；WT2/C4、ARC-C/PIQA
- **代表结果及条件**：Llama2-70B报告单token1.98s；W4A4/7能耗对OWQ/BF16低38.6%/58.6%
- **验证证据**：RTL综合与软件质量评估；系统校准误差NR
- **局限/不能推导的结论**：batch/context信息不足，1.98s不能直接作统一TPOT；未查到P&R；单核功率不等于整机
- **原文定位**：§5.2、表3、图8；DAC归属由作者机构书目交叉核对
- **本轮访问核查范围**：全文HTML核读

原始来源：[来源1](https://arxiv.org/html/2409.05902v3#S5.SS2)；[来源2](https://scholar.dgist.ac.kr/handle/20.500.11750/57857?mode=full)


<a id="anda"></a>
## ANDA — Anda: Unlocking Efficient LLM Inference with a Variable-Length Grouped Activation Data Format

HPCA，2025。类别：数字ASIC。

- **被模拟硬件**：可变尾数位串行GEMM ASIC；GPU-like基线是建模的空间加速器
- **目的**：自适应精度压缩浮点激活和计算
- **工具链**：自研cycle-accurate simulator；SystemVerilog、Cadence Genus；综合网表VCD
- **建模层级**：周期级性能模型+活动驱动综合功耗
- **工艺/PVT**：16nm，0.8V nominal；工艺角NR
- **频率/时基**：285MHz；各ASIC基线同频
- **能量/面积来源**：Genus综合网表仿真VCD功耗；SRAM独立工具NR
- **存储与DRAM**：HBM2 256GB/s、3.9pJ/bit；同片上容量、同峰值吞吐
- **模型/场景**：OPT/LLaMA/LLaMA2 1.3–30B；batch1；PPL长度2048；硬件仅FP-INT GEMM
- **代表结果及条件**：1%质量容差下，相对GPU-like FP-FP建模基线，平均GEMM加速2.49×、面积效率4.03×、能效3.16×
- **验证证据**：作者称与functional simulations核对；无数值误差报告
- **局限/不能推导的结论**：system-level措辞不代表完整LLM；KV等FP16；无P&R披露；非GPU实测
- **原文定位**：§V-A、V-D/E，表III
- **本轮访问核查范围**：全文HTML核读

原始来源：[来源1](https://arxiv.org/html/2411.15982v1#S5)


<a id="kelle"></a>
## KELLE — Kelle: Co-design KV Caching and eDRAM for Efficient LLM Serving in Edge Computing

MICRO，2025。类别：数字ASIC/eDRAM。

- **被模拟硬件**：边缘LLM ASIC及eDRAM/KV淘汰、刷新
- **目的**：协同片上存储保留时间和推理调度
- **工具链**：SystemVerilog+DC；Destiny；CACTI7；§6分析式吞吐/带宽模型
- **建模层级**：模块综合+存储模型+分析式调度；未明确整系统cycle-accurate
- **工艺/PVT**：逻辑45nm；Destiny存储65nm、105°C；电压/逻辑角NR
- **频率/时基**：1GHz
- **能量/面积来源**：逻辑DC；存储Destiny；§8方法段报告约9.5mm²、片上6.52W、外DRAM另列11.74W
- **存储与DRAM**：2MB SRAM+4MB KV eDRAM+256KB激活eDRAM；16GB LPDDR4 64GB/s，CACTI7；含外存时延能量
- **模型/场景**：Llama2/3/3.2、Mistral、Qwen2、OPT；默认batch16，prompt128–1024、decode512–8192
- **代表结果及条件**：对等片上面积Original+SRAM平均时延改善3.94×、能效4.46×
- **验证证据**：论文公开模块/存储来源及访存公式；硬件校准误差/开源NR
- **局限/不能推导的结论**：混合工艺估算；未见P&R或波形活动来源；不能从时序示意图推定完整周期仿真
- **原文定位**：§6公式4–6；§8 Hardware Evaluation开头方法段及§8.1；Table2为质量表
- **本轮访问核查范围**：全文HTML核读

原始来源：[来源1](https://arxiv.org/html/2510.16040v1#S8)


<a id="axcore"></a>
## AXCORE — AxCore: A Quantization-Aware Approximate GEMM Unit for LLM Inference

MICRO，2025。类别：数字ASIC。

- **被模拟硬件**：近似混合精度GEMM ASIC
- **目的**：降低浮点/整数混合GEMM成本
- **工具链**：DNNWeaver派生模拟器；SpinalHDL→Verilog→DC；CACTI；公开artifact
- **建模层级**：周期性能模型+RTL综合+软件质量
- **工艺/PVT**：TSMC28nm；电压/角NR
- **频率/时基**：1GHz；基线同频/峰值/SRAM
- **能量/面积来源**：DC逻辑；CACTI SRAM；能量图含Core/Buffer/DRAM/Static
- **存储与DRAM**：64×64阵列、4×4 tiling；给足带宽；DRAM型号/能耗校准未完整披露
- **模型/场景**：OPT2.7–30B、Llama2-7/70B；WT2/ARC-E/HellaSwag/PIQA/WinoGrande；硬件主图OPT13/30B decode、batch32、output1
- **代表结果及条件**：对FPC能量降低2.2×、TOPS/W提高6.4×
- **验证证据**：公开RTL、质量脚本、性能/能耗模拟器与预期结果；未查到硅片校准误差
- **局限/不能推导的结论**：图16密度排除最终累加；4张RTX6000Ada为实验主机；非GPU目标芯片；无P&R披露
- **原文定位**：§6.1、6.3/6.4、附录A；PDF9–12、14–15页
- **本轮访问核查范围**：全文PDF及artifact附录核读；公开代码入口已确认

原始来源：[来源1](https://soldierchen.github.io/assets/pdf/axcore-micro25.pdf)；[来源2](https://github.com/CLab-HKUST-GZ/micro58-axcore)；[来源3](https://doi.org/10.5281/zenodo.16895417)


<a id="hsa"></a>
## HSA — Hybrid Systolic Array Accelerator with Optimized Dataflow for Edge Large Language Model Inference

ISLPED，2025。类别：数字ASIC。

- **被模拟硬件**：双数据流数字ASIC；主端到端对象RetNet
- **目的**：适配prefill与decode计算形状
- **工具链**：SystemC→Catapult HLS→RTL→DC→Innovus P&R；VCS/PrimeTime
- **建模层级**：后布局模块/加速器仿真；外存参数模型
- **工艺/PVT**：TSMC28nm；能效点0.81V；角NR
- **频率/时基**：500MHz
- **能量/面积来源**：表II 0.636mm²、0.108W、0.256TOPS；后布局功耗时延
- **存储与DRAM**：DDR5 51.2GB/s，32pJ/Byte固定访问能耗；SRAM宏来源NR
- **模型/场景**：256PE；RetNet1.3B，prompt/output750/50与50/750；Llama用于补充质量
- **代表结果及条件**：面积归一吞吐247/117tokens/s/mm²；tokens包括prompt与output
- **验证证据**：HLS/综合/布局布线/后布局流程明确；数值校准误差NR
- **局限/不能推导的结论**：RetNet不含普通softmax注意力；ConvSA由数据流推估、向量单元从5nm缩28nm；非全部同PDK重做
- **原文定位**：§II、§V、表I/II及脚注
- **本轮访问核查范围**：全文HTML核读

原始来源：[来源1](https://arxiv.org/html/2507.09010v1#S5)


<a id="spatten"></a>
## SPATTEN — SpAtten: Efficient Sparse Attention Architecture with Cascade Token and Head Pruning

HPCA，2021。类别：数字ASIC。

- **被模拟硬件**：稀疏注意力ASIC；另有复用阵列FC的e2e扩展
- **目的**：token/head剪枝、渐进量化减少计算与访存
- **工具链**：SpinalHDL→RTL→Verilator；Ramulator；Genus；CACTI
- **建模层级**：RTL应用周期仿真+DRAM命令模拟+综合/文献PPA
- **工艺/PVT**：固定点逻辑40nm；部分softmax单元借45nm文献成本；电压/角NR
- **频率/时基**：1GHz
- **能量/面积来源**：Genus逻辑；CACTI SRAM/FIFO；softmax指数/除法借文献FMA/FPU成本
- **存储与DRAM**：HBM2由Ramulator统计ACT/读写命令，乘文献能耗；不是统一硅片实测
- **模型/场景**：30个BERT/GPT2 attention workloads；e2e单列GPT2-Medium 8-bit FC
- **代表结果及条件**：等资源缩小版对A³吞吐1.6×、能效1.4×；e2e对TITAN Xp平均35×加速
- **验证证据**：Verilator逐应用周期、真实GPU软件对照；未报告硅片校准误差
- **局限/不能推导的结论**：摘要attention加速比不可当全模型；GPU为当时软件栈；部分FPGA功耗投影、混合来源PPA
- **原文定位**：§V-A、表I–IV、§V-B End-to-End Performance
- **本轮访问核查范围**：全文HTML核读

原始来源：[来源1](https://arxiv.org/html/2012.09852v2#S5)


<a id="dscim"></a>
## DSCIM — DS-CIM: Digital Stochastic Computing-In-Memory Featuring Accurate OR-Accumulation via Sample Region Remapping for Edge AI Models

DATE，2026。类别：随机数字CIM。

- **被模拟硬件**：32Kb SRAM随机CIM宏；LLM为软件误差注入
- **目的**：SNG和采样域重映射支持OR累加
- **工具链**：Virtuoso、Liberate/Abstract、DC、Innovus；布局后电路仿真；软件质量模型
- **建模层级**：定制宏布局后仿真+模型误差注入；没有完整LLM系统时序模型证据
- **工艺/PVT**：40nm，0.7–1.2V；工艺角NR
- **频率/时基**：统一时钟NR；峰值T64与质量T256须区分
- **能量/面积来源**：DS-CIM1/2宏面积0.78/0.72mm²；TableIII仅TOPS/W、TOPS/mm²按40nm及1b输入×1b权重归一；输入87.5%稀疏
- **存储与DRAM**：本地SRAM CIM；外部DRAM/全系统调度能耗NR
- **模型/场景**：FP8 LLaMA-7B对齐INT8；T256误差注入六任务
- **代表结果及条件**：六任务平均66.0%→62.6%/58.8%，降3.4/7.2pp；峰值3566.1TOPS/W是宏条件指标
- **验证证据**：宏电路实现和布局后结果明确；质量由误差注入验证
- **局限/不能推导的结论**：峰值效率与最佳质量条件不同；不构成整机J/token、实际p-bit器件或完整LLM芯片证据
- **原文定位**：§V、TablesII–III、Fig.7
- **本轮访问核查范围**：全文HTML核读

原始来源：[来源1](https://arxiv.org/html/2601.06724v1)；[来源2](https://arxiv.org/abs/2601.06724)


<a id="unicaim"></a>
## UNICAIM — UniCAIM: A Unified CAM/CIM Architecture with Static-Dynamic KV Cache Pruning for Efficient Long-Context LLM Inference

DAC，2025。类别：FeFET CAM/CIM。

- **被模拟硬件**：FeFET注意力筛选/计算电路
- **目的**：静动态KV剪枝与CAM/CIM联合设计
- **工具链**：HSPICE + 软件剪枝精度实验
- **建模层级**：器件/电路与算法混合；非完整ASIC周期级模型
- **工艺/PVT**：45nm BSIM MOSFET+Preisach FeFET；线寄生采用引用模型；PVT未核全
- **频率/时基**：整机时钟NR；电路操作时延受ADC并行数量约束
- **能量/面积来源**：局部attention AEDP；计64个10b SAR ADC并行读出
- **存储与DRAM**：512初始token+64 decode槽、d128、3b cell；外部DRAM能耗NR
- **模型/场景**：LongChat-v1.5-7B-32k；LongBench HotpotQA/NarrativeQA；prompt约1.5K/2.5K；F1
- **代表结果及条件**：1b cell、50%剪枝，AEDP对Sprint/TranCIM/CIMFormer改善8.2/13.9/124×
- **验证证据**：HSPICE与算法质量证据；无全芯片实测或系统误差校准
- **局限/不能推导的结论**：局部ADC已考虑，不等于全部数据搬运已闭合；不能将attention AEDP变成E2E J/token
- **原文定位**：§IV-A/B、TableII、Figs10–13
- **本轮访问核查范围**：全文HTML核读

原始来源：[来源1](https://arxiv.org/html/2504.07479v1)；[来源2](https://mengli.me/publication/dac-2025-unicaim/)


<a id="neupims"></a>
## NEUPIMS — NeuPIMs: NPU-PIM Heterogeneous Acceleration for Batched LLM Inferencing

ASPLOS，2024。类别：NPU+HBM-PIM。

- **被模拟硬件**：自定义NPU+HBM PIM；GPU对照为实测A10040GB
- **目的**：batch LLM的NPU/PIM异构调度
- **工具链**：ONNXim+修改DRAMsim3；真实A100/PyTorch基线
- **建模层级**：NPU和DRAM周期模型；稳态服务抽样
- **工艺/PVT**：22nm仅CACTI7双row-buffer面积模型；整NPU节点NR
- **频率/时基**：Table2 1GHz在HBM栏，不推定所有模块同频
- **能量/面积来源**：DRAMsim3 Micron功耗模型；PIM all-bank compute按read功耗/电流4×，另加row-buffer背景
- **存储与DRAM**：8个128×128阵列、8个128×1向量单元、32HBM channels
- **模型/场景**：GPT-3形状7/13/30/175B；ShareGPT平均80入/296出、Alpaca12入/56出；B64–512；合成稳态再抽10batch
- **代表结果及条件**：对NPU-only约2.4×吞吐；Table5功耗1.8×/节能25%属HBM/PIM相关估计
- **验证证据**：开源ONNXim/DRAMsim3修改代码；真实GPU对照；并非全系统实测校准
- **局限/不能推导的结论**：稳态抽样不是所有请求完整服务回放；4×PIM电流是设定；22nm非整机工艺
- **原文定位**：§8.1–8.2、Tables2–5
- **本轮访问核查范围**：全文HTML与代码入口核读

原始来源：[来源1](https://arxiv.org/html/2403.00579v3)；[来源2](https://github.com/casys-kaist/NeuPIMs)


<a id="attacc"></a>
## ATTACC — AttAcc! Unleashing the Power of PIM for Batched Transformer-based Generative Model Inference

ASPLOS，2024。类别：GPU+HBM-PIM。

- **被模拟硬件**：GPU做FC、HBM-PIM做attention及共同计算
- **目的**：受容量/SLO约束的生成推理加速
- **工具链**：修改Ramulator；Verilog/DC；修改FinCACTI；真实DGX A100性能校准
- **建模层级**：命令/周期模型+数字综合+存储模型
- **工艺/PVT**：ASAP7预测7nm逻辑库；DRAM新增逻辑另折1z、密度假设；非全机7nm
- **频率/时基**：GEMV/累加666MHz；softmax1.3GHz
- **能量/面积来源**：HBM ACT/read文献能量；片内read按显微照片数据通路长度缩放；SRAM FinCACTI
- **存储与DRAM**：HBM PIM、容量等额1280GB DGX-Large对照
- **模型/场景**：LLaMA65B/GPT3 175B FP16、MT-NLG530B INT8；输入输出128/512/2048；batch受30/50/70ms-token SLO约束
- **代表结果及条件**：§7.2 LLaMA65B对DGX-Large最高2.81×；报告请求时间和energy/output-token
- **验证证据**：OPT66B在DGX A100实测用于性能校准；开放模拟器
- **局限/不能推导的结论**：GPU校准不等于新PIM能耗实测；预测库/DRAM折算假设需保留；PDF截图未成功，正文文字可核
- **原文定位**：PDF10–12页、§7.1–7.3、Figs13–15
- **本轮访问核查范围**：全文PDF文字核读

原始来源：[来源1](https://scale.snu.ac.kr/papers/2024-04-Conference-ASPLOS-AttAcc.pdf)；[来源2](https://github.com/scale-snu/attacc_simulator)


<a id="cent"></a>
## CENT — PIM Is All You Need: A CXL-Enabled GPU-Free System for Large Language Model Inference

ASPLOS，2025。类别：GDDR6-PIM+CXL。

- **被模拟硬件**：GPU-free PIM+controller/vector/RISC-V
- **目的**：面向LLM生成的设备与多设备互连协同
- **工具链**：功能模拟器；修改Ramulator2；CXL解析模型；DC
- **建模层级**：设备周期模型+功能检查+通信解析；混合粒度
- **工艺/PVT**：GDDR6-PIM 1Y(14–16nm)；控制器TSMC28nm综合后投影7nm；面积另含die-shot缩放
- **频率/时基**：28nm控制器临界路径1ns；投影7nm/2GHz
- **能量/面积来源**：Micron calculator+Samsung GDDR6 IDD/V；MAC按gapless-read电流3×
- **存储与DRAM**：GDDR6 PIM和CXL；controller不全是同一节点实现
- **模型/场景**：Llama2-7/13/70B，512入3584出；GPU vLLM B128，CENT吞吐B32/40/80，低延迟另比B1
- **代表结果及条件**：E2E吞吐geomean2.3×、能效2.3×；prefill GPU快2.5×，decode CENT快2.5×
- **验证证据**：公开trace generator/power/scripts/results；功能模拟器检查指令
- **局限/不能推导的结论**：性能模型不需真实权重；功能正确不等于时延校准；批量差异和3×电流/节点投影须保留
- **原文定位**：§6–7、Tables4–5、AppendixA
- **本轮访问核查范围**：全文HTML及artifact入口核读

原始来源：[来源1](https://arxiv.org/html/2502.07578v3)；[来源2](https://github.com/Yufeng98/CENT)


<a id="pimgpt"></a>
## PIMGPT — PIM GPT a hybrid process in memory accelerator for autoregressive transformers

npj Unconventional Computing，2024。类别：GDDR6-PIM+ASIC。

- **被模拟硬件**：bank-level PIM MAC+独立ASIC非线性/控制
- **目的**：自回归小batch生成
- **工具链**：自研C++ event-driven clock-cycle accurate；DC；TSMC Memory Compiler
- **建模层级**：事件驱动周期模型，package/channel/bank状态机；ASIC综合
- **工艺/PVT**：ASIC TSMC28nm HPC+；PIM MAC28nm综合后1.25V缩放并乘1.5布线补偿
- **频率/时基**：ASIC1GHz
- **能量/面积来源**：ASIC0.64mm²、峰值304.59mW；DRAM命令IDD×t×V含refresh；I/O5.5pJ/bit
- **存储与DRAM**：PIM命令时序取SK Hynix AiM原型；普通DRAM命令借GDDR5时序，电流借DDR5 datasheet并乘3；非目标DRAM工艺完整P&R
- **模型/场景**：8个GPT2/3模型最大1.4B；B1生成1024tokens、重复10次；T4 CUDA events+pynvml
- **代表结果及条件**：最终期刊对T4速度41–137×、能效123–383×
- **验证证据**：状态机级模型与GPU实测基线；代码需向作者申请
- **局限/不能推导的结论**：未见新ASIC/PIM系统校准；2025-03-04 correction独立页未取得，采用当前正文；勿混旧预印本
- **原文定位**：Methods Hardware/Simulation configuration、Table2
- **本轮访问核查范围**：最终正文核读；更正独立页待核

原始来源：[来源1](https://www.nature.com/articles/s44335-024-00004-2)


<a id="xformer"></a>
## XFORMER — X-Former: In-Memory Acceleration of Transformers

IEEE TVLSI，2023。类别：ReRAM+SRAM CIM。

- **被模拟硬件**：静态权重ReRAM Projection Engine+8T SRAM动态Attention Engine
- **目的**：异构存算减少写入和片外访问
- **工具链**：自研架构模型并入PUMAsim；8T SRAM SPICE；数字RTL/DC；CACTI；NeuroSim误差
- **建模层级**：器件/宏电路/架构混合仿真
- **工艺/PVT**：数字32nm CMOS；ReRAM2b、128×128；完整PVT NR
- **频率/时基**：数字1GHz；每crossbar2个8b ADC、1.28GS/s；1b DAC
- **能量/面积来源**：Projection Engine ReRAM/DAC/ADC用PUMA；Attention Engine 8T-SRAM MVM及写入用SPICE，SAR ADC功耗引文献[28]；数字DC、片上存储CACTI
- **存储与DRAM**：iso-area SRAM基线显式计外DRAM；型号/IDD方法段NR
- **模型/场景**：BERT-base/large encoder；GLUE≤512、SQuAD384
- **代表结果及条件**：最高对GTX1060速度85×/节能7.5×；对NVM-only10.7×/4.6×
- **验证证据**：电路/架构/误差分层；未找到整体实测校准数字
- **局限/不能推导的结论**：不是现代autoregressive decode；最终期刊排版未逐页比对；不可继承其器件参数作标准
- **原文定位**：§VI、TablesI–IV、§VII；作者预印本技术细节
- **本轮访问核查范围**：作者全文核读；期刊页受限

原始来源：[来源1](https://arxiv.org/html/2303.07470v1)；[来源2](https://doi.org/10.1109/TVLSI.2023.3282046)


<a id="pcmalbert"></a>
## PCMALBERT — Demonstration of transformer-based ALBERT model on a 14nm analog AI inference chip

Nature Communications，2025。类别：实测PCM+模拟数字系统。

- **被模拟硬件**：14nm PCM芯片实际执行inProj/outProj/FC1/FC2；其他运算外部电脑执行
- **目的**：验证模拟AI上Transformer线性层和漂移补偿
- **工具链**：芯片测量+软件hardware-in-loop；数字单元14nm模拟投影
- **建模层级**：模拟MAC实测；整系统PPA混合估计
- **工艺/PVT**：14nm PCM AI芯片；统一PVT NR
- **频率/时基**：统一系统时钟NR，不填猜测GHz
- **能量/面积来源**：MAC含activation到chip edge及ILP/OLP转换实测；其余数字运算模拟同芯片部署
- **存储与DRAM**：动态attention/LayerNorm实测流程在外部控制电脑；完整自主系统未实测
- **模型/场景**：ALBERT12层共享权重7.1M；7GLUE任务；B1序列≤128；合成150/300/500/1000长度分析
- **代表结果及条件**：平均hardware准确率低于FP1.8%（原文口径）；系统估计>3TOPS/W；30天漂移实验
- **验证证据**：器件/宏质量实测、漂移及重校准证据强
- **局限/不能推导的结论**：实测线性层不等于全LLM整机实测；补充材料全部测量设置未核全
- **原文定位**：Fig1、Fig5；Methods Power performance measurement and estimation
- **本轮访问核查范围**：最终正文核读，补充材料未全核

原始来源：[来源1](https://www.nature.com/articles/s41467-025-63794-4)


<a id="llmcompass"></a>
## LLMCOMPASS — LLMCompass: Enabling Efficient Hardware Design for Large Language Model Inference

ISCA，2024。类别：通用加速器模型。

- **被模拟硬件**：GPU/TPU类加速器DSE，不是CUDA指令模拟器
- **目的**：快速探索LLM硬件/映射/成本
- **工具链**：自研层级映射与双缓冲模型；SCALE-Sim阵列周期缓存
- **建模层级**：分析式/分块时序；向量softmax/LN/GELU、all-reduce；不执行数值
- **工艺/PVT**：面积模型采用7nm数据与经验开销；不是目标芯片统一重综合
- **频率/时基**：TableI目标A100/MI210/TPUv3：1410/1700/940MHz；MI210实测验证固定1400MHz（§III-C脚注3）
- **能量/面积来源**：延迟、面积、美元成本；论文未提供能耗模型
- **存储与DRAM**：DRAM主要容量/带宽，非命令级模型
- **模型/场景**：GPT-3推理及算子；对商用GPU/TPU验证
- **代表结果及条件**：LLM latency平均误差4.1%；prefill0.69%、decode7.5%；算子10.9%；面积GA100/Aldebaran5.1%/8.1%
- **验证证据**：与实际目标硬件算子/推理时延、die面积对照
- **局限/不能推导的结论**：误差依对象；无随机功能/PPL、RNG/CDC/稀疏索引成本；不能当能量后端
- **原文定位**：§III/III-C PDF3–5页、TableI；§III-D/TableII/Fig6 PDF7页面积验证
- **本轮访问核查范围**：全文PDF与代码入口核读

原始来源：[来源1](https://augustning.com/assets/papers/llmcompass-isca-2024.pdf)；[来源2](https://github.com/PrincetonUniversity/LLMCompass)


<a id="onnxim"></a>
## ONNXIM — ONNXim: A Fast, Cycle-Level Multi-Core NPU Simulator

IEEE CAL，2024。类别：NPU模拟器。

- **被模拟硬件**：多核ASIC NPU；EPYC是仿真宿主
- **目的**：快速NPU算子/多核/存储设计探索
- **工具链**：ONNX图/指令+tile计算延迟；Ramulator、BookSim
- **建模层级**：计算tile时序、DMA依赖、DRAM/NoC周期争用；无已核实数值功能后端
- **工艺/PVT**：工艺由目标另行给定；论文不是ASIC PPA实现
- **频率/时基**：TableII两种目标1GHz
- **能量/面积来源**：主要输出周期/利用率；无现成校准全PPA
- **存储与DRAM**：8×8或128×128阵列、DDR4/HBM2；KV增长/GQA研究
- **模型/场景**：GPT-3 prefill/decode，512输入/100生成；Llama3 GQA/MHA
- **代表结果及条件**：0.23% MAE仅8×8 Gemmini核GEMM/Conv，验证排除DRAM/NoC
- **验证证据**：对Gemmini RTL局部核验；开源
- **局限/不能推导的结论**：不能引用0.23%作LLM系统误差；需新增随机算子、索引流、读出和能量表
- **原文定位**：§II、III-A/C/E，TableII
- **本轮访问核查范围**：全文HTML与官方入口核读

原始来源：[来源1](https://arxiv.org/html/2406.08051v1)；[来源2](https://github.com/PSAL-POSTECH/ONNXim)


<a id="pytorchsim"></a>
## PYTORCHSIM — PyTorchSim: A Comprehensive, Fast, and Accurate NPU Simulation Framework

MICRO，2025。类别：NPU模拟器。

- **被模拟硬件**：可编程NPU；TOGSim为其内部Tile-Operation Graph后端
- **目的**：联合编译、功能、时序及融合研究
- **工具链**：PyTorch→RISC-V/NPU指令；Spike功能；扩展gem5 tile时序；TOGSim+Ramulator2/BookSim
- **建模层级**：功能执行与分块事件/周期时序解耦；softmax/转换/归约/融合
- **工艺/PVT**：目标参数可配置；非工艺PPA库
- **频率/时基**：TPUv3型940MHz；16MB scratchpad/core
- **能量/面积来源**：论文核心输出功能/时间；没有开箱完整PPA
- **存储与DRAM**：Ramulator2/BookSim争用；数据相关稀疏可由Spike供tile信息
- **模型/场景**：GEMM/Conv/LN/softmax/attention、ResNet/BERT；当前代码含Llama decode
- **代表结果及条件**：TPUv3型单核runtime MAE11.5%；稀疏对SST-STONNE误差1.1–2.6%
- **验证证据**：单核目标/多类算子验证；开源
- **局限/不能推导的结论**：11.5%非所有LLM误差；通用dynamic-shape仍列后续；p-bit需要功能、指令、时序和成本接口
- **原文定位**：§3/Table2；§4 PDF9–11页；§5.1
- **本轮访问核查范围**：全文PDF与当前代码说明核读

原始来源：[来源1](https://jongse-park.github.io/files/paper/2025-micro-pytorchsim.pdf)；[来源2](https://github.com/PSAL-POSTECH/PyTorchSim)


<a id="scalesim"></a>
## SCALESIM — SCALE-Sim v3: A modular cycle-accurate systolic accelerator simulator for end-to-end system analysis

ISPASS，2025。类别：矩阵阵列模拟器。

- **被模拟硬件**：脉动阵列ASIC，核心GEMM/Conv
- **目的**：多核/稀疏/布局/存储分析
- **工具链**：SCALE-Sim v3+Ramulator+Accelergy(CACTI/Aladdin)
- **建模层级**：阵列周期与访问轨迹；非数值LLM执行
- **工艺/PVT**：成本由配置/插件工艺给定，无统一节点
- **频率/时基**：配置给定，无统一GHz
- **能量/面积来源**：动作计数接Accelergy估能量/功率
- **存储与DRAM**：多核共享L2、稀疏、SRAM布局/端口、Ramulator
- **模型/场景**：矩阵/CNN及稀疏Vegeta；非全部LLM非线性/serving
- **代表结果及条件**：新增1:4/2:4稀疏对RTL误差≤5%；不是整机能耗误差
- **验证证据**：阵列RTL、Accelergy、Ramulator分别验证；新增稀疏局部核对
- **局限/不能推导的结论**：p-bit非脉动数据通路需换计算模型；2026TPU扩展已增实测回归，参数不能直接迁移
- **原文定位**：v3 §VII–VIII；2026扩展另列来源
- **本轮访问核查范围**：全文HTML与官方代码入口核读

原始来源：[来源1](https://arxiv.org/html/2504.15377v1)；[来源2](https://github.com/scalesim-project/scale-sim-v3)；[来源3](https://arxiv.org/html/2603.22535v1)


<a id="timeloop"></a>
## TIMELOOP — Timeloop: A Systematic Approach to DNN Accelerator Evaluation

ISPASS，2019。类别：映射/分析工具。

- **被模拟硬件**：可参数化DNN ASIC及分层存储
- **目的**：联合architecture/mapping DSE
- **工具链**：Timeloop分析模型与搜索器
- **建模层级**：循环、空间/时间映射、动作计数和吞吐/带宽约束；非事务全系统
- **工艺/PVT**：依技术成本表；文中65nm/16nm示例
- **频率/时基**：用户配置/时间模型
- **能量/面积来源**：输出周期/能量/面积，依赖组件成本
- **存储与DRAM**：分层容量/复用/带宽/互连；原论文非LLM KV/softmax模型
- **模型/场景**：107个DeepBench用于能量验证；另组合成workload用于周期验证；另有Eyeriss/AlexNet复现
- **代表结果及条件**：107个DeepBench能量误差≤8%；合成工作负载预测/参考周期比78–99%、均值95%；65→16nm重搜映射最高节能22%
- **验证证据**：与专用NVDLA参考模型对照，六个周期outlier指向传输/布局停顿
- **局限/不能推导的结论**：不是所有硬件95%准确；工艺变化可能改变最优映射；候选仍需TLM合法性复查
- **原文定位**：§VII PDF7–8页、§VIII-B
- **本轮访问核查范围**：全文PDF核读

原始来源：[来源1](https://people.csail.mit.edu/anurag_m/papers/2019.timeloop.ispass.pdf)；[来源2](https://github.com/NVlabs/timeloop)


<a id="accelergy"></a>
## ACCELERGY — Accelergy: An Architecture-Level Energy Estimation Methodology for Accelerator Designs

ICCAD，2019。类别：能耗估计框架。

- **被模拟硬件**：ASIC/自定义器件组件，不负责调度
- **目的**：由动作和技术能量表组合系统能量
- **工具链**：primitive/compound组件+插件ERT；可接CACTI/Aladdin和用户表
- **建模层级**：动作计数×energy/action；时间/事件由外部模型给出
- **工艺/PVT**：示例Aladdin40nm；验证Eyeriss65nm；不是统一40nm标准
- **频率/时基**：动作能量表需匹配技术/PVT；静态能量和平均功率换算需持续时间；不验证Fmax
- **能量/面积来源**：能量，当前亦支持面积表；未列组件不会自动计入
- **存储与DRAM**：存储可用插件；DRAM刷新/后台/CDC需显式建模
- **模型/场景**：65nm Eyeriss、AlexNet/ImageNet、16bit
- **代表结果及条件**：总能量估计在post-layout参考5%误差以内；关键能量分项占比相对差异8%以内
- **验证证据**：小模块post-layout生成能量表+cycle计数；全模块P&R功耗作ground truth
- **局限/不能推导的结论**：该5%不继承到p-bit；没有调度器、没有自动补齐漏项；需明确状态能量/clock边界
- **原文定位**：§2；§5.1/5.3 PDF6–7页
- **本轮访问核查范围**：全文PDF核读

原始来源：[来源1](https://accelergy.mit.edu/paper.pdf)；[来源2](https://github.com/Accelergy-Project/accelergy)


<a id="zigzag"></a>
## ZIGZAG — ZigZag: Enlarging Joint Architecture-Mapping Design Space Exploration for DNN Accelerators

IEEE TC，2021。类别：映射/分析工具。

- **被模拟硬件**：DNN ASIC，现代码含数字/模拟IMC
- **目的**：扩展不均匀存储复用的architecture/mapping搜索
- **工具链**：ZigZag分析模型+映射搜索
- **建模层级**：循环/分层存储分析；非数值、非DRAM命令模型
- **工艺/PVT**：早期稿CACTI7、65nm；当前由用户工艺参数给定
- **频率/时基**：主要报告周期；换算秒需指定可实现频率；本次未核到统一频率
- **能量/面积来源**：energy/latency/area来自组件表/工具输入
- **存储与DRAM**：搜索空间/容量/复用约束；真实队列、端口/DRAM须外部核查
- **模型/场景**：早期稿Eyeriss/ENVISION及内部加速器
- **代表结果及条件**：早期稿能量误差约5%/7.5%；内部post-synthesis能量≤6%、PE利用率≤9%
- **验证证据**：对发表的Eyeriss/ENVISION结果及内部post-synthesis结果核对；精确百分比来自早期全文
- **局限/不能推导的结论**：正式全文该数字未核；搜索最优只对表达的空间；IMC支持不等于支持随机FFN/Ising
- **原文定位**：早期稿§V–VI PDF10–11页；当前hardware文档
- **本轮访问核查范围**：早期全文+正式元数据，最终全文未核

原始来源：[来源1](https://ieeexplore.ieee.org/document/9360462/)；[来源2](https://arxiv.org/pdf/2007.11360)；[来源3](https://github.com/KULeuven-MICAS/zigzag)；[来源4](https://kuleuven-micas.github.io/zigzag/hardware.html)


<a id="accelsim"></a>
## ACCELSIM — Accel-Sim: An Extensible Simulation Framework for Validated GPU Modeling / AccelWattch

ISCA2020 / MICRO2021；2.0为2026预印本，2020。类别：GPU模拟器。

- **被模拟硬件**：商用GPU；不是p-bit ASIC
- **目的**：GPU微架构和能耗评估
- **工具链**：SASS trace驱动周期模型；AccelWattch功耗；2026扩展TMA/WGMMA/vLLM
- **建模层级**：GPU指令/缓存/互连；数值与控制流来自取trace目标
- **工艺/PVT**：依GPU校准配置；无统一ASIC节点
- **频率/时基**：功耗校准需固定频率/温度；不可任意改GHz即称可实现
- **能量/面积来源**：AccelWattch GV100 SASS-SIM功耗MAPE9.2%、HW计数模式7.5%
- **存储与DRAM**：GPU缓存/DRAM/互连；新的稀疏控制流需新trace
- **模型/场景**：2026预印本H100含Llama3.1-8B、Qwen2.5-7B等；prefill+1decode；层抽样
- **代表结果及条件**：2026v1 H100周期MAPE13.5%；Llama3.1-8B/Qwen2.5-7B推理19.6%/21.1%；官网摘要13.4%，采用v1，差异原因未进一步核实
- **验证证据**：真实GPU性能/功耗校准；模式、版本与workload特定
- **局限/不能推导的结论**：总体误差不可替代LLM误差；GPU功耗不能简单换成p-bit单元能耗后认作ASIC PPA
- **原文定位**：AccelWattch§4/§6 Fig7；2026v1 §VI/TableVI
- **本轮访问核查范围**：论文与官方版本核读

原始来源：[来源1](https://accel-sim.github.io/)；[来源2](https://github.com/accel-sim/accel-sim-framework)；[来源3](https://people.ece.ubc.ca/aamodt/papers/accelsim.isca2020.pdf)；[来源4](https://paragon.cs.northwestern.edu/papers/2021-MICRO-AccelWattch-Kandiah.pdf)；[来源5](https://arxiv.org/html/2608.22602v1)


<a id="astrasim"></a>
## ASTRASIM — ASTRA-sim（含2026 ASTRA-sim 3.0扩展）

ISPASS2020/2023；3.0为2026预印本，2020。类别：多设备系统模拟器。

- **被模拟硬件**：分布式加速器/通信；3.0扩展片上资源
- **目的**：多GPU/多设备计算通信争用
- **工具链**：可插拔compute/memory/network；3.0 CU/wavefront与load/store
- **建模层级**：事件/资源层；ReduceOp可用给定周期
- **工艺/PVT**：组件配置而非统一工艺
- **频率/时基**：组件配置/给定周期
- **能量/面积来源**：本次未核得新p-bit电路/PVT能耗来源
- **存储与DRAM**：片上与跨设备争用；适合远程KV/分离prefill-decode
- **模型/场景**：分布式DNN；3.0扩展工作负载
- **代表结果及条件**：本次未找到可引用整系统误差百分比：NR
- **验证证据**：公开工具/论文；未重跑
- **局限/不能推导的结论**：不能再概括只有网络；也不宜作本项目单芯片PPA主后端
- **原文定位**：官方论文索引；3.0 §4
- **本轮访问核查范围**：官方资料与3.0方法段核读

原始来源：[来源1](https://astra-sim.github.io/)；[来源2](https://github.com/astra-sim/astra-sim)；[来源3](https://arxiv.org/html/2606.10440v1)


<a id="mba"></a>
## MBA — MBA: Mega-Buffer Architecture Based on 1T1C IGZO eDRAM for Efficient LLM Inference

DAC，2026。类别：IGZO eDRAM ASIC。

- **被模拟硬件**：具有GB级片上eDRAM的专用LLM架构；A100为对照
- **目的**：以KV优先、双缓冲、iteration-aware淘汰减少HBM流量
- **工具链**：自研behavior-level计算图模拟器；修改FinCACTI；DeepScaleTool；遗传搜索
- **建模层级**：行为/算子图时延能量模型；非明确周期级
- **工艺/PVT**：目标7nm；PE成本由45nm文献缩到7nm；非7nm整芯片P&R
- **频率/时基**：PE 0.5GHz；其他模块频率NR
- **能量/面积来源**：估计569.87mm²、615TOPS；SFU/NoC借文献；eDRAM改FinCACTI
- **存储与DRAM**：96blocks，各25×16×16PE与24MB eDRAM；总local2.25GB、global640MB；HBM1.5TB/s、3.9pJ/bit
- **模型/场景**：Llama3.1-8B/Qwen3-14B，WT2；MBA/A100 W8A8 SmoothQuant，COMET W4A4KV4；prefill/decode均评
- **代表结果及条件**：对GPU/COMET报告E2E速度5.99×/3.63×、能效8.86×/4.93×
- **验证证据**：明确参数和行为模型；本次全文未见硬件时序/能量误差校准
- **局限/不能推导的结论**：不同精度、工艺投影与存储模型拼接；未证明A100每项测量流程；结果非新ASIC实测
- **原文定位**：用户509_Camera_Ready_Paper.pdf第5页§5/6、Table1、Fig7；全文6页；DAC官方节目
- **本轮访问核查范围**：用户PDF全文核读，第5页渲染核表；公开元数据核对

原始来源：[来源1](https://63dac.conference-program.com/presentation/?id=RESEARCH509&sess=sess318)


<a id="ascend"></a>
## ASCEND — ASCEND: Accurate yet Efficient End-to-End Stochastic Computing Acceleration of Vision Transformer

DATE，2024。类别：随机数字ASIC。

- **被模拟硬件**：ViT随机计算电路/加速器；不是生成LLM
- **目的**：SC GELU/迭代近似softmax与训练协同
- **工具链**：RTL+Synopsys DC；软件ViT训练/评估
- **建模层级**：综合级非线性模块面积延迟；加速器面积汇总；网络质量
- **工艺/PVT**：TSMC28nm；V/PVT NR
- **频率/时基**：未给统一整机时钟；表内Delay不能取倒数冒充整机频率
- **能量/面积来源**：softmax m64，By8：1.62e5µm²/16.20ns；TableVI推荐配置总面积4.47e6µm²
- **存储与DRAM**：未查到完整外DRAM、调度、I/O和整机能耗模型
- **模型/场景**：7层4头ViT，CIFAR10/100；W2-A2-R16；训练/近似感知微调
- **代表结果及条件**：GELU/softmax最高ADP改善5.29×/12.6×；推荐准确率90.79/66.18%，FP参考94.52/73.80%
- **验证证据**：RTL综合与软件任务质量；器件无物理随机源实测
- **局限/不能推导的结论**：end-to-end指SC计算/网络路径；ADP为局部模块；不能当LLM端到端latency/energy证据
- **原文定位**：用户71_pdf_upload.pdf第5–6页§VI、TablesIII–VI
- **本轮访问核查范围**：用户全文PDF核读，第5页渲染核表

原始来源：[来源1](https://arxiv.org/abs/2402.12820)；[来源2](https://arxiv.org/html/2402.12820v1)


<a id="isingsot"></a>
## ISINGSOT — Energy-Efficient Parallel Ising SoftMax Engine for Transformer Attention Based on Asynchronous SOT-P-Bits

IEEE Electron Device Letters，2026。类别：物理p-bit+模拟系统。

- **被模拟硬件**：实验SOT-MTJ器件与异步Ising softmax；网络替换用功能仿真
- **目的**：物理Boltzmann分布实现softmax并做器件补偿
- **工具链**：实测器件概率特性+Ising ensemble演化模拟+模型函数替换
- **建模层级**：器件实测；分布/功能仿真；外围未整合
- **工艺/PVT**：SOT-MTJ堆栈实验工艺；不对应一个完整数字ASIC节点；CMOS PVT NR
- **频率/时基**：异步；16/32µs是演化时间，不是GHz时钟或完整读出时间
- **能量/面积来源**：约0.26pJ/bit为引用器件条件的概率核心投影；不含输入准备/输出读出
- **存储与DRAM**：§IV明确完整外围输出实现超出范围；DRAM/整机调度NR
- **模型/场景**：DeepSeek-LLM-7B-Base、TinyLlama1.1B、DistilGPT2；WT2 PPL与Self-BLEU；历史Base仅作文献
- **代表结果及条件**：N=10^9独立副本ensemble分布约32µs达到文中FP16比较线；功能PPL接近FP参考
- **验证证据**：实验器件+分布模型；非完整softmax引擎/LLM整机实测
- **局限/不能推导的结论**：ensemble分布精度不等于单实例有限时间计数精度；0.26pJ/bit不能直接算整机；输入/读出须补
- **原文定位**：用户SOT-P-Bits PDF第1页器件/第3页§IV、Figs4–5
- **本轮访问核查范围**：用户作者接受稿全文核读，第3页渲染核对

原始来源：[来源1](https://doi.org/10.1109/LED.2026.3691358)


<a id="dramsys"></a>
## DRAMSYS — DRAMSys4.0: An Open-Source Simulation Framework for In-depth DRAM Analyses

International Journal of Parallel Programming，2022。类别：DRAM时序后端。

- **被模拟硬件**：特定JEDEC标准+特定控制器行为
- **目的**：快速且保留时序的DRAM系统探索
- **工具链**：SystemC TLM2.0 AT、扩展DRAM-AT命令协议；可嵌Verilator RTL；DRAMPower
- **建模层级**：事件驱动TLM可保留周期级JEDEC约束；不是逐拍信号仿真
- **工艺/PVT**：随memspec；软件没有统一ASIC工艺
- **频率/时基**：示例控制器:PHY为1:4；宿主i9 5GHz不是被模拟时钟
- **能量/面积来源**：可耦合DRAMPower；不自动给全芯片PPA
- **存储与DRAM**：bank/row、scheduler、refresh/power-down、response queue及trace analyzer
- **模型/场景**：MediaBench与特定RTL DDR3控制器；不同访存密度
- **代表结果及条件**：调整后平均带宽偏差1.2%、平均响应1.0%；逐事务平均相对误差6.12%（含refresh）
- **验证证据**：与特定RTL对照；关闭refresh后逐事务误差<1%；明确平均误差可能掩盖分布
- **局限/不能推导的结论**：没有跨所有控制器的黄金RTL；JEDEC合法不等于目标系统准确；public/授权扩展标准按版本区分
- **原文定位**：§2.1/2.4、§3 Table2/Fig7、§5.1
- **本轮访问核查范围**：全文与官方README核读

原始来源：[来源1](https://link.springer.com/article/10.1007/s10766-022-00727-4)；[来源2](https://github.com/tukl-msd/DRAMSys)


<a id="ramulator2"></a>
## RAMULATOR2 — Ramulator 2.0: A Modern, Modular, and Extensible DRAM Simulator

IEEE CAL，2023。类别：DRAM时序后端。

- **被模拟硬件**：可扩展DRAM标准/控制器
- **目的**：快速新内存机制研究
- **工具链**：Ramulator2可插拔控制器/设备；命令trace
- **建模层级**：DRAM周期级；不包含完整NPU与电路PPA
- **工艺/PVT**：由内存规格定义，不等于ASIC节点
- **频率/时基**：由DRAM speed grade/timing给定
- **能量/面积来源**：时间后端；功耗需独立模型/适配；当前扩展按版本核
- **存储与DRAM**：行/列/命令约束；输入请求率/地址流决定结果
- **模型/场景**：8类stream+8类random合成trace，多请求强度
- **代表结果及条件**：原论文Micron DDR4 Verilog检查未见时序/状态转换违规；不是延迟预测0%误差
- **验证证据**：输出命令trace送Micron Verilog验证；2026新增2.1论文须单独引用
- **局限/不能推导的结论**：协议正确不能代替系统接口/多通道/CPU前端校准；当前仓库能力勿倒填2023论文
- **原文定位**：2023论文§3.1；2026更新仅作版本提醒
- **本轮访问核查范围**：原文方法与官方资料核读

原始来源：[来源1](https://arxiv.org/abs/2308.11030)；[来源2](https://people.inf.ethz.ch/omutlu/pub/Ramulator2_arxiv23.pdf)；[来源3](https://github.com/CMU-SAFARI/ramulator2)；[来源4](https://arxiv.org/abs/2606.13844)


<a id="drampower"></a>
## DRAMPOWER — DRAMPower: Open-source DRAM Power & Energy Estimation Tool

官方工具；相关模型DSD2011/DATE2013/DAC2013，2013。类别：DRAM能耗后端。

- **被模拟硬件**：DRAM core及可选interface/termination
- **目的**：命令/状态轨迹转能量
- **工具链**：DRAMPower，核读README6.3.1；memspec+command trace+data/toggle
- **建模层级**：命令和状态时间积分；不负责调度或合法性验证
- **工艺/PVT**：电流电压来自具体内存规格/模型；非通用logic节点
- **频率/时基**：memspec timing以DRAM cycles；电流等采用SI单位
- **能量/面积来源**：core与interface分别算；RD/WR IDD不含I/O，需另计；不是整个控制器/PHY芯片成本
- **存储与DRAM**：含ACT/PRE/RD/WR/background等；rank处理与idle假设须检查
- **模型/场景**：合法命令trace；可带数据或toggle rates
- **代表结果及条件**：工具输出能量/功率，没有通用实测误差保证
- **验证证据**：项目说明模型曾对等效电路验证；用户必须提供合法trace与相容参数
- **局限/不能推导的结论**：自身不检查trace时序合法；官方master是开发版；不能把2018旧版误差套6.3.1，也不能称自动精准
- **原文定位**：README Usage、Memory Specifications、Variation-aware、Disclaimer
- **本轮访问核查范围**：官方当前说明核读

原始来源：[来源1](https://github.com/tukl-msd/DRAMPower)


<a id="vampire"></a>
## VAMPIRE — What Your DRAM Power Models Are Not Telling You: Lessons from a Detailed Experimental Study

SIGMETRICS / POMACS，2018。类别：DRAM实测校准。

- **被模拟硬件**：DDR3L真实模块，不是LLM加速器
- **目的**：揭示IDD/data/结构差异并拟合功耗
- **工具链**：50条DDR3L模块、三厂商实验；VAMPIRE
- **建模层级**：命令+数据值/模块结构变化的经验模型
- **工艺/PVT**：测试模块各自工艺代际；不提供LLM统一ASIC节点
- **频率/时基**：DDR3规格；非NPU核心时钟
- **能量/面积来源**：实测电流功耗校准；模型纳入data/结构差异
- **存储与DRAM**：DDR3L；公开trace模型和测量数据
- **模型/场景**：模块命令/数据模式测试；非现代HBM直接验证
- **代表结果及条件**：测试集MAPE6.8%；同文旧DRAMPower32.4%是当时模块/版本结果
- **验证证据**：直接器件/模块实测与误差评估
- **局限/不能推导的结论**：不能把6.8%搬到DDR4/HBM；也不能据旧版32.4%否定新DRAMPower；说明需平台校准
- **原文定位**：§9.1及相关工作；作者原文/研究组摘要
- **本轮访问核查范围**：作者原文与官方项目核读

原始来源：[来源1](https://ghose.cs.illinois.edu/papers/18sigmetrics_vampire.pdf)；[来源2](https://pdl.cmu.edu/PDL-FTP/associated/18sigmetrics_vampire_abs.shtml)；[来源3](https://github.com/CMU-SAFARI/VAMPIRE)


<a id="memintegration"></a>
## MEMINTEGRATION — Integration, Enhancements and Evaluation of Memory Simulators

arXiv预印本，2026。类别：模拟器集成验证。

- **被模拟硬件**：CPU系统+多个DRAM模拟器；方法可迁移NPU
- **目的**：检查接口时钟/响应语义是否破坏内存模型
- **工具链**：ZSim+Ramulator/Ramulator2/DRAMsim3/DRAMSys4
- **建模层级**：三视角：DRAM后端、CPU–内存接口、应用观察
- **工艺/PVT**：真实测试平台/配置特定；非新ASIC工艺
- **频率/时基**：重点时间域一致性；不是统一频率模型
- **能量/面积来源**：主要验证性能，不能作新器件能耗证据
- **存储与DRAM**：修复immediate-response与delayed-response模型不匹配；地址映射/NoC/预取
- **模型/场景**：STREAM与pointer-chase等内存基准
- **代表结果及条件**：修复后多数STREAM带宽差<5%，pointer-chase延迟仍低15–18%
- **验证证据**：三视角与真实硬件对照；公开修改；2026-10-11 v1
- **局限/不能推导的结论**：预印本，非四会接收证明；成熟后端接好后仍可能有前端接口误差
- **原文定位**：§II-B、IV-A/B、VI-B/C；摘要
- **本轮访问核查范围**：全文方法/结果核读

原始来源：[来源1](https://arxiv.org/html/2610.15873v1)


<a id="santa"></a>
## SANTA — Stochastic Sparse Attention for Memory-Bound Inference

ICML，2026。类别：GPU软件/随机算法。

- **被模拟硬件**：RTX6000Ada上CUDA/PyTorch kernel；没有新ASIC
- **目的**：V采样和gather-add减少decode带宽
- **工具链**：GPU实测+随机算法数学/软件验证；非新硬件模拟器
- **建模层级**：kernel与批生成实测；prefill保持dense
- **工艺/PVT**：商用GPU；论文没有新ASIC工艺实现，不能填55/7nm为该方法工艺
- **频率/时基**：GPU具体锁频设置本次未核得；不是自定ASIC时钟
- **能量/面积来源**：能量讨论与硬件实现分开；无p-bitASIC面积/器件能耗证明
- **存储与DRAM**：实际GPU KV读写；采样V行，QK扩展另列
- **模型/场景**：v2 §3.5/Table3 Llama-3.1-8B-Instruct，BF16权重/KV，30k输入、B6、每prompt2048输出，9batches平均
- **代表结果及条件**：decode101.22→80.97s/batch，1.25×；ms/output-token8.237→6.589=批总时间/(6×2048)
- **验证证据**：真实GPU性能+质量+公开kernels
- **局限/不能推导的结论**：6.589ms不是单请求TPOT；kernel1.5×不等于全请求1.5×；不能视为物理随机源验证
- **原文定位**：v2 §3.4–3.6、Table3；正式proceedings与官方代码
- **本轮访问核查范围**：v2全文HTML/Table3、用户图与正式会议页核读

原始来源：[来源1](https://arxiv.org/html/2605.01910v2)；[来源2](https://proceedings.mlr.press/v306/lee26j.html)；[来源3](https://github.com/OPUSLab/SANTA)
