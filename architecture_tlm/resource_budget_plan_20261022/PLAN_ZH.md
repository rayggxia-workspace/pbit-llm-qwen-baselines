# p-bit LLM ASIC资源预算与系统仿真实施计划

日期：2026-10-22。适用对象：独立p-bit／数字混合ASIC，片上SRAM＋外部DRAM，覆盖FFN、Attention及完整decode。正式仓库为 `rayggxia-workspace/pbit-llm-qwen-baselines`；本计划由 [Issue112](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/112)交付。

建议先以 **2 MiB、4 MiB SRAM作为主要候选，1 MiB保留现有参考，8 MiB检查扩容收益**，同时搜索带宽、编码恢复和计算资源。最终配置由同总面积下的时延、能量和质量曲线决定。当前局部算术面积优势可以用于增加资源，但完整芯片面积账本尚未闭合，不能把节省的门面积全部当作可用SRAM面积。

本文是后续实施计划。所列搜索点尚未执行，不修改现有默认配置，不启动新模型、TLM或EDA实验。

## 1 先确定比较方法

保留两类主对照，分别回答不同问题：

| 对照 | 固定条件 | 允许分别优化的内容 | 回答的问题 |
|---|---|---|---|
| 相同资源 | 同工艺/PVT、频率、SRAM容量与端口、片外内存配置、质量协议 | 映射、分块、融合、预取和调度；明确数字与随机计算模块数量 | 更换算术或采样方法本身有什么收益 |
| 相同总面积 | 同工艺/PVT、总面积上限、片外内存与功率上限、质量协议 | 数字与p-bit方案分别选择计算数量、SRAM组织、恢复资源和数据流 | 计算电路省下的面积能否换来更好的整机表现 |

数字对照至少包含BF16参考和现有W8数字FFN＋准确Attention；随机方案包含随机FFN＋准确Attention，以及筛选／PV／其他采样器。独立消融FFN、Attention、随机服务和存储优化，不能让p-bit方案独享改进后的调度。

同总面积比较不要求两方SRAM一样大，也不要求计算阵列一样多。必须给双方相同的搜索范围、约束和选择规则。未知面积或能量项保留未标定；只在有完整计费依据的配置上给整机PPA排名。

首先以一个完成面积账本的数字ASIC得到面积锚点 `A0`，再分别搜索 `A0`，必要时增加 `0.5A0`、`2A0` 的预算曲线。这个面积锚点比现在任意指定10或20 mm²更有依据。面积账本包括：计算、SRAM宏与外围、局部计数／寄存状态、随机服务、编码恢复、控制互连、时钟及必要的内存接口。

## 2 已有证据与工作集规模

当前集成基线：`eb317e4f6fb1b0d8844887401f3275f128ef8a83`，分支 `pbit-tlm-attention-details-20261016`。统一v6封存执行版本为 `fba22b192ab914046e50cc405f6dd473bf30d154`，原52项情景保持原字节。以下均为条件TLM及只读核算，不是芯片测量。

| 当前Qwen配置或结果 | 数值／边界 | 对资源规划的含义 |
|---|---|---|
| 模型 | Qwen2.5-0.5B，24层，D=896，FFN=4864；14个Q头、2个KV头、head_dim=64 | GQA候选并集和物理读取需按KV组计算 |
| 核／SRAM | 100 MHz／80 MHz | 不能只用一个时钟换算所有资源的周期 |
| 计算资源 | 512 MAC/核周期、64向量lane、16非线性lane；8个64×64 SC引擎 | 是当前合同，尚未证明可达吞吐或最优配比 |
| 存储与接口 | Qwen 1 MiB，16 bank×128 bit、1RW；公共fabric 16 GB/s；DRAM Link 16 GB/s、80 ns、64 B、在途窗口32 | 容量、bank带宽、公共带宽和有效外存吞吐分别限制性能 |
| 2K/seed0完整decode | BF16准确234.36001 ms；W8数字163.56481 ms；SC准确201.67681 ms；SC筛选PV 197.93816 ms | 当前随机方案尚未胜过同W8数字对照 |
| SC全部FFN原始波服务 | 3.41088 ms/token | 不能把这个时间当作整FFN或整机时间 |
| SC恢复代理 | 55.15776 ms/token | 优先落实恢复电路与流水；不能由72个代理op推导出72个完整恢复器 |
| 完整物理能量／面积 | 未闭合，保持null | 局部价格小计不能作为整芯片能量或面积优势 |

