## 2026-10-28 Issue55 第十二轮审核：已完成本地验证，等待集中PR合入main

负责人jieruiz；独立分支review/55-pr-round12；目录tmp/pr55-review-round12-20261028；远端main基线5188bd4695d373cfef78602cfcca4f66b6431696（PR203面积0.81规则已合并）。本轮选择性集成PR194/195/196/197/205/192/189，精确head、验证、原件SHA和限制见work/jieruiz/55/round12/REVIEW_ZH.md及evidence/MANIFEST.json；尚未发布的本地合并不等于远端已合并。

PR190仍为main默认共同调度基线；192的HBM/扩容/本地端口/500MHz/门控均为可选候选，不改默认。194/196补数字功能合同，195/197补GU模块与100MHz SS/TT PPA，205补T32矩阵及33类参数模块能耗，189提供有边界的文献/架构分析。中央台账带入此前审核的56条历史记录和8条本批记录，共64条；其他分支未验收记录不随本次进入main。根目录台账另含作者待审记录，保留，不以main子集覆盖。

测试与SHA核验均记录实际范围；部分外部原件本机不可达、205旧M8全矩阵MODE0三个seed的Icarus回放超时，保留原VCS证据和限制。未重跑GPU、DRAMSys、综合、STA或PT。不是新模型质量验收；继续采用Instruct/后训练模型。100MHz算出功耗不证明500MHz或后布局闭合；OR4误差较大且本批能耗不优于数字串行。原始工艺/面积/能量不改字节，汇总面积按0.81且不重复折算。

下一步：核对远端head/检查/审查状态，推送集中审核PR并按用户既有授权合并，回读main及原PR状态，更新Issue55和本地记忆后回收本轮工作副本。剩余PR分流及最优先170、185/188、后训练迁移依赖链见报告；没有宣称全部开放PR均完成源码审核。无新增长期作业；Projects未确认写权限，不虚报已同步。


发布确认：面积0.81默认规则已上传 [PR203](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/203)，ready/open、未合并；Issue28已同步。本地规则即时按用户要求执行，正式合并状态以后续回执为准。
## Issue28面积口径更新：本地已完成，待发布

2026-10-28T11:12:48+08:00；负责人jieruiz；分支task/28-area-081；base main@d83eeb1fc6b89a3dff51b5b62bf79acf665c7166，目录tmp/area-scale-issue28-20261028。登记用户指定65流程→线性0.9→面积0.81为后续默认55nm口径，原始报告/功耗/时延不改；未新建仿真、未批量改历史数值。AGENTS和长期备忘录已同步本地入口。旧Issue28工作目录有未提交内容，未触碰。下一步通过同Issue的新PR交付（PR29已历史合并），不混入其他实验。Projects沿既有权限限制待同步。

发布确认（2026-10-27T11:59:44.018808+00:00）：本地SRAM端口12新项/14对照已上传PR192，提交9c853d49ce426144a4a0740a38653e3daaa905b3；6远端关键文件原字节回读一致、24摘要/执行Git字节同封存SHA。Issue186已同步，待审未合并；无本任务运行作业、无新全36层/PPA。回执work/jieruiz/186/LOCAL_PORTS_PUBLICATION.json。

## 2026-10-27 Issue186：SRAM本地端口/频率优化十二项完成

复用task/186-local-pipeline/PR192，jieruiz，tmp/ffn-local-pipeline-issue186-20261025；main base d83eeb1f。已读取最新Issue/PR/README/AGENTS与Gemmini/ONNXim一手资料，新增主unified_v6的可选local_ports_20261027后端，不另造整机。正式默认DDR4/历史配置保留，新候选限定500MHz扩容/HBM/8MiB条件。

