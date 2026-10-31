## 2026-10-31 Issue220：Attention十组训练方案

负责人rayggxia；task/220-attention-ten-case-plan，PR base main@7d42c7d30fa9c729c899ba7f815332dd6ed5671a。正式入口qwen3/training/attention_ten_case_20261031/REMOTE_AGENT_PLAN_ZH.md，交接work/rayggxia/220。用户确定5种无筛选方案及5个SparQ配对、P8阈值/8位sigmoid入口、传统稠密逐节点Gibbs。设计建议QKV/O-only更新943718400权重、两条匹配数字控制、100M上限和准确前缀/概率后缀；其余参数冻结但保留反向图。

10组矩阵/P8表及5个错误配置拒绝检查通过；三个小分数行的6项精确稳态和72项人口广播/稠密等价检查通过。仅本地设计/数值合同验证，无LLM训练/GPU/Slurm/RTL/PPA。实际训练器和原optimizer/LR/data源配置仍待对方接合，不把已有参考当即用runner。发布以同目录PUBLICATION.json和Issue220回执为准，不自动合并，Projects待维护者同步。已有其他任务记录原字节保留。

## 2026-10-29 Issue204：用户要求继续SRAM存内比较主架构

双随机结构继续SRAM驻留、本地SNG并行比较，阵列输出随机权重bit；不默认搬整组权重到DFF，不默认每采样走普通窄口完整读。两颗全局LFSR32（输入一颗/权重一颗）、T32/8×4与原共享尺度保持；P8输入/P7权重各需5位抖动。ICG DFF及普通宏预读保持仅作对照。已更新12方案页，新增13_SRAM存内比较估算口径与证据.md并同字节同步根阅读镜像。

历史框架可以延续：真实宏库/尺寸/面积/保持与装载＋SRAM邻近标准单元SNG/驱动表征＋存储节点带载接口增量。旧四32×144宏2.25KiB、576bit预读Q保持不是完整64×64存内比较；S0–S5保持/读写有原件但CE关闭动态缺表/hold/XZ边界限制保留。Issue146实际N64/M1/seed17/T32数字前端SS100MHz115.3µW、340ns/39.202pJ，含一颗LFSR/输入比较/固定W门控，不含物理SRAM，功耗表告警保留；不可直接当新W-SNG价格。真实定制存储位/位线比较尚未表征；新最小探针应是7幅值存储位+W7比较/必要隔离，旧模板只有bitcell/AND/BUF。不能将缺接口能量填0，或每拍重复收费全普通读；按真实本地模式收费。普通宏外围也不能任意扣除成裸cell成本。

只读核实Issue146与本机原件；旧source508bdaa4当前workspace GitHub ref404，未伪造远端可见、不重跑/接管其任务。源码/证据阅读SHA见SRAM_CIM_VALIDATION.json。rayggxia继续Issue204/PR209/task/204-bf16-baseline，源基线06b14a96fef58533c5af85851a2a6eae17d07aee；本轮仅合同/历史证据整理，无新RTL/EDA/SPICE/PPL，不新增run，完整根union保留。实际发布见SRAM_CIM_PUBLICATION.json，PR待审未合并、Projects待维护者同步。

## 2026-10-29 Issue204：用户指定输入/权重各一颗全局LFSR32

用户进一步明确：全部输入共用一颗LFSR32，全部权重共用另一颗LFSR32，分层计数器独立生成层号。主候选据此固定，连接独立只作数学精度对照，不按每连接完整PRNG计成本。P8输入/P7幅值权重且8×4时，仅各需5位格内抖动；两颗32位状态共64位、单5位格计数器合69位（不含概率/权重保持、累计和广播）。T64/128/256分别5+4、4+4、4+3位抖动。只广播所需低位与层号，不把32位全部拉给比较器；K64/M输出仍有64个X-SNG及64M个W-SNG。

先单乘法T32/64/128/256，再64对乘累加与M输出复用；当前只是用户方案记录，未启动实现/EDA/模型。两轴不同非零seed、实际抽头/反馈与短窗联合/时间相关性、帧间连续推进另验；普通LFSR5缺零/31周期不能直接替代32值均匀抖动。全局共享改变点积协方差，不能继承连接独立PPL；先精确归约、OR4单列，原尺度不改。已更新功耗面积目录12方案页并逐字同步根镜像，不新增run、旧台账不改。rayggxia，Issue204/PR209、task/204-bf16-baseline，源基线f5d22ac4470c9a423bbba238994957f1a4491cd0；本补充发布见TWO_LFSR_PUBLICATION.json，PR待审未合并、Projects待维护者同步。

## 2026-10-29 Issue204：双随机双轴分层架构分析（未启动EDA）

