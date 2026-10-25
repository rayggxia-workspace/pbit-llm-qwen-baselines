# 给定功能与工艺库，怎样确定周期数：HLS是否适合本项目

核查：2026-10-25；Issue187 / PR189的专题补充。依据原论文评估章节、工具官方资料，以及只读PR190@ee21c0ce9a14662aad98abbda8277f8af37365b8。没有运行HLS、RTL、EDA或新的模型实验。下文的试点方案是研究建议，尚未实施。

**建议局部引入ASIC HLS，优先试验“桶归约—定点系数恢复—宽位部分和累加”，保留现有unified_v6。论文需要可实现的时序和成本证据；HLS是获得证据的一条路线，没有证据表明必须使用HLS才能发表。** 已有RTL能完成闭环的模块无需重写。

## 1. 功能和工艺库为什么还不能确定几拍

函数定义了输入输出关系；工艺库给出单元在特定PVT和负载下的延迟/面积/功耗模型。两者之间还缺少微架构：

- 每拍处理多少元素，多少乘法器/加法器并行，哪些资源复用；
- 数据位宽、舍入、饱和和中间结果范围；
- 目标时钟、uncertainty、I/O延迟与负载，以及流水寄存器位置；
- SRAM端口、bank和读延迟、FIFO容量、随机源供给速率；
- 输入输出握手、循环依赖、冲突、反压、跨时钟域与复位行为。

以64个数求和为例：平衡二叉树有6级加法逻辑，**6级逻辑不等于6个时钟周期**。能否一拍跨多级必须看具体位宽、负载、布线及STA；也可以插寄存器形成多级流水，或复用少数加法器执行较多拍。算法相同而周期、面积和吞吐均不同。

普通RTL综合/DC读取已经描述了寄存器与状态转移的RTL，主要回答“这个结构能否满足指定时钟、成本多少”。不能指望它自动把任意一拍行为改成任意拍协议；重定时/流水优化也受工具、约束和等价关系限制。组合路径超时后，把延迟除以时钟向上取整，不能代替实际插入流水寄存器并验证接口。

