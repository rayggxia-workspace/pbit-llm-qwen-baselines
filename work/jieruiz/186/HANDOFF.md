# Issue186 / PR190：HBM完整25项已核验

更新2026-10-25T10:44:17.130922+00:00；负责人jieruiz；分支task/186-mature-scheduling；目录tmp/mature-scheduling-issue186-20261025；base task/182-memory-hierarchy，PR190待审未合并。

本地实现和25项全部completed/SHA/36层验证：e7505ee4的Slurm3019/3020（17项），43b7b1ff的3037/3038（8项）。104回归，36微基准；旧DDR四模式逐段时间/能量不变。2K ms/token：BF16 599.340→402.629；W8 426.364→333.664；SC R8准确503.639→438.038；SC R8筛选PV三seed474.154→407.167。核心100MHz、共享8MiB/64GBs SRAM、随机采样不变。HBM16GiB理论256GB/s、实际连续读185.786；新增256B主机事务/有效64admitted，PV32→128分批。源快照不可改。

成果architecture_tlm/unified_v6/HBM_RESULTS_ZH.md、HBM_TIMING_ZH.md、results/hbm_20261025、记录本O11；work/jieruiz/186/HBM_DELIVERY_AUDIT.json。原始RESULT/trace保留个人远端pbit-scheduling-issue186-20261025/hbm_e7505ee4和hbm_43b7b1ff；无运行中本任务，无GPU/PPL/RTL/PT。HBM占位电流禁用，总物理能量/面积null，不比较不完整小计。GU数值宏/普通算术吞吐未签核。FFN主体约267ms不随HBM显著变快；KV同组单通道热点尚在，可另测XOR映射，未宣称已优化。

本轮发布状态以HBM_PUBLICATION.json为准；尚未生成回执时仅本地完成。保持Issue186开放，PR不自动合并。看板缺read:project，待有权限成员同步。恢复先核远端Issue/PR、collect_hbm.py及--pipeline，analyze_hbm.py --require-complete，再report_hbm.py；勿重跑健康/已完成任务。

---
# Issue186 / PR190：HBM 时序对照运行中

更新2026-10-25T10:21:59.630749+00:00；负责人jieruiz；分支task/186-mature-scheduling；工作目录tmp/mature-scheduling-issue186-20261025；PR190未合并，base仍task/182-memory-hierarchy。

本地已实现mature_hbm2_narrow/wide/pipelined，100MHz核心、8MiB/64GBs SRAM、FFN R8和采样固定。执行e7505ee4/Slurm3019+3020的17项，43b7b1ff/Slurm3037+3038的8项；均CPU任务，无GPU/PPL。微基准16+20项completed，DDR旧/新4种访问每段时延与能量相等；HBM连续读28.65/112.10/185.79GB/s。104回归通过。全模型以HBM_COLLECTION/HBM_PIPELINE_COLLECTION为实时完成依据，尚未全部收齐，不能报最终结果。HBM功率占位所以关闭PowerAnalysis，总物理能耗/面积null。

恢复：读Issue186/PR190与HANDOFF，collect_hbm.py（及--pipeline）核远端封存SHA；analyze_hbm.py --require-complete待25项完成后验证。源码不可修改，不重提交健康任务。完成后写完整时间表、更新同PR/Issue/记忆；不自动合并。尚未发布本轮结果。看板缺read:project，待权限。

---
历史交接保留：

# Issue186 / PR190：部分和局部驻留与128阵列对照

更新2026-10-25T08:40:00.103148+00:00；负责人jieruiz；目标rayggxia-workspace/pbit-llm-qwen-baselines；分支task/186-mature-scheduling；独立目录tmp/mature-scheduling-issue186-20261025；base仍task/182-memory-hierarchy@0341b4ac。核心代码和24项结果已经推送7714f509a4622daed9e352859101b88673b055c2，PR190开放待审、未合并。最终远端回执见LOCALITY_PUBLICATION.json；补充说明和本交接已随9fed8c65上传。

本轮原始13项Slurm2995/源b1df81d2，修复跨窗口预取后11项Slurm3008/源829559dc；全部completed且原RESULT、EXECUTION、汇总SHA核验。首轮结果保留，原45项不改。两条源快照只改局部驻留实现及测试；控制0/1没有重跑不变路径。101项unified_v6测试通过；24项最终交付审计通过。没有GPU/PPL、新RTL/PT或真实模型载荷。

最终2K单token ms：原8×64=509.471；8×64/R8=503.639；R16/全K相同；16×64/R8=453.289；2×128/R8双组源=506.931、单组581.392；8×128/R8双组=434.075；8×128全K双组=432.817；同轮W8数字426.364。部分和每层17.6445→2.0586MiB，R8减少88.33%；数学/权重总量未变。扩到8×128增加4倍计算/权重位置，不是同面积收益。