按模型形状可直接得到下列容量。MiB为2^20 byte；论文中的MB沿用其原标注。

| 数据，batch=1 | 算式 | 容量 |
|---|---|---:|
| 单层三个FFN矩阵，W8 | `3×896×4864` byte | 12.46875 MiB |
| 全24层FFN，W8 | 上项×24 | 299.25 MiB |
| 2K上下文全层KV，BF16 | `2(K,V)×24×2048×2(KV头)×64×2 byte` | 24 MiB |
| 8K上下文全层KV，BF16 | 上项上下文长度改8192 | 96 MiB |
| 2K／8K单层KV，BF16 | 全层容量÷24 | 1／4 MiB |

当前W8路径只将FFN权重变成W8，其他投影和lm_head等仍保留BF16。封存结果的权重读取为674,136,064 byte/token，不能把它描述为“整个模型均为INT8”。

增加几MiB SRAM主要用于分块、双缓冲、KV复用和中间状态。能装下一层KV或一部分FFN权重，不等于全模型跨token常驻；必须明确哪些数据驻留、何时被替换、实际消除了哪些DRAM事务。

## 3 可以实施的任务与优先级

| 顺序 | 可以做的工作 | 主要输入 | 具体产出 | 验收条件 |
|---|---|---|---|---|
| P0 | 建立完整资源与成本账本 | v6配置/动作、Issue107数字RTL、Issue110仿真台账、已有SRAM宏 | 每模块实例数、存储位数、latency/II、PVT、PPA来源与缺项表 | 不重复计费，未知不置零；SC局部计数和权重保持有明确物理归属 |
| P0 | 固定基线与分解下界 | 封存BF16/W8/SC结果、工作集、物理字节 | 各阶段计算/访存/恢复需求和条件下界 | 原件不重写；资源busy、等待和墙钟不重复求和 |
| P1 | 参数化存储布局和真实调度 | 现有SRAM Arena、权重ping/pong、访存事务 | 容量变化会改变分块/缓冲/驻留的可执行模型 | 额外容量确实被使用；读写、bank、端口、寿命、回压与容量检查通过 |
| P1 | 编码与恢复专用流水 | Issue107候选模块、当前代理合同 | 通用向量复用和专用恢复两类实现，按真实latency/II计时 | 供给与消费匹配；删除被替换代理项；数值变化单独验证 |
| P2 | 联合搜索存储、带宽、计算和随机服务 | 上述模型和物理候选表 | 两类对照的可行配置及Pareto前沿 | 数字与随机方案都优化；面积超限、带宽不可实现或质量不符者不参与排名 |
| P3 | 校准少数代表点 | 前沿上的小面积点、性能拐点和高性能点 | 关键RTL STA/PPA、代表trace的DRAMSys/DRAMPower结果 | 时钟可达、接口约束、功耗边界及DRAM规格可追溯；区分前后布局 |
| P4 | 扩展模型、prefill与质量核验 | 通过前几步的少数候选 | Qwen与Llama规模外推、prefill/decode分账、同配置质量与PPA表 | 完整WT2/任务协议冻结；prefill单独实现，不用当前decode结果冒充TTFT |

P0可以先用现有封存数据完成；新实现、仿真和服务器作业应在执行时冻结版本、输入、负责人及验收范围。无需一开始对全部配置布局布线，也无需先重建完整周期精确NPU。

## 4 初始搜索范围和物理约束

| 设计变量 | 初始候选 | 选择依据及约束 |
|---|---|---|
| Qwen片上SRAM | 1、2、4、8 MiB | 2/4 MiB作为主要候选；8 MiB检验饱和；Llama另立工作集和预算，不能强套Qwen结论 |
| SRAM公共fabric | 16、32、64 GB/s | 同时改变可实现的bank并行、接口和互连；读写合计定义保持一致 |
| 外存数据带宽 | 16、32、64 GB/s | 绑定真实通道数、总线宽度/速率、控制器与PHY成本；报告持续有效吞吐 |
| SC引擎数 | 4、8、16 | 先明确每引擎的权重供给、计数保持和恢复需求，再扩展；64×64暂作参考而非架构硬约束 |
| 数字计算并行度 | 现有512 MAC/周期及其相邻规模 | 按具体数制重新综合/查表，不把BF16 MAC和W8乘法器视为同成本 |
| 编码／恢复 | 向量复用；专用流水及有限实例数 | 搜索完整输出吞吐、II、局部状态和共享方式，不按代理op数量直接复制电路 |
| Attention辅助资源 | 在线Softmax、归约、索引/直方图及V累加的共享与并行方案 | 包含排序/预算修复、转换、回写和稀疏请求开销 |
| 随机服务 | 有限本地PRNG吞吐、共享域、重播/重播种与源时钟 | 就地供给，不新增随机流SRAM/FIFO；FFN共享门限不能自动用于Attention独立提议 |
| 时钟 | 初轮保留100 MHz核／80 MHz SRAM | 先隔离数据流收益；后续只使用STA支持的工作点，CDC与互连延迟重新核算 |

