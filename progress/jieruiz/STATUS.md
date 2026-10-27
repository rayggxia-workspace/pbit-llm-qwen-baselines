# 2026-10-27 随机版调度优化运行中

Issue186/PR192，jieruiz，task/186-local-pipeline，base main d83eeb1f，目录tmp/ffn-local-pipeline-issue186-20261025。执行410fa5af，Slurm3156七CPU项已运行，源码/提交回执SCHEDULE_V2_SOURCE/SUBMISSION；133本地检查与远端每项11测试通过，无已完成全模型结果或加速数字。

固定500MHz/32SC/GU64NL128/8MiB512bank512GBs/HBM/screen_pv，不门控。三项分别和组合：资源日历、SC跨窗口program、BF16普通矩阵prefill；数据容量/算术/样本不变。collect_schedule_v2.py收completed封存，再analyze_schedule_v2.py验证旧基线复现和同seed工作量/字节。不要重交健康3156、不要修改远端source。发布状态见SCHEDULE_V2_PUBLICATION，Projects待权限。等待时不用重跑旧PPL/RTL/PT。

---

发布确认（2026-10-27）：论文建模口径已推送PR192，提交81b826c80dcd4265883d7a40a83f1673d5251164并回读policy原字节一致；Issue186已同步，仍待审、未合并。仅文档，无新仿真或代码参数变更；回执work/jieruiz/186/PAPER_POLICY_PUBLICATION.json。

# 2026-10-27 论文建模口径更新（Issue186/PR192）

负责人jieruiz；task/186-local-pipeline；基线本轮556462dc，base main d83eeb1f；目录tmp/ffn-local-pipeline-issue186-20261025。用户指定两份资料已读，源码核对确认保守限制；新增PAPER_MODELING_POLICY_ZH.md与输入SHA索引，未改TLM运行代码/参数、未提交新仿真。实际发布见PAPER_POLICY_PUBLICATION.json；PR不自动合并，Projects沿既有权限缺口待同步。

下一步按policy优先数字/SC合理预取、就绪调度和有限DMA流水，而非为未知项叠加串行等待；采用成熟PE/FPU的L/II依据，新PPA后续回填。新PR196已提供计数和数字RTL功能证据，工艺结果仍待回传，不重跑既有12项或健康任务。用户本轮先确认论文建模方向，不将此文档说成已实现优化或新速度结果。

---

发布确认（2026-10-27）：计数器/真实门控/数字校准清单已推送PR192并回读原字节，提交623f0236dfa68853e16e7ae8a6155a0d8fa9b70b；Issue186/193已同步，PR仍待审、未合并。没有新RTL/ICG/PT或数字校准结果。回执work/jieruiz/186/COUNTER_PLAN_PUBLICATION.json。

# 2026-10-27 计数器/门控/数字校准清单：本地完成

本人Git认证jieruiz；task/186-local-pipeline，PR192 base main d83eeb1f，任务目录tmp/ffn-local-pipeline-issue186-20261025。仍open/unmerged；具体上传回执见work/jieruiz/186/COUNTER_PLAN_PUBLICATION.json。
本次改动仅设计审计、派生脚本/结果、任务清单与记忆。144个合成事件帧整数等价通过；不属于RTL验证，没有新PPA/PPL/提交作业。待办与合同见architecture_tlm/clock500_resource_20261026/COUNTER_GATING_DIGITAL_TODO_ZH.md。
下一步接续Issue193实现合并档位归约候选、验证真实ICG，接续数字校准；500MHz需新STA。当前只记录计划，不能勾成已做。PR/Issue发布后同步，Projects依既有缺read:project待维护者操作。
记忆同步注意：根阅读副本在本轮开始已含其他任务较新的记录，历史字节与本分支不同；本轮新增段逐字一致，保留所有原记录。未把其他任务的未公开内容推入PR192，完整镜像归并仍待专门维护；不得为追求字节一致覆盖较新记录。

---

