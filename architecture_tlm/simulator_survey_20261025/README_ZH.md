# LLM架构模拟器与PPA证据综述

核查日期：2026-10-25。负责人：rayggxia。任务：[Issue187](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/187)。文档基线：main @ 5273e5d9fdae811a714f1a278fee6e776c5675af。本报告只读调研，没有运行模型、TLM、RTL、EDA或新的PPA实验。

**结论：我们需要的是经过分层验证的p-bit/数字混合ASIC系统模型。保留现有unified_v6，结合已接入的映射工具和DRAM后端，再补齐新模块的可实现时序、活动能量、随机统计及端到端验证，比直接换一个大型模拟器更合适。** TLM可以作为主干；关键在它保留了什么依赖和资源约束，以及这些参数如何得到验证。

阅读入口：

- [保守调度审计](CONSERVATIVE_SCHEDULING_AUDIT_ZH.md)：核查PR192固定版本的资源预约、DMA/SRAM屏障、数字/SC优化不对称及12项封存配置；区分正确性检查与架构政策，不把代表性工具对照当作多数统计。
- [HLS与周期数专题](HLS_LATENCY_ZH.md)：给定功能和工艺库后还缺什么、五篇实现实例、Latency/II/STA区别及本项目局部HLS试点；对照最新PR190。原33条矩阵保持不变。
- [逐篇证据与工艺/时钟/结果边界](EVIDENCE.md)：33个论文/工具条目，包含18个硬件方案、1个GPU软件方案、9个映射/加速器工具条目、4个DRAM工具/校准条目、1个集成验证研究。
- [可筛选CSV](EVIDENCE.csv) / [结构化JSON](EVIDENCE.json)：相同记录，逐项保留出处、章节、访问限制。
- [本项目模拟器需求和验收建议](REQUIREMENTS_ZH.md)：哪些能力必须有、哪些可简化、怎样校准。
- [来源与本地PDF指纹](SOURCES.json)：只保存索引与SHA，不上传用户论文PDF。

## 1. 这次调查能回答什么

这是一组围绕“如何证明新架构有效”挑选的代表性证据，不是对所有会议论文的全量普查。以DAC、HPCA、MICRO、ASPLOS、ISCA为主要来源，补充DATE、ISLPED、ICCAD、IEEE期刊、实际器件工作及2026公开更新。包含少量BERT/ViT/RetNet研究作为方法参照，不能把它们全部称为生成式LLM实验。

每篇分别核查：

1. **模拟对象**：新ASIC、可配置NPU、商用GPU、GPU+PIM、CIM宏，还是器件。
2. **作者的贡献和评估范围**：单模块、线性层、attention、完整模型、请求或服务系统。
3. **时序模型**：分析公式、算子/事件图、tile级、DRAM命令级、RTL，及其组合。
4. **物理成本来源**：工艺库综合、活动功耗、布局后、SPICE、存储模型、文献借值、工艺投影或真实测量。
5. **验证与可复现性**：拿什么当参考、验证了哪一部分、误差指标、代码与版本。
6. **结果边界**：质量、速度、能量、面积的条件是否相同；哪些成本缺失。

NR仅表示本次核查的原文范围没有明确披露。未取得最终全文、未核补充材料、只核代码入口，另行写明。**没有公开细节不等于作者没有做；有开源代码也不等于模型已经得到硅片校准。**

## 2. ASIC和XPU不是互斥分类

ASIC描述“为特定用途设计的芯片”，NPU描述功能，GPU描述一种处理器体系结构。研究中的新NPU通常就是ASIC；XPU只是泛称。应分成两个字段：**实现形态**和**计算架构/角色**。

例如：

| 论文/工具 | 被评估的目标 | 容易误读的地方 |
|---|---|---|
| Anda | 新GEMM ASIC与重实现的FP-FP空间阵列 | GPU-like不是在NVIDIA GPU上实测 |
| ONNXim/PyTorchSim | 多核或可编程NPU模型 | 运行模拟器的EPYC/x86不是被设计的目标硬件 |
| SANTA | 现有RTX6000Ada上的软件kernel | 随机算法有效不等于已实现p-bit ASIC |
| NeuPIMs/AttAcc | NPU或GPU加HBM-PIM | NPU逻辑、DRAM阵列、外围可以有不同工艺/时钟 |
| IBM PCM ALBERT | 真实PCM线性层芯片加软件外围 | 部分实测不等于整模型在自主芯片上运行 |
| SOT-Ising SoftMax | 器件实测加分布/功能仿真 | 概率核心能耗不含完整输入准备与读出 |