先用解析约束剔除明显不可行点，再做粗粒度联合搜索，在Pareto附近细化。不要穷举所有变量的大笛卡尔积，也不要逐个变量优化后就宣称达到联合最优。

### 4.1 容量不能代替带宽

当前128 bit SRAM端口在80 MHz下，每bank理论单向数据率为1.28 GB/s；16 bank的合计理论值为20.48 GB/s，但公共fabric只有16 GB/s。读写共享、冲突、仲裁和CDC会进一步限制有效吞吐。想得到32/64 GB/s，需要配套bank、端口和互连设计，不能只增加一个带宽参数。

同一4096×128的64 KiB宏面积为0.312163310025 mm²。复制相同宏时，1/2/4/8 MiB的宏面积分别约4.99/9.99/19.98/39.96 mm²，尚未包括wrapper、互连、时钟等外围。这是当前宏组织的投影，不是通用55 nm密度，也不代表换成更大或更深宏仍保持相同单位成本；其他宏几何应优先查已有库摘要，拟合仅用于带误差的探索。

### 4.2 目标时延可以反推外存需求

保持当前W8路径、674,136,064 byte/token的权重读取，不增加跨token权重驻留或压缩时，权重部分就要求：

| 目标decode时间 | 最低持续权重带宽，不含KV等 |
|---|---:|
| 50 ms/token | 13.48 GB/s |
| 20 ms/token | 33.71 GB/s |
| 10 ms/token | 67.41 GB/s |

当前Link每32×64 B请求窗口排空并额外支付80 ns，连续流的有效带宽约为 `2048/(80+128) = 9.846 GB/s`，并非持续16 GB/s。这个模型应作为一个保守后端保留，再加入持续在途请求／真实控制器后端对照；不得静默修改旧结果。

## 5 TLM应补哪些能力

1. **存储分配随映射变化。** 当前固定两个64 KiB权重slot；新增可选的多tile缓冲、权重驻留、KV组局部缓存和中间状态分配。每种策略输出分配表、存活区间、峰值和物理容量。增容但未改变分配时，应如实报告无收益。
2. **展开供数与保持接口。** 明确每个SC引擎一波所需的权重、激活、尺度、计数状态及读出保持方式。普通SRAM宏的串行读出不能免费变成32 KiB全宽并行驻留口；也不将全部权重改存DFF。
3. **建立有限队列和流水。** DMA写入、SRAM消费、编码、SC执行、恢复和输出之间建立数据依赖与回压。允许重叠的阶段必须有独立端口、双缓冲或队列支持，不能直接把几个时间取最大值。
4. **搜索FFN融合。** 比较完整gate/up屏障与按对应输出块执行SwiGLU，再将z供给down的流水。计入部分和保持、down权重重读和新缓冲，防止“融合”反而增加访存。
5. **优化Attention的物理稀疏路径。** 保持在线/融合数字基线；按GQA并集读取K、按实际唯一索引读取V，考虑burst合并、重复样本计数及广播。候选比例不能直接充当DRAM字节比例。
6. **把有限随机供给接入整机。** 记录每消费者需要的随机字宽、并行路数、独立域、帧启动、重放、恢复和回压。源生产与消费可以重叠，但重叠范围须有调度依据；PR103小接口验证不等于整机已启用新后端。
7. **改进外存模型。** 首轮快速筛选用Link，少数代表点导出真实地址trace接DRAMSys/DRAMPower，覆盖行命中、ACT/PRE、刷新、低功耗和后台能量。I/O/PHY功耗是否包含单列，不能把64 pJ/B占位变成已校准DRAM模型。

已有ZigZag／映射脚本可继续承担其支持的矩阵分块搜索。SC的T/K、随机域、编码恢复和采样地址需扩展成本及依赖描述；通用映射器不会自动理解这些新算子。暂不以全面迁移某个NPU模拟器作为第一步。

## 6 下界和优化目标怎样报告

对给定映射、固定物理字节和已知有效带宽，先报告条件下界：

