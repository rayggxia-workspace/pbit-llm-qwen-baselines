# 28nm SRAM参数提取与最小仿真清单

日期：2026-11-09；TLM接入负责人：rayggxia；Issue225 / PR249。交给SRAM/EDA执行方使用。**先提取库参数，再对一个代表宏补少量PT；本轮不要求仿真完整LLM或960KiB整阵列。**

## 1．现在有什么，缺什么

当前28nm TLM没有接入真实28nm SRAM宏PPA。普通片上存储暂按240个独立bank、每bank4KiB、每次16B、单端口1RW，共960KiB建模。bank竞争、地址、读写量、DMA回压由执行模型处理；宏本体的面积、能量与可达周期另需表征。

| 项目 | 当前依据 | 是否28nm工艺库数据 |
|---|---|---|
| 单4KiB宏面积 | CACTI 0.00552094mm²；迁移55nm校准残差后中心0.00697290mm² | 否 |
| 16B读／写能量 | CACTI 1.809／4.752pJ；迁移后3.561／4.702pJ | 否 |
| 单宏静态漏电 | CACTI 0.646µW；迁移后2.598µW | 否 |
| 访问／最小周期 | CACTI 0.736／0.581ns | 否 |
| TLM当前服务 | 250MHz：4ns/拍；500MHz：2ns/拍，默认单拍返回、每拍可发一次 | 显式假设，未获28nm宏验证 |

上述迁移只是条件估计，不能称28nm校准。严格WHOLE_CONFIG的SRAM价仍为null；粗估报告另用了这些假设。960KiB中心面积1.6735mm²、整token SRAM能量约2.41mJ也不是新工艺实测。28nm面积系数为1，**不能再乘55nm专用的0.81**。

## 2．需要生成哪些宏

采用与28nm逻辑匹配的foundry/process及memory compiler。当前逻辑标为TSMC28HPC+、TT0.9V25°C；SRAM应使用其自身实际支持的电源/角点，不强行把另一工艺或另一电压宏改名成此配置。先记录差异，再决定能否匹配。

| 优先级／ID | 深度×数据宽度 | 单宏容量 | 用途与本轮要求 |
|---|---:|---:|---|
| **必须 S0** | **256×128bit，1RW** | **4KiB** | 校准当前240bank组织；先完成这一种就有用 |
| 建议 S1 | 128×128bit，1RW | 2KiB | 评估减小bank深度与容量的代价；先库提取即可 |
| 建议 S2 | 512×128bit，1RW | 8KiB | 校准更深bank的面积/周期变化；先库提取即可 |
| 备选 S3 | 256×64bit，1RW | 2KiB | 若没有128bit宏，可用两个64bit宏并行组成一个16B逻辑bank |

如只有32bit宽，也可四个256×32组成一bank。必须同时计入四宏面积、同时读写能量及接口，不能只记一宏。1RW指同一端口一拍读或写，不能同时读写；不要求双端口。默认无ECC；repair、mask、sleep等按compiler实际生成选项记录，不擅自从面积扣除。

**最小工作量：S0的TT与SS库参数＋S0在TT下的两个频率功耗检查。** S1/S2暂不逐项跑PT；FF角和更多slew/load网格可以以后补。

## 3．第一步：先从.lib／.ds／.lef提取

提供宏名、compiler版本、depth/width、端口、PVT、电源、memory选项、pin映射和行为模型读延迟。原文件保留在本地或授权共享存储，给出路径及SHA-256即可；不把工艺库本体上传公开GitHub。

| 文件 | 提取内容 | 要解决的问题 |
|---|---|---|
| `.lef`／`.ds` | 宏WIDTH、HEIGHT，单位；布图边界；keep-out另外列 | 得到真实宏占地。库`area`另存并核单位，不默认其必为µm² |
| `.lib` | `nom_voltage/temperature/process`、time/cap/leak单位；各电源域 | 区分TT/SS和不同电压，不混价 |
| `.lib`／`.ds` | clock→Q最大延迟、A/D/CE/WE setup/hold、最小时钟周期及高低脉宽 | 判断4ns／2ns能否连续读写 |
| `.lib`／`.ds` | 读延迟拍数、连续请求启动间隔、输出保持/写时输出行为 | 分清延迟、吞吐和数据保持 |
| `.lib` | `internal_power`的related_pin／when／rise/fall条件；各状态leakage | 区分读、写、关闭、保持，不把一个表项直接当pJ |
| `.lib`／`.ds` | 输入电容、允许slew/load范围、sleep/retention状态及唤醒开销（如支持） | 给接口和空闲状态定边界 |