用户要求保持输入及权重各自共享尺度，思考两侧随机比特流、双分层（非DS-CIM互斥映射）及待评估模块。已只读核实PR207@05d7d986的尺度合同/dual_gu数值参考：x每64共享原四档PoT、W每64×64共享PoT LSB，码[-127,127]不变、pW=abs(q)/128；T32沿已有8×4联合格，非32²拍。原数值参考W按连接独立，硬件分组/列共享改变协方差，不能继承PPL。未修改Issue201/206源码、模型/尺度默认或运行其他任务。

方案入口digital_circuit_simulation_registry/12_双随机分层矩阵架构评估计划.md，论文与项目Git blob在references/dual_stochastic_20261029/SOURCES.json，根镜像两文件同字节。主候选一套signed popcount64+13位累计，OR4近似分支popdiff16+11位累计，均为每输出一个状态而非每权重位平面一套；9/10位饱和另验。双分层不会消除OR碰撞：4个相同pX=pW=.5共用二维点时，精确和1、OR4仅.25，手算/32格枚举一致，非新电路仿真。两侧SNG可拆高层判断/低5位边界比较；收益待测。必须计2D调度/真实抖动分发、X8/W7比较、驻留SRAM/ICG DFF、符号AND、归约/累计、组间PoT对齐舍入及M扩展广播，不能把旧69pJ除6当新功耗。

DS-CIM、DATE2017 Sobol、ICCAD2018 LD、uGEMM及Frontiers2023一手正文已读；原生方案与论文映射/条件推进不同。当前仅分析建议，不预设T32精度/能效，不新增run、无新RTL/PPA/模型/PPL，全部旧record字节不改。建议先同尺度/同事件数数值与共享拓扑消融、再功能和同PVT集成PPA；未自动启动这些后续实验。rayggxia，继续Issue204/PR209/task/204-bf16-baseline、复用原checkout；文稿科学源69f1503894becdddbb1440bd2d24ed2d43b237f5已推送PR209，10文件tree与3关键内容/blob读回一致；回执见DUAL_PLAN_PUBLICATION.json；PR待审未合并，Projects沿既有限制待维护者同步。

## 2026-10-29 Issue204：功耗面积文件夹补齐模块长期索引

用户要求把此前模块的功耗、面积、时钟及具体文件地址统一整理，避免遗忘。已在digital_circuit_simulation_registry新增11_矩阵与算术模块功耗面积时钟索引.md及summaries/20261029_matrix204/MODULE_INDEX.json、MODULE_MODES.csv，覆盖Issue204六批66配置/209运行模式：四档首轮8、单尺度16、参数模块33、BF16五核、四lane INT8两核、64路INT8两核。固定读取提交4175c5565fcd714b0648d97a15c1697b5fbcee05；6源汇总/源码逐字及66原始报告归档SHA核验，保留每项活动/idle、raw与×.81等效面积、100MHz/10ns、操作定义/平均周期/原生延迟和II（未知留空）、STA负值/告警、源码Git地址与本机绝对原件路径。旧04页保留原始表值并加新入口和面积口径说明，README补导航。

同3份新文件已逐字同步根阅读镜像；各自README/04原有内容保留，旧record字节不改、不用67条任务子集覆盖89条完整根union。无新EDA/模型/PPL、不新增run。复现build_power_index.py，核验POWER_INDEX_VALIDATION.json；未来新增模块需同时更新中央run与阅读索引。rayggxia，继续Issue204/PR209、task/204-bf16-baseline，复用tmp/matrix-t32-issue204-20261028；本补充科学源4207651c9cfd2cbabfc4c3572a83e21e07d25998已推送PR209，13文件tree及5关键内容/blob读回一致；回执见POWER_INDEX_PUBLICATION.json；PR待审未合并，Projects待维护者同步。

## 2026-10-29 Issue204：按用户要求完成同64路并行INT8对照

rayggxia，task/204-bf16-baseline / PR209（base main），复用tmp/matrix-t32-issue204-20261028；执行base158e489816bde1547d07cd3f9e377b809055f63f+明确未提交冻结快照。用户澄清重点为整体面积/功耗、要求同SC的64路物理输入并行度，主比较已改为64个动态signed8×8并行乘法+六级平衡树+32/22位结果寄存，不以四路复用替代。旧四路/BF16/SC原件完整保留。正式入口architecture_tlm/int8_parallel64_20261028/results/REPORT_ZH.md与FINAL_SUMMARY.json。