```text
T_LB = max(Q_DRAM / B_DRAM_eff,
           Q_SRAM / B_SRAM_eff,
           各计算/恢复/随机资源的最少服务时间)
```

这个式子假设允许理想重叠，是资源下界，不保证可达。队列、依赖、启动、bank冲突和串行阶段可能使实际时间更长。映射改变Q后必须重算下界，不能拿优化前的大流量当成优化后“理论最优”。另外给出工作集与驻留容量决定的必需外存流量界，区分固定trace下界与跨映射的通信下界。

例如当前Qwen 2K/seed0 W8路径SRAM总读写1,405,768,576 byte，在16 GB/s读写合计fabric下仅数据传输就至少87.860536 ms；163.56481 ms是其约1.86倍。这只说明当前固定流量和接口合同还有差距，不代表离所有架构的全局最优为1.86倍。

目标时延和质量预算未确定时，输出不可同时改善面积、能量和时延的Pareto前沿；预算确定后，可最小化J/token并约束总面积、TPOT、平均/峰值功率和质量。初期缺物理价格时只比较时间、字节、动作与面积区间，完整J/token保持未完成。

每个最终候选至少输出：

- 总面积与模块分解；宏面积和标准单元面积边界。
- decode step时间、每请求TPOT及batch总吞吐；prefill/TTFT另列。
- 总J/token及计算、SRAM、DRAM、随机服务、转换恢复、时钟/后台等分解。
- DRAM/SRAM物理读写字节、有效带宽、bank冲突、资源利用率、等待及峰值存储。
- 同配置质量、采样T/K/S、随机共享/相关性和至少三个独立种子；质量预算由用户确定，不能沿用“5%是会议标准”。
- `T/T_LB`、下界所依赖的字节和带宽，以及尚未标定项。

## 7 第一轮实施边界与交付

第一轮主负载使用Qwen2.5-0.5B、batch=1、2K与8K上下文，先比较完整decode。数字BF16、W8数字、SC准确及筛选PV作为最小矩阵；赢家／拒绝保留独立实验，因为其服务成本和样本相关性不同。先固定算法和质量协议再改变资源，避免把减少采样当作纯架构加速。

形成可行前沿后，用Llama 2 7B检查规模外推，LLaMA-1按已有兼容入口复核；更大模型不默认获得更多免费SRAM或外存带宽。batch=4/8和prefill作为独立扩展，需实现对应调度，不能仅将batch=1结果除以batch。

建议第一轮最终交付五项：完整资源/成本账本、参数化TLM与映射接口、同资源/同面积结果表、Pareto及下界图、少数候选的物理和DRAM校准证据。所有新结果单独目录、绑定执行提交和manifest；旧52项只作回归参考。

## 8 已有文件和精确版本入口

下表为正式仓库路径，可按固定提交读取，不要求在本机重复完整checkout。未合并依赖按各自head引用，不视为已进入集成。

