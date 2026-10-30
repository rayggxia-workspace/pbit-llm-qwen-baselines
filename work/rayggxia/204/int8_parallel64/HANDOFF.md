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

恢复先读最新Issue204/PR209及PUBLICATION，核对准确head。结果已齐、无遗留作业；不重跑init.py、不重交旧快照。prepare.py会重建RTL/bench/fixtures，只在新目录运行。下一步审核、质量/真实存储供数和多输出共享边界；不自动追加昂贵EDA或模型实验。