SS1.08V125℃100MHz，面积raw×.81一次。64路32位结果：raw34842.96µm²、等效0.028222798mm²；满速2.126333mW/21.2633pJ每完整N64点积，原生1拍结果、II1=10ns；每35拍接受一帧且100MHz时钟自由运行时0.1148mW/40.1800pJ。22位结果raw34756.92µm²、等效0.028153105mm²，满速2.118333mW/21.1833pJ，同35拍0.108933mW/38.1267pJ。固定N64无bias的22位精确，非任意K累加器，外部均32位；综合高符号位复制/合并，缩位面积差约0.247%。

同原SC54操作数匹配：从原ZIP恢复X/W并逐项SHA核验，每帧W行f%8、absW上限127、X原signed8。SC54原0.0055240704mm²、0.198466667mW、69.4633pJ/350ns。相同64并行度SC面积小5.109倍、各自满速功率低10.714倍，但数字原生吞吐高35倍、满速能量低3.267倍；同350ns完成工作率下SC能量/功率为数字1.729倍。可以支持同64路SC面积优势，不能宣称目前SC相同工作率能耗优势。SC OR4/T32/去LSB近似、数字精确，合成输入匹配不等于模型质量匹配；无新模型/PPL。

最终两top/三seed各164事务，984 RTL及984映射门级输出逐项oracle/四态valid通过，24PT窗口mapped端口/leaf活动100%。v1另24窗口已算出但hold−.061165ns，原件保留；v2核验源/配置/库绑定/原网表后，DC原生hold-only实际插buffer，每核面积仅+raw1.44µm²（等效1.1664）。不重编译算术/retime、不放宽约束；最终setup/hold：32位1.429668/.032151ns，22位1.881098/.027525ns，parser flags空。数据delay1/.02ns、slew.05、load20fF、uncertainty.5/.05，reset4.5..5.5ns释放，无false/multicycle。无CTS/SDF/SPEF/完整毛刺，不是物理签核。

两执行ZIP/8报告/24传输文件/全部成员SHA已核验；准确作业与命令RUN_LEDGER，v2manifest f39df885a073d53ac9c5a7584d78e97906122722b29664ba0155f8e6cd434c8d，原件project_archives/matrix204_parallel64_20261029，私有配置/SDC/库模型指纹单列EXECUTION_FINGERPRINTS。Slurm38447564/38447584/38447776/38447785及两只读DC命令帮助作业均COMPLETED/0:0，不重交。权重/概率存储、SRAM/RNG/比较器/格式/真实广播/ICG仍在核边界外，paced不称最佳数字门控能量。

中央run matrix-int8-par64-204-20261029，任务分支67、完整本地根镜像89，分别保留原66/88个record字节并check/render，不以小子集覆盖全union。新run原件/成员全可访问；历史不可达项见LOCAL_REGISTRY_CHECK.json。科学源48be94077e14a668be0633d44a8dbc7694e505e3已推送PR209，47文件tree及8关键内容/blob远端回读一致；实际回执见同目录PUBLICATION.json；PR待审未合并，Issue保持open，Projects连接器不支持写待维护者同步。

## 2026-10-28 Issue204：经典INT8本工艺结果及SC面积质疑复核

rayggxia，task/204-bf16-baseline / PR209接续，基线6435de8854d8ddb93375e03085ed1eea9c3f9002，复用tmp/matrix-t32-issue204-20261028。用户明确要求按成熟参考计算INT8，随后质疑“无论怎样SC面积肯定更小”；已核查源/映射库存，不根据期待反改结果。入口architecture_tlm/int8_classic_ppa_20261028/results/REPORT_ZH.md、AREA_EXPLANATION_ZH.md及完整SUMMARY。

经典四lane signed8×8→16位乘积寄存→17/18位平衡归约→输出驻留累加；INT32主参考和固定N64无bias精确INT22。一帧64项点积一个输出，不是64×64全矩阵。三seed216完整帧+6 reset中断功能与对应门级通过，18PT窗口全映射leaf/端口活动核验；matched48帧来自BF16原INT8派生数据，整数结果/128与BF16/FP32逐位同值。无新模型/PPL。

SS1.08V125℃100MHz：INT32 raw3825.36µm²、等效0.003098542mm²、0.2151mW、40.869pJ/帧；INT22 raw3621.96µm²、等效0.002933788mm²、0.207mW、39.330pJ。正常18拍valid/19拍帧间隔=180/190ns；位宽收缩省5.32%面积/3.77%能量，不截断有效结果。setup/hold分别3.082494/.082897ns与3.299786/.082897ns，parser未列警告。前布局无CTS/SDF/SPEF，不是物理签核。