发布确认（2026-10-26）：500MHz/门控科学结果已推送并远端head/tree/报告原字节核验，科学提交efbcbd44ad325435e0bf73282d95b0ff2156a434；PR192开放待审、未合并。回执work/jieruiz/186/CLOCK500_PUBLICATION.json；Issue186已同步，Projects待权限。

## 2026-10-26 Issue186 / PR192：500MHz扩资源与门控完整12项

负责人jieruiz；task/186-local-pipeline，base main d83eeb1f；本地tmp/ffn-local-pipeline-issue186-20261025。CPU Slurm3124全部12项completed，执行64e0cf8a、后处理4ca97270；110统一回归＋32机制/PPA测试、36层、原件SHA、动作流量/门控寿命守恒通过。没有新PPL/RTL/PT/500MHz STA；不自动合并PR。
500MHz只提频157.595ms；再单独扩计算143.956、单独扩SRAM76.750、两者并扩NL64=63.134ms。GU64/NL128三seed：不门控64.411ms，门控64.526ms(+0.178%)；同存储普通BF16准确110.012→110.157ms。主候选32×64×64 SC、2048MAC/拍、桶256/恢复64/累加128、8MiB E宏512bank/512GBs，SRAM仍80MHz/HBM固定时序；注意力本轮仍screen_pv，未重跑Ising。
门控保留状态、idle8拍关闭/请求1拍唤醒，存储/随机/配置总线除外。新Issue193计数M1=一个输出，32阵列2048输出；B7/M8面积复制后counter209.803mm²，已知单元+宏小计279.637mm²，不是全片面积。100MHz动态/泄漏拆分，500MHz外推，默认关钟时段80%idle动态可消除：已计价27.34→8.41W，1.761→0.543J/token；ICG/CTS/HBM/数字阵列idle及面积/本地CIM等未知。旧100MHz/NL64未门控约0.476J/1.55W/93mm²仅工程预算；提速不自动减少能量，且新旧采样数不同。完整PPA null。
成果architecture_tlm/clock500_resource_20261026/RESULTS_ZH.md、COMPARISON.json、PPA_ANCHORS.json；记录本O15；回执work/jieruiz/186/CLOCK500_{SUBMISSION,COLLECTION,VALIDATION}.json。功耗原件POWER_RESULT SHA7e554296…10d59已关联统一台账power-recovery，现73条schema通过，无重复run。
发布状态以CLOCK500_PUBLICATION.json为准；该文件生成并远端回读前只算本地完成。Projects缺read:project待维护者同步。恢复先核Issue/PR/HANDOFF，不重跑健康/完成任务，未价成本不能当零；下一步实现并测500MHz流水线/ICG，优化巨大计数结构与HBM供数。

---

# 2026-10-26 Issue186 / PR192：500MHz扩资源与门控（运行准备）
负责人jieruiz；分支task/186-local-pipeline；base d83eeb1f；目录tmp/ffn-local-pipeline-issue186-20261025。
已完成显式500MHz profile、32SC/2048MAC/512GBs SRAM、可选门控和RNG每动作参考能量保持；37项测试通过。即将冻结源码并提交CPU Slurm，尚无新完整结果。无新PPL/RTL/PT/500MHz STA，不自动合并PR。
成果architecture_tlm/clock500_resource_20261026；回执work/jieruiz/186/CLOCK500_SUBMISSION.json存在且确认后才视为已提交。看板缺read:project待同步。

---

# Issue186 本地权重双bank续作（2026-10-25）

科学交付HEAD `22432ffffa9f3af600a9288be5d9212bd68f2e98`；PR192，45个远端blob原字节核验通过；后续提交仅同步发布回执。

负责人jieruiz；task/186-local-pipeline；base main d83eeb1fc6b89a3dff51b5b62bf79acf665c7166；目录tmp/ffn-local-pipeline-issue186-20261025。原PR190已合并，新PR发布回执见work/jieruiz/186/PIPELINE_PUBLICATION.json；已上传PR192（https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/192），待审、未合并；不自动合并。

