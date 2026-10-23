# Issue157：后训练版 Qwen3-4B SparQ 基线（2026-10-23）

负责人 amlink1219；分支 `task/157-sparq-qwen3`，独立目录 `workspace_projects/sq157`；PR以PR147的 `task/144-qwen3-stochastic@357db588` 为依赖，不将其称为已合并。用户明确选择 Qwen/Qwen3-4B 后训练版，另建BF16对照。

已完成：论文v6与官方固定标签的GQA/预算差异审计；SparQ核心、原Qwen3接合、缓存PPL/官方任务计分与断点完整覆盖；双K/选择器成本账本。CPU Slurm2872在TF4.51.3/Torch2.7.1+cu128通过45项、无跳过、CUDA未初始化。后续新增诊断和benchmark测试将另列；尚无完整模型质量或物理PPA结论。

CPU准备2867因ensurepip缺失失败、2868因嵌套.pth未展开缺Torch失败，已保留日志；修复为个人隔离overlay显式连接本人两个既有依赖根。2871正在同一新任务home下载固定revision，不使用其他成员的权重或目录。GPU作业尚未提交。本轮不恢复暂停Issue116/123，不重跑PR147的26项Base后缀。

正式入口 [SparQ](../../qwen3/sparq/README_ZH.md)、[硬件账本](../../architecture_tlm/sparq_baseline/README_ZH.md)；精确恢复与未完成项见 [HANDOFF](../../work/amlink1219/157/HANDOFF.md)。任务准备代码/测试证据先上传，完整WT2、PIQA1838、ARC-Easy2376、HellaSwag10042、GPU速度/板级能量仍待执行；ASIC完整网表/STA/PPA尚缺。Projects权限需回读，不改权限；不自动合并/关闭Issue。

---

# Issue116 已暂停（用户明确要求，2026-10-23）

目标状态`paused`，不标complete、不自动恢复；只做收尾上传和交接。[PR126](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/126)开放待审/未合并，暂停前已推送3347bd8，最终收尾提交与远端核验见`work/amlink1219/116/PUBLICATION.json`。权威入口：[暂停总结](../../work/amlink1219/116/PAUSE_REPORT_ZH.md)、[HANDOFF](../../work/amlink1219/116/HANDOFF.md)；A–G仅A完成本轮冻结，B/C/D/E/G部分完成，完整新后端F未开始。

既有68真实裁剪+8合成、真实context64 GQA及81实现/71独审/43旧回归保持原结论；公开ActiveMemory候选的兼容和64/128/256探针另列，不改默认Kernel。2K候选仅建图后按用户指令中止，PID290792/251584/274768已停，无2K成功记录。三名子代理已停止；暂停时本人服务器队列为空，并行2783为CANCELLED/0:15，本任务未取消它。

正式结果、完整v5矩阵、v4失败、源快照、153项既有本地诊断和暂停回执均归档于本分支；私有模型/GQA原始输入留本人服务器并登记SHA。主树无未提交生产代码；其他工作树保留诊断草稿及14项仅换行差异，详见PAUSE_WORKTREE_INVENTORY，不清理/重置。Projects仍缺read:project；GitHub交接按用户要求通知仓库成员`@jieruiz`。只有用户明确恢复后才执行HANDOFF中的后续检查。

---

# Issue116 暂停前验收快照（历史时点）

负责人amlink1219，task/116-cycle-execution，独立workspace_projects/cycle23。FFN/query有限周期核、共享KV的GQA分组、native随机协议、缩小单层、v6桥与交互trace已完成；最终81实现测试、71独立测试、43旧回归通过。Slurm2776 real68+smoke8全通过，矩阵独立核302制品/34trace/98,340操作与4,597真实read hashes。新增真实context64、7query/1KVhead：Slurm2782的5个S32 CLI与6个S16独审配置双模式通过，独审42个case/head共2,688值逐bit相等。协议RTL9case252握手、ONNXim2官方+4场景、PR122固定版本12case兼容复验通过。有限预取死锁、免费union、无界operand响应已修并保留证据；无完整新后端Qwen/Llama/PPL/STA/PPA结论。

入口architecture_tlm/cycle_v1/IMPLEMENTATION_ZH.md，独立审查audit/REVIEW_ZH.md，交接work/amlink1219/116/HANDOFF.md。[PR126](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/126)开放待审、未合并；基础发布ddd2e340的438对象/8原始blob已核，包含GQA的最终发布以PUBLICATION.json的verified_head/对象与SHA回执为准。尚缺真实全维整层、多token/2K/8K、全局容量/随机网络、在线DRAM命令后端和PPA校准，原方案A–G未全部完成。N64/128规模探针显示超线性成本，未启动2K；PR125已在独立工作树接续完整FFN及调度性能工作，不复制未发表实现。旧v6/random_service/历史结果未改，权重/私有fixture留本人存储；并行PR119/120/122/125不覆盖。已在PR125留下正式后端交接；实际STA/PPA交由jieruiz，尚未运行。本任务作业均已完成，GPU仅2759/2781捕获（14秒/9秒），其余CPU-only；5090可用，未切4090。新GQA私有fixture下载被自动审批拒绝，改在服务器验证，仅回传白名单回执。Projects缺read:project待同步，不改权限。

---
以下为Issue98历史发布回执，与Issue116发布状态分开：