面积复核：SC54寄存器77个/449.064µm²，组合1860个/5075.006µm²，总5524.070µm²；INT32寄存器109个/785.279µm²，组合793个/2313.263µm²，总3098.542µm²，全部已乘.81一次。SC寄存器更小但六平面并行符号/OR/计数/累加/恢复组合网络更大；整数只4个乘法器复用16拍。两核都未放整组权重/概率存储，未发现因漏权重DFF或双乘.81导致排序。旧64路全并行INT8约0.04621mm²确实比SC大，但20ns帧间隔不同；N64问题长度不等于物理并行度，不能宣布SC所有实现必然更小，也不把当前SC54称面积下界。

当前粗比SC54相对四路INT32面积1.78倍、能量1.70倍、帧间隔1.84倍，不能支持相对INT8已有巨大优势。对同批数值BF16556.2pJ参考，INT32能量低13.61倍、面积低14.50倍。SC输入/近似精度不同；SRAM、供数、随机源、格式与广播/时钟边界未闭合，不宣布整片胜负。未来可优化SC符号/计数路径，但需独立质量与PPA，不因用户直觉覆盖负结果。

v1/v2门级X失败保留，v2去重定时仍失败，故不能归因于重定时本身。波形定位同步reset时控制计数LSB停留X；v3真实异步控制reset、同步sum、valid保护无reset产品寄存，v4相同电路强化四态ready/valid拒收后完成门级/PPA。数据delay1/.02ns、slew.05、load20fF、uncertainty.5/.05；reset下降沿附近4.5..5.5ns释放与BF16补充契约相同，未加false/multicycle、未force初值、未改库模型。最终set_fix_hold core后compile_ultra，不重定时。

4执行ZIP/14报告/42传输文件和成员SHA核验，配置/SDC/库模型指纹单列EXECUTION_FINGERPRINTS；准确作业见RUN_LEDGER。v4 manifest6523fbde32b9d8cad460f09f1ccf9892466788071fc20aa37a931d86d507255f。实际执行为base6435de88+未提交冻结快照，不伪造执行提交。原件project_archives/matrix204_int8_classic_ppa_20261028，本轮无运行作业；私有控制器不发布。

中央run matrix-int8-classic-204-20261028，任务/完整根镜像各自增量union check/render，准确数见REGISTRY_CHECK。旧record字节保留，不用任务子集覆盖全镜像；本run所有产物可访问，旧94路径仍不可访问。科学源fe060b5a26bfa5281b8a61b353cb8b5bd33f47d9已推送PR209，49文件tree及8关键内容/blob远端回读一致；准确回执见同目录PUBLICATION.json；待审未合并、Issue保持open，Projects工具不支持写待维护者同步。

## 2026-10-28 Issue204：成熟BF16本工艺N64 PPA完成，INT8经典划分已核对

rayggxia，task/204-bf16-baseline / PR209接续，源起点99bf019c。用户明确要求按经典流水划分做本工艺PPA，再查INT8；这是新授权，已实际运行EDA，不沿用上轮“无EDA”的历史结论。复用tmp/matrix-t32-issue204-20261028，未接管Issue107。结果入口architecture_tlm/bf16_ppa_20261028/results/REPORT_ZH.md、FINAL_SUMMARY.json及INT8_CLASSIC_ZH.md。

CVFPU77811635/common_cells9afda9ab精确上游，BF16×BF16/FP32乘加及独立乘/加；四lane非融合DOT4树+四FP32交错上下文，N64正常29拍valid、帧间隔30拍=300ns。五top45个三seed窗口、27696标量+108整帧功能比较及对应门级回放已完成；48个INT8派生帧另用Fraction精确点积核验。合成数据，无模型/PPL；不称单轮舍入fusedDOT4或最佳生产矩阵引擎。

N64原始面积55454.76µm²，raw×0.81等效0.044918mm²，normal平均1.923333mW、577.000pJ/完整64项点积；INT8派生输入556.200pJ。相对SC54(0.005524mm²/69.4633pJ/350ns)约8.13倍面积、8.31倍能量，SC帧间隔长16.67%。这是异精度/不同合成激励的计算核对照，不能宣称整片或同质量优势；既有INT822.19/38.80pJ仍比SC省能。

原共享reset0.02..1ns约束导致async removal负余量。相同SHA网表补充STA明示下降沿附近4.5..5.5ns释放，数据约束不变、无false/multicycle，N64setup/hold 0.000027/0.143288ns；四独立标量en→valid仍−0.061165ns hold，未修复。功耗表范围、高扇出和极小setup余量保留；无CTS/SDF/SPEF或复位分配实装，不称物理签核。