13/13 CPU Slurm3074 completed，3完整36层＋10单层，执行6f73ef65，SHA/工作量/流量守恒通过；44项相关测试通过。407.143→315.236→307.049ms/token（原/双bank/再bypass）；FFN 268.576→176.680→168.488ms；旧结果逐数复现。新目录architecture_tlm/ffn_local_pipeline_20261025，记录本O14。没有新PPL/RTL/PT或完整物理PPA；SRAM已知内部动态不能当整机能量；HBM能耗未知。原件远端pipeline_6f73ef65，健康完成任务不重跑。Projects缺read:project待同步。下一步审核有限双bank接口与计数结果/恢复流水，不混淆硬件扩容和调度。

---

## 2026-10-25 第十一轮实际合并回执

PR183已合入main（a73a75ce0566f5fff0b8c38fcb03d04961885f76），PR190最终审核291c437a已合入main（f8a861487170c2cd65bc9ecb95eb3e4f72b863be）。旧008b0227之后的七文件增量仅文献与派生分析，输入SHA和派生文档重现通过，执行代码/配置/原结果未变；110回归与18小形状测试无需重复冒充新实验。正式入口architecture_tlm/BASELINE_ZH.md；默认DDR4、HBM显式对照、R8/128/资源扩容候选分开。PR181历史回执与本轮审核/入口文档将由review/55-pr190-main交付main，最终文档PR及SHA见Issue55。后续质量用Instruct/后训练模型；真实质量、GU数值闭环、物理PPA未验收。其余17PR仍待完整审核。

## 2026-10-25 第十一轮：PR190转为main共同调度基线（发布前）
已合并：PR180 → main，2026-10-24T14:41:06Z，提交5273e5d9fdae811a714f1a278fee6e776c5675af。全部验证与远端blob核验完成，无本任务运行中作业；Projects待权限。准确回执见work/jieruiz/179/MERGE_VERIFIED.json。

# 当前统一TLM交付：Issue179 / PR180（2026-10-24）

负责人jieruiz，Issue55；review/55-pr190-main，目录tmp/pr55-review-round11-20261025，main基线5273e5d9。190@008b0227及依赖183@0341b4ac、历史回执181@8f401be4审核通过有限交付，准备进入main，实际合并以Issue55最终回执为准。110测试、18小形状重放、688执行源码blob、246本地制品SHA与六组汇总核验通过；440个远端原件条目本轮未重下载。默认mature_ddr4、HBM显式对照、R8/128/大MAC宽SRAM作为候选；正式入口architecture_tlm/BASELINE_ZH.md。没有改科学代码/默认资源，没有新GPU/全模型DRAMSys/RTL/PT。旧TLM分支改为历史追溯，后续主线面向main；完整PPA/真实质量仍未知。报告work/jieruiz/55/round11/REVIEW_ZH.md，归档project_archives/pr_review_issue55_round11_20261025；其余17项分流未宣称完整审核。下一步精确head合并、回读验证、镜像同步及审阅副本回收；Projects待维护者同步。
发布确认（2026-10-25T12:50:42.665685+00:00）：ASIC文献与剩余瓶颈报告已推送bd283248并回读SHA核验；Issue186/PR190已更新、未合并；准确回执work/jieruiz/186/ASIC_COMPARISON_PUBLICATION.json。

# Issue186 / PR190：ASIC论文比较说明本地完成

负责人jieruiz；分支task/186-mature-scheduling，base task/182-memory-hierarchy；目录tmp/mature-scheduling-issue186-20261025。只读分析、无新作业；发布回执未生成前不视作已上传。Projects缺read:project待同步。

## 2026-10-25 Issue186：ASIC文献与剩余时延归因

2026-10-25T12:48:53.666246+00:00。本轮仅一手论文核查＋既有3058结果派生，未新跑TLM/PPL/RTL或改默认。报告architecture_tlm/unified_v6/ASIC_PAPER_COMPARISON_ZH.md，输入SHA/计算见work/jieruiz/186/ASIC_COMPARISON_DERIVATION.json；发布状态见ASIC_COMPARISON_PUBLICATION.json，同PR190不自动合并。