TT用库的标称电压/温度；SS用compiler提供的Vmin/高温角。没有对应角时明确缺失，先交TT也可以。记录所取表格的slew和load坐标；不要把整张表的最大值不加说明地用于所有条件。

`.lib`功耗表单位及when条件容易误用：可以先交原提取值与单位，再通过PT统一输出W/pJ。已有compiler宏不要求重新做晶体管SPICE。库提取是工艺库表征依据，仍不是本项目硅片实测。

## 4．第二步：只对S0做代表性功耗/接口验证

### 4.1 电路边界

实例化**真正的SRAM宏**并使用其Liberty功耗/时序模型。不要综合Verilog行为RAM成为触发器阵列；不要仅用无功耗的black box后把0当SRAM功耗。VCS可用compiler行为模型检查读写功能；PT用对应宏`.lib/.db`计价。若只有库，没有内部网表，也可做宏级表征，不必展开内部晶体管。

接口信号由执行方映射：CLK、CE/CS、WE、A[7:0]、D[127:0]、Q[127:0]、可选BWE/睡眠脚；写清每个有效电平。读写全16B；暂不测部分写掩码。写入在macro实际有效边沿完成，读取按真实延迟比较，输出保持行为按规格检查。

测试源/计数器/PRNG只是testbench激励，**不计入SRAM宏面积或功耗**。宏输出网络与实际需要的读出寄存器、地址译码、bank选择/时钟门控分别报告，不与TLM既有DMA/FIFO重复计费。

### 4.2 时钟与负载

- **250MHz＝4ns；500MHz＝2ns，分别报告**。同一宏不因两频率重复计面积；若compiler换成更快版本，另列版本面积。
- baseline可先用CLK/input slew＝0.05ns、Q每bit负载＝1fF；仅当位于实际库有效范围内才采用，否则换库内最近合理值并记录。可选补Q负载10fF敏感性；不要把1fF结果当全片长互连功耗。
- 宏库时序提取与“SRAM＋近端接口”STA分开。片内通路用真实发射/接收寄存器或合理片内接口预算；不要把整芯片外部I/O的1ns输入＋1ns输出直接套到2ns SRAM片内周期。
- **返回延迟2拍，不代表最小接受周期也变成1拍。** 若宏最小周期2.5ns，则500MHz下不能每2ns接收请求；TLM可能需每2核心拍发一次。若周期满足2ns但clock→Q/接口需要流水，则可能保留II1、增加返回延迟。两者必须分开给出。

### 4.3 最小活动窗口

S0先在TT角运行以下6种窗口，250/500MHz各一组；一个明确seed17足以做第一轮标定，读/写随机窗可选再补503/1009。每窗先预热256拍，再统计4096拍；初始化单列，不把一次性写入初始化均摊给每次读。

| 窗口 | 行为 | 重点 |
|---|---|---|
| RD_SEQ | 每个可接受周期读一次，地址顺序循环 | 连续读取吞吐及能量 |
| RD_RAND | 同样频率，地址伪随机，预存数据约50% bit变化 | 数据/地址活动敏感性 |
| WR_RAND | 连续全字写，地址/数据伪随机，记录实测翻转率 | 写能量与持续写周期 |
| MIX_RW | 同端口读写交替，50%读/50%写 | 读写切换及正确性 |
| IDLE_CLK_ON | CE关闭、CLK继续、A/D保持 | 禁用宏的时钟相关功耗 |
| IDLE_CLK_OFF | CE关闭、宏时钟停止，数据保持 | 门控后保持/漏电 |

若宏无连续读取能力，降低请求频率至合法II并报告，不能在功能违规下算“每拍能量”。SS先做时序/库范围检查即可；TT功耗先交。不要求每种宏、每个角、每个seed都跑一遍。

若某频率STA失败，保留失败路径和数值；其功耗可单列诊断，不写成该频率有效价。无需为此阻塞另一个已通过频率和库面积的交付。

## 5．返回什么结果

### 5.1 每宏、每PVT一行库参数

`macro_id, macro_name, foundry_process, compiler_version, PVT, VDD_V, temp_C, depth, data_bits, ports, area_um2, width_um, height_um, read_latency_cycles, min_read_period_ns, min_write_period_ns, clk_to_Q_max_ns, input_setup_ns, input_hold_ns, output_hold_behavior, ecc_mask_repair_options, source_paths, source_SHA256`