v1..v7负结果/源包/原始报告保留，原字节、远端SHA和全部报告成员核验。v6标量完整，v6 N64仅TB time变量裁剪失败；v7只修波形裁剪并核验全部RTL/bench/fixture/库绑定/约束后复用相同网表，未重综合。补充STA独立冻结。执行是base99bf019c+uncommitted快照，后续源码提交需按ZIP逐字绑定，不伪造执行提交。准确批次见work/rayggxia/204/bf16_ppa/RUN_LEDGER.json；本轮作业已结束，不重交。

中央run matrix-bf16-204-20261028；分支与根镜像分别向各自最新record集合增量登记，旧record字节均保留，绝不用分支子集覆盖完整镜像。准确数量、check/render及原件校验见REGISTRY_CHECK.json。科学源5d21923c7dc7268e2cb19cf393bd858dc3dfb52b已推送PR209，70文件tree与8关键文件内容/blob回读一致；实际回执见同目录PUBLICATION.json。PR待审未合并、Issue不关闭，Projects沿既有限制待维护者同步。

INT8经典实现采用signed8×8→16位积，output-stationary INT32反馈累加，或DOT4/8平衡树后累加；固定N64无bias最坏范围可用22位精确，但可复用长K/带bias经典基线应保留32位，再把22位列独立消融。Gemmini/NVDLA一手源码/文档已核查；推荐100MHz先用乘法级+累加级，是否树内增级交STA决定，无新INT8 PPA冒称。

## 2026-10-28 Issue204：已找到完整28nm BF16数字阵列功耗证据

rayggxia，task/204-bf16-baseline / PR209接续，源起点d6aa128997072acd837508c7703844bf950603ec。用户要求确认是否没有28/55nm BF16数字矩阵依据、缺乏时再自建仿真。二轮已找到MFSA完整正文和FlexBlock作者PDF，纠正首轮检索不足；两原PDF及表II/V原图已下载、SHA绑定、渲染核对。当前入口architecture_tlm/bf16_baseline_20261028/README_ZH.md、LITERATURE_RECHECK_ZH.md及literature_recheck.py。

MFSA2026-10-14预印本：28nm SS0.72V/125℃/1GHz，16×16全格式数字阵列，BF16输入/FP32累加；后布线RC+LLM门级轨迹稳态估算1.85W/1.024TOPS，排除reset/预装/排空。两op/MAC由256PE×两项×1GHz核验，得3.61328pJ/MAC、231.25pJ/64MAC；对SC54核69.4633pJ为3.329倍，仅异工艺/异精度/异边界归一，非N64冷启动延迟或整片节能。原73pJ摘要换算保留低完整度版本，不作为唯一参考。

FlexBlock作者文件头为2203.06673v1：65nm BF16 SA128×128、333MHz、9.84W、1.77TFLOPS；P/T约711.59pJ/64MAC，但吞吐只占乘法器理论峰值16.22%，属含利用率/周期模型的负载归一，不能据此宣布10倍优势；SRAM另CACTI。外部65nm面积不套本项目0.81。55nm严格同PVT/数据/接口仍未找到已核验匹配项，不断言不存在。

有了可用28nm参考，用户“确认没有才自建”的条件未成立，本轮未启动新RTL/EDA/Slurm/GPU/PPL，中央台账84条不变。后续本工艺表征仍是独立工作，不冒称已测。实际追加提交/回读见work/rayggxia/204/bf16_baseline/LITERATURE_PUBLICATION.json；PR209待审不合并，Projects沿既有限制。

## 2026-10-28 Issue204：BF16数字基线调研与可复算预算
发布切换：原PR205已于2026-10-28T10:51:05Z合并；本BF16补充改用task/204-bf16-baseline，基于main@7874891，准确新PR查PUBLICATION.json。原成果不重跑。

rayggxia，同task/204-matrix-t32 / PR205，复用tmp/matrix-t32-issue204-20261028；本轮读取既有证据及一手论文，无新RTL/EDA/Slurm/GPU/PPL，中央台账84条不变。结果architecture_tlm/bf16_baseline_20261028/REPORT_ZH.md及ESTIMATE.json；estimate.py核验旧SS/TT两份summary SHA、三seed单位和负时序，绑定旧RTL，重算预算。

主比较合同BF16×BF16、FP32累加。28nm Li等TCAS-II论文作者机构摘要可核实1761.41GFLOPS/W；条件按2 FLOPs/MAC为1.13545pJ/MAC、64项72.6691pJ，非55nm已测事务，全文累加/舍入/FLOP计数/面积/N64延迟未核验，不按工艺或0.81换能量。与本SC54计算核69.4633pJ接近，不能据此宣称巨大节能。SC需数字>1.08536/5.42682/10.85365pJ/MAC才分别持平/5倍/10倍，均未计两侧缺失前后端成本。