# Issue123 已按用户要求停止（2026-10-23）

task/123-full-ffn-ppa / PR125待审。正式PR126@160f46e＋PR122@8007d98接合已上传d944081；28项冻结包测试、120次独立随机payload复核及45RTL场景通过。完整fixture已捕获。

CPU2783于03:41按用户要求取消，CANCELLED/0:15、24:20，无全尺寸成功summary/trace/数值结论；本任务无运行作业。主机候选源码、已有34测试回执和小烟测已归档，未接入发布runner，未新提交全尺寸作业。

已做/未做/恢复步骤及中间文件索引见work/amlink1219/123/STOP_REPORT_ZH.md。STA/PPA交接文件已上传并@jieruiz，待其实际EDA；PPA/PPL未知。保留必要复现快照，未删除唯一数据；无自动继续。Projects待read:project，不自动合并/关闭。

---

发布回执（Issue121）：科学提交`3e8cb017e71a96aa628b1772810b7fdf12884245`已上传[PR122](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/122)，87项远端Git对象一致，开放待审、未合并。Issue116已回传接合结果；后续元数据提交不改变验证源码。

# 2026-10-23 Issue121：编码恢复与周期后端接合

负责人amlink1219；独立分支task/121-encoding-cycle，基线46804fb。已先核Issue116活跃本地实现，分工登记在#116；本包复用#107算术，参考#118/PR120供数边界，不改116工作树或默认FFN，不重复#117资源搜索。

完成显式两类计数语义、FUSED0恢复、逐输出Resource/Operation适配及有限结果槽RTL。28项软件测试、12组cycle/event重放（1536输出）、27组最终RTL（6861输出/108reset flush）通过，另8项索引测试通过；源码/产物SHA已核。主服务器CPU-only作业2767/2769/2773均完成，未申请GPU，没有本任务运行作业。

入口architecture_tlm/encoding_restore_contract/README_ZH.md；交接work/amlink1219/121/HANDOFF.md。116后端四文件固定本地已提交cd27d980，发布时需复核远端新接口；完整FFN接合、STA/每操作能量/质量仍待补。PPA保持null，未声称全链闭合。极小数舍入差和-128总线反号均有反例，新增模块AGENTS约束维护。

成果已完成，上传/PR状态以work/amlink1219/121/PUBLICATION.json回执及远端ref为准；不自动合并/关闭。Projects实测缺read:project，暂待有权限者同步；仓库上传不受影响。
# 2026-10-23 Issue117：ASIC资源计划首轮优化

负责人amlink1219；独立workspace_projects/ar117，task/117-asic-resource-optimization；base集成46804fb。接续Issue112规划，本轮208项新完整decode TLM已全部完成：128共同候选粗筛＋64预声明代表点补充＋16vector128跟进，五代表点覆盖四方法/2K8K/三seed。没有剩余运行、待补case或GPU/Slurm任务。71项测试通过（28新增＋43原v6），52＋40旧情景145payload SHA未变；独立verify通过208完整键集合、配置/源/receipt、336query覆盖及容量/相位/资源守恒。

执行提交44dbbbdbc2720963b2b24bf03cdf7582a2d97075、315862412e15695c3fa21e6c573d9e5f3547e70d、b1b4d183678e25f24b7b37c273fcb3f61c37483b；十份执行清单的数值/调度源SHA集合相同。容量only无时延收益，同1MiB映射小幅改善；vector128下SC筛选/PV三seed均值比同配置W8在8K快7.543849%，2K慢4.166733%。结果是合成事务条件估计，未做新PPL/RTL/EDA；完整面积/能量/A0仍null，不能宣称SC普遍更优或完整同面积验收。

正式入口architecture_tlm/resource_optimization_v1/README_ZH.md、RESULTS_ZH.md、results/analysis_20261023/SUMMARY.json与VALIDATION.json；交接work/amlink1219/117/HANDOFF.md含精确重汇总/验收命令。208项完整交付通过PR119，PR待审未合并，最终远端head/验证见PUBLICATION.json；统一台账已按CALIBRATED_ESTIMATE登记，check/render与8项台账测试通过。历史指定阅读镜像路径本机不存在、未同步。Projects缺read:project待补。不重复Issue116周期后端或PR120/Issue118供数/局部状态合同；后者待审且未纳入本轮。下方历史保留，实时状态以各任务最新回执为准。

---
# Issue118 FFN供数与局部状态合同（2026-10-23）

# Issue116 周期级TLM执行后端（2026-10-23）

已上传[PR120](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/120)，科学提交`8bea1dfd1db24263a6daea5e6a29de641b23f03c`，48个远端Git文件对象核验一致；Issue118验收清单/结果评论同步。PR待审、未合并。Projects现场返回INSUFFICIENT_SCOPES/read:project，待有权限者同步；仓库发布不受影响。此后仅发布回执/交接元数据不改科学结果。

负责人amlink1219；`task/118-ffn-storage-contract`；base集成46804fb；独立目录`workspace_projects/sf23`，未改cycle23任务工作树。六项供数合同执行、四非法配置、30功能测试、66整数场景888逐档输出通过，源/结果SHA已核。正式入口`architecture_tlm/ffn_storage_contract/README_ZH.md`与研究状态对齐报告；台账`ffn-storage-118-design`，DESIGN_PROOF。