成果：architecture_tlm/unified_v6/FFN_LOCALITY_ZH.md、results/locality_20261025/（含window_prefetch）、ARCHITECTURE_OPTIMIZATION_LOG_ZH.md及EVIDENCE索引。默认实现保留，configure()显式启用候选；新增多检查点源是有限宏，未映射Issue95真实端点；完整面积/能量null。SRAM/DRAM/Attention保持原合同。看板缺read:project，待有权限维护者同步。

恢复：先核Issue186/PR190与依赖PR183；collect_locality.py与--prefetch核原件；analyze_locality.py --stage1与无参数、make_locality_report.py、verify_locality_delivery.py重建和核验。原始远端两个locality_<commit8>/source不可修改。无需重跑健康任务。下一步优先R8本地bank/检查点端口RTL/STA/PT与GU编译器/真实模型质量闭环；不自动合并或切换默认。

---
历史记录：

# Issue186 / PR190：成熟调度共同模型交付

更新：2026-10-25T06:33:00.231770+00:00；负责人jieruiz；目标rayggxia-workspace/pbit-llm-qwen-baselines。
分支task/186-mature-scheduling，独立目录tmp/mature-scheduling-issue186-20261025；依赖PR183@0341b4ac，PR190的base=task/182-memory-hierarchy。代码与45项结果已上传，科学head49fb2358；PR190已转ready，待审未合并，远端树/核心字节核验通过。最终元数据head以PUBLICATION.json/PR190为准，不自动合并。

已完成：共同有限tile/slot/响应生命周期、数字本地状态与K64 W8恢复、SG实际DRAM、默认mature_ddr4。110回归；真实DRAM10小整机＋8SG；原生ONNXim25情景和官方39/47，ASan/UBSan结果SHA一致且stderr零；独立CMake重新构建DRAM桥8项结果一致。45完整Qwen3-4B/36层/2K或8K decode合成事务按completed MANIFEST/配置/源码/结果SHA核验，主概率三seed。

主要ms/token：2K BF16准确599.340、W8准确426.364、SC准确509.471、W8筛选PV396.842、SC筛选PV479.976、SC校正拒绝700.421；8K依次756.072/582.989/666.099/419.557/502.691，未测8K拒绝。同Attention的W8更快，不能将联合加速归因SC FFN。数字tile、SG和SC阵列有限扫描，64容量候选62合法；4MiB/64bank只作结构性建议，不冒称完整重跑。

本轮Slurm2938/2942/2943/2976/2984/2986/2987/2993/2994已封存完成；失败2941（小fixture预算）、2983（下载）、2985（fmt链接）原件保留。无GPU/PPL/训练/新RTL/PT；源快照未改、未碰其他任务。大trace/构建在个人远端pbit-scheduling-issue186-20261025，Git小汇总/索引。23个本任务重复输入/缓存已逐SHA确认远端后回收2,936,618B，见CLEANUP_COMPLETED/ATTEMPTS_AND_RECOVERY。

成果：architecture_tlm/unified_v6/MATURE_SCHEDULING_ZH.md、SCHEDULER_RESEARCH_ZH.md；results/scheduling_20261025/COMPARISON.csv/AGGREGATE.json/FINAL_AUDIT.json；原生和DRAM桥接可执行源码在probes/。HANDOFF见work/jieruiz/186。

限制：MAC512/拍、片上接口、GU定点恢复、NL独立随机供给和部分PPA仍宏假设；全芯片能耗/面积null。DRAM负ACT未截零、不反馈时序；core J仅诊断。不是完整ONNXim Qwen移植、全局最优或全芯片周期精确。Projects缺read:project待同步；Issue187/PR189其他成员调研只读。

下一步：先复核PR190最后head及依赖PR183；验收前不关闭Issue186。优先做计数/系数状态双缓冲和恢复流水线，给数字参考相同优化机会；质量与RTL/PPA另闭环。没有本任务待完成仿真或需重复提交的健康作业。

## 可执行恢复步骤

1. 读远端Issue186/PR190/依赖PR183和当前STATUS，不把旧提交回执的submitted当最新状态。
2. 本地核查HEAD、远端workspace URL及GitHub jieruiz身份；原始运行源码bab9721d/6b0df70b不可改。源/配置矩阵在各SOURCE和SUBMISSION。
3. `collect_schedule.py`、`--w8`、`--bf16-8k`、`--ablation`分别从4个个人输出根按SHA收集；`analyze_schedule.py --require-complete`、`verify_delivery.py`、`make_report.py --require-complete`生成45项汇总。
4. 无需重跑模型或上游probe。原生与bridge README含构建命令及边界；失败日志索引保留。重建新结果用新目录。
5. 交付后继续只用同PR分支更新、待审核不合并；查看PUBLICATION.json确认远端实际head，模型总能耗/面积不得用priced subtotal填充。

---
以下为阶段日志，仅用于历史追溯：

# Issue186 交接