旧本工艺BF16标量KIND2在SS100MHz setup−26.219376ns、TT−10.537953ns；原731输入/5变长帧不是N64。其通用转换和26次依赖规格化循环值得优化，但未做新网表关键路径归因，不能用旧失败实现代表成熟基线。建议补专用乘法、树LZC FP32加法、融合MAC、共享处理DOT2/4/8与真实N64反馈/归约封装，验证35拍/350ns附近预算；两个算术lane不自动保证32拍。旧原件保留，不接管Issue107；BF16与SC W8/T32/OR4精度不同，匹配量化数字控制仍需保留。

研究稿/脚本本地完成；实际推送状态查work/rayggxia/204/bf16_baseline/PUBLICATION.json和PR205，不宣称新BF16 PPA已完成。Projects沿既有限制待有权限维护者同步。

# Issue204：参数化模块能耗完整交接（2026-10-28）

rayggxia；task/204-matrix-t32，同PR205，base main@d83eeb1fc6b89a3dff51b5b62bf79acf665c7166。执行基线9f762ced3d25b47bf3963fbf38ff8d321850854b；复用tmp/matrix-t32-issue204-20261028。新目录architecture_tlm/module_energy_20261028，不改旧冻结PPA或模型/整机默认。

用户授权测试不同输入/输出精度popcount和不同位宽移位相加，补时间累计器与组合验证估算边界。33个固定top全部VCS功能PASS，99次RTL回放/162396逐周期比较；另完成对应门级回放和396个PT窗口（3seed×sparse/dense/replay/idle）。全部所报setup/hold非负，最小2.643270/0.007787ns，功耗表范围警告保留；无CTS/SDF/SPEF。

关键结果：pop8/16/32/64 full输出dense单次0.05251/0.09941/0.19720/0.39630pJ；pop64少一个输出LSB面积只降约0.54%、dense能量约1.20%。9位饱和累计4.8554pJ/33拍（清零+32次）；六平面9位固定恢复1.3190pJ/35拍驻留一次。77/54/50状态位组合分别84.6883/69.4633/67.9817pJ/35拍，55nm等效面积6647.90/5524.07/5447.09µm²；54→50只省2.13%能量，48点积相对OR基线额外NRMSE0.969%→1.538%，非模型质量。

未经校准的独立模块和对bank高估约23%、对单平面约26%–27%；统一独立端口20fF与内部连接负载不同，且有相关性/综合/控制差异。用bank54校准后预测bank50，三seed最大绝对误差0.637%，仅是N64/同输入的位宽配置留出验证，不能宣称跨规模/全芯片普适误差。popcount+恢复树两项不足；必须补mask/OR、累计器、时钟/控制、调用次数与组合校准。共享输入计数属于随机输入量化+数字后端的独立对照，不能冒充本OR4路线收益；匹配确定量化数字参考仍待独立开展。

V1 manifest f454a321，349归档成员：旧Python不支持Path.write_text(newline=...)，38441318共33任务在EDA前失败，全部日志保留。V2仅修复driver，manifest cb9fb058b35c723970752bde9fd4e6ee4496808b2a380ad626e899c68ef5b8da，350成员。成功Slurm38441385功能、38442559四类pilot、38442655其余29类（全量4并发）；无遗留任务，勿重交已完成33/396。Windows Icarus DLL错误623导致本地功能工具不可用，pyslang0错225警告，实际功能门禁来自服务器VCS。

67报告归档、2源包原字节、远端/本地大小SHA和全部成员SHA已核验，stable project_archives/matrix204_module_energy_20261028。报告/完整JSON：architecture_tlm/module_energy_20261028/results；执行索引EXECUTION_INDEX.json；传输TRANSFER_VERIFICATION.json；中央新run matrix-modules-204-20261028，84条union check/render、83旧record原字节保留。源码和结果已推送，科学源080729c314e2e0e62efada3e32d4c27c7eac4bb5，68文件完整tree及10关键回读核验，实际回执PUBLICATION.json；PR205待审未合并，Projects既有权限限制待维护者同步。

边界：组合top没有人为I/O寄存器；顺序top含真实计数/控制/结果寄存器，CE非ICG。bank为预解码7幅值位W和乘积符号，abs(W)显式限127；SRAM/概率保持、RNG/比较器、编码/符号预处理、物理广播、最终格式恢复在外。pop缩输出位是丢LSB、单位2^DROP；固定移位与可变对齐分开。非16 pop的replay为IIDp=.35，align replay为随机字，其余由旧M8合成回放派生，均不是模型数据。原PT samples字段0为占位元数据错误，派生表按stim en补32样本/帧，原始字节不改。