T32保持/串行重读6.92us/3.2768ms，只是不同局部资源的SRAM->消费接口；计数48KiB→5KiB不是PPA收益。无新模型/PPL/RTL/STA/GPU/Slurm，无运行中作业。Issue116周期核心保持独立。任务分支/PR与Projects状态以`work/amlink1219/118/PUBLICATION.json`实际回执为准，不自动合并。接续命令和未验证项见同目录HANDOFF。

以下保留历史进度，旧“未合并”不是2026-10-23实时状态：

# Issue124 恢复吞吐与数据流消费实验（2026-10-23）

负责人amlink1219，独立task/124-recovery-dataflow，执行54a9968，基于集成46804fb3。先核Issue116、PR120/122和Issue123/PR125后划分范围；只消费既有合同，完整FFN由123继续，不复制116开发源。

48/48短投影条件仿真、24对同配置SC/W8、20项测试、8项登记守卫通过；独立验证467520操作及15类篡改拒绝。SC221.3625→205.75µs（−7.05%），同配置W8也205.75µs；主瓶颈是部分和接口。读宽128B单独候选206.35µs，增加双槽仅再降0.6µs而需更多保持状态。输入/门限为冻结合成数据，非完整FFN/PPL/STA/PPA。

入口architecture_tlm/ffn_dataflow_optimization/README_ZH.md，原始48gzip、3输入及SHA清单已准备；中央台账新增本任务1条/48行，当前分支36条564行，未合并其他任务登记须集成取并集。交接work/amlink1219/124/HANDOFF.md；结果提交c509772已上传PR127，未合并，回执见PUBLICATION.json。最终PR126已发布116冻结依赖；13份GitHub空缓存重建逐SHA与原20项测试通过，复现阻塞解除，执行源不漂移。Projects实测缺read:project，本机固定阅读镜像路径不存在，二者待同步。不自动合并/关闭Issue，无运行中的本任务作业。

---
以下为Issue98历史发布回执，与Issue116发布状态分开：

发布回执（2026-10-22）：科学文档提交`84eea461f22eff53f2e9502ada995a22cb7a0cac`已上传任务分支，[PR108](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/108)开放待审，未合并；7项源文件远端原始字节/SHA已核。后续发布元数据提交不改变报告。Projects实测缺read:project，待同步。

# Issue98 Prefill专项补充（2026-10-22）

负责人amlink1219；原Issue98负责人rayggxia保持。独立分支task/98-prefill-analysis-amlink1219，PR base pbit-tlm-attention-details-20261016@eb317e4f6fb1b0d8844887401f3275f128ef8a83。独立工作目录为本机visualizations/2026/10/22/01a16312-a5d6-71b0-a2e7-06d7139a3b28/prefill_upload，仅文档暂存和Git对象发布，不切换或覆盖其他checkout。

阶段：报告及文献证据本地整理完成，上传/PR状态以work/amlink1219/98/prefill/PUBLICATION.json的实际远端回执为准。正式入口architecture_tlm/benchmark_protocol_20261022/PREFILL_ANALYSIS_ZH.md。覆盖原16项文献与库内3项补充；核对当前统一TLM明确不含prefill/摘要首次构建/TTFT，建议数字prefill Attention＋概率decode，不改变联合FFN双阶段约定或活动默认。

验证：逐项来源、JSON/矩阵ID、相对链接、UTF-8/LF、SANTA算术与科学制品SHA，实际结果见work/amlink1219/98/prefill/VALIDATION.json。无新模型/PPL/训练/服务器/TLM/RTL/EDA；无运行任务。Projects实时缺read:project，待有权限者同步；PR审核/合并待定，不关闭Issue。恢复先查Issue98、PR106及本分支PR，交接见work/amlink1219/98/prefill/HANDOFF.md。

---

# Issue92 计算成本补充（2026-10-22，当前）

负责人amlink1219，接续Issue92/task/92-pbit-gate-pilot/PR94。新增部署运算账本qwen/results/pbit_gate_cost_20261022/README_ZH.md、COST.json及compute_cost.py。每自由块32连续乘法/40加法/8bit门控/9概率事件、两阶段；原三位置混合F21，层0/12/23候选QK省378/−165/379 MAC，小网第一层新增672乘法，不能称整体节能。含公共特征/动态归一化、GQA并集与固定S的PV边界。9模型形状、2304隐藏态门控等价、6项均值回算及独立只读审阅通过；没有新训练/Slurm/完整PPL/RTL/PPA，原质量结果保持。发布随PR94，待审未合并；上传核验以work/amlink1219/92/compute_cost/PUBLICATION.json实际回执为准。Projects沿同日已验证read:project不足待同步，不自动合并/关闭Issue。

---

# Issue92 第二轮直接目标优化（2026-10-22，当前）

负责人amlink1219，task/92-pbit-gate-pilot/PR94。CPU45项通过、90配置先冻结后独立盲评全部完成，GPU2744/2746/2748/2751均COMPLETED/0:0；无在运行作业。pbit三seed盲集遗漏1.978%/2.021%/24.845%，原T1 4.253%/3.550%/31.365%，强max4 2.069%/2.163%/24.723%。层0平均候选与质量改善；层12成本+0.5%；层23权衡。不能称全面优势/PPL/PPA。135文件小档逐SHA通过，原大数据/日志/32MB冻结留个人服务器。