ASIC可用TB/s片上SRAM：SN40L为分布式520MiB/1040PMU、数百TB/s局部聚合，HBM约2TB/s/socket；Groq作者报告220MiB/88slice显式编译调度，未把无法完整打开的产品brief的80TB/s用于定量证据。AttAcc多HBM堆栈、NeuPIMs TP4起步/B64–512吞吐不能当单芯片B1；OPAL报告70B约1.98s/token但外存等口径不足；DS-CIM是40nm宏后布局+LLM误差注入，未给整机TPOT，不把TOPS/W当J/token。

当前8192MAC/拍，SRAM512→1024GBs只使125.505→107.639ms，少14.24%；密集91.111→73.972，attention33.614→32.893。外存8.347GB/token÷256GBs下界32.606ms，即使片上无限快也不能变成A100模型4.162ms。A100预测约94.8%来自忽略L2约束的M1 GEMV快捷路径，主要依赖2039GBs外存；不能把它快主要归因7.22TBs L2。剩余还含单消费者/偏晚DMA、131万span生成忙13.115ms、跨描述符屏障及KV通道热点。忙碌时间重叠不能相加。下一步优先入口/异步多tile/本地双缓冲/KV分布及匹配目标HBM，数字和概率共享优化；未量化这些未实现项能各省多少。

---

发布确认（2026-10-25T12:17:21.681310+00:00）：16项资源/调度结果已推送并回读字节，科学提交59f8b146，远端head 277636732f5498a97036a659bfdefe3193e42fe4；PR190待审未合并、Issue186已同步；准确回执work/jieruiz/186/RESOURCE_PUBLICATION.json。

# Issue186 / PR190：16项硬件×调度对照本地完成

更新2026-10-25T12:12:51.806581+00:00；负责人jieruiz；分支task/186-mature-scheduling；工作目录tmp/mature-scheduling-issue186-20261025；base task/182-memory-hierarchy。本轮本地已完成，发布状态以work/jieruiz/186/RESOURCE_PUBLICATION.json为准；同PR190，未合并、不自动合并。执行b01058f7，CPU Slurm3057八项实际DRAMSys小模型与3058十六项完整Qwen3-4B/36层/2K/B1数字BF16全部completed，110回归；配置/源码/原结果SHA及MAC4.626251776G、DRAM8.347GB/SRAM16.705GB/tile/容量守恒核验。

100MHz、8MiB、64KiB本地固定：旧F512MAC/64GBs 402.629→379.372ms（只预填充省5.78%）；共同E宏对照512/64为400.439→377.666，8192/64=362.130，512/512=171.013→155.844，8192/512=125.505，8192/1024=107.639，32768/512=124.807。主要瓶颈是SRAM接口/bank资源偏小，计算扩容收益明显饱和；预填充只一项策略，大算力零收益不代表全局调度最优。下一DMA发起仍偏晚，单本地load/retire串行。MAC吞吐/本地16或64KiB每拍供数、更多bank的mux/fabric/CTS为未签核目标；没有新PPL/RTL/PPA，整机PPA null，随机FFN未扩容。

参数源自2026-10-14的可调512MAC/100MHz默认，不是模型限制。公开LLMCompass A10040MiB L2=7219.2GBs可作规模参照；TPUv3的16GiB全局层是外存抽象，460.6GBs不得称片上SRAM。报告unified_v6/RESOURCE_SCHEDULING_ABLATION_ZH.md，结果results/resources_20261025，优化记录O13；原件个人远端pbit-scheduling-issue186-20261025/resource_b01058f7。恢复读Issue/PR/STATUS/HANDOFF，collect/analyze/report_resources.py，无需重跑健康/完成任务。Projects无read:project待同步。

---

发布确认（2026-10-25T11:27:01.963799+00:00）：本轮LLMCompass代码/五配置结果/报告已推送并回读原字节，科学head 1bfaa067013853f1eee8ea9239ca77a050e28353；PR190开放待审、未合并，Issue186已同步。准确回执work/jieruiz/186/COMPASS_PUBLICATION.json。

# Issue186 / PR190：LLMCompass独立数字基线已本地完成