后续：先用这组数据估相同接口/频率/负载附近的算术配置，扩大输入规模时补signed-popcount/增量宽度（当前累计器D6只对应OR后16路），并做新组合校准；新存储/随机前端/真实ICG/物理连线独立补齐。报告不按状态位比例推功耗，不把纯算术表当整机PPA，无新PPL/GPU。

---

# Issue204：计数器缩位分析（2026-10-28）

负责人rayggxia，沿用task/204-matrix-t32和PR205，base main@d83eeb1f。分析基线a288901fa783277a134bf7052e49d4e09437308f；既有EDA科学源5dcef4fd99200418f804cbd51f3bf325d1cbea60。独立目录architecture_tlm/matrix_counter_precision_20261028，不修改单尺度或四档冻结执行输入。

用户要求统计32拍各权重位平面累计，研究饱和/截断和低位舍弃，查论文是否必须全按最大值位宽。本轮只做冻结合成数据的数值回放与一手论文核查，不新跑模型、RTL/DC/PT或改变台账83个硬件run。BF16复跑/模型语料字段不适用：未做模型推理/PPL比较；Issue206只读权重量化合同和已封存源码成员SHA，不继承其质量或PPA。

已完成：功耗432输出、功能432输出全部独立重构等于原OR oracle，60个原始输入SHA核验；主M8统计384输出、24条驻留W行，各32拍。B0–B6平均绝对累计53–58、99分位166–220；B7平均1.36、最大32。9位饱和额外NRMSE0.242%；B0–B6用9位、B7用7位为70位状态；删除B0后61位、额外NRMSE1.063%。均以原OR输出RMS归一，不是模型准确率。全8位饱和10.681%、回绕74.642%，负面结果与极值功能退化均保留。64位混合校准例在seed1009留出误差1.072%，尚非模型候选验收。

理论修正：严格signed [-512,512]需11位，但10位只在最后一拍+512缺1；每平面误差≤1、8平面加权原始误差≤255。固定权重支持Gp个OR4组时，精确计数范围±32Gp，可依位平面进一步收紧。逐拍饱和不等于帧末饱和；截计数LSB会丢失逐拍小增量，相关断言已通过。

论文：REX-SC §II-C明确6位饱和对照；SC-DCNN §4.1/Fig7近似并行计数（非直接缩时间计数）；DS-CIM §III-D四拍latch缓存后更新宽累加器。原文链接和适用范围在SOURCES.json/REPORT_ZH.md，不把论文PPA移植成我方收益。Issue206冻结aa43d00d的PoT量化clamp(-127,127)，7个幅值平面；仅在采用这一接口后B7可无损删，不改旧完整INT8边界。

成果REPORT_ZH.md、RESULTS.json、MANIFEST.json、WEIGHT_CONTRACT_REFERENCE.json；复现命令python architecture_tlm/matrix_counter_precision_20261028/analyze.py、report.py。分析已推送，科学源904068b9e70bab558f93c93ff2c230216164cf51；13文件完整tree与6关键回读核验，PR205待审未合并；回执PUBLICATION.json。无新服务器作业；Projects既有权限限制待同步。

后续建议：11位精确对照，10位保守端点饱和，9位/低位删除候选；先补真实权重/激活分布和独立模型质量，再按同条件RTL/DC/PT测饱和与门控成本，不按状态位数直接推功耗。不要重跑已完成96窗口或启动昂贵模型任务。

---

# Issue204 单尺度INT8完成回执（2026-10-28）

发布确认：单尺度科学源5dcef4fd99200418f804cbd51f3bf325d1cbea60已推送PR205，217文件完整tree与8关键逐字/blob回读通过；Issue204正文已同步，PR ready/open未合并，本任务无遗留作业。

负责人rayggxia，task/204-matrix-t32，PR205 open/ready/unmerged，base main@d83eeb1fc6b89a3dff51b5b62bf79acf665c7166，科学输入基线cc04dee9890ea6dcfbeee872b0cab914d3b1c2c6。本地目录tmp/matrix-t32-issue204-20261028。沿用原Issue/PR，不改旧四档冻结输入、其他任务或整机/模型默认。

用户决定：64路共用一个尺度、真正signed INT8[-128,127]、N64/T32；每幅值位平面和符号先OR4，64→16个事件，再做精确并行计数。实现3版：V1直接实现；V2把每组正负各6位改为一个signed7时间计数；V3使用专用无符号popcount并隔离末端恢复输入，保留signed7组计数。mode3每拍popcount16再时间累计；mode6每组独立累计后求和，二者同事件OR oracle全等。SC内部20位，数字22位，输出符号扩展32位。

