# 完整数字 Attention 首轮参考评估

2026-10-19；负责人 amlink1219；[Issue36](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/36)。这是可执行的解析参考，已完成三种上下文的算量、容量、流量和已知 SRAM 局部成本核验；尚未获得完整 Attention 的同工艺 PPA。结果见 [ledger](../results/digital_attention_reference_20261019/ledger.json) 和 [CSV](../results/digital_attention_reference_20261019/summary.csv)。

## 采用的数字参考 D0

选择 **分块在线 Softmax、GQA 共享 K/V 的浮点数字 Attention**。它在相同数学定义下计算所有 key，输出最终 Attention 向量；不把“先写出全部概率再读回”的额外流量强加给数字方案。近似数字 EXP、量化和 p-bit 后续都应在完整模型 PPL 预算内比较成本，局部误差只作定位。

算法依据是 [FlashAttention](https://arxiv.org/abs/2205.14135) 与 [Online normalizer](https://arxiv.org/abs/1805.02867)：对每个 K/V tile 计算分数，维护 running max `m`、归一化和 `l`、未归一化加权输出 `u`，更新 max 时同步重缩放 `l/u`，最后只对每行做一次倒数并乘输出。不是每个类别一个除法器。作者的 [KV-cache 接口](https://github.com/Dao-AILab/flash-attention#how-to-use-flashattention) 也明确支持增量解码与 GQA；GPU 代码只证明算法/接口，不提供本 ASIC 的 PPA。

完整模块边界是 `x → QKV投影/偏置 → RoPE与KV追加 → QK/online Softmax/PV → 拼接/Wo → y`。24 层依次复用硬件。分别保留核心账本和投影账本；输入 RMSNorm、残差相加、FFN、lm_head、prefill 不在此次模块内，整模型总延迟须再加入这些共同项。RoPE 系数产生/表访问与部分格式转换的成本仍未闭合，不能因配置写入了模块范围就称完整实现已完成。

| 参数 | 本轮固定选择 | 证据状态 |
|---|---|---|
| 模型/负载 | Qwen2.5-0.5B Base；24 层，hidden896，14 Q heads/2 KV heads，d64；batch1，单 token decode | 模型配置；L 为追加后参与扫描的 KV 总长度 |
| 精度 | 输入、权重、KV、输出 BF16；QK累加、分数、指数、分母、PV和重缩放 FP32 | 数值参考定义；非逐位 RTL |
| PV 乘法 | FP32 概率 × 精确扩展的 BF16 V，FP32 累加 | 不能按只有 BF16 乘法的硬件成本收费 |
| 数学 EXP | 稳定自然指数；每行共享倒数 | 尚未固定有限字长 EXP/倒数实现；PWL 是后续独立候选 |
| 数据流 | 一次处理 1 个 KV 组的 7 个 Q heads，64 token tile，K/V 双缓冲 | 复用同一份 K/V；两组串行 |
| 计算资源 | 512 抽象 MAC 槽、64 vector ops/cycle、16 EXP/cycle、1 reciprocal/cycle；100 MHz | 仅资源假设；FP32能力、频率、面积、功率未表征 |
| 物理映射 | 一个 KV 组可映射到 8 个头槽，7 个有效 | padding开销单列，未变成额外算法工作量 |
| 存储 | 16 个独立 1RW E 宏，共64 KiB；投影和Attention分阶段复用 | 宏表值；bank映射、供数和接口STA待验证 |
| 外存/互连 | 双通道DDR4-1866模型原始峰值29.850746 GB/s；DRAM服务上限与SRAM aggregate fabric均假设16 GB/s | 非实测持续带宽；SRAM读写合计 |
| 权重/KV驻留 | 投影权重和整段KV在外存，tile进SRAM；每输入byte一次写入、一次读出 | 不允许84 MiB权重或24 MiB KV免费驻留64 KiB |

100 MHz 下512槽给出51.2 GMAC/s计算容量，但并不意味着投影能持续达到该速率。投影每MAC消费2B权重；16 GB/s读写合计fabric还要承担DMA写入，供数会明显受限。本轮未建立完成的依赖调度与流水线。

## 有哪些文献硬件依据

| 参考 | 已核实的结果 | 能用于本项目的范围 |
|---|---|---|
| [ITA，ISLPED 2023](https://arxiv.org/html/2307.03493v2)，[作者RTL](https://github.com/pulp-platform/ITA) | 1024 INT8 MAC、500 MHz；22FDX核心0.173 mm²/60.5 mW；带64 KiB SRAM子系统0.407 mm²/121 mW | 布局后仿真/功率估计的完整MHA结构依据；不是BF16 GQA decode实测。核心与含SRAM两个边界分开，DRAM/PHY/host不含在内 |
| [SystolicAttention/FSA v4](https://arxiv.org/html/2507.11331v4)，[作者RTL](https://github.com/VCA-EPFL/FSA) | FP16乘法/FP32累加，把max、exp2 PWL、sum与矩阵运算融合；Table3用行为级模型PPL验证近似，含Qwen2.5-0.5B | 支撑融合数字参考和PPL验收方法；性能主场景为非因果完整矩阵、d128，16nm/1.5GHz；无功率/decode结果，面积不含SRAM/DMA |

ITA 时序设计按SS 0.72V/125°C，论文功率按TT 0.8V/25°C、合成活动估计；不能将不同corner拼成我们自己的工作点。论文中Softmax约占核心面积3.3%、功率1.4%，仅适用于该INT8配置，不能据此断言本项目也只有这个占比。当前官方RTL与论文配置已经不同，使用时需固定版本。其显式8bit概率也不能原样表示2048长度均匀分布。

FSA为预印本。它的FP16不等于BF16，Table3 PPL协议不同，不能与本项目11.65直接横比。Table4面积分项与总计存在不一致，故不引用其绝对面积移植到本项目。本文不做22/16nm到55nm的简单缩放，也不把EXP单元面积与整核功率组合为一个完整Softmax PPA。

## 本次跑出的数字账本

所有数均为 **24层合计、每生成一个token**，MAC按一次乘加计1次。投影常量为 `24×[896×(896+2×128)+896²]`；核心为 `2×24×14×64×L`。Softmax普通分数共 `24×14×L`，另有每tile的alpha指数、归约、重缩放、最终归一化与336次倒数。

| KV长度L | QK+PV MAC | QKV+Wo MAC | 完整MAC | KV物理读 | 权重读 | 主数据SRAM写+读下界 |
|---:|---:|---:|---:|---:|---:|---:|
| 512 | 22,020,096 | 44,040,192 | 66,060,288 | 6 MiB | 84 MiB | 11.796480 ms |
| 2048 | 88,080,384 | 44,040,192 | 132,120,576 | 24 MiB | 84 MiB | 14.155776 ms |
| 8192 | 352,321,536 | 44,040,192 | 396,361,728 | 96 MiB | 84 MiB | 23.592960 ms |

MiB=2²⁰B，GB/s=10⁹B/s。每token另有12KiB KV追加；新KV已包含在长度L的保守扫描读数中。SRAM列只计算weights/KV主路径两次传输，未包含所有控制和中间操作数，因此是该假设数据流的资源下界，**不是实际端到端时间，也不是理论最优数字架构时间**。若做DMA直接旁路或双独立fabric须另给接口/面积预算后重算，不能免费减少传输。

2K时纯MAC资源下界为2.580480ms，DRAM原始峰值下界约3.794ms，SRAM主路径下界14.155776ms。显式串行计算阶段假设（含8槽7活padding）为3.954720ms；它与内存下界不能相加后冒称周期准确时间，也不能把二者最大值当已实现延迟。真实时间仍取决于依赖、bank冲突、DMA、FP32流水线、供数、归约和时钟。

2K的单组活跃预算：KV ping-pong32768B、Q896B、FP32 u1792B、m/l56B、score tile1792B、extra8192B，合计45496B。extra包含QKV保留2304B、已完成组输出896B、Wo部分和3584B、控制/RoPE/对齐1408B；不同阶段峰值未必同时存活。64 KiB容量初筛通过不等于bank时序通过。若让24MiB KV全部驻留，用384个64KiB F宏仅宏面积就约119.871mm²；这不是本方案的已分配存储。

## 当前能给出的PPA及缺口

采用项目已发布[精确宏表](../results/sram_calibration_v1_20261016/exact_macro_table.csv)中E/SS，而不是CACTI外推：256×128bit、1.08V/125°C，面积0.03322622205mm²/宏，读10.0527pJ/128bit、写13.9599pJ/128bit。16宏共 **0.5316195528mm²**。读/写周期3.468/3.4271ns通过100MHz宏周期初筛，wrapper/时钟/跨域/互连STA仍未完成。F宏SS写周期11.0613ns，不能把F直接当100MHz宏使用。

2K下，108MiB主数据各一次写/读对应7,077,888次128bit读及同量写，宏内部动态能量：读71.1518847µJ＋写98.8066087µJ＝**0.169958493mJ/token**。只含这条流式路径，未含Q/O/中间score访问、寄存器、输出负载、时钟、计算或DRAM。16宏CE-off漏电合计124.0704µW，也不是模块静态总功率。没有总时间之前，不将它拼成完整能量。

完整能量必须形如 `E_QKV+E_QK+E_EXP/归约+E_PV+E_Wo+E_RoPE/格式+E_全部SRAM/寄存器+E_DMA/DRAM/PHY+E_静态`；完整面积为`SRAM宏+计算/非线性/寄存器+接口/控制/时钟`。当前仅上述SRAM局部项有直接库表依据，故JSON完整energy/area/power/achieved_latency均为null。

旧TLM的2pJ/MAC、1mm²逻辑、20mW idle等不能用来填空：MAC系数源为FP16乘法加FP32加法代理，其他多项是占位；不是当前BF16/FP32电路在所选工艺下的结果。已有整模型66.6ms/9.5mm²等还包含FFN等不同边界，不能改标签当作本次Attention。DRAM模型本身也明确未校准IO/PHY完整能量。

## 质量口径和对p-bit比较的影响

Issue35的原BF16模型复跑已得到完整WT2 **PPL11.652735047455899**，299077计分目标，window2048/stride1024；执行源879050031ac1cc7757e3b7f54e19c25dc40faf72、Slurm2161。这是既有SDPA软件锚点；本轮没有新模型运行，8192也没有新PPL证据。D0重排浮点运算、有限EXP/倒数和FP32 PV都需要行为级接入全模型才能声称质量通过。源记录见[质量来源索引](../../work/amlink1219/36/QUALITY_ANCHOR.json)。

后续比较的横轴应为相同协议下的PPL增量，纵轴分别为完整模块延迟、J/token和mm²；p-bit、数字近似EXP、数字采样均可容忍同一预算内误差。预算尚未由用户固定。实现必须同时记录代码/配置/模型数据SHA、种子、完整计分目标和是否同工艺；不把局部误差排名升级为架构排名。

在当前权重流式参考下，2K时84MiB投影权重占108MiB主读流量的77.8%。因此只替换Softmax不能自动消除权重和K/V搬运；筛选若仍需全部K，节约集中在被跳过的V、PV和部分后续处理。GQA七个Q的候选并集决定实际V加载量，不能把逐头采样率直接当总KV节约率。p-bit能否改善完整模块，须连同这些不变项以及随机源、配置、预热、读出、反馈成本一起比较。这是本参考的设计推论，尚不是p-bit无优势或有优势的结论。

## 可执行的下一步

1. 固定D0的有限字长EXP、共享倒数、FP32 PV、QK点积和DMA/寄存器接口；加入数字PWL候选，对同一整模型协议跑PPL。现有2K BF16锚点直接复用，无改动不重复长跑。
2. 对这些实际单元用同一标准单元库、corner、时钟和输入活动做综合/STA/功率，报告面积、每op能量、启动间隔与延迟。绑定库/许可证前不能声称EDA工具可用或不存在；本轮未执行DC/PT。
3. 把已表征单元及bank映射接入TLM/事务调度，验证16GB/s能否实现，计全SRAM/寄存器访问、DRAM命令及PHY/IO范围；给出完整模块而非max资源下界。
4. 在相同硬件/内存预算下加入QK筛选、数字采样与原生p-bit，行为级以完整WT2 PPL增量过滤候选，然后比较三项PPA。整模型速度还要加入共同FFN/归一化/输出头开销。

本轮实际执行：10项单元测试通过；L512/2048/8192解析运行成功；独立审查工作量、流量、FP32成本口径与PPA空项。无新GPU、RTL、综合或功耗实测。复现命令：

```powershell
python -X utf8 -m unittest discover -s architecture_tlm/digital_attention_reference -p test_evaluate.py -v
python -X utf8 architecture_tlm/digital_attention_reference/evaluate.py --config architecture_tlm/digital_attention_reference/reference_config.json --output <新的结果目录>
```

manifest、文献/Zotero回执、验证与未发布状态见[交接](../../work/amlink1219/36/HANDOFF.md)。本地成果不等同远端PR交付。