更新2026-10-25T11:19:45.927751+00:00；负责人jieruiz；分支task/186-mature-scheduling；目录tmp/mature-scheduling-issue186-20261025；base仍task/182-memory-hierarchy，PR190待审未合并。本轮代码与结果本地已完成，远端发布状态以COMPASS_PUBLICATION.json为准。

公开上游LLMCompass固定2e015fd2，最终执行3b06f295/CPU Slurm3052五配置全部completed；初轮4aef5971/3047保留（补选词与RMS计数前）。5项合同测试各配置通过，真实GQA tile/Softmax mapping完成，136上游文件SHA不变；模型形状/执行/配置/结果SHA核验。无GPU/PPL/RTL/PT。

2K B1 Qwen3-4B数字服务ms/token：A1004.162（旧launch代理20.989，非实测）；小资源HBM256=177.808、HBM186=178.006、补共享SRAM限制350.977；当前TLM402.629。共有4.626251776G MAC。小配置MAC下界90.356ms，SRAM16.705GB/64GBs下界261.020ms。原生GEMV忽略L2，当前TLM则串行shared fill/read/compute；Softmax/部分和位宽/阵列也不同，净差不等于调度可节省。完整结论architecture_tlm/unified_v6/LLMCOMPASS_COMPARISON_ZH.md；结果results/llmcompass_20261025/final，记录本O12。

远端原件/home/Hongjie_Zeng/projects/pbit-scheduling-issue186-20261025/compass_2e015fd2/run_3b06f295；source与upstream不可修改，lookup只在scratch。恢复先核Issue186/PR190、运行collect_compass.py再report_compass.py核SHA和阶段表，无需重跑。下一步先明确数字参考资源档位，再实装共享SRAM/本地供数/计算的有界重叠；Attention内部模型单独比较。保留现有TLM默认和HBM旧结果。Projects无read:project，待有权限成员同步；不自动合并。

---
# Issue186 / PR190：HBM完整25项已核验

发布确认：HBM代码、报告和25项结果已推送并逐字回读核验，科学head 092fe9e8dea2deae9ec943f744f8a144bbc334c1；PR190开放待审、未合并。HBM_PUBLICATION.json为准确回执。

更新2026-10-25T10:44:17.130922+00:00；负责人jieruiz；分支task/186-mature-scheduling；目录tmp/mature-scheduling-issue186-20261025；base task/182-memory-hierarchy，PR190待审未合并。

本地实现和25项全部completed/SHA/36层验证：e7505ee4的Slurm3019/3020（17项），43b7b1ff的3037/3038（8项）。104回归，36微基准；旧DDR四模式逐段时间/能量不变。2K ms/token：BF16 599.340→402.629；W8 426.364→333.664；SC R8准确503.639→438.038；SC R8筛选PV三seed474.154→407.167。核心100MHz、共享8MiB/64GBs SRAM、随机采样不变。HBM16GiB理论256GB/s、实际连续读185.786；新增256B主机事务/有效64admitted，PV32→128分批。源快照不可改。

成果architecture_tlm/unified_v6/HBM_RESULTS_ZH.md、HBM_TIMING_ZH.md、results/hbm_20261025、记录本O11；work/jieruiz/186/HBM_DELIVERY_AUDIT.json。原始RESULT/trace保留个人远端pbit-scheduling-issue186-20261025/hbm_e7505ee4和hbm_43b7b1ff；无运行中本任务，无GPU/PPL/RTL/PT。HBM占位电流禁用，总物理能量/面积null，不比较不完整小计。GU数值宏/普通算术吞吐未签核。FFN主体约267ms不随HBM显著变快；KV同组单通道热点尚在，可另测XOR映射，未宣称已优化。

本轮发布状态以HBM_PUBLICATION.json为准；尚未生成回执时仅本地完成。保持Issue186开放，PR不自动合并。看板缺read:project，待有权限成员同步。恢复先核远端Issue/PR、collect_hbm.py及--pipeline，analyze_hbm.py --require-complete，再report_hbm.py；勿重跑健康/已完成任务。