删除无依据的全局512GB/s cap；E宏SS read最小周期3.468ns，选择250MHz（4ns）且保留200MHz对照，只做宏周期筛查不是wrapper/500MHz STA。建议4个本地共享读写宽通路，各512GB/s，源自128bank×16B×250MHz及512MAC×BF16×500MHz。8MiB、2048个E宏、512逻辑bank、原计算资源、额外16KiB FIFO均不增。真实bank单端口、同通路排队、有限credit/CDC、DRAMSys原外存继续限制，不加免费多端口bitcell。

三源码77650539/Slurm3180六项、4eaedf28/3188两项、5847a24f/3191四项，12新项全部completed/原件SHA核验，另复用2旧accept基线，不重跑健康作业。58软件检查；14项算术/物理SRAM与DRAM字节/FFN及Attention工作/真实随机输出SHA/配置SHA逐数守恒。本任务无运行项；他人作业未操作。

代表性单Qwen3-4B后训练形状层＋完整151936词表/seed0/2K，非全36层TPOT。SC旧8.322292→6.816810ms（缩短18.09%），数字FFN8.936880→7.172958ms（19.74%）；非词表SC1.432796→1.319518、数字2.047748→1.675802ms。只升频SC仅0.46%；首轮把片内DMA按HBM峰值限宽反而变慢，已保留负例，并在等宽对照允许原响应缓冲短时突发。等宽共享/独立/暴露宏总时间相同，因此先选较简单共享宽接口。暴露2048宏/分离ping-pong不增位，但占ping/pong各2MiB、workspace4MiB，unused行不再免费复用。

宏cell面积68.0473mm²、读写动作动态能量不变；SC代表项共享SRAM动态1.25464mJ、漏电0.132166→0.108258mJ。不能将18%提速当18%节能或用旧2.52W套新结构。外围宽接口/driver/mux/gearbox/CDC/CTS及响应缓冲宽读出未新校准；HBM仍timing-only。DRAM/DMA忙5.7175ms/总6.8168ms，MAC忙0.4623ms，可重叠不可相加；后续重点是外存供数/有限tile生命周期，而非盲目加端口。Attention本轮screen_pv准确Softmax，Ising sink未拆beat继续明确拒绝。

入口local_ports_20261027/RESULTS_ZH.md、COMPARISON.json与README_ZH；源/提交/封存/验证/唯一包归档见work/jieruiz/186/LOCAL_PORTS_*，collect三个后缀再analyze不带--partial可重建12/12。O19与统一台账07仅为TLM索引，无新PPA/PPL/数字run。代码结果本地已完成，远端上传状态以LOCAL_PORTS_PUBLICATION.json及发布确认前缀为准；PR不自动合并/Issue不自动关闭，Projects沿既有权限待同步。

---

发布确认（2026-10-27T10:42:13.295877+00:00）：SRAM分slice原型/八项完整对照已上传PR192，提交9109164faf256d82b4fe2541fc1ac78b493f7bae，6远端文件与16原摘要/执行字节核验通过；Issue186已同步，待审未合并。无本任务运行作业，回执work/jieruiz/186/SRAM_SLICE_PUBLICATION.json。无新PPA/36层加速结论，Projects待权限。

## 2026-10-27 Issue186：分slice SRAM八项完成，accept较旧慢约1.1%～1.2%

三执行18dd259a/3169 SC三项、2adacf79/3175 BF16三项、5d543eb9/3178 accept两项全部completed/封存SHA核验；当前无本任务运行作业，不重跑。原BF16配置失败三项及cycle_end保守策略结果保留。45检查（新13）通过，8项逐数保持within算法算术、DRAM/SRAM物理字节、FFN/Attention工作和实际RNG输出SHA，16原摘要/执行字节同MANIFEST。

单Qwen3-4B decoder层＋完整151936词表、seed0，500MHz目标、原8MiB512bank80MHz/总512GBs，新增16KiB有限link FIFO明确未价；不是36层TPOT/新PPA。SC旧8.229026ms、分slice描述符8.280314、beat-cycle_end8.481780、写入接受即归还credit8.322292（对旧+1.1334%）；BF16旧8.831064、描述符8.897864、cycle_end9.125730、accept8.936880（+1.1982%）。accept比保守cycle_end快约1.88%/2.07%，bank仍占完整12.5ns周期。FastCalendar软件优化500预约与旧逐事件相等。没有为了提速暗增总带宽或漏掉R/W冲突。

