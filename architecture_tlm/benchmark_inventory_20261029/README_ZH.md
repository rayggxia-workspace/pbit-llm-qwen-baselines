# p-bit for LLM：分模块与端到端 Benchmark、比较论文及数据对照

整理日期：2026-10-29（北京时间）。正式项目：`rayggxia-workspace/pbit-llm-qwen-baselines`。

这是一份从 **workspace已有调研报告、结果报告及待审分支** 整理出的可查用清单，回答：**测哪个benchmark、替换什么方案、与哪篇文章/哪种对手比较、有哪些数值、这些数值属于什么边界**。

本轮没有新模型训练、PPL/任务推理、TLM、RTL或EDA运行，也没有将文献倍率重新包装成本项目结果。原论文中的数字是“原调研已核并摘录”，并非本轮逐篇重读原始PDF或复现实验。本文列出的对手是当前摘录数据对应的对手，不保证穷尽每篇原文的全部baseline。

## 0. 怎么查这份文件

- 看 **§1**：我们可以采用的模块级与端到端benchmark总清单。
- 看 **§2–3**：逐篇论文的方案、对手、模型/数据、质量/PPA数值与实验条件。
- 看 **§4**：数字Softmax与采样的可直接查用数表；其中概率输出和采样索引输出分别比较。
- 看 **§5**：各类任务对应什么指标，防止同名数据集不同任务混淆。
- 看 **§6**：我们已有的数据、当前配置与出处；主线、历史分支和待审结果分开。
- 看 **§7–9**：比较表应保留的字段、尚缺数据的文章及固定版本来源。

### 0.1 来源与状态

| 来源 | 本次固定版本 | 状态 / 用途 |
|---|---|---|
| main | `787489192ebfcdb61ad72edde406818f450aa3dc` | 当前正式主线；整机TLM、PPA台账与模拟器证据调研 |
| 历史集成分支 | `d6d33995754fcdcea99286e4ce43f91647aa231a` | 包含benchmark协议、逐论文任务指标表、旧Qwen/Llama最终结果；未全部搬入当前main |
| PR199 | 刷新head `01270f9c50d9475017603bf2ee7148193280ded7`；部分结果固定于其祖先 `c7de5064…` | open / draft、未合并；Attention质量、数字Softmax与数字采样边界 |
| PR207 | `104a2e4931782a698388abcb38e71ae059d73636` | open、未合并；Qwen3 FFN与Z1T指标映射 |
| PR209 | `9228b08ca20230600ac41eba479f14228d19b5be` | open、未合并；同64路INT8与BF16核对照 |

表中状态为2026-10-29资料整理时的GitHub只读核验快照，不随后续PR更新而自动改变；所有来源均固定commit。本文补充关联Issue #98，交付分支为`task/98-benchmark-paper-inventory-20261029`，实际PR回执见[PUBLICATION.json](../../work/amlink1219/98/benchmark_inventory_20261029/PUBLICATION.json)。

### 0.2 读表规则

1. **NR-摘录缺失**：现有workspace报告没有摘出这个数字；不表示原论文一定未报告。表中若明确“原文未找到”，只是原调研已阅读范围的结论。
2. **局部、模块、系统、服务请求**分别标记。GEMM加速、Attention加速与完整请求加速不互换。
3. “整模型质量”表示误差经过完整网络；“完整WT2”表示覆盖全部目标；“完整硬件端到端”表示执行与计费边界。三者独立。
4. 除原报告明确给出外，本文不从图上目测精确值，不以TDP当实测功率，不从TOPS/W倒推出J/token。
5. 本项目指定面积折算为`A_55等效=A_raw×0.81`，只适用于本项目相应原始工艺流程；外部论文不套这个系数，功耗/时延也不乘0.81。

## 1. 可以采用哪些benchmark

### 1.1 模块级