正式入口qwen/results/pbit_gate_optimization_20261022/README_ZH.md；代码experiments/pbit_gate_pilot_20261022；交接work/amlink1219/92/HANDOFF.md。本轮科学成果64848a345c7926881f0c4b1ff543954fcc851eea已推送，PR94标题/报告已更新，开放待审、未合并；263项远端Git对象及8项关键原始SHA256已核，Issue92里程碑与结果评论已同步。准确回执见work/amlink1219/92/optimization_v2/PUBLICATION.json；后续提交仅补发布元数据。原第一轮负结果保持，已看blind不再调参，Projects权限不足待同步。

---

# Issue92 小型p-bit筛选网首轮训练（2026-10-22，当前）

负责人amlink1219；task/92-pbit-gate-pilot，独立workspace_projects/gt92，base集成83e15289。CPU2740检查16/16，单5090 GPU2741已COMPLETED/0:0，总45.90秒、训练评估30.05秒；本任务无在运行作业。实际执行53c24f28，48篇文章隔离、1296组，18模型+3基线全部完成。49参数网在三层holdout均落后原max4，预算略高仍差；证明服务器训练可行，未建立算法/PPA优势。未跑学生整模型PPL。

正式入口qwen/results/pbit_gate_pilot_20261022/README_ZH.md；代码experiments/pbit_gate_pilot_20261022；交接work/amlink1219/92/HANDOFF.md。teacher NPZ、LLM与语料保留本人服务器，54项小报告SHA已核。结果提交074172c93b00b30eef30923223fe8a408b1ccd13已推送，[PR94](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/94)开放待审、未合并；82项远端Git对象和8项关键原始SHA256已核，Issue92验收与结果评论已同步。Projects因缺read:project待同步，未进行看板写入。实际回执work/amlink1219/92/PUBLICATION.json；不自动合并。

---

# 2026-10-22 Issue37：Ising最新实现与结果补充

负责人amlink1219；目标rayggxia-workspace/pbit-llm-qwen-baselines；基线5b26c80c28ab22383f12ab31046dd723ca985abb；分支task/37-ising-update-20261022；最小稀疏目录workspace_projects/iu37。结果提交18bd5f299cba76ff0c33dbf0d02d8133eac165d7已推送，[PR89](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/89)开放待审、未合并。

入口architecture_tlm/attention_comparison/ISING_UPDATE_20261022_ZH.md，原README已加最新索引。固定PR79/80/82/86/88来源，补入后缀PPL、真实QKV、驱动量化、v5时序与旧数字参考关系；旧原件/默认不改，不接管Issue78/87。19来源SHA、90配置完成、固定预算覆盖、8组TLM中位数/单位及null PPA共46项离线检查通过；行为与TLM由独立代理审阅。本次无新模型/Slurm/PT，也未重跑上游采样器测试。