结论：需要显式端口/链路以正确定位瓶颈，旧模型不是单向悲观上界；只分区/去global锁不会自动加速，旧模型也有理想化流水。旧全36层5.7008GB SRAM下界11.134ms、fabric忙15.284ms，总57.421ms不能全归因SRAM锁。沿主TLM可选memory_factory新后端，旧默认保留；下一步若验收新后端再做完整36层/公平两侧及NoC/FIFO/CDC成本，不拿本轮单层×36或旧2.52W冒充新整机。

结果sliced_sram_20261027/RESULTS_ZH.md、COMPARISON.json，复核collect_sram_slices.py各后缀再analyze_sram_slices.py不带--partial，已8/8。精确输入/配置/原件/源SHA和唯一源码包归档均在SRAM_SLICE_*；Ising sink尚未映射，当前后端明确拒绝，待独立接入。O18、统一台账06已更新。发布见SRAM_SLICE_PUBLICATION.json；PR192待审未合并、Projects待权限。

---

## 2026-10-27 Issue186：分slice SRAM端口模型，六项完成/accept两项待收

task/186-local-pipeline/PR192；tmp/ffn-local-pipeline-issue186-20261025。用户指出全局SRAM串行模型过粗，已查Gemmini/Eyeriss v2/ONNXim一手资料。沿主unified_v6增加可选memory_factory，默认旧路径保留；新后端sliced_sram_20261027，4×128bank、80MHz16B单端口，4×128GB/s共享读写链路＋DMA/矩阵/向量端点，总8MiB/512GBs不变，额外16KiB双credit FIFO明确未价。bank周期/access/CDC与链路资源拆开，不锁全局fabric。原FFN本地CIM和寄存器已绕过shared fabric，不称全部片上访存原来都串行。

45验证通过（新13），无重叠、物理字节/库能量/算术/状态守恒、500次FastCalendar与原预约全等；FastCalendar只是软件append优化。首执行18dd259a/3169：SC三项completed，BF16三项在配置阶段因SC专用local_pipeline键失败，日志SHA保留；2adacf79/3175只补失败BF16三项，全部completed。六项的实际随机输出SHA和工作/物理字节逐数相等。单层＋全151936词表ms：SC旧8.229026、分slice描述符8.280314、beat-cycle_end8.481780；BF16旧8.831064、描述符8.897864、beat-cycle_end9.125730。不是完整36层TPOT；仅删除global锁未提速，旧模型不是统一悲观上界。

检查发现cycle_end将写FIFO保持至bank周期末；新accept在写入接受后归还credit，bank仍独占12.5ns，setup/hold由接口合同保证，TLM不替代STA。执行5d543eb9/Slurm3178_[2,5]为SC/BF16两个独立协议对照，已提交、尚未封存时不得报收益。三源快照不修改/不重复旧健康任务；当前无新GPU/PPL/RTL/PT。旧整机5.7008GB SRAM裸下界11.134ms，fabric忙15.284ms，总57.421ms；不能把总时间都归因SRAM或把单层×36当整机。

恢复先读SRAM_SLICE_SUBMISSION/BF16FIX_SUBMISSION/ACCEPT_SUBMISSION、COLLECTION、HANDOFF；运行work/jieruiz/186/collect_sram_slices.py _ACCEPT，然后analyze_sram_slices.py（--partial仅允许阶段报告）。RESULTS_ZH/COMPARISON已6/8，源码/配置/原RESULT SHA齐；剩余2成功后去--partial校验8/8再更新PR/Issue/STATUS/备忘录。Ising旧输出sink尚未拆beat，当前新后端明确拒绝；不含BookSim/真实布局/NoC PPA，旧2.52W不迁移。原三包已逐SHA归档project_archives/sram_slices_issue186_20261027，不建全量副本。数字台账06只为TLM索引，run数量不增；Projects待权限，不自动合并。发布见SRAM_SLICE_PUBLICATION.json。