| 内容 | 固定版本与文件 |
|---|---|
| 当前统一TLM说明与52项结果 | [unified_v6/RESULTS_ZH.md，eb317e4f](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/eb317e4f6fb1b0d8844887401f3275f128ef8a83/architecture_tlm/unified_v6/RESULTS_ZH.md) |
| 资源、价格与时序配置 | [unified_v6/config.py，eb317e4f](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/eb317e4f6fb1b0d8844887401f3275f128ef8a83/architecture_tlm/unified_v6/config.py) |
| 完整decode与分块、缓冲调度 | [unified_v6/model.py，eb317e4f](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/eb317e4f6fb1b0d8844887401f3275f128ef8a83/architecture_tlm/unified_v6/model.py) |
| 存储与资源计时核心 | [unified_v6/core.py，eb317e4f](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/eb317e4f6fb1b0d8844887401f3275f128ef8a83/architecture_tlm/unified_v6/core.py) |
| Qwen形状和来源 | [configs/model_qwen.json，eb317e4f](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/eb317e4f6fb1b0d8844887401f3275f128ef8a83/architecture_tlm/unified_v6/configs/model_qwen.json) |
| 本文使用的W8字节与时间原件 | [qwen_L2048_seed0_w8_exact.json，eb317e4f](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/eb317e4f6fb1b0d8844887401f3275f128ef8a83/architecture_tlm/unified_v6/results/qwen_20261022_v2/qwen/qwen_L2048_seed0_w8_exact.json) |
| SC准确路径原件 | [qwen_L2048_seed0_sc_exact.json，eb317e4f](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/eb317e4f6fb1b0d8844887401f3275f128ef8a83/architecture_tlm/unified_v6/results/qwen_20261022_v2/qwen/qwen_L2048_seed0_sc_exact.json) |
| SRAM宏校准及边界 | [calibration.json，eb317e4f](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/eb317e4f6fb1b0d8844887401f3275f128ef8a83/architecture_tlm/llama7b/runtime/results/sram_calibration_v1_20261016/calibration.json)；精确F宏值亦在上述结果的SRAM.calibrated_macro字段 |
| 周期、访存假设与待闭合RTL | [CYCLES_MEMORY_AND_RTL_ZH.md，aedc08d0](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/aedc08d041a52d29387d227cac0ff702dea4cc69/architecture_tlm/digital_ppa_v1/CYCLES_MEMORY_AND_RTL_ZH.md)；PR109当前开放未合并 |
| 数字RTL及工艺表征入口 | [digital_ppa_v1/README_ZH.md，aedc08d0](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/aedc08d041a52d29387d227cac0ff702dea4cc69/architecture_tlm/digital_ppa_v1/README_ZH.md) |
| benchmark、质量和PPA协议提议 | [benchmark_protocol_20261022/README_ZH.md，eb317e4f](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/eb317e4f6fb1b0d8844887401f3275f128ef8a83/architecture_tlm/benchmark_protocol_20261022/README_ZH.md) |
| 随机服务与待接入接口 | [Issue95](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/95)、[PR97](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/97)、[PR103](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/103)；后者开放未合并，正式接入前重新核对head |
| 最新数字电路仿真台账 | [digital_circuit_simulation_registry/README_ZH.md，2b7935f4](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/2b7935f4bbb16c37cb1f59c5a2a394ae005e2b8b/digital_circuit_simulation_registry/README_ZH.md)；PR111当前开放未合并，恢复时核对最新head |
| 较早映射与外存入口 | [architecture_tlm目录，eb317e4f](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/tree/eb317e4f6fb1b0d8844887401f3275f128ef8a83/architecture_tlm)，从mapping_decode.py、dramsys/及总索引进入，先核对所用版本与支持范围 |

本机项目恢复入口：[PROJECT_MEMORY_ZH.md](C:/Users/86134/Documents/a_P_BIT/PROJECT_MEMORY_ZH.md)。便捷阅读副本：`C:/Users/86134/Documents/a_P_BIT/pbit_llm_master_report_20261012/PBIT_LLM_ASIC_RESOURCE_PLAN_ZH_20261022.md`。正式编辑源是本计划的任务分支文件；便捷副本只作同字节阅读，不独立修改。

## 9 论文中值得采用的方法

| 论文 | 已核对的设计与实验 | 可以借鉴的方法 |
|---|---|---|
| [Kelle，MICRO 2025，§3.1与§8](https://www.saiqianzhang.com/gallery/Kelle_Camera_Ready.pdf) | 32×32 RSA、2 MB权重SRAM、256 KB激活及4 MB KV eDRAM、64 GB/s外存；同面积SRAM基线改用24×24阵列和4 MB SRAM。前期4→8 MB SRAM平均加速1.27倍，系统面积/功耗增加26%/29% | 同面积下同时调整存储和计算，并做扩容敏感性。其逻辑45 nm、存储65 nm模型及batch=16不能直接移植为我们55 nm、batch=1的PPA |
| [Anda，HPCA 2025，§V-A和Table III](https://arxiv.org/html/2411.15982v1)，[会议官方程序](https://hpca-conf.org/2025/main-program/) | 16×16专用APU、64 FPU向量单元；1 MB权重和1＋0.125 MB激活缓冲；16 nm、285 MHz、HBM2 256 GB/s。SRAM占所列系统面积约76.96% | 分离同吞吐算子对照与同存储系统对照，把数据格式/转换/存储一起核算；APU不是单个标量MAC，GEMM收益不能直接当完整请求收益 |
| [LLMCompass，ISCA 2024，§III-D与§IV](https://arxiv.org/html/2312.03134v1) | 联合探索计算、片上buffer、片外内存与映射，加入面积/成本模型，区分prefill和decode | 先搜索并找收益饱和点，再选择资源预算；其传统算子模型需扩展才能描述我们的随机服务和恢复链 |

这些工作提供可参考的ASIC设计或架构评估方法；没有统一规定LLM必须配多少MiB SRAM。我们需要证明的是：在相同预算和质量约束下，所选配置优于可实现且已优化的数字对照，并说明收益来自哪里。