对应出处见各条目：[Anda](EVIDENCE.md#anda)、[ONNXim](EVIDENCE.md#onnxim)、[SANTA](EVIDENCE.md#santa)、[PCM ALBERT](EVIDENCE.md#pcmalbert)、[Ising](EVIDENCE.md#isingsot)。

## 3. 论文实际采用哪些仿真路线

### 3.1 新数字ASIC：自研时序模型加局部硬件成本

FIGNA采用SystemC统计时延/访问，逻辑用DC和PrimePower，存储用宏参数，HBM采用固定pJ/bit。Anda采用自研周期模型，并从综合网表VCD估功耗。AxCore基于DNNWeaver并发布artifact。SpAtten用Verilator计算周期、Ramulator产生DRAM活动。它们说明自研模型是可以成为研究方法的，但各自声明覆盖的范围不同。

其中FIGNA、Anda的主要效率结果是**GEMM**；FIGNA主要面积效率还只含逻辑。不能用其倍数证明全模型加速。AxCore的充分带宽假设也不能移植到受DDR4限制的系统而不重算。[FIGNA](EVIDENCE.md#figna)、[Anda](EVIDENCE.md#anda)、[AxCore](EVIDENCE.md#axcore)、[SpAtten](EVIDENCE.md#spatten)。

### 3.2 存储架构：分析或行为模型也有发表先例

Kelle用逻辑综合、Destiny/CACTI及吞吐/带宽公式；MBA明确使用行为级计算图模拟器，并将45nm文献PE成本投影到7nm。MBA研究的重点是大容量IGZO eDRAM、KV优先映射和缓冲策略，其5.99×速度收益来自这样的系统模型。

这类方法适合快速研究容量、带宽和数据复用，但报告的可信范围取决于是否建模了相关争用及依赖。**不能因为某篇论文没详细模拟一个成本，就认为我们的方案也可以忽略；如果我们的收益恰好依赖它，就必须补。** [Kelle](EVIDENCE.md#kelle)、[MBA](EVIDENCE.md#mba)。

### 3.3 PIM：成熟存储后端加自定义计算/互连

NeuPIMs为ONNXim+修改DRAMsim3；AttAcc修改Ramulator；CENT修改Ramulator2，但CXL通信仍用解析模型；PIM-GPT是事件驱动周期模型。这是与我们最接近的方法路线：成熟后端负责已知存储约束，新模块和调度依赖由研究者定义。

不过PIM能量仍包含强假设：NeuPIMs计算电流按读操作4倍，CENT按3倍，PIM-GPT部分普通DRAM时序/电流借其他型号。它们有明确来源和建模过程，但不等于真实新PIM芯片功耗。[NeuPIMs](EVIDENCE.md#neupims)、[AttAcc](EVIDENCE.md#attacc)、[CENT](EVIDENCE.md#cent)、[PIM-GPT](EVIDENCE.md#pimgpt)。

### 3.4 新器件和随机计算：局部证据往往较强，系统覆盖需要另看

DS-CIM有定制宏与布局后仿真，LLM部分是误差注入；峰值效率T64、最佳质量T256，不能拼成同一工作点。UniCAIM明确配置ADC数量及局部电路时延，但外部DRAM与整机调度证据不足。ASCEND的end-to-end主要是随机计算路径和网络训练，主要ADP比较属于GELU/softmax模块，并另报加速器面积。

SOT-Ising SoftMax原文§IV用10^9个独立副本的ensemble来观察分布演化；32µs达到文中FP16比较线，不能直接视为一个物理实例在32µs内完成有限样本高精度读出。其0.26pJ/bit还是核心投影值，明确不含输入准备和输出读出。我们应学习其器件补偿和分布验证，同时单独建模有限采样、相关性及外围。[DS-CIM](EVIDENCE.md#dscim)、[UniCAIM](EVIDENCE.md#unicaim)、[ASCEND](EVIDENCE.md#ascend)、[Ising](EVIDENCE.md#isingsot)。

## 4. 工艺、频率和物理实现并没有统一模板

| 代表工作 | 工艺来源 | 工作频率/时间 | 物理证据层级 |
|---|---|---|---|
| FIGNA | 28nm | 100MHz | 综合+功耗模型 |
| Anda | 16nm、0.8V | 285MHz | 综合网表VCD活动功耗 |
| AxCore | TSMC28nm | 1GHz | RTL综合+架构模型 |
| HSA | TSMC28nm，表内0.81V工作点 | 500MHz | HLS、综合、P&R、后布局 |
| SpAtten | 40nm逻辑，部分45nm softmax文献成本 | 1GHz | RTL周期+综合+引用值 |
| Kelle | 45nm逻辑、65nm存储@105°C | 1GHz | 综合+存储模型 |
| MBA | 目标7nm，PE由45nm缩放 | 500MHz PE | 行为模型+文献/技术投影 |
| AttAcc | ASAP7逻辑及另折算的DRAM逻辑 | GEMV666MHz、softmax1.3GHz | 预测库综合+混合模型 |
| CENT | 28nm控制器综合、投影7nm；GDDR6另有节点 | 目标2GHz控制器 | 综合+工艺投影 |
| DS-CIM | 40nm、0.7–1.2V | 统一频率未核得 | 宏布局后 |
| PCM ALBERT | 14nm真实PCM芯片 | 统一系统频率未核得 | 实测宏+模拟外围 |
| SOT-Ising | 实验SOT-MTJ器件 | 异步演化时间 | 器件实测+分布仿真 |

表内数值的来源、范围及未披露字段见[EVIDENCE](EVIDENCE.md)。**这张表不能用来排名性能。**

没有“全部折到7nm就公平”的统一做法。节点转换不会自动重新完成STA、布线、SRAM布局、DRAM器件、接口或热设计；频率也不能随节点比例任意提高。Timeloop展示，同一架构从65nm迁到16nm后，重搜映射最高还能节能22%，说明技术成本变化会改变调度选择。[原文§VIII-B](https://people.csail.mit.edu/anurag_m/papers/2019.timeloop.ispass.pdf)。

对本项目建议：

- 主结论采用**同一技术来源/PVT、同质量、同系统资源预算**的数字ASIC与p-bit方案。
- 商用GPU作为实际部署参照，完整报告设备、精度、软件栈、batch、长度、功率边界；不把差异全部归功于随机计算。
- 若列工艺归一化结果，作为附加敏感性分析，保留原始值、缩放对象与公式，不将其写成该节点实现结果。
- 分别登记核心、SRAM、DRAM/PHY、异步p-bit时基。固定频率的周期数可供复算；跨域整机首先用秒/纳秒作统一事件时间。

## 5. 模拟器的“误差很小”究竟指什么

| 工具 | 文献验证结果 | 不能据此声称 |
|---|---|---|
| ONNXim | Gemmini 8×8 GEMM/Conv核误差0.23%，排除DRAM/NoC | 整个LLM时延误差0.23% |
| LLMCompass | 平均LLM时延4.1%；prefill0.69%、decode7.5% | 每个算子、每个模型都4.1%；已有能耗模型 |
| PyTorchSim | TPUv3型单核多算子/模型runtime MAE11.5% | 所有LLM或新p-bit硬件都是11.5% |
| Accelergy | 65nm Eyeriss总能量在P&R参考5%误差以内 | 新接一个p-bit组件自动获得5%精度 |
| DRAMSys | 对特定RTL调整后平均带宽1.2%、响应1.0%；逐事务6.12% | 所有控制器、所有接口逐事务1%误差 |
| Accel-Sim 2.0预印本 | H100总体周期MAPE13.5%，部分LLM推理约20% | 所有GPU LLM可用一个统一平均误差 |

出处与版本见相应[EVIDENCE条目](EVIDENCE.md)。误差至少需要同时写**对象、参考、指标、输入集合、配置和版本**。验证算法输出，只能证明功能；验证DRAM命令合法，只能证明协议；回归测试通过，只能证明所测行为与期望一致。这几项均不能单独证明真实硬件性能。

2026一篇模拟器集成预印本进一步说明：即使后端用Ramulator2/DRAMsim3/DRAMSys，接口中的时间域或响应语义错误仍会使应用“看到”的内存性能偏离后端。其修复后多数STREAM带宽误差低于5%，pointer-chase仍低估15–18%。我们应借鉴三视角核对方法，而不把预印本结果当通用误差保证。[原文§II-B/IV/VI](https://arxiv.org/html/2610.15873v1)。

## 6. DRAM功耗需要单独做成一条证据链

文献中至少有三种路线：

| 路线 | 代表 | 能回答什么 | 主要缺口 |
|---|---|---|---|
| 字节数×pJ/bit或pJ/Byte | FIGNA、Anda、MBA、HSA | 初期工作量/能量估计，便于DSE | 行命中、后台、刷新、稀疏放大、空闲状态可能不足 |
| 命令/状态×电流或事件能量 | SpAtten、NeuPIMs、CENT、PIM-GPT | 随访问序列和运行时间变化的能耗 | 具体器件电流、PIM额外计算、PHY/控制器仍需来源 |
| 实测校准的命令/数据模型 | VAMPIRE等 | 检验电流、数据模式和结构变化 | 校准不能跨DDR代际/型号无条件迁移 |

推荐继续使用DRAMSys产生合法且带时间的命令/状态，DRAMPower转换能量。两者职责不同：DRAMPower本身不检查命令时序合法性。6.3.1接口区分core与interface，RD/WR电流的I/O需另外处理；其interface结果也不能冒充整个控制器和PHY宏成本。[官方说明](https://github.com/tukl-msd/DRAMPower)。

能量账本建议写成：

```text
E_system =
  Σ模块动作数 × 对应PVT/位宽/活动条件的动作能量
  + Σ各运行状态功率 × 该状态持续时间
  + DRAM core能量
  + 实际建模边界内的DRAM interface / PHY / controller能量
```

避免将已经含时钟/漏电的模块功耗再重复加一次；避免只乘总字节却声称已计刷新/后台。必须保存bank/rank/channel单位、burst、数据率、IDD、电压、温度、功耗状态、I/O配置和时间窗。VAMPIRE在50条DDR3L模块上的6.8%误差体现实测校准价值，但不能搬到我们的DDR4；同文旧DRAMPower的32.4%也不能当6.3.1误差。[作者论文](https://ghose.cs.illinois.edu/papers/18sigmetrics_vampire.pdf)。

## 7. 对现有unified_v6的判断

本次对照main的统一入口，以及[PR183](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/183) head **0341b4acde1e0afd7decf4a48b037e6b376343d8**的结果文档；PR183在核查时开放待审，未合并。不是将其分支状态当main。

现有模型已经能研究存储配置、跨组预取、阵列规模与条件性能趋势。不能再称为“只算操作数、没有真实DRAM”。但还不能据此声称完整p-bit芯片已比优化数字ASIC/GPU更快、更省电。

| 目前证据 | 正确解释 | 投稿前仍需补 |
|---|---|---|
| DDR4双64-bit通道；DRAMSys命令时序 | 已有真实后端模拟，不是固定16GB/s Link | 前端/后端因果性及代表轨迹独立对照 |
| 8MiB SRAM、55nm SS宏、80MHz；核心100MHz | 宏级容量/部分成本已有依据 | fabric、CDC、接收/响应缓存、控制的实现成本 |
| 8/16/32/64阵列约516.98/468.98/462.11/438.48ms-token | Qwen3-4B形状、B1、2K上下文、一个decode步的条件硬件时间 | 同质量真实激活、多个上下文及完整请求 |
| 数字W8约432.20ms-token | 512MAC/拍宏假设下的同外存参考 | 优化后的数字数据流、同总资源/同面积比较 |
| DRAMPower core能量及负ACT诊断已保留 | 未校准的模型输出；非芯片能耗测量 | 自洽电流、I/O/PHY/控制器、状态与敏感性 |
| 全芯片能量/面积保持null | 正确保留未知成本 | 新FFN/随机源/转换/本地权重保持等完整表征 |

数值只引用PR183对应文档，不是本轮重跑。该分支无权重/语料输入，因此时延与历史PPL尚不能自动拼为同一实验。任意提高配置频率不能替代物理可实现性核查。

已有[Issue186](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/186)负责共同tile生命周期、有界scatter-gather、成熟调度借鉴、数字/概率同资源decode及小规模搜索。本调研**只定义证据与验收要求**，不重复该任务的实现，也不建议另建平行v7。

## 8. 应该保留、接入和补写哪些东西

| 层 | 推荐 | 采用原因 | 仍由我们负责 |
|---|---|---|---|
| 数值功能/质量 | 现有PyTorch路径 | 可用真实Instruct/后训练模型评PPL、任务与多seed | 位精确边界、相关性、有限采样、质量协议 |
| 映射搜索 | 继续既有ZigZag；必要时Timeloop对照 | 同资源下搜索tiling/复用和数字基线 | 新随机算子循环/资源模型，候选合法性 |
| 系统调度 | 保留unified_v6，接续Issue186 | 可表达随机服务、依赖和异构模块 | 有限队列、回压、时钟、仲裁、尾波等 |
| 内存 | DRAMSys+DRAMPower，宏级SRAM表 | 命令级时序和状态能量已有工具 | 配置/接口校准、DRAM功耗边界、CDC/fabric |
| 独立验证 | ONNXim的小型匹配数字/访存探针；新块RTL | 第二实现有助发现TLM自洽但错误的问题 | 对齐资源和调度，解释差异；不能机械要求结果相等 |
| 物理成本 | RTL/DC/STA+活动功耗；关键块P&R；器件SPICE/实测 | 对应我们的新硬件贡献 | 共享RNG、分发、读出、非线性、转换和局部互连 |
| 能量组合 | 现有账本可接Accelergy格式/插件 | 透明组合动作和状态能量 | 正确的组件边界和工艺成本，不必为工具而重写 |
| GPU参照 | 真实GPU测量；必要时Accel-Sim | 评部署差异或GPU微架构 | 功率边界、软件栈、相同工作负载 |
| 编译器/指令扩展 | 仅当论文贡献需要时引入PyTorchSim | 功能+编译+TOG时序链完整 | 新指令语义与后端，迁移工作明显更多 |

**最小可信系统模型不要求全部LLM门级仿真，但要求主要性能收益能在其所依赖的层级得到独立证据。** 如果主张随机源面积/功耗节省，就验证其实现；如果主张稀疏KV减少访存，就输出真实物理突发和延迟；如果主张端到端优于数字，就补齐同质量和公平系统预算。具体接口与检查项见[REQUIREMENTS_ZH](REQUIREMENTS_ZH.md)。

## 9. 投稿时建议至少提供的图表

1. 系统框图与模块边界：工艺、频率、容量/端口、队列、位宽、PVT来源。
2. 数值质量表：同版本Instruct参考、FFN/Attention/联合替换，多seed，PPL和任务分数分别报告。
3. 同预算资源曲线：数字和p-bit各自优化后的时延/能量/面积Pareto，并区分已知与估计成本。
4. prefill/decode分图：TTFT、平均/稳态TPOT、E2E请求时延、J/output-token；batch与输入输出长度完整。
5. 访存和等待分解：数学载荷、物理字节、重读/突发放大、SRAM bank冲突、DRAM排队、RNG等待、有效计算。
6. 消融：量化、随机计算、筛选、V采样、RNG共享、映射/预取，各自贡献分开。
7. 验证图：TLM对RTL/独立参考，平均与尾部误差、偏差最大的案例和原因。
8. 敏感性/不确定性：随机样本速率/相关性、读出成本、SRAM带宽、DRAM电流、上下文长度和模型规模。

这些是本报告基于证据提出的验收建议，不是DAC/四会统一规定的数值门槛，也没有承诺某个配置能达到投稿性能。质量容差和资源预算需在研究结论形成前固定，不事后只挑有利点。

## 10. 优先阅读与尚未解决的来源限制

优先读 **Accelergy、DRAMSys、SpAtten、Anda、AxCore、AttAcc/CENT、PyTorchSim** 的方法与评估章节，分别学习成本组合、TLM验证、稀疏访存、活动功耗、artifact、异构内存、多层功能/时序接口。MBA、DS-CIM、ASCEND和SOT-Ising适合用于识别“强局部证据”和“完整系统证明”的距离。

仍需谨慎的来源：ZigZag精确误差数字来自早期稿；X-Former方法用作者预印本；PIM-GPT独立correction页未取得；IBM完整补充材料未逐项核完；部分论文未报告频率/PVT/外存模型。2026 Accel-Sim/ASTRA-sim等更新标为预印本，不伪称新的正式会议结论。

本轮没有穷尽全部DAC新器件论文，也未将旧调研中只有摘要或二手数字的工作强行填入完整矩阵。后续扩展应继续遵循同一字段和原文证据规则，不为了扩大篇数推测参数。