---

## 2026-10-27 Issue186：共享SRAM分slice原型

用户要求带宽约束落到具体端口/链路，接续task/186-local-pipeline/PR192，复用tmp/ffn-local-pipeline-issue186-20261025。核实shared sram_fabric全局锁＋所有bank整描述符锁/CDC是限制，本地CIM/寄存器已绕过。新sliced_sram_20261027可选factory，默认不改；4×128bank、每bank80MHz16B单端口、4×128GB/s读写合计链路，原8MiB和512GB/s保持。

legacy/分slice描述符/有限beat三对照；beat双credit每slice2×2KiB，新增16KiB payload FIFO显式列为未价硬件成本，无无限缓冲。bank12.5ns发起周期、access延迟与网络/CDC20ns分开，credit按实际在途区间预约，可回填早到空隙。相同bank/link/endpoint排队，不做免费全双工或重排/广播。Ising sink未拆beat，配置明确不支持。

42测试（新增10）已通过，含算术/实际字节/能量/状态守恒和无重叠。下一步冻结6个一层Qwen3-4B全形状/词表实际DRAMSys SC/BF16公平对照；不是36层TPOT，无完成数字时不报加速。执行以SRAM_SLICE_SOURCE/SUBMISSION/COLLECTION为准，不重复旧任务。资料和来源README_ZH.md；不自动合并，Projects待权限。

---

发布确认（2026-10-27T09:40:24.289300+00:00）：功耗重算已上传PR192，科学提交4278dfed5ea5f2d97a53ea66521da366026ed602，6个关键远端文件原字节一致；Issue186已同步，待审未合并。回执work/jieruiz/186/ENERGY_RECALIBRATION_PUBLICATION.json。无新TLM/EDA/PPL，Projects待权限。

## 2026-10-27 Issue186：最新随机版能耗重算（发布状态见回执）

复用task/186-local-pipeline/PR192与tmp/ffn-local-pipeline-issue186-20261025；用户要求用已返回PPA重算并只列关键校准缺口。新增architecture_tlm/ppa_recalibration_20261027后处理，原TLM时序/源/封存结果不改。三seed57.4454ms、32SC/2048MAC、GU64NL128、8MiB512bank；Attention为screen_pv准确Softmax，未启用Ising。

PR197新三级合并计数/B4实测按B7 RTL位数1.36947外推；真实X8计数门控、单MAC/FP32加、既有PRNG和SRAM已映射，数字单元idle不再遗漏，漏电不随频率乘5。共享/局部/响应SRAM各按物理动作分别计，随机流不存SRAM；10 NL端点已含200比较器覆盖192路，不叠收费。旧恢复作公共系数/舍入代理，不额外叠七桶归约。

片上已覆盖12.7864W/0.73452J（新计数CE），10.0280W/0.57606J（计数实测ICG、数字CE）；数字候选消除90%空闲动态、保留工作时钟和漏电后2.5162W/0.14454J。数字门控尚未真实阵列校准，500MHz均固定V能量/拍外推。旧64pJ/B+50mW仅HBM粗预算另6.1661W，候选8.6823W/0.49876J不是全片已测。HBM桥仅时序、零占位电流未被误当0W；完整已校准总值仍null。已计价面积192.7mm²，非物理整片。

PRNG/SRAM已有数据，不重跑本体。关键缺项三类：B7计数/公共恢复/宽部分和及数字门控500MHz集成；CIM全并行读出+阵列互连/CTS；有效HBM能量。Ising反馈仅可选路线缺项，当前不收费。6输入MANIFEST/SHA、8会计守卫通过，无新EDA/PPL/TLM时序。统一台账05_随机版功耗重算.md为索引，不重复新增电路run。发布以work/jieruiz/186/ENERGY_RECALIBRATION_PUBLICATION.json为准；Projects待既有权限，PR不自动合并。