`output_hold_behavior`分别说明CE关闭、写操作、时钟停摆时的Q是否保持/未知；读结果需要寄存器才能保持时必须记录。若厂商只有组合条件表，没有单一周期/保持结论，就交原条件和“不确定”，不自行填0。

### 5.2 每活动窗口一行PT结果

`macro_id, PVT, MHz, mode, seed, window_ns, read_accesses, write_accesses, clock_edges, address_toggle_rate, data_toggle_rate, macro_internal_W, macro_output_switching_W, macro_leakage_W, wrapper_internal_W, wrapper_switching_W, wrapper_leakage_W, gross_energy_pJ, setup_slack_ns, hold_slack_ns, gate_setup_slack_ns, gate_hold_slack_ns, activity_coverage, warnings, raw_report_path, raw_report_SHA256`

没有wrapper就各wrapper字段填“不适用”；若用了ICG，则给单元/脚名和门控时序，不能用普通组合AND替代真实ICG。面积分宏／读出保持／选择逻辑／ICG报告，测试激励逻辑不算。

必须保留功耗分组，避免宏本体、读出网络与已有捕获寄存器重复相加。温度、电压、毛刺/活动覆盖与timing fail不能在汇总中消失。

### 5.3 能量转换口径

先交gross窗口值：`E_window_pJ = P_window_W × window_ns × 1000`。每访问gross能量等于窗口能量除实际完成访问数；混合读写窗不能据一个总数唯一反推出读/写单价。

为TLM还可提供：`incremental_read_pJ = (E_read_window_pJ − P_idle_same_state_W × window_ns × 1000) / read_accesses`，写同理。用哪种idle作为基线需明确。后续TLM选择“增量访问＋全时间状态功率”或“gross访问＋剩余空闲能量”其中一种，不能gross访问再加一次全时钟idle。空闲clock-on和clock-off不同，不应一律只算漏电。

**最希望先拿到的6项：宏真实占地、16B读能量、16B写能量、两种idle功率、最大连续接受速率、读结果返回延迟。** 它们先闭合当前28nm SRAM项，再继续缩容量/资源探索。

## 6．如何接回TLM，以及本次不覆盖什么

本次主要校准普通读写bank：KV工作区、激活/概率码、跨块累加状态、普通权重/DMA装载缓冲。宏本体面积按实际实例加，wrapper另加；库数据本身不能证明240bank互连都在2ns内。CACTI继续用于容量/组织探索，用新的同工艺宏校准，替换现在的跨55nm残差迁移。

**标准1RW宏数据不能证明FFN改造CIM的全部权重能同时呈现在比较器旁边。** 本次不要求把定制CIM完整做出来；普通宏可作存储面积/漏电基准，但CIM本地读出/保持、全并行连线及计算外围另标模块，不把128bit端口的正常读能量直接当“全阵列并行计算能量”。也不从整宏面积随意减一个外围比例，宣称得到真实6T cell面积。

S1/S2若改变bank深度、数量或端口，必须重新检查容量、并行带宽和调度。例如8KiB×120与4KiB×240同为960KiB，独立端口数量却减半，不能继承240端口吞吐。减算核也不自动使部分和与预取所需容量减半。

新结果回来后，在统一`digital_circuit_simulation_registry/records/`登记库提取／功能／STA／PT的实际状态和原字节SHA；库提取不能写成PT完成。更新Issue225的28nm绑定与来源；只改价可重计价，最小周期/端口/延迟变更需新执行版本。禁止覆盖现有封存结果或改55nm默认。

## 7．参考与本地证据入口

- [CACTI官方说明](https://github.com/HewlettPackard/cacti)：解析估计访问时间、周期、面积和能量，不是本工艺宏库表征。
- 当前28nm估计：`architecture_tlm/process_28nm/rough_estimate_20261109/REPORT_ZH.md`及`RESULTS.json`。
- CACTI38638027原结果及SHA：`work/rayggxia/225/process28_rough_20261109/CACTI_PARSED.json`、`result28.txt`、`SHA256SUMS`。
- 接入宏接口：`architecture_tlm/process_28nm/{250MHz,500MHz}/WHOLE_CONFIG.json`。本文件是待执行需求；当前没有因此新增SRAM PPA或更改默认价。