全部完成：V1 672帧、V2 96帧、V3 288帧，共1056帧功能PASS；16个综合变体、96个active/idle PT窗口，SS1.08V125C100MHz。3原始执行包和22报告归档远端/本地SHA/大小及逐成员校验；Slurm全部COMPLETED/0:0，本任务无遗留作业。执行索引EXECUTION_INDEX.json，结果architecture_tlm/matrix_single_scale_20261028/results/FINAL_SUMMARY.json和REPORT_ZH.md；源包/报告在project_archives/matrix204_single_scale_20261028。不得重复昂贵测量或改写冻结输入。

M1：精确树179.906pJ、OR4-popcount16优化版101.932pJ（能量-43.34%、面积-16.51%），16路signed7独立时间累计优化版348.483pJ；数字位串行38.797pJ。M8优化OR4 790.767pJ/帧、数字位串行262.133pJ/帧，每帧8点积。还不能证明SC能效胜数字。共同尺度省去bin选择/移位，但新旧码域、刺激及位宽也改变，不能作纯尺度消融归因。

主PPA为16帧驻留权重、uniform signed INT8输入、公共R8，三seed均值；SC原始期望=数字点积/4。OR损失另报，时间计数硬件改动不改变OR结果；真实模型单尺度质量未验。面积raw×0.81保留双列，不缩放功耗/时间。外部权重存储/保持读口、RNG/比较器、输入量化/尺度选择、最终浮点恢复、物理广播线及CTS/SDF/SPEF在外，CE未冒称ICG。全部时序与功耗警告保留。

中央新run matrix-single-scale-204-20261028，增量union check/render并保留其他record；结果见REGISTRY_CHECK.json。源码/结果已推送，科学源5dcef4fd99200418f804cbd51f3bf325d1cbea60；发布回执见PUBLICATION.json和最新PR205。Projects既有权限限制仍待维护者同步。下一步审阅计数实现、hold/功耗表告警；真实ICG、SRAM驻留端口及真实后训练模型同质量验证独立开展，不自动启动昂贵模型实验。

---

# Issue204：T32矩阵改进验证

更新时间2026-10-28；负责人rayggxia。分支task/204-matrix-t32，PR base main@d83eeb1fc6b89a3dff51b5b62bf79acf665c7166；独立目录C:/Users/86134/Documents/a_P_BIT/tmp/matrix-t32-issue204-20261028。未修改Issue193/186源码或其执行快照。

本地首轮完成：六算法×M1/M8×三seed×15帧，v1/v2各540帧VCS功能通过；8个固定top完成综合、门级及48个SS1.08V125C100MHz PT窗口。恢复时队列已空，不重交EDA。27原始报告归档远端/本地SHA/大小与逐成员SHA均核验；9个执行包原字节保存。报告architecture_tlm/matrix_validation_20261028/results/REPORT_ZH.md及FINAL_SUMMARY.json，精确执行/终态见work/rayggxia/204/EXECUTION_INDEX.json。已推送PR205（ready/open、待审未合并），科学源f19b603578ba215433ae68809c7eed3f30c7bf55；144文件完整tree与本地一致、8关键文件逐字/blob回读通过，回执work/rayggxia/204/PUBLICATION.json与REMOTE_VERIFICATION.json。

M8共享输入计数相对S0：1331.137→479.067pJ/帧（−64.01%），174255.20→168423.79µm²（−3.35%），37→40周期（+8.11%）。M1位平面省能16.88%、面积多37.80%；M1先计数反而多耗能18.40%。普通OR4共享源同号同位权例低估75%。D1确定位串行34.467pJ/帧、11周期、22054.00µm²，低于M1 S0的165.994pJ/帧；尚未证明随机整体胜数字，M8数字同规模尚待扩展。

面积均已按用户要求raw×0.81并保留原始列。S0两尺寸hold−0.041792ns；S2 M8 setup仅0.000099ns，功耗表范围等警告保留。前布局，无CTS/SDF/SPEF、真实模型质量、存储/RNG/比较器/编码/最终浮点尺度及实际广播线成本。D0是未优化q9参考，不称成熟最佳INT8。SRAM/门控权重与内部位宽收紧属于后续，不伪称本轮全链路完成。

中央台账新增matrix-t32-204-20261028，82记录联合check/render、81旧record逐字保留；main缺全台账，本PR只交付增量record及校验回执，不复制别人记录。失败波形/别名/调试可见性版本保留；v3旧数字后处理实际已跑1分34秒后取消并由v9替代，如实记录。Projects既有权限限制待同步。下一步：审阅本轮PR，修hold/功耗表范围，M8数字控制、SC位宽/真实ICG及驻留权重端口验证；不自动启动新模型或昂贵作业。