---

发布确认（2026-10-27）：调度11项完整结果已上传PR192，提交f8292c87415f26d5473c5a98830e5ae6632a434c并回读4个关键blob原字节一致；Issue186已同步，待审未合并。无本任务运行作业，准确回执work/jieruiz/186/SCHEDULE_V2_PUBLICATION.json。

# 2026-10-27 调度两轮已完成

Issue186/PR192；jieruiz；task/186-local-pipeline；base main d83eeb1f；目录tmp/ffn-local-pipeline-issue186-20261025。3156七项＋3163四项全部completed、封存SHA核验；执行410fa5af/5ba79477，健康完成任务不重跑，远端source不可变。本轮全部只用CPU；无本任务运行作业。

同硬件/采样/物理字节，组合三seed均值64.411267→57.445385ms/token，少10.81%；主要来自提前DMA覆盖BF16普通投影本地装载。FFN只少约1.1%，不是随机矩阵算术提升10.8%。134本地软件验证及远端每项12检查；无PPL/新PPA。

入口architecture_tlm/scheduling_v2_20261027/FINAL_RESULTS_ZH.md与FINAL_COMPARISON.json，优化记录O16。collect/analyze_schedule_v2、collect/analyze_schedule_early、report_schedule_final可重建报告；源码/配置/原件SHA见SCHEDULE_*。两个tar包已逐SHA移入唯一归档，见SCHEDULE_PACKAGE_ARCHIVE.json。PR发布状态以SCHEDULE_V2_PUBLICATION.json为准，不自动合并，Projects待维护者同步。

下一步：先审核此次供数政策并给数字基线同样优化；后续分项评估跨描述符有限并发、SRAM按beat服务、SC计算/恢复流水和文献/实库L/II校准。不得把本次模型时间当500MHz芯片实测，不把动态动作不变的10.8%提速当同比能量节省。

---

# 2026-10-27 调度第二轮运行中；首轮已完成

Issue186/PR192，jieruiz，task/186-local-pipeline；目录tmp/ffn-local-pipeline-issue186-20261025。3156七项已completed/SHA核验，seed0 64.3779→64.30045ms，仅0.12%；prefill和日历无总时间收益。首轮执行410fa5af，结果architecture_tlm/scheduling_v2_20261027/RESULTS_ZH.md。

发现下一DMA仍晚发起；新开关early_next_dma在既有响应槽释放后立即issue下一块，保持单响应槽/两共享槽/两本地bank。执行5ba79477、Slurm3163四CPU项已运行，远端每项12测试通过；本地110+24测试。MATRIX_EARLY_DMA.json定义单因素和组合三seed，source与SUBMISSION为准。没有第二轮完整结果，勿提前填加速。

恢复：不改远端source、不重交3163；collect_schedule_early.py按completed收results_early_dma，再analyze_schedule_early.py核同seed工作量/字节和资源，最终报告/PUBLICATION在同一任务。原500MHz/32SC/GU64NL128/8MiB512GBs/HBM/screen_pv均固定，不门控。Projects待权限；无新GPU/PPL/RTL/PT。大原件在个人服务器，Git只小汇总与SHA。

---

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

发布确认（2026-10-27T08:32:15.276444+00:00）：[PR197](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/197)已推送待审、未合并；payload cb2cca56a1c0a0227555be89ee215c337391729a，15份远端文件原字节回读一致，Issue110已同步，Projects待权限。本机固定汇总与目标run同步；本轮无新EDA或TLM改动。回执work/jieruiz/110/PPA_SUMMARY_PUBLICATION.json。

# 2026-10-27 新PPA汇总（Issue110）

jieruiz；task/110-ppa-summary-20261027；base main d83eeb1f；复用tmp/circuit-registry-issue110-20261022；旧PR111已合并，旧任务分支2b7935f4保留。本次新PR发布状态见PPA_SUMMARY_PUBLICATION.json，不能用旧111回执代表本次完成。