交接/来源/验证见work/amlink1219/37/*20261022*与HANDOFF；另21项文档/历史保留检查通过，远端ref/PR head及7项稳定文件SHA已回读核验，PR82/86/88当前head/未合并状态也已复核。发布回执ISING_UPDATE_PUBLICATION_20261022.json。实时GraphQL缺read:project，看板待同步。下一步审阅PR89；最终同质量完整Attention PPA仍未验收，不自动关闭Issue37或合并。

下方保留历史时点：

# 2026-10-20 Issue76 四条硬件训练路线讨论稿

负责人amlink1219；task/76-fourtrack-training-plan；base e4990c15；独立最小稀疏目录workspace_projects/tr76。范围为四条既定训练路线和服务器讨论稿，当前文档已完成内容/结构/链接/样式及独立审阅，已推送PR#77待审未合并；没有训练作业或新PPL/PPA。

正式入口architecture_tlm/training_plans/four_tracks_20261020/TRAINING_PLAN_ZH.md及同目录Word/PLAN.json；辅助资料work/amlink1219/76/。难度3→1→4→2，第3条按用户追问核Git后保留variable，固定8块仅现有评测对照。最新PR52已合并、完整WT2已完成；下方旧“PR52/71待审”等为历史时点，不作当前状态。

实际验证与五项独立审阅修正在VALIDATION/REVIEW，交接见HANDOFF。下一步与服务器方确认执行资源、数据与质量/容量约束后单独建立执行任务。本稿不启动或接管现有评测任务，不自动合并。PR链接：https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/77；上传与看板结果见本任务PUBLICATION回执，当前看板状态为pending_permission。

## 以下保留历史任务记录

结果提交`ac5626fbabcaee09e5ee0c25d376be1f46335bc5`已推送；PR71开放待审、未合并；远端ref/PR head及8项稳定Git blob SHA已核验，见PUBLICATION.json。无模型训练/PPL/PPA。

## ReMix v1精读，Issue70（2026-10-19）

用户指定v1正文和附录核查完成，Zotero原条目/PDF保持，唯一机器note25FR4EFX；24例独立数学校核通过。入口architecture_tlm/research_readings/REMIX_V1_ZH_20261019.md，工作资料work/amlink1219/70/。没有模型复现、训练/PPL/PPA；研究原任务61已关闭，本任务独立交付待审。

本轮p-attention能量调研已上传`a0d08a4208fe505c81aa150abf807fd5e622a0f2`，PR63开放待审未合并；远端ref/PR head及17项稳定制品Git blob已核验，回执P_ATTENTION_PUBLICATION.json。无新模型/训练/PPL/PPA；同事Issue50/59不重交。

## 2026-10-19 可训练能量p-attention调研

接续Issue61/PR63，核查PR52 e3c5e957c3769b5fc6867b42a52facace647a83b仍开放未合并。现有screen_ising已经不显式计算Softmax，直接score差热浴CTMC；新路线是蒸馏筛选器＋低维/低位条件能量＋实际有限链训练，独立mask与binary/tree作为另一结构。报告architecture_tlm/p_attention_feasibility_20261019/README_ZH.md；计划未执行，没有新模型/PPL/GPU/PPA。现有原始/负面证据保持，Issue50/59作业不重交。数学核验与文献入库回执在work/amlink1219/61/p_attention/。Projects仍按既有scope待同步。

本轮activation-only研究已上传`de10df308c78d5983ad4e1461518e8c9dc8d514d`，PR63开放待审、未合并；远端ref/PR head及18项稳定制品Git blob已核，实际回执ACTIVATION_ONLY_PUBLICATION.json。没有新模型PPL、训练或PPA。

本轮用户限定三投影＋连续up＋仅激活p-bit；精确A/B/C未找到执行/PPL，A只在历史§27提案。旧双支/AND/SC不得按名称迁移结论。activation_only报告、结构化计划、21tip/506历史对象审计、StochA直接负面先例和Zotero本批核验已整理；未训练。

用户再次核实门控历史：双路gate/value及三投影K4 AND-bank均已做，不能把保留门控/多位编码当新主线。当前优先训练B4/T32/K32随机计算FFN；旧结构须明确新增条件和数字/原实现对照。报告§4.2与JSON已纠正，未启动训练。


用户纠正后的增量：旧两投影全路径降为高风险诊断，加入匹配20层连续入口与四层4bit原件、表示/采样/结构控制门禁；补充AGENTS防止按单层结果重复优先推荐失败扩层路线。没有新训练或质量结果。

# Issue61：硬件感知训练研究与待执行计划（当前状态）

日期2026-10-19；负责人amlink1219；task/61-hardware-aware-training，独立目录workspace_projects/ht61；base集成88764ec8f6f00ed05f4ab337902bd23ad08cc4a8。身份75301230、目标repo1420564659和push/admin=true已核实。Issue33已关闭、PR58已合并；下方旧“PR58待审”等文字是历史快照。

用户确认较充足H100。本次核Extropic Z1T及一手训练文献、旧P-DNN/AND/variance负结果，提出当前B4/T32/K32到T16的真实短流微调、QK筛选器/有限Ising蒸馏、原生sigmoid/tanh激活及从头训练、DyT独立对照。正式报告与JSON在architecture_tlm/，来源和可执行交接见work/amlink1219/61。

本地56个精确条件Binomial均值/方差案例、SiLU/tanh恒等式、非线性顺序反例、同参数宽度、相对链接与4个既有源码SHA校核通过；仅CPU标准库检查，不是PPL、训练或PPA。独立只读评审后补DyT的embedding/alpha初始化。没有新训练、H100申请、Slurm任务、checkpoint或数据下载。

Issue50/PR52完整联合及Issue59代表任务属于jieruiz，只读公开结果，本任务不重交、不改变其状态。训练数据版本、H100实际调度/配额和本人存储尚需在执行Issue冻结。文献仅公开本批状态，不上传全库书目/PDF。

研究交付已推送777b3e51aec48c5c689c78e2257e18243c18c4b8，PR#63开放待审、未合并（https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/63）；远端ref、PR head、13项文件范围和稳定manifest的Git blob已核验。真实回执见work/amlink1219/61/PUBLICATION.json。看板按实际GraphQL响应记录，权限不足不影响报告交付。不自动合并或关闭Issue61。

以下为继承历史记录，最新协作状态需重新查询远端：

# 分层FFN参考采用已上传（当前状态）

已核验目标任务分支结果提交`e8eec4c8deb296db4c4ed937c5c46192a782c6f4`，[PR58](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/58)开放待审、未合并，接续Issue33。B4/T32/K32主参考及三个对照、源码SHA、13项CPU核心测试和4profile接口均已交付。此前“本地待提交”等段落保留为历史准备快照，准确回执见STRATIFIED_REFERENCE_PUBLICATION.json。

本次没有新模型PPL/GPU作业、未改TLM/PPA默认；PR52完整联合仍未收齐，恢复重新核状态。看板scope不足待同步。稳定manifest不含易变进度/交接/发布回执，后续元数据提交不改变已核验的方法和配置。

# Issue33：采用分层FFN作为后续仿真主参考（2026-10-19）

负责人amlink1219；分支task/33-stratified-ffn-reference，独立目录workspace_projects/fa33；base集成ed0c7a4e8e9546ec89895135efff36aa8a00d568（PR42已合并）。主参考B4/T32/K32，正式配置/复用入口architecture_tlm/ffn_stratified_reference；PR47已经合并，FFN-only完整WT2三seed11.736131±0.000243（BF1611.652735，+0.716%），为既有结果核查，本次未重跑PPL。代码/配置已通过13项核心测试、4profile接口和4源码SHA验证，本次采用变更尚待上传。

PR52读取e3c5e957c3769b5fc6867b42a52facace647a83b，仍Draft未合并；已发布B4T32联合S六档4096目标后缀曲线，完整2430/2461在公开记录中尚未收齐，本任务不重复其工作。FFN-only与联合、后缀与完整、T/K与Ising S分别记录。新参考不改变旧Attention-only原FFN控制或TLM物理PPA默认。

原Issue48/PR49结果已在8dd1b06a上传待审，34/34后缀实验完成；Issue33原PR42现已合并。旧进度段落仅为历史快照，最新协作状态以远端Issue/PR为准。交接见work/amlink1219/33/HANDOFF.md。

# amlink1219 项目进度

更新时间：2026-10-19T03:58:53.771030+00:00；负责人amlink1219（GitHub id75301230）。
正式目标：rayggxia-workspace/pbit-llm-qwen-baselines（repository id1420564659）。2026-10-19实时核验push/admin均为true。
本轮补传基线：pbit-tlm-attention-details-20261016 @c1555ae6594c863011a70845d88c950a68de732b；阶段：五项任务分支均已推送，五个PR待审、未合并。
没有自动合并或关闭Issue；分支、PR待审与已合并分别记录。Projects同步状态见各任务PUBLICATION.json。

| Issue | 分支 / PR | 本轮结果与验证 |
|---|---|---|
| [#1](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/1) | [task/1-amlink1219-hardware-onboarding](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/tree/task/1-amlink1219-hardware-onboarding)；[PR#41](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/41)（待审、未合并） | 协作规范与本机交接；原manifest 9/9。 |
| [#33](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/33) | [task/33-attention-value-plan](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/tree/task/33-attention-value-plan)；[PR#42](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/42)（待审、未合并） | 文献与623行实验计划；原manifest 15/15，计划不等于已执行。 |
| [#35](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/35) | [task/35-attention-e01](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/tree/task/35-attention-e01)；[PR#43](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/43)（待审、未合并） | 原BF16完整WT2 PPL11.652735047455899；CPU39/39，pilot12/12、full465/465；原manifest74/74。 |
| [#36](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/36) | [task/36-digital-attention-reference](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/tree/task/36-digital-attention-reference)；[PR#44](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/44)（待审、未合并） | 在线Softmax+GQA数字参考，10/10解析测试及3上下文账本；原manifest16/16；完整PPA未闭合。 |
| [#37](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/37) | [task/37-attention-comparison](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/tree/task/37-attention-comparison)；[PR#45](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/45)（待审、未合并） | Slurm2164完成，9/9快照测试、32/32事务场景、40返回文件SHA；原manifest68/68；完整物理PPA和PPL尚未验证。 |

Issue37依赖Issue36：PR base为task/36-digital-attention-reference；其余PR base为上述集成分支。
各分支使用相同的AGENTS规则并集与个人进度总表，避免共享文档相互覆盖；正式代码和成果仍按任务分支隔离。
历史执行提交、配置、输入版本、Slurm终态和原始成果散列均保持；原manifest按PUBLICATION.json中的pre_publication_commit读取，不能用后续更新的STATUS/HANDOFF冒充原字节。

正式入口：Issue33 architecture_tlm/ATTENTION_PBIT_VALUE_AND_EXPERIMENT_PLAN_ZH_20261018.md；Issue35 experiments/attention_e01 与 qwen/results/attention_e01_20261019；Issue36 architecture_tlm/digital_attention_reference；Issue37 architecture_tlm/attention_comparison。
辅助/交接：work/amlink1219/<Issue>/。本地工作目录及原任务提交见各PUBLICATION.json；旧STATUS可从原提交恢复。
原始大trace/NPZ留服务器本人/home/Weican_Chen/projects/attention-e01-issue35；Issue37冻结源/原始结果留本人/home/Weican_Chen/projects/attention-compare-issue37。当前没有本轮在运行作业，不重交旧实验。
下一步：审阅上述PR；继续完整随机Attention PPL、有限字长数字实现、真实随机相关性与同工艺PPA验证，不能由代理成本或局部NMSE宣布优势。

## PR42 原始交付状态（历史时点）

源head：ee47cb86c75f8a2bc049f25507f785f087ed671d。以下保留该任务新增的历史状态；最新合并状态以Issue55/相应Issue和GitHub为准。

# Attention历史质量证据核查（2026-10-19T06:28:37.698199+00:00）

负责人amlink1219；Issue33 / PR42补充。已确认历史全部24层decode Attention PPL：单独Ising、max4筛选、筛选＋准确Softmax IID及随机投影＋Ising；各自协议/FFN不同，所核Attention结果是WT2短后缀。尚未找到max4筛选→有限时间Ising同一路联合PPL，当前固定512候选/S32/128配置也未质量验收。

报告architecture_tlm/ATTENTION_QUALITY_EVIDENCE_AUDIT_ZH_20261019.md；固定源与SHA索引work/amlink1219/33/QUALITY_AUDIT_20261019.json。未启动新GPU/Slurm或重跑旧实验。后续只补该联合路径、原FFN隔离对照和当前成本模型配置的质量，完整WT2与decode后缀分别记录。其余PR仍待审未合并，Projects仍待授权。

以下保留此前五项发布时点进度：

# amlink1219 项目进度

更新时间：2026-10-19T03:58:53.771030+00:00；负责人amlink1219（GitHub id75301230）。
正式目标：rayggxia-workspace/pbit-llm-qwen-baselines（repository id1420564659）。2026-10-19实时核验push/admin均为true。
本轮补传基线：pbit-tlm-attention-details-20261016 @c1555ae6594c863011a70845d88c950a68de732b；阶段：五项任务分支均已推送，五个PR待审、未合并。
没有自动合并或关闭Issue；分支、PR待审与已合并分别记录。Projects同步状态见各任务PUBLICATION.json。

| Issue | 分支 / PR | 本轮结果与验证 |
|---|---|---|
| [#1](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/1) | [task/1-amlink1219-hardware-onboarding](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/tree/task/1-amlink1219-hardware-onboarding)；[PR#41](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/41)（待审、未合并） | 协作规范与本机交接；原manifest 9/9。 |
| [#33](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/33) | [task/33-attention-value-plan](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/tree/task/33-attention-value-plan)；[PR#42](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/42)（待审、未合并） | 文献与623行实验计划；原manifest 15/15，计划不等于已执行。 |
| [#35](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/35) | [task/35-attention-e01](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/tree/task/35-attention-e01)；[PR#43](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/43)（待审、未合并） | 原BF16完整WT2 PPL11.652735047455899；CPU39/39，pilot12/12、full465/465；原manifest74/74。 |
| [#36](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/36) | [task/36-digital-attention-reference](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/tree/task/36-digital-attention-reference)；[PR#44](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/44)（待审、未合并） | 在线Softmax+GQA数字参考，10/10解析测试及3上下文账本；原manifest16/16；完整PPA未闭合。 |
| [#37](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/37) | [task/37-attention-comparison](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/tree/task/37-attention-comparison)；[PR#45](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/45)（待审、未合并） | Slurm2164完成，9/9快照测试、32/32事务场景、40返回文件SHA；原manifest68/68；完整物理PPA和PPL尚未验证。 |

Issue37依赖Issue36：PR base为task/36-digital-attention-reference；其余PR base为上述集成分支。
各分支使用相同的AGENTS规则并集与个人进度总表，避免共享文档相互覆盖；正式代码和成果仍按任务分支隔离。
历史执行提交、配置、输入版本、Slurm终态和原始成果散列均保持；原manifest按PUBLICATION.json中的pre_publication_commit读取，不能用后续更新的STATUS/HANDOFF冒充原字节。

正式入口：Issue33 architecture_tlm/ATTENTION_PBIT_VALUE_AND_EXPERIMENT_PLAN_ZH_20261018.md；Issue35 experiments/attention_e01 与 qwen/results/attention_e01_20261019；Issue36 architecture_tlm/digital_attention_reference；Issue37 architecture_tlm/attention_comparison。
辅助/交接：work/amlink1219/<Issue>/。本地工作目录及原任务提交见各PUBLICATION.json；旧STATUS可从原提交恢复。
原始大trace/NPZ留服务器本人/home/Weican_Chen/projects/attention-e01-issue35；Issue37冻结源/原始结果留本人/home/Weican_Chen/projects/attention-compare-issue37。当前没有本轮在运行作业，不重交旧实验。
下一步：审阅上述PR；继续完整随机Attention PPL、有限字长数字实现、真实随机相关性与同工艺PPA验证，不能由代理成本或局部NMSE宣布优势。

## PR43 原始交付状态（历史时点）

源head：d95334373765d5952e023e00e20c1a7152bfaf95。以下保留该任务新增的历史状态；最新合并状态以Issue55/相应Issue和GitHub为准。

# amlink1219 项目进度

更新时间：2026-10-19T03:58:53.771030+00:00；负责人amlink1219（GitHub id75301230）。
正式目标：rayggxia-workspace/pbit-llm-qwen-baselines（repository id1420564659）。2026-10-19实时核验push/admin均为true。
本轮补传基线：pbit-tlm-attention-details-20261016 @c1555ae6594c863011a70845d88c950a68de732b；阶段：五项任务分支均已推送，五个PR待审、未合并。
没有自动合并或关闭Issue；分支、PR待审与已合并分别记录。Projects同步状态见各任务PUBLICATION.json。

| Issue | 分支 / PR | 本轮结果与验证 |
|---|---|---|
| [#1](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/1) | [task/1-amlink1219-hardware-onboarding](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/tree/task/1-amlink1219-hardware-onboarding)；[PR#41](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/41)（待审、未合并） | 协作规范与本机交接；原manifest 9/9。 |
| [#33](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/33) | [task/33-attention-value-plan](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/tree/task/33-attention-value-plan)；[PR#42](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/42)（待审、未合并） | 文献与623行实验计划；原manifest 15/15，计划不等于已执行。 |
| [#35](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/35) | [task/35-attention-e01](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/tree/task/35-attention-e01)；[PR#43](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/43)（待审、未合并） | 原BF16完整WT2 PPL11.652735047455899；CPU39/39，pilot12/12、full465/465；原manifest74/74。 |
| [#36](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/36) | [task/36-digital-attention-reference](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/tree/task/36-digital-attention-reference)；[PR#44](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/44)（待审、未合并） | 在线Softmax+GQA数字参考，10/10解析测试及3上下文账本；原manifest16/16；完整PPA未闭合。 |
| [#37](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/37) | [task/37-attention-comparison](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/tree/task/37-attention-comparison)；[PR#45](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/45)（待审、未合并） | Slurm2164完成，9/9快照测试、32/32事务场景、40返回文件SHA；原manifest68/68；完整物理PPA和PPL尚未验证。 |

Issue37依赖Issue36：PR base为task/36-digital-attention-reference；其余PR base为上述集成分支。
各分支使用相同的AGENTS规则并集与个人进度总表，避免共享文档相互覆盖；正式代码和成果仍按任务分支隔离。
历史执行提交、配置、输入版本、Slurm终态和原始成果散列均保持；原manifest按PUBLICATION.json中的pre_publication_commit读取，不能用后续更新的STATUS/HANDOFF冒充原字节。

正式入口：Issue33 architecture_tlm/ATTENTION_PBIT_VALUE_AND_EXPERIMENT_PLAN_ZH_20261018.md；Issue35 experiments/attention_e01 与 qwen/results/attention_e01_20261019；Issue36 architecture_tlm/digital_attention_reference；Issue37 architecture_tlm/attention_comparison。
辅助/交接：work/amlink1219/<Issue>/。本地工作目录及原任务提交见各PUBLICATION.json；旧STATUS可从原提交恢复。
原始大trace/NPZ留服务器本人/home/Weican_Chen/projects/attention-e01-issue35；Issue37冻结源/原始结果留本人/home/Weican_Chen/projects/attention-compare-issue37。当前没有本轮在运行作业，不重交旧实验。
下一步：审阅上述PR；继续完整随机Attention PPL、有限字长数字实现、真实随机相关性与同工艺PPA验证，不能由代理成本或局部NMSE宣布优势。

## PR44 原始交付状态（历史时点）

源head：1b0af7604037ce8a772063bd9583ce9e1f96f0e5。以下保留该任务新增的历史状态；最新合并状态以Issue55/相应Issue和GitHub为准。

# amlink1219 项目进度

更新时间：2026-10-19T03:58:53.771030+00:00；负责人amlink1219（GitHub id75301230）。
正式目标：rayggxia-workspace/pbit-llm-qwen-baselines（repository id1420564659）。2026-10-19实时核验push/admin均为true。
本轮补传基线：pbit-tlm-attention-details-20261016 @c1555ae6594c863011a70845d88c950a68de732b；阶段：五项任务分支均已推送，五个PR待审、未合并。
没有自动合并或关闭Issue；分支、PR待审与已合并分别记录。Projects同步状态见各任务PUBLICATION.json。

| Issue | 分支 / PR | 本轮结果与验证 |
|---|---|---|
| [#1](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/1) | [task/1-amlink1219-hardware-onboarding](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/tree/task/1-amlink1219-hardware-onboarding)；[PR#41](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/41)（待审、未合并） | 协作规范与本机交接；原manifest 9/9。 |
| [#33](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/33) | [task/33-attention-value-plan](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/tree/task/33-attention-value-plan)；[PR#42](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/42)（待审、未合并） | 文献与623行实验计划；原manifest 15/15，计划不等于已执行。 |
| [#35](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/35) | [task/35-attention-e01](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/tree/task/35-attention-e01)；[PR#43](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/43)（待审、未合并） | 原BF16完整WT2 PPL11.652735047455899；CPU39/39，pilot12/12、full465/465；原manifest74/74。 |
| [#36](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/36) | [task/36-digital-attention-reference](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/tree/task/36-digital-attention-reference)；[PR#44](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/44)（待审、未合并） | 在线Softmax+GQA数字参考，10/10解析测试及3上下文账本；原manifest16/16；完整PPA未闭合。 |
| [#37](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/37) | [task/37-attention-comparison](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/tree/task/37-attention-comparison)；[PR#45](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/45)（待审、未合并） | Slurm2164完成，9/9快照测试、32/32事务场景、40返回文件SHA；原manifest68/68；完整物理PPA和PPL尚未验证。 |

Issue37依赖Issue36：PR base为task/36-digital-attention-reference；其余PR base为上述集成分支。
各分支使用相同的AGENTS规则并集与个人进度总表，避免共享文档相互覆盖；正式代码和成果仍按任务分支隔离。
历史执行提交、配置、输入版本、Slurm终态和原始成果散列均保持；原manifest按PUBLICATION.json中的pre_publication_commit读取，不能用后续更新的STATUS/HANDOFF冒充原字节。

正式入口：Issue33 architecture_tlm/ATTENTION_PBIT_VALUE_AND_EXPERIMENT_PLAN_ZH_20261018.md；Issue35 experiments/attention_e01 与 qwen/results/attention_e01_20261019；Issue36 architecture_tlm/digital_attention_reference；Issue37 architecture_tlm/attention_comparison。
辅助/交接：work/amlink1219/<Issue>/。本地工作目录及原任务提交见各PUBLICATION.json；旧STATUS可从原提交恢复。
原始大trace/NPZ留服务器本人/home/Weican_Chen/projects/attention-e01-issue35；Issue37冻结源/原始结果留本人/home/Weican_Chen/projects/attention-compare-issue37。当前没有本轮在运行作业，不重交旧实验。
下一步：审阅上述PR；继续完整随机Attention PPL、有限字长数字实现、真实随机相关性与同工艺PPA验证，不能由代理成本或局部NMSE宣布优势。