| ID | Benchmark / 输入合同 | 应比较的方案 | 必报数据 | 对应论文卡片 / 本项目来源 |
|---|---|---|---|---|
| B-MAT | 明确M/K/N、W/A/累加位宽的GEMV/GEMM；本项目已有N64、M1/M8、T32合成核；真实层张量另列 | BF16/FP32、匹配W8确定性、位串行、SC精确树/位平面/先计数、OR4 | 面积、运行/空闲功率、J/完整矩阵或点积、延迟、II、bias/RMSE/NRMSE；同一事件流oracle与精确量化oracle分开 | [M01](#m01)–[M07](#m07)；[S12]/[S14]/[S15] |
| B-FFN | 完整`gate/up→SiLU(g)×u→down`；固定层范围、尺度、采样与接口 | 原BF16、确定性W8、随机W8、P-DNN重训路线分别命名 | 每投影/非线性误差与成本；FFN调用能量/时延；替换后的完整模型PPL和任务分数 | [M01](#m01)–[M04](#m04)；[S17]/[S18] |
| B-SMX | 一整行N=128/512/2048/8192分数；普通Softmax输出概率 | 有限精度浮点、整数/LUT/PWL、在线/融合数字实现 | 整行周期、首/末输出延迟、II、面积、能量；输入/输出精度与存储边界；分布/输出误差 | [M10](#m10)–[M14](#m14)；§4.1 |
| B-SAMPLE | 相同候选分数→可供V读取的索引或命中次数；N、S、预热固定 | 数字CDF+IID、systematic计数、Ising赢家保持；准确dense PV为另一条无采样控制 | 准备/采样/仲裁/压缩能量、总延迟、II、面积、随机需求、次数守恒、bias/ESS/相关性 | [M14](#m14)/[M15](#m15)；[S10] |
| B-ATTN | 核心QK/归一化/PV，及完整QKV/RoPE/KV追加/Wo两个边界；历史KV长度512/2048/8192 | 融合在线数字、仅V采样、仅筛选、筛选+有限采样；保持相同GQA与KV布局 | 完整模块J/token、延迟、面积、K/V物理字节、GQA并集、去重命中次数、筛选摘要成本、PPL | [M08](#m08)–[M15](#m15)；[S08]/[S21] |
| B-NL | SiLU/sigmoid/tanh/FSM、编码恢复、BF16/FP32↔整数等逐模块 | 精确/有限精度数字与概率方案；参数/范围匹配 | 最大误差、RMSE、饱和/溢出、端点、面积、J/调用、延迟/II，再做模型质量门禁 | [M13](#m13)；[S22] |
| B-RNG | 原始源、扩展/PRNG、阈值比较与分发端点；明确输出随机字宽/数量 | LFSR、GF64、Bivium、分层/低差异、物理源模型 | pJ/字或端点事件、供给率、并发、面积、状态功率；偏差/相关性/ESS；原始熵与逻辑字分开 | [S04]/[S07]/[S22]；§3.3补充 |
| B-MEM | SRAM读写、bank/端口、DMA/DRAM访问trace；逻辑需求与实际burst分别计 | 驻留/流式、预取/双缓冲、本地/全局通路、DDR4/HBM | pJ/读写、容量、面积、持续带宽、ACT/PRE/row-hit、排队/回压、DRAM背景与I/O能量 | [E02](#e02)、[E04](#e04)–[E08](#e08)；[S06]/[S11] |

64×64只是已有工程点，不是所有论文共同规定的benchmark。矩阵形状相同仍须对齐数制、输出数量、驻留权重、流长、并行上下文和近似误差。

### 1.2 整模型、整机与请求级

| ID | Benchmark | 具体工作负载 / 控制 | 数据与指标 | 当前已有 / 建议范围 |
|---|---|---|---|---|
| B-LM | 完整语言建模 | 同checkpoint/tokenizer/语料；WT2 raw window2048/stride1024；BF16、FFN-only、Attention-only、joint | 目标数、总NLL、PPL、CE nats/token、bits/token；逐seed、计分覆盖与替换层覆盖 | 已有Qwen2.5/Llama2及待审Qwen3结果，§6；第二语料需另立协议 |
| B-TASK | 常识/选择题 | PIQA、ARC-E完整；Qwen历史HellaSwag固定1000题子集；zero-shot | acc、acc_norm、逐题差分、题数/ID、seed SD；完整题集与子集分开 | 已有Qwen39项、Llama2-7B26项；DS-CIM六任务的其余任务不能标成我们已完成 |
| B-LONG | 长文问答/检索 | LongBench HotpotQA/NarrativeQA或明确的检索变体；固定有效长度/KV预算/输出 | EM、QA F1、Recall@k/nDCG等；候选保留与物理KV流量 | 有论文对照与建议，尚不能据短题all-K宣称长筛选验证完成 |
| B-REQ | 固定请求/自由生成 | 建议B1/B4、输入/输出128/512、2048/128；Qwen可补8192/128；检查原生上下文 | TTFT、TPOT、ITL p50/p95/p99、E2E、输出tokens/s、实际输出数与EOS | 这是协议建议，不表示全部跑完；当前main主基线为B1/2K/一个decode步且无prefill |
| B-PPA | 整机能量与面积 | 与质量配置绑定，分别记录chip/core/SRAM/外存/PHY与实际时长 | 平均W、J/request、J/output-token、tokens/J、mm²、tokens/s/mm²、EDP/AEDP、未计成本覆盖率 | 已有局部表征和系统估算；完整物理PPA仍未闭合，§6.5 |
| B-SCALE | 规模/训练与算量 | 固定tokenizer和数据；宽/深/connectivity/训练预算扫描 | loss、参数量、训练FLOPs、tokens_seen；推理参考MAC/FLOPs单独列 | Z1T有训练scaling；我们已有CE/参数/MAC派生，不等于拥有训练scaling曲线 |

### 1.3 每种替换至少保留的控制

| 控制 | 用来隔离什么 |
|---|---|
| 原BF16 + 准确Attention | 原模型质量与数字行为基准 |
| 确定性W8/匹配激活编码和恢复 | 量化、尺度、裁剪/舍入造成的损失 |
| FFN-only | 随机FFN或P-DNN的独立影响 |
| Attention-only | 筛选、Softmax近似、有限采样的独立影响 |
| FFN+Attention joint | 联合误差与交互，不能用两个独立结果相加 |
| 理想IID / 有限CTMC / 实际随机服务 | 将算法理想值、相关性和真实源成本分开 |
| 同资源与同总面积两组实验 | 两种约束分别搜索数字/概率合法映射，不混为一个公平性条件 |

来源：[S01] §8、[S06]、[S08]及[S10]。

## 2. 模块级逐篇论文：比较什么、与谁比较、有哪些数据

| 编号 | 工作 | 主要比较范围 |
|---|---|---|
| [M01](#m01) | DS-CIM: Digital Stochastic Computing-In-Memory Featuring Accurate OR-Accumulation via Sample Region Remapping for Edge AI Models | 32Kb SRAM随机CIM宏；LLM为软件误差注入 |
| [M02](#m02) | FIGNA: Integer Unit-Based Accelerator Design for FP-INT GEMM Preserving Numerical Accuracy | 新设计FP-INT GEMM ASIC；对照FP-FP Engine也重实现 |
| [M03](#m03) | Anda: Unlocking Efficient LLM Inference with a Variable-Length Grouped Activation Data Format | 可变尾数位串行GEMM ASIC；GPU-like基线是建模的空间加速器 |
| [M04](#m04) | AxCore: A Quantization-Aware Approximate GEMM Unit for LLM Inference | 近似混合精度GEMM ASIC |
| [M05](#m05) | uGEMM: Unary Computing Architecture for GEMM Applications | Unary GEMM算术架构；另有小型MLP，非LLM。 |
| [M06](#m06) | SASCHA: Sparsity-Aware Stochastic Computing Hardware Architecture for Neural Network Acceleration | 随机CNN加速器。 |
| [M07](#m07) | tubGEMM: Energy-Efficient and Sparsity-Effective Temporal-Unary-Binary Based Matrix Multiply Unit | 整数矩阵乘法算子。 |
| [M08](#m08) | UniCAIM: A Unified CAM/CIM Architecture with Static-Dynamic KV Cache Pruning for Efficient Long-Context LLM Inference | FeFET注意力筛选/计算电路 |
| [M09](#m09) | SpAtten: Efficient Sparse Attention Architecture with Cascade Token and Head Pruning | 稀疏注意力ASIC；另有复用阵列FC的e2e扩展 |
| [M10](#m10) | ITA: An Energy-Efficient Attention and Softmax Accelerator for Quantized Transformers | MHA核心与含64KiB SRAM的子系统两个边界。 |
| [M11](#m11) | SystolicAttention: Fusing FlashAttention within a Single Systolic Array | 融合浮点Attention阵列。 |
| [M12](#m12) | Design Space Exploration for Softmax Implementations | N=512的一整行普通数字Softmax。 |
| [M13](#m13) | ASCEND: Accurate yet Efficient End-to-End Stochastic Computing Acceleration of Vision Transformer | ViT随机计算电路/加速器；不是生成LLM |
| [M14](#m14) | Energy-Efficient Parallel Ising SoftMax Engine for Transformer Attention Based on Asynchronous SOT-P-Bits | 实验SOT-MTJ器件与异步Ising softmax；网络替换用功能仿真 |
| [M15](#m15) | Stochastic Sparse Attention for Memory-Bound Inference | RTX6000Ada上CUDA/PyTorch kernel；没有新ASIC |
| [M16](#m16) | MFSA（BF16/FP32常规数字阵列参考） | 16×16数字阵列的稳态算术能量。 |
| [M17](#m17) | FlexBlock（作者实现的BF16脉动阵列对照） | 阵列功率/面积与有效吞吐。 |

<a id="m01"></a>

### M01 DS-CIM: Digital Stochastic Computing-In-Memory Featuring Accurate OR-Accumulation via Sample Region Remapping for Edge AI Models（DATE 2026）

| 字段 | 内容 |
|---|---|
| 方案 / 比较层级 | SNG和采样域重映射支持OR累加 32Kb SRAM随机CIM宏；LLM为软件误差注入 |
| 本表数据实际对应的对手 / 控制 | 质量：Full precision、FP8、DS-CIM1、DS-CIM2；本表宏数字为两种宏自身，完整外部宏对手名单未在所用报告摘全。 |
| Benchmark：模型 / 数据 / 输入形状 | FP8 LLaMA-7B对齐INT8；T256误差注入六任务 |
| 质量指标与已有数值 | LLaMA-7B六任务BoolQ/PIQA/HellaSwag/WinoGrande/ARC-E/ARC-C的Accuracy及均分。Full precision 66.3%，FP8 66.0%，DS-CIM1 62.6%，DS-CIM2 58.8%；后两者相对FP8下降3.4/7.2个百分点。未报PPL，acc/acc_norm未锁定。 |
| 硬件指标与已有数值 | 六任务平均66.0%→62.6%/58.8%，降3.4/7.2pp；峰值3566.1TOPS/W是宏条件指标 |
| 其他局部PPA摘录 | DS-CIM1/2宏面积0.78/0.72mm²；TableIII仅TOPS/W、TOPS/mm²按40nm及1b输入×1b权重归一；输入87.5%稀疏 |
| 条件：工艺 / 频率 | 40nm，0.7–1.2V；工艺角NR；统一时钟NR；峰值T64与质量T256须区分 |
| 实现 / 证据层级 | Virtuoso、Liberate/Abstract、DC、Innovus；布局后电路仿真；软件质量模型 |
| 存储与系统边界 | 本地SRAM CIM；外部DRAM/全系统调度能耗NR |
| 本项目怎样使用 / 尚缺什么 | 随机矩阵/CIM主文献对照；必须按同位宽、归约近似、采样长度和并发上下文比较，不能把宏峰值当全模型能效。 峰值效率与最佳质量条件不同；不构成整机J/token、实际p-bit器件或完整LLM芯片证据 |

证据：[S05]、[S03]、[S02]，定位：§V、TablesII–III、Fig.7。原调研访问状态：全文HTML核读；本轮为报告复核，未逐篇重做论文实验。

原文 / 作者实现：[入口1](https://arxiv.org/html/2601.06724v1)；[入口2](https://arxiv.org/abs/2601.06724)。

<a id="m02"></a>

### M02 FIGNA: Integer Unit-Based Accelerator Design for FP-INT GEMM Preserving Numerical Accuracy（HPCA 2024）

| 字段 | 内容 |
|---|---|
| 方案 / 比较层级 | 降低混合精度乘法的浮点硬件成本 新设计FP-INT GEMM ASIC；对照FP-FP Engine也重实现 |
| 本表数据实际对应的对手 / 控制 | 作者重实现的FP-FP Engine；本表3.56×/1.55×对应FP16-INT8的该对照。 |
| Benchmark：模型 / 数据 / 输入形状 | 128×128阵列；BERT输入128tokens；BLOOM/OPT自回归batch32；只评线性GEMM |
| 质量指标与已有数值 | BERT/OPT/BLOOM数值验证；当前资料未摘出可直接引用的逐模型PPL/任务分数表，记NR。原文BF16对齐采用宽表示，不能等同无损A8。 |
| 硬件指标与已有数值 | FP16-INT8对FP-FP Engine平均面积效率3.56×、能效1.55× |
| 其他局部PPA摘录 | 逻辑由DC/PrimePower；寄存器文件0.0625pJ/bit、SRAM0.1053pJ/bit；动态操作计数+漏电×时间 |
| 条件：工艺 / 频率 | 28nm CMOS；电压/工艺角NR；100MHz |
| 实现 / 证据层级 | 自研SystemC；Synopsys Design Compiler、PrimePower；SRAM compiler |
| 存储与系统边界 | HBM2 256GB/s、3.9pJ/bit；不是DRAM命令能耗模型 |
| 本项目怎样使用 / 尚缺什么 | FFN及QKV/Wo线性投影的强数字混合精度对手；重点计转换、宽累加与存储，所列倍率不是完整LLM倍率。 主TOPS/mm²只计逻辑，buffer sweep才含SRAM；不是全LLM、非后布局证据 |

证据：[S05]、[S04]，定位：本地用户PDF第9–12页（印刷768–771），§IV-B1/B2/B3、IV-C、IV-E。原调研访问状态：用户全文PDF核读；本轮为报告复核，未逐篇重做论文实验。

原文 / 作者实现：[入口1](https://doi.org/10.1109/HPCA57654.2024.00064)。

<a id="m03"></a>

### M03 Anda: Unlocking Efficient LLM Inference with a Variable-Length Grouped Activation Data Format（HPCA 2025）

| 字段 | 内容 |
|---|---|
| 方案 / 比较层级 | 自适应精度压缩浮点激活和计算 可变尾数位串行GEMM ASIC；GPU-like基线是建模的空间加速器 |
| 本表数据实际对应的对手 / 控制 | GPU-like FP-FP空间加速器建模基线，统一285MHz、峰值吞吐和片存；质量参考OmniQuant等量化配置。 |
| Benchmark：模型 / 数据 / 输入形状 | OPT/LLaMA/LLaMA2 1.3–30B；batch1；PPL长度2048；硬件仅FP-INT GEMM |
| 质量指标与已有数值 | OPT/LLaMA/Llama2的2048长度PPL；文献代表点采用1%质量容差。完整逐模型分数未在当前矩阵摘出，记NR。 |
| 硬件指标与已有数值 | 1%质量容差下，相对GPU-like FP-FP建模基线，平均GEMM加速2.49×、面积效率4.03×、能效3.16× |
| 其他局部PPA摘录 | Genus综合网表仿真VCD功耗；SRAM独立工具NR |
| 条件：工艺 / 频率 | 16nm，0.8V nominal；工艺角NR；285MHz；各ASIC基线同频 |
| 实现 / 证据层级 | 自研cycle-accurate simulator；SystemVerilog、Cadence Genus；综合网表VCD |
| 存储与系统边界 | HBM2 256GB/s、3.9pJ/bit；同片上容量、同峰值吞吐 |
| 本项目怎样使用 / 尚缺什么 | 可变精度/位串行数字GEMM对手；与SC比较同质量和同资源的线性层成本，不能当真实GPU整模型加速。 system-level措辞不代表完整LLM；KV等FP16；无P&R披露；非GPU实测 |

证据：[S05]，定位：§V-A、V-D/E，表III。原调研访问状态：全文HTML核读；本轮为报告复核，未逐篇重做论文实验。

原文 / 作者实现：[入口1](https://arxiv.org/html/2411.15982v1#S5)。

<a id="m04"></a>

### M04 AxCore: A Quantization-Aware Approximate GEMM Unit for LLM Inference（MICRO 2025）

| 字段 | 内容 |
|---|---|
| 方案 / 比较层级 | 降低浮点/整数混合GEMM成本 近似混合精度GEMM ASIC |
| 本表数据实际对应的对手 / 控制 | FPC等混合精度GEMM对手；本表2.2×能量降低和6.4×TOPS/W对应FPC。 |
| Benchmark：模型 / 数据 / 输入形状 | OPT2.7–30B、Llama2-7/70B；WT2/ARC-E/HellaSwag/PIQA/WinoGrande；硬件主图OPT13/30B decode、batch32、output1 |
| 质量指标与已有数值 | WT2 PPL及ARC-E/HellaSwag/PIQA/WinoGrande；逐项分数未在所用报告摘出，记NR。 |
| 硬件指标与已有数值 | 对FPC能量降低2.2×、TOPS/W提高6.4× |
| 其他局部PPA摘录 | DC逻辑；CACTI SRAM；能量图含Core/Buffer/DRAM/Static |
| 条件：工艺 / 频率 | TSMC28nm；电压/角NR；1GHz；基线同频/峰值/SRAM |
| 实现 / 证据层级 | DNNWeaver派生模拟器；SpinalHDL→Verilog→DC；CACTI；公开artifact |
| 存储与系统边界 | 64×64阵列、4×4 tiling；给足带宽；DRAM型号/能耗校准未完整披露 |
| 本项目怎样使用 / 尚缺什么 | 量化感知近似算术数字对手；其GEMM精度与能量需要同一配置，密度图排除最终累加的边界应保留。 图16密度排除最终累加；4张RTX6000Ada为实验主机；非GPU目标芯片；无P&R披露 |

证据：[S05]，定位：§6.1、6.3/6.4、附录A；PDF9–12、14–15页。原调研访问状态：全文PDF及artifact附录核读；公开代码入口已确认；本轮为报告复核，未逐篇重做论文实验。

原文 / 作者实现：[入口1](https://soldierchen.github.io/assets/pdf/axcore-micro25.pdf)；[入口2](https://github.com/CLab-HKUST-GZ/micro58-axcore)；[入口3](https://doi.org/10.5281/zenodo.16895417)。

<a id="m05"></a>

### M05 uGEMM: Unary Computing Architecture for GEMM Applications（ISCA 2020）

| 字段 | 内容 |
|---|---|
| 方案 / 比较层级 | uMUL-IS/uMUL-ST、Sobol条件更新与缩放/非缩放流式累加。 Unary GEMM算术架构；另有小型MLP，非LLM。 |
| 本表数据实际对应的对手 / 控制 | 文中8位参考、小型MLP及缩放/非缩放、有符号/无符号变体；外部完整对手清单未摘全。 |
| Benchmark：模型 / 数据 / 输入形状 | 16×16×16矩阵任务，4096 MAC；流长256。小型MLP作为应用验证。 |
| 质量指标与已有数值 | MLP绝对准确率94.7%；98.6%是相对8位参考的准确率比例，非绝对准确率。无LLM PPL。 |
| 硬件指标与已有数值 | 非缩放无符号约70nJ、有符号约130nJ；对应面积约0.44/0.77mm²。原表有舍入，P×t与E略有差异。 |
| 其他局部PPA摘录 | NR；不据缺项补零。 |
| 条件：工艺 / 频率 | 45nm综合；400MHz |
| 实现 / 证据层级 | RTL综合与数值/网络实验 |
| 存储与系统边界 | 完整存储边界不能据算术核表推定。 |
| 本项目怎样使用 / 尚缺什么 | GEMM任务能量和unary协议参照，可作算术级对手；不用于LLM整机质量或J/token。 操作数、符号、流长、溢出/缩放不同，不与我们的64输入短流点积直接作倍率。 |

证据：[S07]、[S04]，定位：§V-C/Table VI；§IV、Fig.3–4、§VI/Fig.10。原调研访问状态：原调研全文核读；本轮为报告复核，未逐篇重做论文实验。

原文 / 作者实现：[入口1](https://jsm.ece.wisc.edu/docs/wu-isca2020.pdf)。

<a id="m06"></a>

### M06 SASCHA: Sparsity-Aware Stochastic Computing Hardware Architecture for Neural Network Acceleration（CASES/TCAD 2022）

| 字段 | 内容 |
|---|---|
| 方案 / 比较层级 | GEO采用OR后计数，GEO+取消OR并精确二进制累加；共享种子、位切片及稀疏调度。 随机CNN加速器。 |
| 本表数据实际对应的对手 / 控制 | GEO/GEO+、非切片/位切片、CNN参考；所用报告没有完整硬件倍率表，不补猜对手。 |
| Benchmark：模型 / 数据 / 输入形状 | 经剪枝/误差感知训练的CNN；非切片64拍，切片高/低部分64/8拍。 |
| 质量指标与已有数值 | CNN应用准确率；本报告没有可抄录的逐网络分数，NR；无LLM质量证据。 |
| 硬件指标与已有数值 | 原调研未摘出可同口径引用的绝对P/A/E数值或倍率，NR。已确认面积表不含存储，带宽假设充足。 |
| 其他局部PPA摘录 | NR；不据缺项补零。 |
| 条件：工艺 / 频率 | TSMC28nm；400MHz |
| 实现 / 证据层级 | 综合、CACTI与调度模型 |
| 存储与系统边界 | 存储面积排除；稀疏索引/调度/合并成本另辨。 |
| 本项目怎样使用 / 尚缺什么 | 随机乘法+精确累计及稀疏调度的机制对照；数值PPA表需补原始表后才作排名。 90%级稀疏和训练收益不能套稠密预训练LLM；精确累加本身不构成方案错误。 |

证据：[S04]，定位：§IV–VII、Fig.10–13/18、Table II。原调研访问状态：原调研全文核读；本轮为报告复核，未逐篇重做论文实验。

原文 / 作者实现：[入口1](https://nanocad.ee.ucla.edu/wp-content/papercite-data/pdf/j72.pdf)。

<a id="m07"></a>

### M07 tubGEMM: Energy-Efficient and Sparsity-Effective Temporal-Unary-Binary Based Matrix Multiply Unit（2024预印本v1）

| 字段 | 内容 |
|---|---|
| 方案 / 比较层级 | 无RNG的精确时间一元×二进制GEMM；动态幅度决定执行时长。 整数矩阵乘法算子。 |
| 本表数据实际对应的对手 / 控制 | uGEMM及二进制/一元矩阵方案；本表只摘报告已核定的tubGEMM条件点。 |
| Benchmark：模型 / 数据 / 输入形状 | 45nm比较中的16×16无符号矩阵配置；精确整数任务，时长含归约维推进。 |
| 质量指标与已有数值 | 精确整数算术，无LLM PPL/任务准确率。 |
| 硬件指标与已有数值 | 报告引用约63nJ、最坏5.29µs；完整存储系统未包括。不要把其他N5实现点与本45nm点合并。 |
| 其他局部PPA摘录 | NR；不据缺项补零。 |
| 条件：工艺 / 频率 | 本表引用45nm比较点；论文另有实现节点，分别看原表；本表不反推主频 |
| 实现 / 证据层级 | 后综合PPA及活动估计 |
| 存储与系统边界 | 非完整存储子系统 |
| 本项目怎样使用 / 尚缺什么 | 检验随机性本身的收益，作为无RNG、精确位串行/时间编码对手。 一元时间复用不等于IID随机；单乘最坏周期与完整GEMM周期不同。 |

证据：[S07]，定位：Tables I–V；§II–IV。原调研访问状态：原调研全文核读；本轮为报告复核，未逐篇重做论文实验。

原文 / 作者实现：[入口1](https://arxiv.org/html/2412.17955v1)。

<a id="m08"></a>

### M08 UniCAIM: A Unified CAM/CIM Architecture with Static-Dynamic KV Cache Pruning for Efficient Long-Context LLM Inference（DAC 2025）

| 字段 | 内容 |
|---|---|
| 方案 / 比较层级 | 静动态KV剪枝与CAM/CIM联合设计 FeFET注意力筛选/计算电路 |
| 本表数据实际对应的对手 / 控制 | Sprint、TranCIM、CIMFormer；质量对照full-cache LongChat。 |
| Benchmark：模型 / 数据 / 输入形状 | LongChat-v1.5-7B-32k；LongBench HotpotQA/NarrativeQA；prompt约1.5K/2.5K；F1 |
| 质量指标与已有数值 | LongBench HotpotQA、NarrativeQA答案F1；prompt约1.5K/2.5K。图示接近full-cache，原调研未从无标值曲线目测精确F1；无PPL。 |
| 硬件指标与已有数值 | 1b cell、50%剪枝，AEDP对Sprint/TranCIM/CIMFormer改善8.2/13.9/124× |
| 其他局部PPA摘录 | 局部attention AEDP；计64个10b SAR ADC并行读出 |
| 条件：工艺 / 频率 | 45nm BSIM MOSFET+Preisach FeFET；线寄生采用引用模型；PVT未核全；整机时钟NR；电路操作时延受ADC并行数量约束 |
| 实现 / 证据层级 | HSPICE + 软件剪枝精度实验 |
| 存储与系统边界 | 512初始token+64 decode槽、d128、3b cell；外部DRAM能耗NR |
| 本项目怎样使用 / 尚缺什么 | Attention/KV筛选+CIM电路对手；用F1和Attention AEDP分别比较，不能转成完整模型J/token。 局部ADC已考虑，不等于全部数据搬运已闭合；不能将attention AEDP变成E2E J/token |

证据：[S05]，定位：§IV-A/B、TableII、Figs10–13。原调研访问状态：全文HTML核读；本轮为报告复核，未逐篇重做论文实验。

原文 / 作者实现：[入口1](https://arxiv.org/html/2504.07479v1)；[入口2](https://mengli.me/publication/dac-2025-unicaim/)。

<a id="m09"></a>

### M09 SpAtten: Efficient Sparse Attention Architecture with Cascade Token and Head Pruning（HPCA 2021）

| 字段 | 内容 |
|---|---|
| 方案 / 比较层级 | token/head剪枝、渐进量化减少计算与访存 稀疏注意力ASIC；另有复用阵列FC的e2e扩展 |
| 本表数据实际对应的对手 / 控制 | 等资源缩小版对A³；端到端另对TITAN Xp GPU，不能把这两组倍率混用。 |
| Benchmark：模型 / 数据 / 输入形状 | 30个BERT/GPT2 attention workloads；e2e单列GPT2-Medium 8-bit FC |
| 质量指标与已有数值 | 30个BERT/GPT2 Attention工作负载；所用证据矩阵没有摘出完整逐任务质量表，NR。 |
| 硬件指标与已有数值 | 等资源缩小版对A³吞吐1.6×、能效1.4×；e2e对TITAN Xp平均35×加速 |
| 其他局部PPA摘录 | Genus逻辑；CACTI SRAM/FIFO；softmax指数/除法借文献FMA/FPU成本 |
| 条件：工艺 / 频率 | 固定点逻辑40nm；部分softmax单元借45nm文献成本；电压/角NR；1GHz |
| 实现 / 证据层级 | SpinalHDL→RTL→Verilator；Ramulator；Genus；CACTI |
| 存储与系统边界 | HBM2由Ramulator统计ACT/读写命令，乘文献能耗；不是统一硅片实测 |
| 本项目怎样使用 / 尚缺什么 | 筛选/量化Attention与稀疏访存对手；端到端GPT2扩展必须引用独立边界。 摘要attention加速比不可当全模型；GPU为当时软件栈；部分FPGA功耗投影、混合来源PPA |

证据：[S05]，定位：§V-A、表I–IV、§V-B End-to-End Performance。原调研访问状态：全文HTML核读；本轮为报告复核，未逐篇重做论文实验。

原文 / 作者实现：[入口1](https://arxiv.org/html/2012.09852v2#S5)。

<a id="m10"></a>

### M10 ITA: An Energy-Efficient Attention and Softmax Accelerator for Quantized Transformers（ISLPED 2023）

| 字段 | 内容 |
|---|---|
| 方案 / 比较层级 | INT8矩阵与近似整数Softmax的Attention加速器。 MHA核心与含64KiB SRAM的子系统两个边界。 |
| 本表数据实际对应的对手 / 控制 | 同论文核心/含SRAM子系统、等精度整数Attention；所用报告未完整列出其他芯片对手。 |
| Benchmark：模型 / 数据 / 输入形状 | 1024 INT8 MAC；量化Transformer Attention。512元素整行Softmax周期未核得。 |
| 质量指标与已有数值 | 整数近似质量口径；不能视作BF16 GQA decode已通过PPL，当前摘录无可引用逐模型分数。 |
| 硬件指标与已有数值 | 核心0.173mm²/60.5mW；含64KiB SRAM子系统0.407mm²/121mW。Softmax约28.7kGE；核心面积3.3%、功率1.4%属于本配置。 |
| 其他局部PPA摘录 | NR；不据缺项补零。 |
| 条件：工艺 / 频率 | 22FDX；时序SS0.72V/125°C，功率TT0.8V/25°C，分列；500MHz |
| 实现 / 证据层级 | 后布局仿真/功率估计 |
| 存储与系统边界 | 64KiB片存；不含DRAM/PHY/host |
| 本项目怎样使用 / 尚缺什么 | 完整数字Attention结构与整数Softmax成本锚点；需在本工艺和本数制重实现后作主PPA对照。 FP16/BF16与INT8不同；0.173×3.3%=约0.005709mm²只是比例派生，不是另一个实测独立Softmax核。 |

证据：[S08]、[S09]，定位：原文及作者RTL，Softmax面积/功率分解；S08、S09。原调研访问状态：原调研原文及RTL核查；本轮为报告复核，未逐篇重做论文实验。

原文 / 作者实现：[入口1](https://arxiv.org/html/2307.03493v2)；[入口2](https://github.com/pulp-platform/ITA)。

<a id="m11"></a>

### M11 SystolicAttention: Fusing FlashAttention within a Single Systolic Array（2025预印本v4 / FSA）

| 字段 | 内容 |
|---|---|
| 方案 / 比较层级 | 把max、exp2 PWL、sum与矩阵运算融合到脉动阵列。 融合浮点Attention阵列。 |
| 本表数据实际对应的对手 / 控制 | 原浮点行为参考及融合阵列方案；表中各对手完整名单未在资料摘出。 |
| Benchmark：模型 / 数据 / 输入形状 | FP16乘法/FP32累计；主要非因果完整矩阵、head_dim128；Table3包含Qwen2.5-0.5B等模型PPL。 |
| 质量指标与已有数值 | 行为级PPL验证近似；协议不同，不能与我们的11.65直接横比。当前报告未摘具体PPL值，NR。 |
| 硬件指标与已有数值 | 16nm/1.5GHz；未报告功率与decode结果。Table4面积分项与合计存在不一致，原调研没有移植其绝对面积。 |
| 其他局部PPA摘录 | NR；不据缺项补零。 |
| 条件：工艺 / 频率 | 16nm；1.5GHz |
| 实现 / 证据层级 | 作者RTL与行为/性能模型 |
| 存储与系统边界 | 面积不含SRAM/DMA |
| 本项目怎样使用 / 尚缺什么 | 融合在线数字Attention和有限精度EXP的强对手，不能给数字端强加完整概率矩阵写回。 非因果矩阵性能不等于单query GQA decode；FP16不等于BF16。 |

证据：[S08]，定位：v4 Tables3–4；S08数字参考核查。原调研访问状态：原调研原文及作者RTL核查；本轮为报告复核，未逐篇重做论文实验。

原文 / 作者实现：[入口1](https://arxiv.org/html/2507.11331v4)；[入口2](https://github.com/VCA-EPFL/FSA)。

<a id="m12"></a>

### M12 Design Space Exploration for Softmax Implementations（ASAP 2020，Wei等）

| 字段 | 内容 |
|---|---|
| 方案 / 比较层级 | SoftGen扫描格式、EXP/LOG实现、并行度及输入mem/reg组织。 N=512的一整行普通数字Softmax。 |
| 本表数据实际对应的对手 / 控制 | fixed32 LUT的P1/P2/P4；FP16的P8 DesignWare与LUT；NOREG与内部寄存器组织分别比较。 |
| Benchmark：模型 / 数据 / 输入形状 | 固定512输入，假定外部每拍提供P元素；不同格式不作为同精度曲线。 |
| 质量指标与已有数值 | 有限精度Softmax；没有本项目Qwen完整PPL。DesignWare参考也不是实数精确值。 |
| 硬件指标与已有数值 | fixed32/LUT：P1 1542拍、0.059mm²；P2 775拍、0.085mm²；P4 392拍、0.138mm²。FP16/P8：DW 199拍、0.283300mm²；LUT 201拍、0.220178mm²。原250MHz下分别6.168/3.100/1.568/0.796/0.804µs。 |
| 其他局部PPA摘录 | NR；不据缺项补零。 |
| 条件：工艺 / 频率 | 45nm FreePDK45综合，非P&R；250MHz |
| 实现 / 证据层级 | 公开生成器及综合表 |
| 存储与系统边界 | 以上NOREG依赖外部输入存储；P2/P4带内部寄存器的面积为0.828/0.835mm²，不能混用。 |
| 本项目怎样使用 / 尚缺什么 | 普通数字Softmax周期/面积可引用锚点；同工艺采样对照仍需加入CDF/随机数/索引输出。 不含数字采样或Ising V地址生成；整行周期、II、首/末输出延迟分别记录。 |

证据：[S09]，定位：PDF第7页Tables III/IV；完整逐行表见本文件§4.1。原调研访问状态：原调研原PDF与源码核查；本轮为报告复核，未逐篇重做论文实验。

原文 / 作者实现：[入口1](https://utw10244.utweb.utexas.edu/pubs/SoftMax___ASAP2020_June27.pdf)；[入口2](https://doi.org/10.1109/ASAP49362.2020.00017)。

<a id="m13"></a>

### M13 ASCEND: Accurate yet Efficient End-to-End Stochastic Computing Acceleration of Vision Transformer（DATE 2024）

| 字段 | 内容 |
|---|---|
| 方案 / 比较层级 | SC GELU/迭代近似softmax与训练协同 ViT随机计算电路/加速器；不是生成LLM |
| 本表数据实际对应的对手 / 控制 | 浮点ViT、随机近似配置及原文GELU/Softmax对手；本表ADP为局部非线性比较。 |
| Benchmark：模型 / 数据 / 输入形状 | 7层4头ViT，CIFAR10/100；W2-A2-R16；训练/近似感知微调 |
| 质量指标与已有数值 | CIFAR10/100；W2-A2-R16推荐配置90.79%/66.18%，浮点参考94.52%/73.80%；不是生成LLM任务。 |
| 硬件指标与已有数值 | GELU/softmax最高ADP改善5.29×/12.6×；推荐准确率90.79/66.18%，FP参考94.52/73.80% |
| 其他局部PPA摘录 | softmax m64，By8：1.62e5µm²/16.20ns；TableVI推荐配置总面积4.47e6µm² |
| 条件：工艺 / 频率 | TSMC28nm；V/PVT NR；未给统一整机时钟；表内Delay不能取倒数冒充整机频率 |
| 实现 / 证据层级 | RTL+Synopsys DC；软件ViT训练/评估 |
| 存储与系统边界 | 未查到完整外DRAM、调度、I/O和整机能耗模型 |
| 本项目怎样使用 / 尚缺什么 | SC非线性与训练协同参考；局部ADP不可当LLM端到端能效。 end-to-end指SC计算/网络路径；ADP为局部模块；不能当LLM端到端latency/energy证据 |

证据：[S05]，定位：用户71_pdf_upload.pdf第5–6页§VI、TablesIII–VI。原调研访问状态：用户全文PDF核读，第5页渲染核表；本轮为报告复核，未逐篇重做论文实验。

原文 / 作者实现：[入口1](https://arxiv.org/abs/2402.12820)；[入口2](https://arxiv.org/html/2402.12820v1)。

<a id="m14"></a>

### M14 Energy-Efficient Parallel Ising SoftMax Engine for Transformer Attention Based on Asynchronous SOT-P-Bits（IEEE Electron Device Letters 2026）

| 字段 | 内容 |
|---|---|
| 方案 / 比较层级 | 物理Boltzmann分布实现softmax并做器件补偿 实验SOT-MTJ器件与异步Ising softmax；网络替换用功能仿真 |
| 本表数据实际对应的对手 / 控制 | 文中的FP16分布比较线及浮点模型功能参考。 |
| Benchmark：模型 / 数据 / 输入形状 | DeepSeek-LLM-7B-Base、TinyLlama1.1B、DistilGPT2；WT2 PPL与Self-BLEU；历史Base仅作文献 |
| 质量指标与已有数值 | WT2 PPL和Self-BLEU；所用报告只给接近FP参考的概述，逐模型PPL未摘出，NR；不能用10^9副本分布曲线替代单物理实例有限样本精度。 |
| 硬件指标与已有数值 | N=10^9独立副本ensemble分布约32µs达到文中FP16比较线；功能PPL接近FP参考 |
| 其他局部PPA摘录 | 约0.26pJ/bit为引用器件条件的概率核心投影；不含输入准备/输出读出 |
| 条件：工艺 / 频率 | SOT-MTJ堆栈实验工艺；不对应一个完整数字ASIC节点；CMOS PVT NR；异步；16/32µs是演化时间，不是GHz时钟或完整读出时间 |
| 实现 / 证据层级 | 实测器件概率特性+Ising ensemble演化模拟+模型函数替换 |
| 存储与系统边界 | §IV明确完整外围输出实现超出范围；DRAM/整机调度NR |
| 本项目怎样使用 / 尚缺什么 | 器件概率响应、分布演化与补偿机制参照；输入配置/读出、有限样本/ESS需另计。 ensemble分布精度不等于单实例有限时间计数精度；0.26pJ/bit不能直接算整机；输入/读出须补 |

证据：[S05]，定位：用户SOT-P-Bits PDF第1页器件/第3页§IV、Figs4–5。原调研访问状态：用户作者接受稿全文核读，第3页渲染核对；本轮为报告复核，未逐篇重做论文实验。

原文 / 作者实现：[入口1](https://doi.org/10.1109/LED.2026.3691358)。

<a id="m15"></a>

### M15 Stochastic Sparse Attention for Memory-Bound Inference（ICML 2026）

| 字段 | 内容 |
|---|---|
| 方案 / 比较层级 | V采样和gather-add减少decode带宽 RTX6000Ada上CUDA/PyTorch kernel；没有新ASIC |
| 本表数据实际对应的对手 / 控制 | 准确dense/FlashAttention decode；prop与flash两种采样实现；prefill保持dense。 |
| Benchmark：模型 / 数据 / 输入形状 | v2 §3.5/Table3 Llama-3.1-8B-Instruct，BF16权重/KV，30k输入、B6、每prompt2048输出，9batches平均 |
| 质量指标与已有数值 | Llama3.1-8B-Instruct推理/长文本任务；当前调研摘录未完整列出各质量任务名与逐项分数，NR，不能补造一个统一PPL。 |
| 硬件指标与已有数值 | Table3：dense decode101.22s/batch，flash80.97s/batch，约1.250×；prop约1.229×。8.237→6.589ms/output-token按batch总时长/(6×2048)计算；Attention kernel约1.5×是另一边界。 |
| 其他局部PPA摘录 | 能量讨论与硬件实现分开；无p-bitASIC面积/器件能耗证明 |
| 条件：工艺 / 频率 | 商用GPU；论文没有新ASIC工艺实现，不能填55/7nm为该方法工艺；GPU具体锁频设置本次未核得；不是自定ASIC时钟 |
| 实现 / 证据层级 | GPU实测+随机算法数学/软件验证；非新硬件模拟器 |
| 存储与系统边界 | 实际GPU KV读写；采样V行，QK扩展另列 |
| 本项目怎样使用 / 尚缺什么 | 直接的采样Attention软件基准；对比到最终输出或可读V索引/次数，不把GPU软件测量当p-bitASIC PPA。 6.589ms不是单请求TPOT；kernel1.5×不等于全请求1.5×；不能视为物理随机源验证 |

证据：[S05]、[S04]，定位：v2 §3.4–3.6、Table3；正式proceedings与官方代码。原调研访问状态：v2全文HTML/Table3、用户图与正式会议页核读；本轮为报告复核，未逐篇重做论文实验。

原文 / 作者实现：[入口1](https://arxiv.org/html/2605.01910v2)；[入口2](https://proceedings.mlr.press/v306/lee26j.html)；[入口3](https://github.com/OPUSLab/SANTA)。

<a id="m16"></a>

### M16 MFSA（BF16/FP32常规数字阵列参考）（2026-10-14预印本v1）

| 字段 | 内容 |
|---|---|
| 方案 / 比较层级 | 多格式常规数字脉动阵列；这里仅引用BF16输入/FP32累加点。 16×16数字阵列的稳态算术能量。 |
| 本表数据实际对应的对手 / 控制 | MFSA原表的BF16点；本项目将其作为外部数字锚点，并非原作者测了我们的SC。 |
| Benchmark：模型 / 数据 / 输入形状 | 256PE，每PE两项BF16乘积；稳态LLM轨迹门级活动。 |
| 质量指标与已有数值 | 本摘录无本项目同模型质量比较，NR。 |
| 硬件指标与已有数值 | 1.85W、1.024TOPS；原值派生1.80664pJ/op、3.61328pJ/MAC、231.25pJ/64MAC。表内舍入1.80pJ/op对应230.4pJ/64MAC，两者分别保留。 |
| 其他局部PPA摘录 | NR；不据缺项补零。 |
| 条件：工艺 / 频率 | 28nm、SS0.72V/125°C；1GHz |
| 实现 / 证据层级 | Cadence后布线RC、LLM轨迹门级波形、自动时钟门控；非硅实测 |
| 存储与系统边界 | 稳态窗口排除reset、权重预装和排空。 |
| 本项目怎样使用 / 尚缺什么 | BF16/FP32数字阵列外部能量锚点；与本工艺S15和同量化INT8对照共同使用。 64MAC只是派生算术工作量，非单个短点积完整启动/排空延迟或含存储能量；不跨节点折成本工艺实测。 |

证据：[S13]，定位：§III-A、§IV-D、TableII；S13第二轮复核。原调研访问状态：原调研PDF及第6页表格视觉核对；本轮为报告复核，未逐篇重做论文实验。

原文 / 作者实现：[入口1](https://arxiv.org/html/2610.19645v1)。

<a id="m17"></a>

### M17 FlexBlock（作者实现的BF16脉动阵列对照）（作者PDF版本arXiv:2203.06673v1；文件名2023不作版本依据）

| 字段 | 内容 |
|---|---|
| 方案 / 比较层级 | 论文中的128×128 BF16常规脉动阵列参考点。 阵列功率/面积与有效吞吐。 |
| 本表数据实际对应的对手 / 控制 | 这里引用FlexBlock论文的作者BF16对照阵列；不是将FlexBlock所有多格式结果当BF16单核。 |
| Benchmark：模型 / 数据 / 输入形状 | 128×128 BF16阵列、333MHz，表V有效吞吐1.77TFLOPS。 |
| 质量指标与已有数值 | 所用复核不提供同本项目模型质量数值，NR。 |
| 硬件指标与已有数值 | 74.38mm²、9.84W；由P/T派生约11.12pJ/MAC、711.59pJ/64MAC；按舍入179.6GFLOPS/W则712.69pJ/64MAC。 |
| 其他局部PPA摘录 | NR；不据缺项补零。 |
| 条件：工艺 / 频率 | 65nm；其他PVT本摘录NR；333MHz |
| 实现 / 证据层级 | 作者实现/综合与性能模型；精确阶段见原表 |
| 存储与系统边界 | SRAM由CACTI另估，表V与系统训练能量图分开。 |
| 本项目怎样使用 / 尚缺什么 | 独立BF16阵列风险参照；不能仅由此宣称SC节能十倍。 1.77TFLOPS约为满利用率10.911744TFLOPS的16.22%；P/T含利用率，不能作为满利用标量MAC动作单价。 |

证据：[S13]，定位：§VI-B、§VII-B、TableV；S13第二轮复核。原调研访问状态：原调研PDF及第10页表格视觉核对；本轮为报告复核，未逐篇重做论文实验。

原文 / 作者实现：[入口1](https://jongse-park.github.io/files/paper/2023-tc-flexblock.pdf)。

## 3. 端到端/系统与质量补充：逐篇数据

### 3.1 系统、请求或完整模型路径

| 编号 | 工作 | 主要比较范围 |
|---|---|---|
| [E01](#e01) | OPAL: Outlier-Preserved Microscaling Quantization Accelerator for Generative Large Language Models | 混合精度MxV/softmax专用ASIC |
| [E02](#e02) | Kelle: Co-design KV Caching and eDRAM for Efficient LLM Serving in Edge Computing | 边缘LLM ASIC及eDRAM/KV淘汰、刷新 |
| [E03](#e03) | Hybrid Systolic Array Accelerator with Optimized Dataflow for Edge Large Language Model Inference | 双数据流数字ASIC；主端到端对象RetNet |
| [E04](#e04) | NeuPIMs: NPU-PIM Heterogeneous Acceleration for Batched LLM Inferencing | 自定义NPU+HBM PIM；GPU对照为实测A10040GB |
| [E05](#e05) | AttAcc! Unleashing the Power of PIM for Batched Transformer-based Generative Model Inference | GPU做FC、HBM-PIM做attention及共同计算 |
| [E06](#e06) | PIM Is All You Need: A CXL-Enabled GPU-Free System for Large Language Model Inference | GPU-free PIM+controller/vector/RISC-V |
| [E07](#e07) | PIM GPT a hybrid process in memory accelerator for autoregressive transformers | bank-level PIM MAC+独立ASIC非线性/控制 |
| [E08](#e08) | MBA: Mega-Buffer Architecture Based on 1T1C IGZO eDRAM for Efficient LLM Inference | 具有GB级片上eDRAM的专用LLM架构；A100为对照 |
| [E09](#e09) | Z1T: Sparse Transformer-Like Models for Probabilistic Hardware | 为Z1重设计并训练的模型及异构decode成本估算。 |
| [E10](#e10) | MoNDE: Mixture of Near-Data Experts for Large-Scale Sparse Models | GPU+NDP异构MoE系统。 |
| [E11](#e11) | Splitwise: Efficient Generative LLM Inference Using Phase Splitting | 服务系统，非新算术ASIC。 |

<a id="e01"></a>

### E01 OPAL: Outlier-Preserved Microscaling Quantization Accelerator for Generative Large Language Models（DAC 2024）

| 字段 | 内容 |
|---|---|
| 方案 / 比较层级 | 保留离群值、减少量化推理成本 混合精度MxV/softmax专用ASIC |
| 本表数据实际对应的对手 / 控制 | 原BF16与OWQ量化参考；本表W4A4/7能耗分别对OWQ/BF16。 |
| Benchmark：模型 / 数据 / 输入形状 | Llama2-7/13/70B、OPT；WT2/C4、ARC-C/PIQA |
| 质量指标与已有数值 | WT2/C4 PPL，ARC-C/PIQA Accuracy；报告没有摘出完整逐模型质量数表，NR。 |
| 硬件指标与已有数值 | Llama2-70B报告单token1.98s；W4A4/7能耗对OWQ/BF16低38.6%/58.6% |
| 其他局部PPA摘录 | DC逻辑功耗面积；CACTI存储含漏电；表3单核逻辑0.9293mm²、335.85mW |
| 条件：工艺 / 频率 | 65nm；电压/角NR；NR：已查§5.2和硬件表未给出 |
| 实现 / 证据层级 | RTL（SRAM除外）+Design Compiler；CACTI；系统模拟器名称NR |
| 存储与系统边界 | 512KB global buffer；每核2KB softmax buffer；外部DRAM配置/模型NR |
| 本项目怎样使用 / 尚缺什么 | 量化/新算术的生成模型系统参照，保留原浮点、量化参考与新算术三层。 batch/context信息不足，1.98s不能直接作统一TPOT；未查到P&R；单核功率不等于整机 |

证据：[S05]，定位：§5.2、表3、图8；DAC归属由作者机构书目交叉核对。原调研访问状态：全文HTML核读；本轮为报告复核，未逐篇重做论文实验。

原文 / 作者实现：[入口1](https://arxiv.org/html/2409.05902v3#S5.SS2)；[入口2](https://scholar.dgist.ac.kr/handle/20.500.11750/57857?mode=full)。

<a id="e02"></a>

### E02 Kelle: Co-design KV Caching and eDRAM for Efficient LLM Serving in Edge Computing（MICRO 2025）

| 字段 | 内容 |
|---|---|
| 方案 / 比较层级 | 协同片上存储保留时间和推理调度 边缘LLM ASIC及eDRAM/KV淘汰、刷新 |
| 本表数据实际对应的对手 / 控制 | 等片上面积Original+SRAM及文中KV/存储消融；质量相对原FP16，采用W8A16等整套方案。 |
| Benchmark：模型 / 数据 / 输入形状 | Llama2/3/3.2、Mistral、Qwen2、OPT；默认batch16，prompt128–1024、decode512–8192 |
| 质量指标与已有数值 | Llama2-7B WT2 PPL5.47→5.74(+4.94%)；13B WT2 4.88→5.62(+15.16%)；7B PG19 10.51→12.59(+19.79%)。7B ARC-E74.62→72.78，PIQA79.11→77.35（%）。其他任务见§5任务表。 |
| 硬件指标与已有数值 | 对等片上面积Original+SRAM平均时延改善3.94×、能效4.46× |
| 其他局部PPA摘录 | 逻辑DC；存储Destiny；§8方法段报告约9.5mm²、片上6.52W、外DRAM另列11.74W |
| 条件：工艺 / 频率 | 逻辑45nm；Destiny存储65nm、105°C；电压/逻辑角NR；1GHz |
| 实现 / 证据层级 | SystemVerilog+DC；Destiny；CACTI7；§6分析式吞吐/带宽模型 |
| 存储与系统边界 | 2MB SRAM+4MB KV eDRAM+256KB激活eDRAM；16GB LPDDR4 64GB/s，CACTI7；含外存时延能量 |
| 本项目怎样使用 / 尚缺什么 | 同面积KV/eDRAM系统与质量取舍参照；数字/存储节点不同，不能当全同工艺芯片数据。 混合工艺估算；未见P&R或波形活动来源；不能从时序示意图推定完整周期仿真 |

证据：[S05]、[S03]、[S02]，定位：§6公式4–6；§8 Hardware Evaluation开头方法段及§8.1；Table2为质量表。原调研访问状态：全文HTML核读；本轮为报告复核，未逐篇重做论文实验。

原文 / 作者实现：[入口1](https://arxiv.org/html/2510.16040v1#S8)。

<a id="e03"></a>

### E03 Hybrid Systolic Array Accelerator with Optimized Dataflow for Edge Large Language Model Inference（ISLPED 2025）

| 字段 | 内容 |
|---|---|
| 方案 / 比较层级 | 适配prefill与decode计算形状 双数据流数字ASIC；主端到端对象RetNet |
| 本表数据实际对应的对手 / 控制 | 文中ConvSA/其他脉动阵列；给出的面积归一吞吐为HSA自身工作点。 |
| Benchmark：模型 / 数据 / 输入形状 | 256PE；RetNet1.3B，prompt/output750/50与50/750；Llama用于补充质量 |
| 质量指标与已有数值 | 主硬件模型RetNet1.3B；Llama量化补充有PPL/GSM8K，但不能将其质量绑定到RetNet PPA。 |
| 硬件指标与已有数值 | 面积归一吞吐247/117tokens/s/mm²；tokens包括prompt与output |
| 其他局部PPA摘录 | 表II 0.636mm²、0.108W、0.256TOPS；后布局功耗时延 |
| 条件：工艺 / 频率 | TSMC28nm；能效点0.81V；角NR；500MHz |
| 实现 / 证据层级 | SystemC→Catapult HLS→RTL→DC→Innovus P&R；VCS/PrimeTime |
| 存储与系统边界 | DDR5 51.2GB/s，32pJ/Byte固定访问能耗；SRAM宏来源NR |
| 本项目怎样使用 / 尚缺什么 | prefill-heavy/decode-heavy双负载设计参照；RetNet与标准Softmax Transformer分开。 RetNet不含普通softmax注意力；ConvSA由数据流推估、向量单元从5nm缩28nm；非全部同PDK重做 |

证据：[S05]，定位：§II、§V、表I/II及脚注。原调研访问状态：全文HTML核读；本轮为报告复核，未逐篇重做论文实验。

原文 / 作者实现：[入口1](https://arxiv.org/html/2507.09010v1#S5)。

<a id="e04"></a>

### E04 NeuPIMs: NPU-PIM Heterogeneous Acceleration for Batched LLM Inferencing（ASPLOS 2024）

| 字段 | 内容 |
|---|---|
| 方案 / 比较层级 | batch LLM的NPU/PIM异构调度 自定义NPU+HBM PIM；GPU对照为实测A10040GB |
| 本表数据实际对应的对手 / 控制 | NPU-only及实测A10040GB软件平台；本表约2.4×对应NPU-only。 |
| Benchmark：模型 / 数据 / 输入形状 | GPT-3形状7/13/30/175B；ShareGPT平均80入/296出、Alpaca12入/56出；B64–512；合成稳态再抽10batch |
| 质量指标与已有数值 | 使用GPT-3配置/形状，不等于下载真实GPT3权重测质量；所用报告无新PPL/任务分数，NR。 |
| 硬件指标与已有数值 | 对NPU-only约2.4×吞吐；Table5功耗1.8×/节能25%属HBM/PIM相关估计 |
| 其他局部PPA摘录 | DRAMsim3 Micron功耗模型；PIM all-bank compute按read功耗/电流4×，另加row-buffer背景 |
| 条件：工艺 / 频率 | 22nm仅CACTI7双row-buffer面积模型；整NPU节点NR；Table2 1GHz在HBM栏，不推定所有模块同频 |
| 实现 / 证据层级 | ONNXim+修改DRAMsim3；真实A100/PyTorch基线 |
| 存储与系统边界 | 8个128×128阵列、8个128×1向量单元、32HBM channels |
| 本项目怎样使用 / 尚缺什么 | 大batch异构NPU/PIM调度和存储映射参照；不能转为B1单请求TPOT。 稳态抽样不是所有请求完整服务回放；4×PIM电流是设定；22nm非整机工艺 |

证据：[S05]，定位：§8.1–8.2、Tables2–5。原调研访问状态：全文HTML与代码入口核读；本轮为报告复核，未逐篇重做论文实验。

原文 / 作者实现：[入口1](https://arxiv.org/html/2403.00579v3)；[入口2](https://github.com/casys-kaist/NeuPIMs)。

<a id="e05"></a>

### E05 AttAcc! Unleashing the Power of PIM for Batched Transformer-based Generative Model Inference（ASPLOS 2024）

| 字段 | 内容 |
|---|---|
| 方案 / 比较层级 | 受容量/SLO约束的生成推理加速 GPU做FC、HBM-PIM做attention及共同计算 |
| 本表数据实际对应的对手 / 控制 | DGX-Large等容量平台，1280GB容量对齐；GPU部分由DGX A100/OPT66B校准。 |
| Benchmark：模型 / 数据 / 输入形状 | LLaMA65B/GPT3 175B FP16、MT-NLG530B INT8；输入输出128/512/2048；batch受30/50/70ms-token SLO约束 |
| 质量指标与已有数值 | 主要形状/性能工作负载；所用报告未摘生成质量分数，NR。 |
| 硬件指标与已有数值 | §7.2 LLaMA65B对DGX-Large最高2.81×；报告请求时间和energy/output-token |
| 其他局部PPA摘录 | HBM ACT/read文献能量；片内read按显微照片数据通路长度缩放；SRAM FinCACTI |
| 条件：工艺 / 频率 | ASAP7预测7nm逻辑库；DRAM新增逻辑另折1z、密度假设；非全机7nm；GEMV/累加666MHz；softmax1.3GHz |
| 实现 / 证据层级 | 修改Ramulator；Verilog/DC；修改FinCACTI；真实DGX A100性能校准 |
| 存储与系统边界 | HBM PIM、容量等额1280GB DGX-Large对照 |
| 本项目怎样使用 / 尚缺什么 | SLO/容量约束下系统时延和energy/output-token参照；芯片/堆栈数量及动态batch须一致才算倍率。 GPU校准不等于新PIM能耗实测；预测库/DRAM折算假设需保留；PDF截图未成功，正文文字可核 |

证据：[S05]，定位：PDF10–12页、§7.1–7.3、Figs13–15。原调研访问状态：全文PDF文字核读；本轮为报告复核，未逐篇重做论文实验。

原文 / 作者实现：[入口1](https://scale.snu.ac.kr/papers/2024-04-Conference-ASPLOS-AttAcc.pdf)；[入口2](https://github.com/scale-snu/attacc_simulator)。

<a id="e06"></a>

### E06 PIM Is All You Need: A CXL-Enabled GPU-Free System for Large Language Model Inference（ASPLOS 2025）

| 字段 | 内容 |
|---|---|
| 方案 / 比较层级 | 面向LLM生成的设备与多设备互连协同 GPU-free PIM+controller/vector/RISC-V |
| 本表数据实际对应的对手 / 控制 | GPU vLLM等平台；吞吐GPU B128、CENT按模型B32/40/80，低延迟B1另列。 |
| Benchmark：模型 / 数据 / 输入形状 | Llama2-7/13/70B，512入3584出；GPU vLLM B128，CENT吞吐B32/40/80，低延迟另比B1 |
| 质量指标与已有数值 | Llama2配置、功能/指令轨迹；性能模型不要求实际权重，所用报告未摘新PPL/任务质量结果。 |
| 硬件指标与已有数值 | E2E吞吐geomean2.3×、能效2.3×；prefill GPU快2.5×，decode CENT快2.5× |
| 其他局部PPA摘录 | Micron calculator+Samsung GDDR6 IDD/V；MAC按gapless-read电流3× |
| 条件：工艺 / 频率 | GDDR6-PIM 1Y(14–16nm)；控制器TSMC28nm综合后投影7nm；面积另含die-shot缩放；28nm控制器临界路径1ns；投影7nm/2GHz |
| 实现 / 证据层级 | 功能模拟器；修改Ramulator2；CXL解析模型；DC |
| 存储与系统边界 | GDDR6 PIM和CXL；controller不全是同一节点实现 |
| 本项目怎样使用 / 尚缺什么 | GPU-free PIM、请求及分阶段能量参照；不能忽略prefill与decode方向相反或batch差异。 性能模型不需真实权重；功能正确不等于时延校准；批量差异和3×电流/节点投影须保留 |

证据：[S05]，定位：§6–7、Tables4–5、AppendixA。原调研访问状态：全文HTML及artifact入口核读；本轮为报告复核，未逐篇重做论文实验。

原文 / 作者实现：[入口1](https://arxiv.org/html/2502.07578v3)；[入口2](https://github.com/Yufeng98/CENT)。

<a id="e07"></a>

### E07 PIM GPT a hybrid process in memory accelerator for autoregressive transformers（npj Unconventional Computing 2024）

| 字段 | 内容 |
|---|---|
| 方案 / 比较层级 | 自回归小batch生成 bank-level PIM MAC+独立ASIC非线性/控制 |
| 本表数据实际对应的对手 / 控制 | 真实NVIDIA T4测量，CUDA events+pynvml；采用最终期刊正文，非旧预印本倍率。 |
| Benchmark：模型 / 数据 / 输入形状 | 8个GPT2/3模型最大1.4B；B1生成1024tokens、重复10次；T4 CUDA events+pynvml |
| 质量指标与已有数值 | GPT2/3模型工作负载；当前摘录无可引用PPL/下游任务表，NR。 |
| 硬件指标与已有数值 | 最终期刊对T4速度41–137×、能效123–383× |
| 其他局部PPA摘录 | ASIC0.64mm²、峰值304.59mW；DRAM命令IDD×t×V含refresh；I/O5.5pJ/bit |
| 条件：工艺 / 频率 | ASIC TSMC28nm HPC+；PIM MAC28nm综合后1.25V缩放并乘1.5布线补偿；ASIC1GHz |
| 实现 / 证据层级 | 自研C++ event-driven clock-cycle accurate；DC；TSMC Memory Compiler |
| 存储与系统边界 | PIM命令时序取SK Hynix AiM原型；普通DRAM命令借GDDR5时序，电流借DDR5 datasheet并乘3；非目标DRAM工艺完整P&R |
| 本项目怎样使用 / 尚缺什么 | B1自回归PIM+非线性ASIC的系统参照；需要保留DRAM时序、电流借值和独立更正页待核状态。 未见新ASIC/PIM系统校准；2025-03-04 correction独立页未取得，采用当前正文；勿混旧预印本 |

证据：[S05]，定位：Methods Hardware/Simulation configuration、Table2。原调研访问状态：最终正文核读；更正独立页待核；本轮为报告复核，未逐篇重做论文实验。

原文 / 作者实现：[入口1](https://www.nature.com/articles/s44335-024-00004-2)。

<a id="e08"></a>

### E08 MBA: Mega-Buffer Architecture Based on 1T1C IGZO eDRAM for Efficient LLM Inference（DAC 2026）

| 字段 | 内容 |
|---|---|
| 方案 / 比较层级 | 以KV优先、双缓冲、iteration-aware淘汰减少HBM流量 具有GB级片上eDRAM的专用LLM架构；A100为对照 |
| 本表数据实际对应的对手 / 控制 | A100 GPU、COMET；MBA/A100 W8A8 SmoothQuant，COMET W4A4KV4，精度并不完全相同。 |
| Benchmark：模型 / 数据 / 输入形状 | Llama3.1-8B/Qwen3-14B，WT2；MBA/A100 W8A8 SmoothQuant，COMET W4A4KV4；prefill/decode均评 |
| 质量指标与已有数值 | WT2作为生成工作负载；所读全文未报告PPL或任务准确率，不能因使用WT2就补写PPL。 |
| 硬件指标与已有数值 | 对GPU/COMET报告E2E速度5.99×/3.63×、能效8.86×/4.93× |
| 其他局部PPA摘录 | 估计569.87mm²、615TOPS；SFU/NoC借文献；eDRAM改FinCACTI |
| 条件：工艺 / 频率 | 目标7nm；PE成本由45nm文献缩到7nm；非7nm整芯片P&R；PE 0.5GHz；其他模块频率NR |
| 实现 / 证据层级 | 自研behavior-level计算图模拟器；修改FinCACTI；DeepScaleTool；遗传搜索 |
| 存储与系统边界 | 96blocks，各25×16×16PE与24MB eDRAM；总local2.25GB、global640MB；HBM1.5TB/s、3.9pJ/bit |
| 本项目怎样使用 / 尚缺什么 | 大容量片上eDRAM、prefill/decode与访存消融参照；系统行为模型/工艺投影不称硅实测。 不同精度、工艺投影与存储模型拼接；未证明A100每项测量流程；结果非新ASIC实测 |

证据：[S05]，定位：用户509_Camera_Ready_Paper.pdf第5页§5/6、Table1、Fig7；全文6页；DAC官方节目。原调研访问状态：用户PDF全文核读，第5页渲染核表；公开元数据核对；本轮为报告复核，未逐篇重做论文实验。

原文 / 作者实现：[入口1](https://63dac.conference-program.com/presentation/?id=RESEARCH509&sess=sess318)。

<a id="e09"></a>

### E09 Z1T: Sparse Transformer-Like Models for Probabilistic Hardware（Extropic官方报告，2026-09-04）

| 字段 | 内容 |
|---|---|
| 方案 / 比较层级 | 4-sparse tanh-linear、DyT、GCA/AFT-conv；与FPGA分工，另有稀疏GPT2 scaling实验。 为Z1重设计并训练的模型及异构decode成本估算。 |
| 本表数据实际对应的对手 / 控制 | GPT2-small/XL质量/训练FLOPs参照；H100 dense-equivalent模型成本参照，分别列10/50/100% MFU。 |
| Benchmark：模型 / 数据 / 输入形状 | OpenWebText、GPT2 BPE；验证loss/训练FLOPs/参数量/connectivity。发布checkpoint：4层D12288、序列256、fan-in4；效率示例：4层D512、上下文1024、H4/kernel4。 |
| 质量指标与已有数值 | 验证交叉熵/scaling曲线；代码CE/ln2在BPE上属于bits/token，不能无条件称bits/byte。当前资料没有与Qwen同tokenizer/同WT2的可直接横比分数。 |
| 硬件指标与已有数值 | 仅Z1采样8.74nJ/token；Z1+已计FPGA且排除词表/芯片间搬运294.52nJ/token；加入FPGA logits约136.4µJ/token。示例串行58.8µs/token≈17,000token/s；均为估算。 |
| 其他局部PPA摘录 | 所列H100比值14–139×对应排除logits/搬运的边界，不是完整系统实测倍率。 |
| 条件：工艺 / 频率 | Z1概率硬件+FPGA；卡数/匹配全系统面积未建模；Z1内部50MHz；示例25×32次采样约16µs |
| 实现 / 证据层级 | 模型训练与公开浮点JAX前向；物理部分为能量/时延模型估计 |
| 存储与系统边界 | 需足够Z1芯片并行放置采样算子；不将D12288公开权重套D512效率示例。 |
| 本项目怎样使用 / 尚缺什么 | 原生p-bit模型与loss/规模律/成本边界参照；若作模型质量横比，需要独立对齐语料、分词及上下文。 不同模型/语料/tokenizer与架构；质量曲线未包含同样的有限采样/激活量化验证；总面积和所需并行芯片数NR。 |

证据：[S16]、[S04]，定位：官方report的scaling/encoding/architecture/performance；本项目S16的逐项指标映射。原调研访问状态：原调研报告、源码和配置核查；本轮复用；本轮为报告复核，未逐篇重做论文实验。

原文 / 作者实现：[入口1](https://extropic.ai/writing/z1t)；[入口2](https://huggingface.co/Extropic-AI/Z1T-0)。

<a id="e10"></a>

### E10 MoNDE: Mixture of Near-Data Experts for Large-Scale Sparse Models（DAC 2024）

| 字段 | 内容 |
|---|---|
| 方案 / 比较层级 | CPU/GPU与Near-Data专家执行协同，针对MoE。 GPU+NDP异构MoE系统。 |
| 本表数据实际对应的对手 / 控制 | GPU/CPU专家执行和MoNDE NDP执行；原报告未摘完整结果表/倍率，NR。 |
| Benchmark：模型 / 数据 / 输入形状 | Switch Transformer、NLLB-MoE；主机实测profiling+专家周期模型。 |
| 质量指标与已有数值 | 当前调研未列新的任务质量数值，NR。 |
| 硬件指标与已有数值 | 可核NDP28nm/1GHz；当前报告未摘精确速度/能量倍率，NR。 |
| 其他局部PPA摘录 | NR；不据缺项补零。 |
| 条件：工艺 / 频率 | 28nm；NDP核心1GHz |
| 实现 / 证据层级 | DC+同工艺buffer compiler；专家周期模型+Ramulator |
| 存储与系统边界 | Micron DDR4-3200功耗计算器，按电压调整至LPDDR；近似不能当目标内存实测。 |
| 本项目怎样使用 / 尚缺什么 | 专家卸载/异构调度方法参照，当前不作为稠密Qwen的数值主对手。 稀疏MoE专家系统与稠密Qwen不同；GPU/新增NDP面积功率分列。 |

证据：[S01]，定位：§4.1、§4.3、Table3；S01代表工作表。原调研访问状态：原调研作者全文核读；本轮为报告复核，未逐篇重做论文实验。

原文 / 作者实现：[入口1](https://jaewoong.org/pubs/dac24-monde.pdf)。

<a id="e11"></a>

### E11 Splitwise: Efficient Generative LLM Inference Using Phase Splitting（ISCA 2024）

| 字段 | 内容 |
|---|---|
| 方案 / 比较层级 | 将prefill与decode在异构GPU集群上拆分调度。 服务系统，非新算术ASIC。 |
| 本表数据实际对应的对手 / 控制 | 同构/异构服务部署与GPU profiling参考；当前报告未摘所有配置倍率。 |
| Benchmark：模型 / 数据 / 输入形状 | BLOOM176B、Llama70B及请求分布；A100/H100实机profiling+离散事件模拟。 |
| 质量指标与已有数值 | 主要服务系统性能；当前摘录无替换后PPL质量实验，NR。 |
| 硬件指标与已有数值 | 报告TTFT/TBT/E2E和SLO；性能模型MAPE<3%。该<3%是模型误差，不是应用质量损失或能量误差。 |
| 其他局部PPA摘录 | NR；不据缺项补零。 |
| 条件：工艺 / 频率 | 商用GPU平台，不指定一个新ASIC节点；实际锁频/运行频率在原调研中未找到 |
| 实现 / 证据层级 | 实机profiling+服务仿真 |
| 存储与系统边界 | 含跨设备阶段交接，平台功率预算不等于请求实测能量。 |
| 本项目怎样使用 / 尚缺什么 | 端到端请求指标和prefill/decode分解的协议参照，非p-bit电路PPA对手。 服务吞吐、排队、SLO与单设备单token不同；不得把资源功率预算当每请求J。 |

证据：[S01]，定位：§V-B；S01代表工作与性能定义。原调研访问状态：原调研作者全文核读；本轮为报告复核，未逐篇重做论文实验。

原文 / 作者实现：[入口1](https://www.microsoft.com/en-us/research/wp-content/uploads/2023/12/Splitwise_ISCA24.pdf)。

### 3.2 新器件、质量与其他应用补充

这些条目帮助选任务、理解基线与器件误差；并非全部是生成LLM端到端硬件对手。

<a id="q01"></a>

### Q01 ARTEMIS: A Mixed Analog-Stochastic In-DRAM Accelerator for Transformer Neural Networks（CASES/TCAD 2024）

| 字段 | 内容 |
|---|---|
| 方案 / 比较层级 | 模拟累加+随机in-DRAM算术与层映射。 混合器件/架构方案，任务跨OPT、BERT、翻译与ViT。 |
| 本表数据实际对应的对手 / 控制 | FP32、8bit、8bit+SC分层参考。 |
| Benchmark：模型 / 数据 / 输入形状 | OPT-350M/OpenAssistant-Guanaco；BERT/ALBERT的GLUE；Transformer-base/TED-HRLR；ViT/ImageNet。 |
| 质量指标与已有数值 | OPT BLEU18.07→17.79→17.49；SC相对8bit额外下降0.30（约1.69%）。GLUE子任务/聚合未列，翻译作者称Accuracy，ImageNet top-k未明确。 |
| 硬件指标与已有数值 | 本次所用调研无完整PPA数值摘表，NR；原文给电路/数据路径模型。背景中每subarray 64MAC操作48ns不等于SC每bit时钟。 |
| 其他局部PPA摘录 | NR；不据缺项补零。 |
| 条件：工艺 / 频率 | 混合LTSPICE、Genus、CACTI-3D成本；完整统一PVT未核；没有统一整机时钟摘录 |
| 实现 / 证据层级 | Python逐层映射+电路/存储模型 |
| 存储与系统边界 | 有HBM ACT及数据路径能量表，完整边界需原表 |
| 本项目怎样使用 / 尚缺什么 | 量化误差和随机额外误差分解的示例；用于对应应用或方法对照。 BLEU不是PPL；不得把不同模型和不同任务分数合成7B生成LLM验证。 |

证据：[S03]，定位：§IV-A、TableIV，PDF第9页。原调研访问状态：原调研全文核读；本轮为报告复核，未逐篇重做论文实验。

原文 / 作者实现：[入口1](https://arxiv.org/pdf/2407.12638)。

<a id="q02"></a>

### Q02 SCARLET（DATE 2026）

| 字段 | 内容 |
|---|---|
| 方案 / 比较层级 | 光学PCM和动态近似浮点乘法。 光学/转换/激光成本模型及语言模型数值评价。 |
| 本表数据实际对应的对手 / 控制 | 同模型原浮点与近似算术配置；本表差值来自Fig.4(a)。 |
| Benchmark：模型 / 数据 / 输入形状 | OPT2.7/6.7/13B、Llama2-7/13B、GPTNeo2.7B；WikiText下一token预测。 |
| 质量指标与已有数值 | Token Accuracy；Llama2-13B图中差值−0.11%（保留原文%口径）；未锁定WT2/WT103完整计分协议，未报PPL。 |
| 硬件指标与已有数值 | 系统评估设5GHz、O-E5GS/s；GF22FDX SRAM缩至7nm，HBM20pJ/bit。完整硬件倍率未在所用报告摘出，NR。 |
| 其他局部PPA摘录 | NR；不据缺项补零。 |
| 条件：工艺 / 频率 | 光子器件+数字节点投影，非全系统7nm实现；系统模型5GHz；不能替换成器件18GHz演示 |
| 实现 / 证据层级 | 光电器件/架构成本模型 |
| 存储与系统边界 | SRAM节点缩放与HBM固定单价 |
| 本项目怎样使用 / 尚缺什么 | 近似算术的Token Accuracy方法参照，不能以其差值设本项目PPL阈值。 argmax准确率不保证PPL；器件漂移进入完整质量的证据未核得。 |

证据：[S03]、[S01]，定位：§IV-A/B、Fig.4。原调研访问状态：原调研全文核读；本轮为报告复核，未逐篇重做论文实验。

原文 / 作者实现：[入口1](https://www.bu.edu/peaclab/files/2026/03/SCARLET_CameraReady.pdf)。

<a id="q03"></a>

### Q03 Analog Foundation Models（2025公开论文v3）

| 字段 | 内容 |
|---|---|
| 方案 / 比较层级 | PCM噪声建模、硬件感知训练和静态量化。 现代小型Instruct LLM的模拟噪声质量验证。 |
| 本表数据实际对应的对手 / 控制 | 原浮点、无噪声LLM-QAT SI8/W4，以及Analog FM噪声配置SI8/W16_hw_noise/O8；三者不同。 |
| Benchmark：模型 / 数据 / 输入形状 | Phi-3-mini-4k-instruct、Llama-3.2-1B-Instruct；MMLU/GSM8K/BoolQ/HellaSwag/MedQA/AGIEval/ARC-C/ARC-E/ANLI九任务；补充MATH-500、IFEval、XSTest、GLUE。 |
| 质量指标与已有数值 | Phi3九任务均分70.03→66.22；LLM-QAT65.70。Llama3.2-1B均分45.49→40.91，但GSM8K45.79→30.75。10次噪声重复，shot协议各任务不同。 |
| 硬件指标与已有数值 | 当前摘录不提供全模型硅片PPA/端到端速度数据，NR。 |
| 其他局部PPA摘录 | NR；不据缺项补零。 |
| 条件：工艺 / 频率 | PCM噪声模型，非全模型芯片运行；不适用统一芯片主频 |
| 实现 / 证据层级 | 噪声/训练软件实验 |
| 存储与系统边界 | W16为软件表示，不等于模拟16bit有效精度。 |
| 本项目怎样使用 / 尚缺什么 | 现代LLM多任务和器件噪声鲁棒性参考，非直接硬件速度/能效对手。 有再训练和量化，不能当无训练随机替换的容差；九任务均分不能掩盖GSM8K损失。 |

证据：[S03]，定位：Table1、§3、Appendix A/E、Table14。原调研访问状态：原调研v3全文核读；本轮为报告复核，未逐篇重做论文实验。

原文 / 作者实现：[入口1](https://arxiv.org/html/2505.09663v3)。

<a id="q04"></a>

### Q04 Demonstration of transformer-based ALBERT model on a 14nm analog AI inference chip（Nature Communications 2025）

| 字段 | 内容 |
|---|---|
| 方案 / 比较层级 | 验证模拟AI上Transformer线性层和漂移补偿 14nm PCM芯片实际执行inProj/outProj/FC1/FC2；其他运算外部电脑执行 |
| 本表数据实际对应的对手 / 控制 | 对应浮点ALBERT、hardware-in-loop和补偿/漂移配置；iso-accuracy定义为超过对应浮点准确率的99%。 |
| Benchmark：模型 / 数据 / 输入形状 | ALBERT12层共享权重7.1M；7GLUE任务；B1序列≤128；合成150/300/500/1000长度分析 |
| 质量指标与已有数值 | 七项RTE/MRPC/CoLA/SST-2/QNLI/QQP/MNLI均按该论文Accuracy；CoLA不是官方GLUE MCC。原文概述平均低1.8%保留原口径；逐项表未在矩阵摘全。 |
| 硬件指标与已有数值 | 平均hardware准确率低于FP1.8%（原文口径）；系统估计>3TOPS/W；30天漂移实验 |
| 其他局部PPA摘录 | MAC含activation到chip edge及ILP/OLP转换实测；其余数字运算模拟同芯片部署 |
| 条件：工艺 / 频率 | 14nm PCM AI芯片；统一PVT NR；统一系统时钟NR，不填猜测GHz |
| 实现 / 证据层级 | 芯片测量+软件hardware-in-loop；数字单元14nm模拟投影 |
| 存储与系统边界 | 动态attention/LayerNorm实测流程在外部控制电脑；完整自主系统未实测 |
| 本项目怎样使用 / 尚缺什么 | 线性层硬件在环、漂移和重校准的强证据；动态Attention外部执行，不能称全LLM芯片实测。 实测线性层不等于全LLM整机实测；补充材料全部测量设置未核全 |

证据：[S05]、[S03]、[S02]，定位：Fig1、Fig5；Methods Power performance measurement and estimation。原调研访问状态：最终正文核读，补充材料未全核；本轮为报告复核，未逐篇重做论文实验。

原文 / 作者实现：[入口1](https://www.nature.com/articles/s41467-025-63794-4)。

<a id="q05"></a>

### Q05 CQ-CiM: Hardware-Aware Embedding Shaping for Robust CiM-Based Retrieval（DAC 2026 / arXiv v3）

| 字段 | 内容 |
|---|---|
| 方案 / 比较层级 | 嵌入压缩/量化/抗噪，改检索表示。 检索系统与FP16 LLM文档选择，非LLM内部算术替换。 |
| 本表数据实际对应的对手 / 控制 | Vanilla嵌入等检索参考；下述ArguAna点为128维2bit设置。 |
| Benchmark：模型 / 数据 / 输入形状 | all-MiniLM-L6-v2等嵌入模型；ArguAna/FiQA/CQADupStackGisRetrieval/NanoHotpotQA/ARCChallenge等检索；top-5相关文档选择。 |
| 质量指标与已有数值 | ArguAna Vanilla Recall@5/nDCG@10=0.468/0.385；CQ-CiM=0.529/0.433。另有nDCG@5与文档选择Accuracy，不能叫生成答案正确率。 |
| 硬件指标与已有数值 | 所用质量报告未给本表可统一引用的整机PPA，NR。 |
| 其他局部PPA摘录 | NR；不据缺项补零。 |
| 条件：工艺 / 频率 | 面向FeFET/ReRAM等CiM非理想性；NR |
| 实现 / 证据层级 | 嵌入/量化/噪声与检索评估 |
| 存储与系统边界 | 生成LLM保持FP16 |
| 本项目怎样使用 / 尚缺什么 | 若研究外部检索/嵌入存算可使用；不能直接与FFN/Attention PPL排序。 ARCChallenge/HotpotQA的检索变体不等于同名选择题/生成问答任务。 |

证据：[S02]、[S03]，定位：§4、Table2、Fig.6、§4.4。原调研访问状态：原调研全文核读；本轮为报告复核，未逐篇重做论文实验。

原文 / 作者实现：[入口1](https://arxiv.org/html/2602.20083v3)。

<a id="q06"></a>

### Q06 Lightening-Transformer: A Dynamically-Operated Optically-Interconnected Photonic Transformer Accelerator（HPCA 2024）

| 字段 | 内容 |
|---|---|
| 方案 / 比较层级 | 动态光子点积架构与噪声感知训练。 光子Transformer算子与BERT/DeiT应用。 |
| 本表数据实际对应的对手 / 控制 | 同位宽无噪GPU：8bit BERT-base、4bit DeiT-T。 |
| Benchmark：模型 / 数据 / 输入形状 | BERT-base/SST-2、DeiT-T/ImageNet-1K。 |
| 质量指标与已有数值 | SST-2与ImageNet分类Accuracy；所用报告未摘逐配置数值，NR。 |
| 硬件指标与已有数值 | 性能表含更广模型，但不能自动算作对应质量验证；本表无可引用统一硬件数值，NR。 |
| 其他局部PPA摘录 | NR；不据缺项补零。 |
| 条件：工艺 / 频率 | 光子/数字外围混合成本；本表NR |
| 实现 / 证据层级 | 架构/器件模型与噪声感知质量 |
| 存储与系统边界 | 具体数据搬运边界按原文另核 |
| 本项目怎样使用 / 尚缺什么 | 器件噪声+训练的评价方法参考，应用范围须匹配。 Encoder/视觉分类不是7B生成LLM；同位宽参考也不是原始浮点PPL。 |

证据：[S02]，定位：§V-E、Fig.14。原调研访问状态：原调研全文核读；本轮为报告复核，未逐篇重做论文实验。

原文 / 作者实现：[入口1](https://scopex-asu.github.io/files/publications/ONN_HPCA2024_Gu.pdf)。

<a id="q07"></a>

### Q07 X-Former: In-Memory Acceleration of Transformers（IEEE TVLSI 2023）

| 字段 | 内容 |
|---|---|
| 方案 / 比较层级 | 异构存算减少写入和片外访问 静态权重ReRAM Projection Engine+8T SRAM动态Attention Engine |
| 本表数据实际对应的对手 / 控制 | GTX1060、NVM-only以及iso-area SRAM等基线；两组倍率分开。 |
| Benchmark：模型 / 数据 / 输入形状 | BERT-base/large encoder；GLUE≤512、SQuAD384 |
| 质量指标与已有数值 | BERT-base/large；GLUE与SQuAD；所用报告没有摘完整质量数表，NR。 |
| 硬件指标与已有数值 | 最高对GTX1060速度85×/节能7.5×；对NVM-only10.7×/4.6× |
| 其他局部PPA摘录 | Projection Engine ReRAM/DAC/ADC用PUMA；Attention Engine 8T-SRAM MVM及写入用SPICE，SAR ADC功耗引文献[28]；数字DC、片上存储CACTI |
| 条件：工艺 / 频率 | 数字32nm CMOS；ReRAM2b、128×128；完整PVT NR；数字1GHz；每crossbar2个8b ADC、1.28GS/s；1b DAC |
| 实现 / 证据层级 | 自研架构模型并入PUMAsim；8T SRAM SPICE；数字RTL/DC；CACTI；NeuroSim误差 |
| 存储与系统边界 | iso-area SRAM基线显式计外DRAM；型号/IDD方法段NR |
| 本项目怎样使用 / 尚缺什么 | 静态ReRAM与动态SRAM异构CIM的系统/模块参照；不是自回归decode的直接速度基线。 不是现代autoregressive decode；最终期刊排版未逐页比对；不可继承其器件参数作标准 |

证据：[S05]，定位：§VI、TablesI–IV、§VII；作者预印本技术细节。原调研访问状态：作者全文核读；期刊页受限；本轮为报告复核，未逐篇重做论文实验。

原文 / 作者实现：[入口1](https://arxiv.org/html/2303.07470v1)；[入口2](https://doi.org/10.1109/TVLSI.2023.3282046)。

<a id="q08"></a>

### Q08 ASADI（HPCA 2024）

| 字段 | 内容 |
|---|---|
| 方案 / 比较层级 | ReRAM模拟/数字存内稀疏Attention。 Attention/Transformer架构性能与能耗评估。 |
| 本表数据实际对应的对手 / 控制 | 当前质量报告没有完整摘出对手清单/倍率，NR。 |
| Benchmark：模型 / 数据 / 输入形状 | BERT/BART/GPT2等；列九GLUE、SQuAD v1.1、WT2、IMDB、ImageNet-1K；Syn-4K/8K为性能负载。 |
| 质量指标与已有数值 | 已核主文未找到新的应用质量数值表；列出WT2不等于报告PPL。 |
| 硬件指标与已有数值 | 当前摘录没有可统一引用的具体PPA数值，NR。 |
| 其他局部PPA摘录 | NR；不据缺项补零。 |
| 条件：工艺 / 频率 | ReRAM/数字混合；本表NR |
| 实现 / 证据层级 | 架构/存算评估 |
| 存储与系统边界 | Float32表示、1bit/cell；其余边界需按原文 |
| 本项目怎样使用 / 尚缺什么 | 保留为架构对手候选，补齐所需硬件原表后再填数。 不能据任务清单补出PPL/F1或质量容差。 |

证据：[S02]，定位：§VI-A；S02/S03。原调研访问状态：原调研主文核读；本轮为报告复核，未逐篇重做论文实验。

原文 / 作者实现：[入口1](https://www.comp.nus.edu.sg/~tulika/HPCA24.pdf)。

<a id="q09"></a>

### Q09 3D-CIMlet（DAC 2025）

| 字段 | 内容 |
|---|---|
| 方案 / 比较层级 | RRAM/eDRAM异构chiplet与映射。 映射、能量、时延、热和可靠性。 |
| 本表数据实际对应的对手 / 控制 | 所用报告未摘完整对手与倍率表，NR。 |
| Benchmark：模型 / 数据 / 输入形状 | 含GPT2/WikiText-2等映射工作负载。 |
| 质量指标与已有数值 | 取得主文未找到新的PPL/任务质量表。 |
| 硬件指标与已有数值 | 有能量/时延/热/可靠性评价；本次资料没有完整数值摘表，NR。 |
| 其他局部PPA摘录 | NR；不据缺项补零。 |
| 条件：工艺 / 频率 | 多类存算/三维chiplet，不能写单一节点；本表NR |
| 实现 / 证据层级 | 芯粒/映射/器件成本评估 |
| 存储与系统边界 | 具体容量、互连和外围按原文补表 |
| 本项目怎样使用 / 尚缺什么 | 多芯片/存储映射参照，暂不作为生成质量数值对手。 工作负载名称不证明应用质量；热/可靠性指标不换算为PPL。 |

证据：[S02]，定位：§V；S02/S03。原调研访问状态：原调研作者主文核读；本轮为报告复核，未逐篇重做论文实验。

原文 / 作者实现：[入口1](https://engineering.purdue.edu/NanoX/assets/pdf/2025_DAC_3D-CIMlet_AAM.pdf)。

### 3.3 随机源、读出和非LLM机制资料：可用到哪一层

| 工作 | 已有benchmark/数据 | 能用于什么比较 | 限制 / 来源 |
|---|---|---|---|
| P2LSG，ASP-DAC2024 | 128拍乘法MAE0.88%，Sobol0.45%；两路8位发生器45nm综合163µm²、16.05µW | 随机/低差异发生器面积、功率及有限前缀误差 | 标量/图像；不是GEMM或LLM，64路共享协方差须重验；[S04] §3.4 |
| Deterministic Methods for SC using Low-Discrepancy Sequences，ICCAD2018 | 双8位乘法完整精确周期65536拍；128拍Sobol MAE约0.451% | 联合序列覆盖、短前缀、面积×时延 | ADP为能耗代理，未验证神经网络质量；不表示所有8位乘法都需65536拍；[S04] §3.5 |
| Dither computing，ARITH2021 | 确定性主体+随机余量，理论/数值/小型网络；当前报告未摘统一PPA数表 | 量化残差随机化的算法对手 | 非本项目完整FFN或整机实测；[S04] §3.3 |
| p-PIM，Advanced Science2026 | 单sMTJ时间复用+FPGA硬件在环64×64；256拍/4位MNIST96.52±0.15% | 原生随机器件、列累加/激活与读出 | 器件数据100Hz采样后复用，FPGA50MHz不是器件独立采样率；非LLM；[S04] §2.4 |
| Current Digitizers，PR Applied2025 | ADC6b：911244.6µm²、12064pJ、480ns；ADC2b：59244.6µm²、1388.2pJ、480ns；sCDC：7352.2µm²、455.2pJ、335ns | 模拟列和后的读出电路P/A/E/延迟 | TableI是读出边界，非完整MVM/LLM；单器件硬件在环与后版图电路分别看；[S04] §3.8 |
| ASTRA，GLSVLSI2025 | OPT350/Guanaco BLEU18.07→17.79→17.49；光学AND/电荷归约/ADC模型 | 光学乘法与模拟归约，量化/随机损失分解 | 8位128脉冲非IID p-bit；非7B WT2质量；[S04] §3.7 |
| SC-CNN/BISC后续、VLSI2024事件相机SCIM | 前者训练CNN；后者12nm实测、278–514M Event/s | 存储组织、共享SNG、ADC-less与硅片证据方法 | 图像/事件性能不可当LLM token性能；[S04] §3.1–3.2 |

原报告中的完整题名、DOI及原文链接见[S04]。以上数据只按各原边界使用，不补算LLM能效倍率。

## 4. Softmax与采样：可直接查用的数据表

### 4.1 N=512整行数字Softmax，ASAP2020

| 格式 / 实现 | 并行P | 整行周期 | 原250MHz下µs | 原45nm面积mm² | 仅按100MHz换算µs |
|---|---:|---:|---:|---:|---:|
| fixed32 / LUT | 1 | 1542 | 6.168 | 0.059 | 15.42 |
| fixed32 / LUT | 2 | 775 | 3.100 | 0.085 | 7.75 |
| fixed32 / LUT | 4 | 392 | 1.568 | 0.138 | 3.92 |
| FP16 / DW EXP、LOG | 8 | 199 | 0.796 | 0.283300 | 1.99 |
| FP16 / LUT | 8 | 201 | 0.804 | 0.220178 | 2.01 |

来源：[S09]、[M12](#m12)。100MHz列只是`cycles/f`，不是本工艺重新实现的延迟；没有把外部面积乘0.81。NOREG输入存储不含在上表。fixed32与FP16分别比较精度与并行度，FP16也不等于BF16。原报告没有可直接填进本项目的同工艺能量列，保留缺项。

### 4.2 其他数字Softmax锚点

| 文章 / 方案 | 已有面积/时钟数据 | 明确缺项与使用范围 |
|---|---|---|
| Li等，Science China Information Sciences2024，α=1/4 | 65nm，2336.00/2492.40µm²，clock5ns；Table5同表对手3051.60µm² | 来自出版方PDF搜索索引，原调研下载/视觉复核未完成；N512整行周期未核得。只能作小面积定点核线索，不得说整行只需5ns |
| ITA整数Softmax | 22FDX，28.7kGE；约0.005709mm²由0.173mm²×3.3%派生 | 512整行周期NR；完整核心/片存边界见[M10](#m10) |
| ConSmax v3中的普通Softmax对手 | 16nm/130nm：0.011/0.18mm²；Fmax909/285.71MHz，N256 | 这是普通Softmax对手而非ConSmax本体；整行周期/完整位宽未核得。功率频率500/80MHz与Fmax不同；ConSmax改归一化并训练，不是普通Softmax精确实现 |

来源：[S09]；[Li DOI](https://doi.org/10.1007/s11432-024-4137-4)、[ConSmax v3](https://arxiv.org/html/2402.10930v3)。这些线索未形成同工艺的直接胜负表。

### 4.3 采样必须另设输出合同

| 路线 | 输出到哪里才算可比 | 要计的主要动作 | 目前证据 |
|---|---|---|---|
| 准确dense在线Softmax/PV | 最终Attention向量 | QK、max/exp/归约、PV、重缩放；无需额外采样 | 有数学/软件和架构参考；全模块同工艺PPA未闭合 |
| 数字CDF+IID | 候选索引/次数ready，或接相同V读/累加的最终输出 | max/exp、质量/CDF、存储、每样本随机值、选择、可选直方图/压缩 | 官方CUDA路径与旧宏动作已有；后续电路同工艺PPA未闭合 |
| 数字systematic | 直接非零索引+命中次数，允许合法融合 | prefix scan、偏移、floor差、次数发射/压缩 | SANTA代码已核；不是每位置一个独立PRNG，也无独立ASIC单价 |
| Ising赢家保持 | 合法赢家/次数ready，或相同最终输出 | 分数范围/差值、LUT、阈值保持、随机驱动、反馈/公平仲裁、输出与计数 | 有局部功能、数值、控制/阈值PPA与模型质量；未组成完整同质量PPA |

来源：[S10]。S次采样中去重V读要保留命中次数；不能只按mask把重复样本算一次。数字CDF可针对未归一权重直接抽样，不能强制额外生成整行概率或128bit one-hot。比较同S用于诊断，最终还要匹配误差/PPL和有效样本/实际V读量。

## 5. Benchmark数据集与评分指标对照

### 5.1 生成LLM与常识/推理

| 数据 / 任务 | 指标 | 已采用的论文 | 我们已有/可补 |
|---|---|---|---|
| WikiText-2 raw | PPL、NLL/CE；必须固定分词、拼接、窗口和目标 | Kelle、OPAL、AxCore、SOT-Ising等；SCARLET用的是另一指标Token Accuracy | 已有Qwen2.5/Llama2及待审Qwen3；不能直接对不同tokenizer比原PPL |
| C4 / PG19 | 对应语料PPL | OPAL/C4；Kelle/PG19 | 作为第二语料候选；本表不标我们已完成 |
| PIQA、ARC-E | acc和可适用的acc_norm | DS-CIM、Kelle、OPAL、AxCore、AFM等，按各论文实际覆盖 | 我们已有完整题集，§6.3 |
| HellaSwag | 多项选择Accuracy；保留acc与acc_norm | DS-CIM、AxCore、AFM | 我们联合Qwen表为1000固定子集，非完整10042题 |
| BoolQ、WinoGrande、ARC-C | 二分类/选择题Accuracy | DS-CIM六任务集合；AFM等按实际覆盖 | 要与DS-CIM六任务均值对照时须补齐；不可用三任务均值冒充六任务 |
| MMLU/MedQA/AGIEval/ANLI | 任务正确率，按固定shot汇总 | AFM主表 | 各任务能力、提示与shot不同；无本项目已完成声明 |
| GSM8K/MATH-500 | 提取生成最终答案后答对比例 | AFM；HSA补充质量有GSM8K | 非多选似然评分；生成长度/提取与CoT需固定 |

AFM主表shot依次：MMLU5、GSM8K CoT8、BoolQ0、HellaSwag5、MedQA2、AGIEval0、ARC-C/E各10、ANLI7。不能与我们的0-shot分数直接横排。来源：[S02]/[S03]。

### 5.2 长上下文、生成与其他任务

| 任务 | 实际指标/输出 | 论文 | 比较时必须保留 |
|---|---|---|---|
| LongBench HotpotQA / NarrativeQA | 生成答案的词重叠F1 | UniCAIM | 有效输入约1.5K/2.5K，不因模型名32k就填32K测试 |
| TriviaQA / Qasper | 可为EM/答案F1；Kelle表统称Accuracy，具体脚本未锁定 | Kelle | 不以当前Harness默认脚本倒推作者未披露协议 |
| CNN/DailyMail | 摘要ROUGE-1 | Kelle；MLPerf采用自己的ROUGE质量协议 | 不能换算PPL增幅；质量与请求吞吐边界同时固定 |
| OpenAssistant-Guanaco | BLEU | ARTEMIS、ASTRA | 文本重叠不是通用事实正确率，不是PPL |
| GLUE | 多个任务；官方有Accuracy/F1/MCC/相关系数 | PCM ALBERT、ARTEMIS、Lightening等不同子集 | PCM ALBERT七项统一用Accuracy，包括CoLA；不能写成官方GLUE综合分 |
| ArguAna/FiQA/CQADupStack等 | Recall@k、nDCG@k；另有LLM文档选择Accuracy | CQ-CiM | 同名ARCChallenge/HotpotQA检索任务与答题任务不同 |
| CIFAR10/100、ImageNet | 分类Accuracy，明确top-k | ASCEND、Lightening等 | 非生成LLM质量；不与PPL混成同一容差 |
| IFEval/XSTest | 指令通过率、拒绝/误拒指标 | AFM补充 | 不计入其主表九任务均值 |

来源：[S02]。`acc_norm`不是扣除随机猜测后的分数；当前lm-eval v0.4.8默认多选归一化使用候选字符串字符长度，具体自定义任务还须看YAML/实现。[S01]

## 6. 我们已有的对应数据：可以从哪里开始比较

下面是方便使用的代表性摘表。完整seed、更多配置、失败及原始SHA仍以链接报告为准；本文不复制每个历史run的全部参数笛卡尔积，也不以一种质量结果替另一种硬件配置背书。

### 6.1 Qwen2.5-0.5B：FFN-only完整WT2

原BF16 SDPA不改；全部24个FFN替换。固定W8、每64通道共享R8，g/u共用输入计数，FP32 SiLU(g)×u后z独立重编码；每seed299077目标，window2048/stride1024。三seed±为总体SD，非语料置信区间。

| 控制/方案 | T / K | 完整PPL均值±总体SD | 相对同协议BF16 |
|---|---|---:|---:|
| BF16 | — | 11.652735 | 基准 |
| B2 / pot2 sampled | 32/32 | 11.769199 ± 0.001183 | +0.999% |
| B4 / pot4 sampled | 16/16 | 11.900826 ± 0.003825 | +2.129% |
| B4 / pot4 sampled | 32/32 | 11.736131 ± 0.000243 | +0.716% |
| B4 / pot4 sampled | 64/64 | 11.693775 ± 0.001432 | +0.352% |
| B4 / pot4 sampled | 128/128 | 11.683928 ± 0.000383 | +0.268% |
| B1 / pot1 sampled，自然IID控制 | 64/1 | 17.800039 ± 0.013904 | +52.754% |

来源：[S17]。这张表适合比较采样/尺度对模型质量的影响；T是每x/z阶段采样数，不是完整FFN或token周期。确定性mean不等于非线性随机网络的整体数学期望。此历史理想行为/FP32恢复结果不能直接绑定当前定点GU或OR4核的PPA。

### 6.2 Qwen2.5-0.5B：联合FFN/Attention完整WT2

本轮matched cached BF16=11.652118068，和上一节vectorized BF16略有差异，必须用本轮控制。batch32、全部299077目标、window2048/stride1024；Attention计分query经过24层单token替换，前缀保留准确；FFN在prefill/decode均替换。

| FFN | Attention | S | 完整PPL均值 | seed总体SD |
|---|---|---:|---:|---:|
| 原FFN | 准确SDPA | — | 11.652118 | 0 |
| B4/T32 | 准确SDPA | — | 11.732192 | 0.001821 |
| 原FFN | screen_ising | 128 | 12.318676 | 0.005035 |
| B4/T32 | screen_ising | 128 | 12.423820 | 0.002870 |
| B4/T32 | screen_ising | 256 | 12.274153 | 0.005388 |
| B4/T32 | screen_ising | 512 | 12.207062 | 0.001103 |

来源：[S18]。S为burn16/spacing4的有限CTMC观测，不是物理周期或ESS；S256/S512缺匹配原FFN完整控制，不能补算对应联合交互项。这里的旧CTMC与新赢家保持/定点LUT分支不同。

### 6.3 下游任务：已有完整题集和固定子集

Qwen共39次配置评测，zero-shot；PIQA1838、ARC-E2376、HellaSwag固定1000题。以下为报告中的acc_norm，完整acc和逐seed请看[S19]；不在看结果后挑一个指标宣称无损。

| Qwen方案 | PIQA acc_norm % | ARC-E acc_norm % | HellaSwag1000 acc_norm % |
|---|---:|---:|---:|
| 本轮BF16 | 69.967 | 58.333 | 52.400 |
| FFN-only B4/T32 | 69.840 | 58.852 | 51.833 |
| FFN+Ising64 | 69.568 | 59.105 | 50.833 |
| FFN+Ising128 | 69.677 | 58.474 | 51.700 |
| FFN+Ising512 | 69.695 | 58.726 | 52.100 |

Llama2-7B共26次配置评测，PIQA1838、ARC-E2376、zero-shot、lm_eval0.4.8；各替换三seed。以下亦为acc_norm，完整acc、逐题oracle和标准差见[S20]。

| Llama2-7B方案 | PIQA acc_norm % | ARC-E acc_norm % |
|---|---:|---:|
| 本轮BF16 | 78.99891 | 74.66330 |
| FFN-only B4/T32/K32 | 78.99891 | 74.32660 |
| Attention-only S128 | 77.43925 | 73.83558 |
| joint S128 | 77.87450 | 73.58305 |
| joint S512 | 78.67247 | 74.06004 |

这些短题的候选可保留全部K，主要检验FFN/有限采样答题影响，不证明8K/更长筛选收益。Qwen与Llama分数及同名数据集不跨模型作为因果对照；DS-CIM的六任务均值也不能由上述三/两任务均值替代。

### 6.4 新Qwen3-4B：质量数据与Z1T派生指标，均为待审结果

| 任务/来源 | 匹配对照 | 替换方案结果 | 适用范围 |
|---|---|---|---|
| Attention-only完整WT2，PR199 | BF16 PPL11.538153；本项目纯SparQ10.797926 | SparQ+赢家保持S128：11.177429 ± 0.006594（样本SD） | 后训练Qwen3-4B、原FFN/投影/归一化保持；r32/k128/local32、burn32、三seed；299077目标、全36层单query，dense prefill |
| FFN-only完整WT2，PR207 | BF16 PPL11.537160；CE2.445573nats/token；3.528216bits/token | G64/B4 PPL14.883993±0.018381（样本SD），+29.0092%；CE2.700286、3.895689bits/token | 全36个FFN与窗口前缀替换；GU64、NL128、冻结风险四档；GU仍FP32恢复oracle，不能叫全链整数bittrue |

来源：[S21]/[S16]及[PR207的完整WT2结果说明](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/207)（本次API快照已保存）。两轮BF16控制不同，不能交叉拼接。Attention结果相对纯SparQ仍有约3.51%PPL增加；低于BF16不构成“采样本身提升模型”的证明。其理想K+V元素需求为dense的17.41%、纯SparQ的87.91%，是逻辑集合，不是物理DRAM流量或加速比。

Z1T映射报告还给出以下**原始稠密模型算术计数**，不是SC物理事件数：[S16]

| Qwen3-4B组成 | 唯一参数 | 2K时MAC/token | 8K时MAC/token |
|---|---:|---:|---:|
| 36层FFN | 2,689,597,440 | 2,689,597,440 | 2,689,597,440 |
| QKV/Wo投影 | 943,718,400 | 943,718,400 | 943,718,400 |
| 共享embedding/lm_head | 388,956,160 | 388,956,160 | 388,956,160 |
| QK/PV | 无独立权重参数 | 603,979,776 | 2,415,919,104 |
| 主要MAC合计 | 不适用 | 4,626,251,776 | 6,438,191,104 |
| 按2FLOPs/MAC等效 | 不适用 | 9.252504 GFLOPs | 12.876382 GFLOPs |

另有196096个Norm参数，总参数4,022,468,096。FFN参数占66.8644%，但主要矩阵MAC占比为2K时58.1377%、8K时41.7757%。这些比例不是时间、能量或面积占比。CE=ln(PPL)、bits/token=CE/ln2；真正bits/byte需要按原始字节另归一，本文没有计算BPB或训练scaling。

### 6.5 当前main整机条件时延

Qwen3-4B后训练**形状**、36层、B1、总上下文2048、一个decode token；不加载权重，不测PPL，不含prefill。默认共同调度100MHz、8MiB/64bank/64GB/s SRAM；数字512MAC/拍、SC8×64；以下明确选择准确Attention。

| FFN配置 | 默认DDR4 ms/token | HBM流水 ms/token |
|---|---:|---:|
| BF16数字 | 599.340 | 402.629 |
| W8数字、K64块尺度恢复 | 426.364 | 333.664 |
| 原SC8×64 | 509.471 | NR |
| SC8×64/R8局部部分和 | 503.639 | 438.038 |

来源：[S11]。这是共同条件下的时延/工作量对照，不是同质量/同面积最优ASIC结论；HBM功率参数占位，不能引用为有效HBM能耗。更快的资源/500MHz/局部端口候选分别看配置，不替代默认表。最新完整物理能耗/面积仍未闭合，`priced subtotal`不能改名“完整芯片能耗”。

已有真实GPU锚点由统一协议引用：RTX5090、Qwen0.5B/B1、SDPA/eager、固定真实token重放；2K decode窗口cache2048–2175约14.033ms/步、1.8832J/步。范围包含全部层与lm_head，不含CPU选词/tokenizer；是板卡测量，非墙插、非优化GPU下界，也不是自由生成请求。协议给本机原报告位置，Git中不据此新增原始payload：[S01] §9。不能拿它与不含lm_head/不同模型形状的ASIC局部估算直接相除。

### 6.6 模块PPA：main的T32单尺度矩阵

N64、M1、T32、真正signed INT8（含−128）、驻留权重合成激励；SS1.08V/125°C/100MHz。面积已raw×0.81。每帧一个64项点积；三seed合成活动均值。

| 计算核 | 等效面积mm² | 功率mW | 能量pJ/帧 | 周期/帧 |
|---|---:|---:|---:|---:|
| v1精确三级树 | 0.012504 | 0.4862 | 179.906 | 37 |
| v3精确位平面 | 0.018434 | 0.4300 | 150.512 | 35 |
| v1共享输入计数 | 0.016629 | 0.4626 | 185.040 | 40 |
| v3 OR4→popcount16→累计 | 0.010440 | 0.2912 | 101.932 | 35 |
| v1 INT8并行乘加 | 0.046210 | 1.1093 | 22.187 | 2 |
| v1 INT8位串行 | 0.015264 | 0.3880 | 38.797 | 10 |
| v3 OR4→16路时间计数→求和 | 0.031465 | 0.9957 | 348.483 | 35 |

来源：[S12]。OR4对相同事件精确参考的NRMSE约M1 0.4232、M8 0.4417；单独采样误差又是另一参考。M1优化OR4相对数字位串行能量2.627倍、时间3.5倍、面积小31.60%；M8每点积98.846pJ对32.767pJ，能量3.017倍。没有真实模型精度、RNG/比较器、权重存储/读口、输入量化、最终浮点恢复、CTS/SDF/SPEF等完整成本，不能借用§6.1 PPL。

### 6.7 待审PR209：同64路并行INT8与BF16补充

与§6.6不同，这里SC54为六幅值平面1..6、OR4/T32并去掉LSB；不是把§6.6 v3核改名。数字与SC匹配输入批次不代表输出质量相同。相同SS1.08V/125°C/100MHz，面积单次×0.81。

| 方案 / 工作节奏 | 面积mm² | 平均功率mW | pJ/N64完整帧 | 原生延迟/间隔 | 实际发帧 |
|---|---:|---:|---:|---|---|
| SC54 T32/OR4 | 0.005524070 | 0.198467 | 69.4633 | 封装帧间隔35拍 | 350ns |
| 64路INT8/32位结果，满速 | 0.028222798 | 2.126333 | 21.2633 | 1拍/1拍 | 10ns |
| 同一INT8，匹配SC发帧 | 0.028222798 | 0.114800 | 40.1800 | 原生仍1拍/1拍 | 350ns |
| 64路INT8/22位结果，满速 | 0.028153105 | 2.118333 | 21.1833 | 1拍/1拍 | 10ns |
| 同一22位INT8，匹配SC发帧 | 0.028153105 | 0.108933 | 38.1267 | 原生仍1拍/1拍 | 350ns |
| 另一资源点：四lane BF16/FP32，normal | 0.04491836 | 1.923333 | 577.0000 | N64帧间隔30拍 | 300ns |

来源：[S14]/[S15]。64路INT8和四lane BF16不是同物理并行度；因此最后一行只作独立资源点。SC54对32位INT8面积小5.109倍，各自满速功率低10.714倍，但同350ns完成工作率下SC能量仍为数字1.729倍。paced时钟仍自由运行100MHz，未宣称数字ICG最优；也没有新PPL/真实供数、存储、RNG、完整广播和时钟树成本。BF16标量存在hold负例；数字64路最终setup/hold通过不等于P&R/芯片签核。

## 7. 实际做比较时，应该使用哪一组数据

| 要支撑的主张 | 应选benchmark与论文 | 目前能直接引用的资料 | 还必须对齐 |
|---|---|---|---|
| 随机矩阵更省面积/能量 | B-MAT；DS-CIM、uGEMM、SASCHA、tubGEMM、FIGNA、Anda、AxCore；数字本工艺为主 | §6.6/6.7与各论文卡片 | 相同形状/位宽/误差、并行度、权重驻留、前端与恢复；宏TOPS/W只补充 |
| 替换整个FFN有价值 | B-FFN+B-LM/B-TASK；矩阵与非线性分开消融 | §6.1–6.4；P-DNN另列重训路线 | 真实g/u/z合同、SwiGLU依赖、完整FFN成本；旧FP32质量不继承当前整数核 |
| Ising优于数字归一化/采样 | B-SMX+B-SAMPLE；ITA/FSA/SoftGen/SANTA/SOT-Ising/ASCEND | §4、S08–S10、PR199局部与质量证据 | 数字必须算到索引/次数，Ising必须含阈值/RNG/仲裁；同误差、实际样本与V集合 |
| Attention减少访存且保持质量 | B-ATTN+B-LONG/B-LM；UniCAIM/SpAtten/SANTA/Kelle | §6.4质量和S08账本；S21逻辑集合 | GQA并集、真实burst、筛选/摘要/KV写与索引成本、长题有效保留率 |
| 整模型更快更省电 | B-REQ+B-PPA；OPAL/Kelle/AttAcc/NeuPIMs/CENT/PIM-GPT/MBA，GPU作外部部署参照 | §6.5、main配置及成本覆盖率 | 同模型/质量、B/长度/阶段、芯片数/内存、含lm_head与电源边界；完整PPA当前未闭合 |
| 原生p-bit重训模型有效 | B-SCALE+B-LM+B-PPA；Z1T及概率器件资料 | S16派生指标与Z1T卡片 | 统一文本/字节归一、上下文、训练预算和有限采样；重训与保留Qwen权重路线分开 |

### 7.1 每条比较记录应保存的字段

`论文/方案版本、对手版本、比较边界、模型/checkpoint/tokenizer、任务与split/ID、shot/提示/评分、输入输出长度、B、prefill/decode、W/A/KV/累加精度、尺度与舍入、采样S/T/K及预热/间隔、硬件资源与复用、PVT/频率、存储与外存配置、面积边界、功率窗口、能量分子/输出分母、实现阶段、来源页/表/commit、绝对值、倍率、误差条、缺失项。`

几个可直接使用的定义：[S01]

```text
PPL = exp(总NLL / 有效目标token数)
CE[nats/token] = 总NLL / 有效目标数
bits/token = CE / ln(2)                         # 不等于bits/byte
相对PPL变化 = PPL_new/PPL_ref - 1
准确率百分点变化 = score_new[%] - score_ref[%]

TTFT = 第一个输出时间 - 请求到达时间
TPOT = (最后输出时间 - 第一个输出时间)/(G-1)   # G>1
输出吞吐 = Σ输出token数 / 批次或服务测量时长
J/output-token = 对应测量边界总能量 / 对应输出数
E = Σ动作数×增量能量 + Σ状态功率×持续时间
EDP = E×T；AEDP = A×E×T
```

服务时间可重叠，模块busy时间不能直接相加成端到端时延。面积按实际物理实例计，不按复用层数乘；能量则按实际调用/状态时长计。MAC按1还是2ops、1b归一与完整任务MAC分列。文献PVT、工艺投影、综合、后布局和实测分开。

## 8. 明确的缺项与可恢复入口

### 8.1 现有调研尚不足以填精确数值的地方

- FIGNA/Anda/AxCore等在已有报告中保留机制和代表倍率，但没有逐模型全质量表；对应卡片的NR是“摘录不足”，并非断言原文没有。
- SANTA已有GPU性能/质量验证，但当前摘要未展开每个质量任务和分数；若选作正式主对照，应回到固定v2主表和附录逐项补表，不能自行填成WT2 PPL。
- UniCAIM的F1图没有精确标值，原调研没有目测补数；ASADI/3D-CIMlet所读主文未找到新质量数表。
- Li2024数字Softmax只有出版方索引表格线索，尚缺原PDF视觉核对和整行周期；ConSmax普通Softmax对手缺完整位宽/整行周期。不能将其小面积和另一篇的延迟组合。
- VQT-CiM（DAC2025，10.1109/DAC63849.2025.11133264）、HEIRS（DAC2024，10.1145/3649329.3657327）、DBC（DAC2025，10.1109/DAC63849.2025.11132851）在旧调研中尚缺可核完整任务/质量表，本文件只保留身份与补查项，不引用二手精度阈值。[S03]
- 当前main端到端完整物理PPA、当前FFN定点数制的整模型质量与全部外围成本仍未闭合；PR199/207/209的结果也不能仅因已上传就写成已合并或已验收。

### 8.2 资料与复核

同目录提供[逐篇结构化目录](PAPER_CATALOG.json)、[来源哈希索引](SOURCE_MANIFEST.json)及[核验记录](VALIDATION.json)。只公开既有GitHub资料的索引、本文与必要元数据；本机GitHub读取/生成辅助脚本、Zotero状态与恢复待办不属于此公开文档包。

本次按用户要求以独立分支和PR交付，关联既有Issue #98，原负责人及原验收状态保持。没有新训练、模型评测、TLM或EDA；不自动合并。发布状态与后续接续见[交接](../../work/amlink1219/98/benchmark_inventory_20261029/HANDOFF.md)。

工具论文校准误差另见[S05]/[S06]，不能混入新架构胜负表：LLMCompass的4.1%是其LLM时延平均误差，Accelergy的5%对应特定Eyeriss能量，均不自动成为我们p-bit组件的误差保证。

### 8.3 文献库维护说明

本机文献库核对和未匹配项恢复待办保留在本地，尚未完成的入库不因文档上传而计作完成。公开文档不包含个人库条目列表、数据库、配置、附件或待办JSON。

## 9. 固定版本来源索引

- **S01**：[统一benchmark、质量与PPA协议，Issue98/PR100及频率补充](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/d6d33995754fcdcea99286e4ce43f91647aa231a/architecture_tlm/benchmark_protocol_20261022/README_ZH.md)。
- **S02**：[论文模型、任务、指标逐篇对照，Issue51/PR56](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/d6d33995754fcdcea99286e4ce43f91647aa231a/architecture_tlm/LLM_PAPER_TASK_METRIC_MAP_ZH_20261019.md)。
- **S03**：[新器件/随机LLM质量数值及容差核查](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/d6d33995754fcdcea99286e4ce43f91647aa231a/architecture_tlm/EMERGING_LLM_QUALITY_METRICS_ZH_20261019.md)。
- **S04**：[17项原文阅读与机制总结](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/d6d33995754fcdcea99286e4ce43f91647aa231a/architecture_tlm/PBIT_LLM_READING_SYNTHESIS_ZH_20261018.md)。
- **S05**：[33项论文/工具的逐篇证据矩阵，Issue187/PR189](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/787489192ebfcdb61ad72edde406818f450aa3dc/architecture_tlm/simulator_survey_20261025/EVIDENCE.md)。
- **S06**：[LLM模拟器与PPA证据综述](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/787489192ebfcdb61ad72edde406818f450aa3dc/architecture_tlm/simulator_survey_20261025/README_ZH.md)。
- **S07**：[DS-CIM/uGEMM/SASCHA/tubGEMM与本项目随机矩阵指标审计](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/787489192ebfcdb61ad72edde406818f450aa3dc/architecture_tlm/simulator_survey_20261025/STOCHASTIC_METRIC_AUDIT_ZH.md)。
- **S08**：[数字在线Attention参考及512/2048/8192账本](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/d6d33995754fcdcea99286e4ce43f91647aa231a/architecture_tlm/digital_attention_reference/README_ZH.md)。
- **S09**：[普通数字Softmax周期、面积和开源实现调研，PR199未合并](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/c7de50647d697a837cc12340b8488746061ab167/architecture_tlm/attention_compare_20261027/SOFTMAX_DIGITAL_SURVEY_ZH_20261028.md)。
- **S10**：[数字IID/systematic与Ising的统一采样输出边界，PR199未合并](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/01270f9c50d9475017603bf2ee7148193280ded7/architecture_tlm/attention_compare_20261027/DIGITAL_SAMPLING_BASELINE_ZH_20261029.md)。
- **S11**：[当前main整机基线与可选配置](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/787489192ebfcdb61ad72edde406818f450aa3dc/architecture_tlm/BASELINE_ZH.md)。
- **S12**：[T32单尺度矩阵局部PPA与误差，PR205已合并](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/787489192ebfcdb61ad72edde406818f450aa3dc/architecture_tlm/matrix_single_scale_20261028/results/REPORT_ZH.md)。
- **S13**：[BF16数字基线文献复核，PR209未合并](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/9228b08ca20230600ac41eba479f14228d19b5be/architecture_tlm/bf16_baseline_20261028/LITERATURE_RECHECK_ZH.md)。
- **S14**：[同64路INT8数字核对照，PR209未合并](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/9228b08ca20230600ac41eba479f14228d19b5be/architecture_tlm/int8_parallel64_20261028/results/REPORT_ZH.md)。
- **S15**：[本工艺BF16/FP32核PPA，PR209未合并](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/9228b08ca20230600ac41eba479f14228d19b5be/architecture_tlm/bf16_ppa_20261028/results/REPORT_ZH.md)。
- **S16**：[Z1T指标映射及Qwen3-4B参数/MAC/CE派生，PR207未合并](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/104a2e4931782a698388abcb38e71ae059d73636/qwen3/results/group_shared_20261028/Z1T_METRIC_MAP_ZH.md)。
- **S17**：[Qwen2.5-0.5B固定W8/多档/分层FFN完整WT2](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/d6d33995754fcdcea99286e4ce43f91647aa231a/qwen/results/multiscale_stratified_20261019/RESULTS_ZH.md)。
- **S18**：[Qwen2.5-0.5B联合FFN/Attention完整WT2](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/d6d33995754fcdcea99286e4ce43f91647aa231a/qwen/results/joint_full_wt2_20261020/RESULTS_ZH.md)。
- **S19**：[Qwen39项任务准确率结果](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/d6d33995754fcdcea99286e4ce43f91647aa231a/qwen/results/task_accuracy_20261019/RESULTS_ZH.md)。
- **S20**：[Llama2-7B26项任务最终核验](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/d6d33995754fcdcea99286e4ce43f91647aa231a/llama2/results/task_accuracy_20261020/FINAL_RESULTS_20261022_ZH.md)。
- **S21**：[Qwen3-4B SparQ+Ising Attention-only完整WT2，PR199未合并](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/c7de50647d697a837cc12340b8488746061ab167/experiments/sparq_ising_20261028/results/REPORT_ZH.md)。
- **S22**：[统一数字电路仿真台账](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/787489192ebfcdb61ad72edde406818f450aa3dc/digital_circuit_simulation_registry/README_ZH.md)。
- **S23**：[ASIC系统、带宽及比较边界补充](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/787489192ebfcdb61ad72edde406818f450aa3dc/architecture_tlm/unified_v6/ASIC_PAPER_COMPARISON_ZH.md)。
- **S24**：[prefill工作负载与边界专题](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/d6d33995754fcdcea99286e4ce43f91647aa231a/architecture_tlm/benchmark_protocol_20261022/PREFILL_ANALYSIS_ZH.md)。
- **S25**：[Qwen2.5-0.5B原始BF16基线协议](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/787489192ebfcdb61ad72edde406818f450aa3dc/baselines/BASELINES.md)。

下列参考式链接用于正文表格，均与上述固定版本一致。

[S01]: https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/d6d33995754fcdcea99286e4ce43f91647aa231a/architecture_tlm/benchmark_protocol_20261022/README_ZH.md
[S02]: https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/d6d33995754fcdcea99286e4ce43f91647aa231a/architecture_tlm/LLM_PAPER_TASK_METRIC_MAP_ZH_20261019.md
[S03]: https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/d6d33995754fcdcea99286e4ce43f91647aa231a/architecture_tlm/EMERGING_LLM_QUALITY_METRICS_ZH_20261019.md
[S04]: https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/d6d33995754fcdcea99286e4ce43f91647aa231a/architecture_tlm/PBIT_LLM_READING_SYNTHESIS_ZH_20261018.md
[S05]: https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/787489192ebfcdb61ad72edde406818f450aa3dc/architecture_tlm/simulator_survey_20261025/EVIDENCE.md
[S06]: https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/787489192ebfcdb61ad72edde406818f450aa3dc/architecture_tlm/simulator_survey_20261025/README_ZH.md
[S07]: https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/787489192ebfcdb61ad72edde406818f450aa3dc/architecture_tlm/simulator_survey_20261025/STOCHASTIC_METRIC_AUDIT_ZH.md
[S08]: https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/d6d33995754fcdcea99286e4ce43f91647aa231a/architecture_tlm/digital_attention_reference/README_ZH.md
[S09]: https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/c7de50647d697a837cc12340b8488746061ab167/architecture_tlm/attention_compare_20261027/SOFTMAX_DIGITAL_SURVEY_ZH_20261028.md
[S10]: https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/01270f9c50d9475017603bf2ee7148193280ded7/architecture_tlm/attention_compare_20261027/DIGITAL_SAMPLING_BASELINE_ZH_20261029.md
[S11]: https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/787489192ebfcdb61ad72edde406818f450aa3dc/architecture_tlm/BASELINE_ZH.md
[S12]: https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/787489192ebfcdb61ad72edde406818f450aa3dc/architecture_tlm/matrix_single_scale_20261028/results/REPORT_ZH.md
[S13]: https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/9228b08ca20230600ac41eba479f14228d19b5be/architecture_tlm/bf16_baseline_20261028/LITERATURE_RECHECK_ZH.md
[S14]: https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/9228b08ca20230600ac41eba479f14228d19b5be/architecture_tlm/int8_parallel64_20261028/results/REPORT_ZH.md
[S15]: https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/9228b08ca20230600ac41eba479f14228d19b5be/architecture_tlm/bf16_ppa_20261028/results/REPORT_ZH.md
[S16]: https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/104a2e4931782a698388abcb38e71ae059d73636/qwen3/results/group_shared_20261028/Z1T_METRIC_MAP_ZH.md
[S17]: https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/d6d33995754fcdcea99286e4ce43f91647aa231a/qwen/results/multiscale_stratified_20261019/RESULTS_ZH.md
[S18]: https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/d6d33995754fcdcea99286e4ce43f91647aa231a/qwen/results/joint_full_wt2_20261020/RESULTS_ZH.md
[S19]: https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/d6d33995754fcdcea99286e4ce43f91647aa231a/qwen/results/task_accuracy_20261019/RESULTS_ZH.md
[S20]: https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/d6d33995754fcdcea99286e4ce43f91647aa231a/llama2/results/task_accuracy_20261020/FINAL_RESULTS_20261022_ZH.md
[S21]: https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/c7de50647d697a837cc12340b8488746061ab167/experiments/sparq_ising_20261028/results/REPORT_ZH.md
[S22]: https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/787489192ebfcdb61ad72edde406818f450aa3dc/digital_circuit_simulation_registry/README_ZH.md
[S23]: https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/787489192ebfcdb61ad72edde406818f450aa3dc/architecture_tlm/unified_v6/ASIC_PAPER_COMPARISON_ZH.md
[S24]: https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/d6d33995754fcdcea99286e4ce43f91647aa231a/architecture_tlm/benchmark_protocol_20261022/PREFILL_ANALYSIS_ZH.md
[S25]: https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/787489192ebfcdb61ad72edde406818f450aa3dc/baselines/BASELINES.md