更新时间 2026-10-25T05:33:14.297869+00:00。负责人jieruiz；工作树 `tmp/mature-scheduling-issue186-20261025`。任务分支`task/186-mature-scheduling`；基线0341b4ac/PR183，PR目标base `task/182-memory-hierarchy`；当前未合并。

## 已完成

共同 tile 有界队列与slot generation / retire、显式数字operand存储、真实DRAMSys SG；103旧回归通过。SG gate2938封存于results/scheduling_20261025/sg_gate。实际联调2942十项完成，VERIFIED.json保留远端原文件hash和小汇总。2941失败因小fixture2块装不下mandatory blocks，已修正为4，生产默认8未改。

## 运行中和不可变执行

31项数组2943，max20 CPU workers，未请求GPU。执行源码commit `bab9721d629df643e4096f5111a0a4ac5722ed3e`，57file闭包见SOURCE_bab9721d.json，包SHA `39873a2cd859d3ee8d16aef51f780703ae1ea4f212125c08d40ef37dd1d06c1d`。
远端 `/home/Hongjie_Zeng/projects/pbit-scheduling-issue186-20261025/full_bab9721d/`，source/不可改；results/case_N为各唯一输出；logs/为Slurm日志。SSH使用既有lab-server-ai配置，不提交凭据。只从MANIFEST.status=completed以及RESULT_SUMMARY/EXECUTION/rawRESULT的SHA确认完成。

## 待办

1. 独立审计共同pipeline，完成新tests及原生ONNXim最小probe；需要升级/远程操作由root执行，子agent此前升级阻塞，未完成的构建不能写成已运行。
2. 收集31项完成数据、失败单列；`analyze_schedule.py`检查封存summary/config/version/rawSHA。原始大JSON/trace留个人远端项目，Git只小汇总/manifest。
3. 对比共同资源BF16/W8/SC、筛选PV/拒绝、2K/8K和有限tile/SG/阵列扫描，区分单seed资源试探与3seed主要概率结果。旧PR183结果明确其旧schedule版本。
4. 完成SCHEDULER_RESEARCH_ZH/MATURE_SCHEDULING_ZH，发布同一任务分支/PR，更新Issue/STATUS/memo。不要自动合并。看板缺read:project，待同步。

## 范围

合成事务和架构时延；无PPL/质量、GPU速度、新RTL/PT或完整芯片PPA。SC固定点GU restore仍有数值宏待验；价格为空不等于0。DRAMPower负ACT已知限制原值保留。#187广泛论文矩阵由rayggxia负责，本任务不改其目录。

## 本轮后续更新（2026-10-25）

- PR已创建并附本对话：#190，https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/190 ，目前draft，远端首次head5f3e5473；后续本地提交尚需继续推送。
- 新增7个共同tile测试；110项回归已通过，UNITTEST_110.txt。SRC bab9721d 的31主配置不改。
- 审计发现旧数字W8仅按整行一次scale，漏每K64块独立scale。修正并显式记录FP32 partial buffer、读写/端口；MAC吞吐仍是宏假设。补测7项Slurm2976，执行6b0df70b43055fa235fb34a9933ba20f4d394895，目录w8_6b0df70b。7项均已完成核SHA。修正主要增加动作数，被DMA等待覆盖，所以common_W8时间426.32053→426.36383ms，不可把补计成本说成调度收益。
- 增补8K BF16原精度参考Slurm2984，执行仍用bab9721d不可变source；配置commit73727073和BF16_8K_MATRIX.json，独立输出bf16_8k_bab9721d，待收集。
- 原生ONNXim：2983下载HTTP超时自然失败；2985离线源码编译因fmt缺少header-only链接失败。均保留原目录。2986/native_v3在-DFMT_HEADER_ONLY修正后25case完成，官方WS39/47断言通过；尚需下载并核验MANIFEST。原Core.cc/WS.cc/Sram.cc字节保持不变，兼容头补丁与SC显式latency hook有记录。只有小probe+合成有限内存，不是完整ONNXim Qwen/实际DRAM。
- 主31项目前已收26项、无FAILURE，尚待3个rejection、一个8K PV seed、SG64等；以实时MANIFEST为准，不用这段旧数量代替实查。
- 统一collect_schedule.py可收主、--w8；需保持--bf16-8k支持已在本地写好。analyze_schedule.py只读SHA封存后形成COMPARISON，已去掉重复详细records以限制体积。
- 静态SRAM容量64候选62合法，正式小JSON在results/scheduling_20261025/legality。4MiB/64bank可容纳当前映射且保持端口，8MiB多余容量未利用；这是结构性容量结论，正式时延配置仍8MiB。
- 待完成：收39完整对照及native证据；报告/图和剩余假设审计；把CLI推荐入口统一到mature_ddr4；推送同PR、转ready（不合并）、Issue/STATUS/唯一memo同步；清理本任务可恢复临时缓存但不删原证据/源码。
