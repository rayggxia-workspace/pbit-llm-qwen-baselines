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

恢复先读最新Issue204/PR209及PUBLICATION，核对准确head。结果已齐、无遗留作业；不重跑init.py、不重交旧快照。prepare.py会重建RTL/bench/fixtures，只在新目录运行。下一步审核、质量/真实存储供数和多输出共享边界；不自动追加昂贵EDA或模型实验。