HLS位于这两者之间：对**可综合**C++/SystemC，结合目标技术、资源和时钟约束，完成操作调度、资源绑定并生成RTL。PyTorch代码、普通Python TLM、任意SystemC事务代码不等于可直接综合的输入。官方示例也要求设计者描述计算、访存与通道，而不是仅提交数学公式。[Catapult](https://www.siemens.com/en-us/products/ic/catapult-high-level-synthesis/hls/)；[Stratus](https://www.cadence.com/en_US/home/tools/digital-design-and-signoff/synthesis/stratus-high-level-synthesis.html)；[ESP示例](https://www.esp.cs.columbia.edu/docs/mentor_systemc_acc/mentor_systemc_acc-guide/)。

## 2. 别人实际上怎样做

下表是有针对性的实例，不是HLS使用率统计。未写HLS的论文不推断其私有流程是否间接用过HLS。

| 工作 | 实现与周期证据 | 工艺/频率 | 对我们的意义与边界 |
|---|---|---|---|
| **HSA，ISLPED 2025** | SystemC→Catapult HLS→DC（加入clock gating）→Innovus→VCS/PrimeTime后布局评估 | TSMC 28nm，500MHz | 明确的ASIC HLS例子；作者仍自行设计混合阵列、数据流、RMSNorm/RoPE。主模型RetNet 1.3B，不能视为Qwen/softmax完整硬件模板 |
| **FSGen，DAC 2026** | Chisel生成RTL；DC综合、VCS门级仿真、PrimeTime/PTPX；自建周期级模型提供活动统计和早期功耗估计 | TSMC 40nm；探索上限1GHz，Table 1候选实际列712–823MHz | 用参数化RTL生成器探索架构，而非通用C++ HLS；§7.1没有声明完成布局布线，不将其写成后布局结果 |
| **SpAtten，HPCA 2021** | SpinalHDL→RTL；Verilator跑应用得到周期，Ramulator模拟HBM；Genus估逻辑成本 | TSMC 40nm，1GHz配置 | 可用RTL直接校准筛选/Attention；Softmax部分面积能量另借45nm FMA/FPU数据，不能把全部成本都称本工艺RTL实测 |
| **Anda，HPCA 2025** | SystemVerilog→Genus；综合网表VCD估功耗，自建周期级模拟器对照功能仿真 | 16nm，0.8V，285MHz | RTL与快速系统模型结合；主要评估FP-INT GEMM，未给出整LLM周期误差百分比，未声明HLS |
| **HLSTransform，2024公开论文/ICML workshop项目** | HLS、流水/展开/数组分区；§4.2说明速度来自系统仿真 | VU9P FPGA；文中描述模块约200–300MHz | 展示HLS可处理Transformer，但实际110M的llama2.c模型，不能因标题就认为跑了Llama 2 7B；也不能把FPGA周期/PPA当55nm ASIC证据 |

原文定位：[HSA §IV–V、Table I](https://arxiv.org/html/2507.09010v1#S5)；[FSGen §5–7、Table 1](https://arxiv.org/html/2608.09252v1#S7)；[SpAtten §V-A、Table I](https://arxiv.org/html/2012.09852v2#S5)；[Anda §V-A](https://arxiv.org/html/2411.15982v1#S5)；[HLSTransform §3.3、4.2、5.1](https://arxiv.org/html/2405.00738v1)及[作者代码](https://github.com/andrewchang03/HLSTransform)。主综述的其他证据见[EVIDENCE.md](EVIDENCE.md)。

FSGen特别值得借鉴的是“有限架构空间→生成实现→时序/功耗验证→快速模型探索”的流程。它探索了768个配置，但这不是所有电路实现的全局最优证明。其功耗模型还考虑输入翻转与零位统计，说明只知道操作次数不足以给出活动功耗。本轮未下载运行其artifact。[FSGen原文](https://arxiv.org/html/2608.09252v1)。

## 3. 要同时记录Latency、II和时钟

| 参数 | 实际含义 | 容易犯的错误 |
|---|---|---|
| 首结果延迟L | 一次输入被接受到对应输出产生的周期数；需定义握手边界 | 把整个循环总延迟或组合ns直接当L |
| 启动间隔II | 可连续接受两组新输入的最小间隔 | 延迟6拍不表示每6拍才能接新输入；II=1也不表示1拍完成 |
| 时钟周期Tclk | 在指定PVT、uncertainty、负载和物理阶段下成立的周期 | 给出100MHz约束就认定硬件已达到100MHz |
| 有效吞吐 | 受II、数据依赖、供给及输出反压共同限制 | 内核II=1就认定含DRAM/RNG的整机每拍都工作 |

对于固定流水、无停顿且每次输入同样大小的模块，输入批数为B时：

`C_no_stall = L + (B - 1) × II`。

此处L已经包含从首输入到首输出的所有内部级数；不要再次重复加同一段排空。任务启动、尾包、写回和实际停顿按接口另计。循环调度还受资源数、内存端口和递归依赖约束；例如单个累加反馈链不能在不满足依赖的情况下强行设II=1。[AMD调度/指标定义](https://docs.amd.com/r/en-US/ug1399-vitis-hls/Schedule-Viewer)；[流水依赖约束](https://docs.amd.com/r/en-US/ug1448-hls-guidance/Pipeline-Scheduling)。这些资料用于说明调度概念，不提供我们的ASIC成本。

HLS报告是已生成某个候选实现的证据，比任意填写宏延迟更强；仍需C/RTL验证、综合与STA。面积与功耗需要注明阶段，关键模块最好完成P&R/CTS及寄生参数下的时序和活动功耗。HLS报告与后端不一致时以实际实现约束回填，不能选择较好的一份数字。

## 4. 我们代码里哪些周期还需要闭环

只读版本：PR190 head `ee21c0ce9a14662aad98abbda8277f8af37365b8`；该PR开放待审，未合并。源码链接按此SHA固定，避免以后分支漂移：

- [ffn_latest.py](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/ee21c0ce9a14662aad98abbda8277f8af37365b8/architecture_tlm/unified_v6/ffn_latest.py)：`defaults()`、`batch_cycles()`和`restore()`。
- [config.py](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/ee21c0ce9a14662aad98abbda8277f8af37365b8/architecture_tlm/unified_v6/config.py)：数字MAC与向量资源默认值。
- [MATURE_SCHEDULING_ZH.md](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/ee21c0ce9a14662aad98abbda8277f8af37365b8/architecture_tlm/unified_v6/MATURE_SCHEDULING_ZH.md)：共同存储调度后的45项条件结果及限制。

| 当前字段/操作 | 代码模型 | 本轮判断 |
|---|---|---|
| 输入编码 | 64 lanes，L=3，II=1 | 是明确可替换的时序合同；本轮未发现与这组准确配置一一对应的已验收后端证据 |
| 桶移位归约 | `restore()`中64 lanes，L=3；调用量values×buckets | 需生成真实数据通路，验证归约依赖、路由与各档移位；调用量本身不证明实际流水 |
| q16系数恢复 | 16 lanes，L=6，II=1 | 最适合先做HLS或手写流水RTL对照 |
| 跨tile部分和 | 32 lanes，L=2，64位状态；显式读写部分和 | 必须检查同地址反馈、读改写次序、存储端口与独立累加上下文 |
| 最终BF16转换 | 16 lanes，L=3 | 固定数值语义后可HLS；不能擅改舍入、溢出或特殊值处理 |
| 数字MAC | 512 MAC/拍，startup=2 | 比较基线也要实现/校准，不能只校准概率方案 |
| NL随机供给 | 192个8位字/拍接口需求，默认stream II=2 | HLS不能证明独立性，也不能证明物理随机源可持续供给；仍依赖源、缓存、仲裁及统计验证 |

例如按当前公式，64个结果、16 lanes、L=6、II=1，算得9拍。这只是**给定参数的数学后果**，并不证明55nm电路的L必为6。接上HLS/RTL后应替换这些字段的证据来源，保留停顿与有限资源调度。

PR190报告SC桶归约、系数恢复和跨tile宽累加合计约78.5ms资源忙时。忙时可能与其他资源重叠，不能当作直接可删除的整机延迟。在相同Attention配置下SC仍慢于W8数字，故首先优化恢复/累加流水很有实际意义；此前较早“调度仍在实施”的综述表述属于当时快照。

GU定点恢复对原FP32训练参考的系数编译/舍入等价仍未闭合。先固定数值语义再做HLS，否则只是更精确地实现一个可能不同的算法。HLS不能继承历史PPL。

## 5. 工具选择与适用范围

**首选候选：Catapult + 可综合C++/SystemC；条件是研究环境确有许可、技术库接入及可用后端。** HSA提供了与DC/Innovus连接的直接论文先例；MatchLib提供通道/FIFO/仲裁等组件，可减少接口工作。若已有Cadence Stratus与Genus完整环境，采用Stratus同样合理，不必为论文品牌切换EDA。

HLSFactory可以帮助批量运行和提取latency、II、critical-path/slack及面积分项；它不是HLS编译器，也不提供商用许可。其公开Catapult例子使用Nangate45nm，不能把示例面积分数当我们55nm的面积。[HLSFactory官方教程](https://github.com/sharc-lab/HLSFactory/blob/main/docs/source/tutorials/catapult_flow.md)。

有55nm `.lib` 仍需核实工具支持的技术库准备流程、算术映射/定点类型、SRAM/ROM宏模型与端口约束；不能默认把任意工艺文件放进去即可。只检测了本机PATH，未发现catapult/stratus/bambu/vitis_hls命令；**这不代表服务器未安装或没有许可**，本轮未登录服务器核查。

| 模块 | 推荐路线 | 理由 |
|---|---|---|
| 桶恢复、定点转换、归约、宽位累加 | ASIC HLS试点＋一个清楚的RTL参考 | 调度、展开、共享与流水选择多，HLS能降低试错成本 |
| 数字参考MAC/向量操作 | 相同库/约束下的RTL或HLS | 公平比较需要相近实现努力，避免故意弱基线 |
| 已有PRNG、比特排列、AND阵列、特殊计数器 | 优先复用/优化已有RTL | 位级结构与共享已明确，HLS未必更好，需比较后判断 |
| SRAM/CIM本地权重宏 | 宏模型＋适配接口，必要时自定义RTL | C数组不能证明真实SRAM有全并行读口；HLS分区/复制的成本必须计入 |
| p-bit物理源与异步Ising演化 | 器件/SPICE/实测模型＋数字接口 | HLS仅综合数字外围，不能生成或验证物理噪声/弛豫时间 |
| 整机DRAM、调度、CDC | 保留TLM/DRAMSys，关键边界RTL验证 | HLS模块内部调度不会自动解决整机资源竞争或异步时钟边界 |

Vitis/Vivado HLS可作为FPGA原型与算法实验工具，但FPGA的DSP、BRAM和布线与55nm ASIC不同。不能照搬其周期/频率/PPA形成ASIC结论。Chisel、SpinalHDL属于描述/生成RTL的路线，不应与自动行为调度HLS混称。

MatchLib还明确区分接近逐周期RTL行为的仿真模式与更快的TLM模式；允许注入通道停顿。因此即便C++/SystemC能运行，也要记录用的仿真模式，不能统称“周期准确”。[MatchLib官方说明](https://github.com/NVlabs/matchlib)。ESP示例当前默认面向FPGA技术映射，适合学接口，不能原封不动当ASIC55nm流程。

## 6. 一个范围受控的试点怎样验收

1. **冻结功能合同**：4/7桶输入格式、q16系数编译、移位、signedness、累加范围、舍入/饱和和输出顺序；列出输入完整到输出被接受的握手边界。先与数值参考逐位核对。
2. **固定对照资源**：同一55nm库/PVT、核心10ns目标周期及同一uncertainty、相同宏端口与带宽。10ns是目标，不是先验可达。若失败，保留失败点，再比较加流水或降频；不能只改报告中的周期。
3. **有限设计搜索**：例如8/16/32 lanes与II目标1/2，探查展开、乘法器共享、归约树和独立累加上下文。面积/功率预算固定后筛选Pareto点；增加lane不叫免费加速。用至少一个有竞争力的参数化RTL实现判断HLS质量。
4. **实现验证**：C/RTL数值验证、连续流与反压/尾包/复位/同地址依赖；综合、STA、代表激励活动功耗；关键候选完成P&R/CTS与寄生时序/功耗。记录失败/时序违例，不仅保存成功配置。
5. **回填模块合同**：记录首结果延迟、II、输入输出宽度、可在途数、FIFO/部分和容量、读写/随机源消耗、合法时钟/PVT、面积/活动能量、工具版本与SHA，以及各阶段证据。频率/II随配置变化必须一并更新。
6. **系统与质量复核**：用同一输入事务对照RTL与TLM，验证周期和停顿；再运行同资源数字/概率端到端比较。若数值实现改变，重新验证后训练模型质量；没有实现变化不重复昂贵PPL。新数字仿真按Issue110规则进入统一台账。

最终论文可采用“模块ASIC HLS/手写RTL＋关键模块物理验证＋经过对照的系统TLM”。强度由创新点和主张决定：若声称p-bit核心在面积能耗上优于数字，随机源、读出、控制、转换和存储接口都必须纳入，不能仅给HLS数字后处理的结果。若局部HLS不值得引入，手写参数化RTL完成相同证据链也成立。

本轮只完成方法调研和现有代码参数审计。尚未确认商用HLS环境，尚无HLS生成实现、调度报告或本模块新PPA，不能把建议写成已获得周期/面积结论。