16原始报告归档SHA重算228正式窗口（150＋78），两条run已有，更新矩阵complete，不增重复run；78条schema通过，其他记录不变。04汇总、76模式与228窗口CSV已生成，X4超表负结果和smoke保留。已从服务器只读收齐，无新仿真/训练/PPL，无本任务运行作业。

主入口digital_circuit_simulation_registry/04_最新功耗面积汇总.md；REGISTRY_UPDATE/PPA_SUMMARY_VALIDATION记录验证。正式PR仅目标两个record与汇总，根其余78聚合/private pending历史不混入main。根00/01/02/03和归档表已更新；汇总文件与本机固定入口同字节。当前TLM参数没有自动替换；后续按边界选择活动/idle/泄漏和调用次数，500MHz、大负载和完整采样反馈另表征。

下一步审核本次表/PR，再按任务回填TLM；不重跑已完成EDAs，不编辑95/193别人的工作目录或STATUS。Projects待维护者同步，不自动合并。

---

## 2026-10-25 第十一轮实际合并回执

已发布 [PR194](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/194)，待审、未合并。PUBLICATION.json是PR创建时的精确回执；后续文档同步提交不改变封存源码55c607dc和ZIP。

# jieruiz当前进度

2026-10-25；负责人jieruiz；Issue193；分支task/193-ffn-calibration-stage1；base main d83eeb1f；目录tmp/ffn-calibration-issue193-20261025。第一轮55nm计数/整数恢复校准包本地完成，源码55c607dc已推送；结果PR交付状态以work/jieruiz/193/PUBLICATION.json为准。

实际验证：9配置RTL功能、9固定top展开、29流程测试通过；没有VCS/DC/PT/新Slurm/PPL。100MHz为目标，不是工艺时序通过。正式成果architecture_tlm/ffn_calibration_stage1；ZIP位于本地根ffn_calibration_stage1_20261025.zip；哈希见work/jieruiz/193/DELIVERY.json。

新增台账record并在根联合阅读索引check/render，67条旧记录不变。main尚未包含完整registry，正式台账集成待后续同步；Projects缺read:project。用户下一步按RUN_FIRST_ZH.md先运行SS两项smoke，把小报告包回传后调整流水线。交接work/jieruiz/193/HANDOFF.md。

此前Issue186/PR192独立待审；本任务未接管、覆盖或合并。

发布确认（2026-10-27）：校准v2已上传[PR196](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/196)，提交69c61309d80656d3562ccc47209fd424c1c91329，远端tree/关键blob原字节已核验；待审、未合并。Issue193/107已同步，无新EDA/PPA。准确回执work/jieruiz/193/PUBLICATION.json。

# jieruiz当前进度

更新2026-10-27；负责人jieruiz；Issue193，关联107/133/186；分支task/193-calibration-v2，PR发布状态见work/jieruiz/193/PUBLICATION.json；base main d83eeb1f；独立目录tmp/calibration-v2-issue193-20261027。

本地已完成新精确计数器、可配置实库ICG接口、真正流水的BF16/FP32数字代表核及DC/VCS/PT脚本。16计数配置128帧、24数字配置22245事务、31flow测试和ICG功能门禁通过。完整结果与SHA见architecture_tlm/calibration_v2_20261027和work/jieruiz/193/DELIVERY.json。没有新综合/STA/PT、500MHz达标或PPL；未改TLM默认，未合并。

待用户工艺仿真：g0可先跑，g2需要实际库单元映射；缺失PPA和ICG信息不是零成本。下一步按RUN_FIRST_ZH.md跑代表性100MHz并回传，检查关键路径后再250/500MHz与门控。exp/recip/rsqrt、完整向量链、CIM/时钟树、真实模型数值闭环仍在原待办。Projects待维护者同步。可执行交接见work/jieruiz/193/HANDOFF.md。
