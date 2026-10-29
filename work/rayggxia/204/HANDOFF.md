## 2026-10-29 Issue204：双随机双轴分层架构分析（未启动EDA）

用户要求保持输入及权重各自共享尺度，思考两侧随机比特流、双分层（非DS-CIM互斥映射）及待评估模块。已只读核实PR207@05d7d986的尺度合同/dual_gu数值参考：x每64共享原四档PoT、W每64×64共享PoT LSB，码[-127,127]不变、pW=abs(q)/128；T32沿已有8×4联合格，非32²拍。原数值参考W按连接独立，硬件分组/列共享改变协方差，不能继承PPL。未修改Issue201/206源码、模型/尺度默认或运行其他任务。

方案入口digital_circuit_simulation_registry/12_双随机分层矩阵架构评估计划.md，论文与项目Git blob在references/dual_stochastic_20261029/SOURCES.json，根镜像两文件同字节。主候选一套signed popcount64+13位累计，OR4近似分支popdiff16+11位累计，均为每输出一个状态而非每权重位平面一套；9/10位饱和另验。双分层不会消除OR碰撞：4个相同pX=pW=.5共用二维点时，精确和1、OR4仅.25，手算/32格枚举一致，非新电路仿真。两侧SNG可拆高层判断/低5位边界比较；收益待测。必须计2D调度/真实抖动分发、X8/W7比较、驻留SRAM/ICG DFF、符号AND、归约/累计、组间PoT对齐舍入及M扩展广播，不能把旧69pJ除6当新功耗。

DS-CIM、DATE2017 Sobol、ICCAD2018 LD、uGEMM及Frontiers2023一手正文已读；原生方案与论文映射/条件推进不同。当前仅分析建议，不预设T32精度/能效，不新增run、无新RTL/PPA/模型/PPL，全部旧record字节不改。建议先同尺度/同事件数数值与共享拓扑消融、再功能和同PVT集成PPA；未自动启动这些后续实验。rayggxia，继续Issue204/PR209/task/204-bf16-baseline、复用原checkout；文稿本地完成，实际发布见DUAL_PLAN_PUBLICATION.json；PR待审未合并，Projects沿既有限制待维护者同步。

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

## 最新：参数化模块能耗库已发布（2026-10-28）

科学源080729c314e2e0e62efada3e32d4c27c7eac4bb5，同PR205待审。33配置/396窗口/99功能回放完成，67报告/2源包核验。恢复优先读module_energy/HANDOFF.md和architecture_tlm/module_energy_20261028/results/REPORT_ZH.md。无本任务遗留Slurm，旧位宽/单尺度结果如下保留。

---

## 最新：OR4计数位宽分析已发布（2026-10-28）

科学源904068b9e70bab558f93c93ff2c230216164cf51，同PR205，数值统计/一手论文核查，无新RTL/PPA。恢复先读counter_precision/HANDOFF.md与architecture_tlm/matrix_counter_precision_20261028/REPORT_ZH.md。原单尺度PPA和旧四档如下保留。

---

## 最新：单尺度INT8后续已发布（2026-10-28）

科学源5dcef4fd99200418f804cbd51f3bf325d1cbea60，同PR205待审未合并。新16核96窗口/1056帧、22报告/3源包已核验，83条台账联合检查通过。详细交接见work/rayggxia/204/single_scale/HANDOFF.md；旧四档结果如下保留，恢复应优先读单尺度交接。

---

# Issue204：T32矩阵改进验证

更新时间2026-10-28；负责人rayggxia。分支task/204-matrix-t32，PR base main@d83eeb1fc6b89a3dff51b5b62bf79acf665c7166；独立目录C:/Users/86134/Documents/a_P_BIT/tmp/matrix-t32-issue204-20261028。未修改Issue193/186源码或其执行快照。

本地首轮完成：六算法×M1/M8×三seed×15帧，v1/v2各540帧VCS功能通过；8个固定top完成综合、门级及48个SS1.08V125C100MHz PT窗口。恢复时队列已空，不重交EDA。27原始报告归档远端/本地SHA/大小与逐成员SHA均核验；9个执行包原字节保存。报告architecture_tlm/matrix_validation_20261028/results/REPORT_ZH.md及FINAL_SUMMARY.json，精确执行/终态见work/rayggxia/204/EXECUTION_INDEX.json。已推送PR205（ready/open、待审未合并），科学源f19b603578ba215433ae68809c7eed3f30c7bf55；144文件完整tree与本地一致、8关键文件逐字/blob回读通过，回执PUBLICATION.json与REMOTE_VERIFICATION.json。

M8共享输入计数相对S0：1331.137→479.067pJ/帧（−64.01%），174255.20→168423.79µm²（−3.35%），37→40周期（+8.11%）。M1位平面省能16.88%、面积多37.80%；M1先计数反而多耗能18.40%。普通OR4共享源同号同位权例低估75%。D1确定位串行34.467pJ/帧、11周期、22054.00µm²，低于M1 S0的165.994pJ/帧；尚未证明随机整体胜数字，M8数字同规模尚待扩展。

面积均已按用户要求raw×0.81并保留原始列。S0两尺寸hold−0.041792ns；S2 M8 setup仅0.000099ns，功耗表范围等警告保留。前布局，无CTS/SDF/SPEF、真实模型质量、存储/RNG/比较器/编码/最终浮点尺度及实际广播线成本。D0是未优化q9参考，不称成熟最佳INT8。SRAM/门控权重与内部位宽收紧属于后续，不伪称本轮全链路完成。

中央台账新增matrix-t32-204-20261028，82记录联合check/render、81旧record逐字保留；main缺全台账，本PR只交付增量record及校验回执，不复制别人记录。失败波形/别名/调试可见性版本保留；v3旧数字后处理实际已跑1分34秒后取消并由v9替代，如实记录。Projects既有权限限制待同步。下一步：审阅本轮PR，修hold/功耗表范围，M8数字控制、SC位宽/真实ICG及驻留权重端口验证；不自动启动新模型或昂贵作业。

恢复步骤：先读PUBLICATION.json与最新Issue204/PR，然后读REPORT/FINAL_SUMMARY、EXECUTION_INDEX和中央record。已有8核/48窗口不重跑。私有登录/Slurm/传输工具位于本工作目录private/，其内容不上传；读取EDA_SERVER_LOGIN_AND_FILES_ZH_20261028.txt使用现有helper。原始报告和执行包在C:/Users/86134/Documents/a_P_BIT/project_archives/matrix204_t32_20261028；源码/配置/报告成员SHA已绑定。27报告/9包已收，本轮无遗留作业。PR205待审未合并，不自动合并或关闭Issue。

修改冻结源码必须另建执行版本，不在当前EXECUTION_MANIFEST所列输入上原地修补。finalize.py为离线核验/报告生成，不执行EDA；update_registry.py为中央增量union，保留其他任务记录。中央镜像可能有并发新增，重新union后再同步，不能用旧catalog覆盖。
