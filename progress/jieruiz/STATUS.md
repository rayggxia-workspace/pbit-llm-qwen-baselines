# Issue28：代表任务准确率的记忆同步（本地待发布）

2026-10-19，已同步北京时间17:13:52正式提交回执；负责人/实际认证`jieruiz`；正式仓库`rayggxia-workspace/pbit-llm-qwen-baselines`。canonical目录`tmp/project-memory-issue28-20261018`，分支`task/28-project-memory`；本轮起点为已集成的`b2527f12924a53da7334afbe78c752c101814193`。PR29已实际合并，Issue28持续维护open；本轮补充尚未推送、未创建新PR，交由当前主任务统一发布，不能向已关闭PR29写成待审更新。

已核验canonical起始clean、GitHub身份、Issue28/PR29/PR62。两次git fetch分别连接重置/不可连接；只读GitHub API核实当前integration恰为同一个b2527f1，`git merge --ff-only`确认Already up to date，未reset或覆盖并行集成。已读最新AGENTS、README、memo及历史STATUS/HANDOFF，保留Issue55的23项审核/21项合并记录。

本轮仅同步`PROJECT_MEMORY_ZH.md`第5.8节和第12.1节、本人STATUS及Issue28 HANDOFF，根阅读副本由正式memo复制并核字节。Issue59/PR62首源348c8286，PIQA1838/ARC-E2376全量、Hella1000固定子集，BF16/FFN-only/Ising64/128/512共39配置。13scorer＋2plan CPU通过；2474原BF16完整WT2 11.652735，但向量化/cached候选sumLL差0.1168触发原门禁，未绕过。新075574源2475/2476已全部READY，独立naive cached sumLL1e-5及greedy严格核对通过，9pilot完成，新BF16完整WT2仍11.652735。正式数组2477 baseline三任务、2478 ARC-E12项、2479 PIQA12项、2480 Hella1000的12项于09:13:52Z提交，后三者afterok2477；CPU汇总2481 afterany。collector-only源0d4be877，15collector本地CPU通过；075574数值源不改，无正式准确率可报。候选缓存/RNG/summary恢复和首答案token真实decode边界、短prompt不能验证长context筛选均已记录。实验属于Issue59，本次文档维护不启动模型/Slurm/PT/TLM。

验证：UTF-8/LF、`git diff --check`、仅三项正式文件范围、根副本/Git blob字节一致（提交后复核）。下一步：主任务核实2477～2481最新状态，再统一发布独立后续PR和Issue同步；Projects此前缺read:project待同步，本轮没有重查或声称看板已更新。

## 以下为继承的历史任务状态，保留时间与发布语境

本任务收尾补审PR58已实际合并`88764ec8f6f00ed05f4ab337902bd23ad08cc4a8`；总计23项、21合并、49/52留draft。首批22项/20合并的冻结回执保留在下文，新参考单独验证，不作为新完整PPL/PPA。报告通过PR60交付。

# jieruiz 当前进度：Issue55 PR审核已交付

2026-10-19；正式仓库rayggxia-workspace/pbit-llm-qwen-baselines，实际认证jieruiz；分支task/55-pr-backlog-review，独立目录tmp/pr-backlog-delivery-20261019，base 20a2565e0465846891c0a4ad0976e4395e7d3ecf。

本轮22项审查已完成，20项实际合并（不含此前PR47），49/52保留draft。20回执、逐项依据、刷新证明和实际验证见work/jieruiz/55/REVIEW_ZH.md、REVIEW.json、receipts/及evidence/。本交付仅审核记录和记忆状态，不修改科研代码/原件。

实际验证：102项CPU unittest为101通过/1个Windows权限skip，另独立协议fixture通过；DRAM13/13及4组TLM重放通过，43/44/45/40汇总复现。最终科研代码/配置/结果blob与测试提交e4798f70保持一致。没有新GPU/服务器/许可EDA/PPA。

有限任务Issue3/5/9/23/26/33/35/36/39/51验收关闭；7/22/28/37继续开放。Projects缺read:project，待同步，不影响已核实的仓库写入/合并。49/52完整确认及作者ready未完成，不替作者转ready，不重交作业。

审查报告正在通过任务55文档PR发布，实际PR/merge状态以Issue55及远端回执为准。恢复先读取最新GitHub，不能重复合并已处理项；长期备忘录root阅读副本须从已提交Git blob同步。

## 历史任务状态（保留原文和时间）

# Issue51 论文任务与质量指标对照补充

- 日期2026-10-19；负责人/已核验登录jieruiz；独立目录tmp/paper-task-map-issue51-20261019，分支task/51-paper-task-map，base TLM @856105beaefaee307ba1a9b1972aa61d8f82ba59。
- 原PR53已合并（merge856105b），不是待审状态。用户追加要求保存论文—任务—指标对照，沿用Issue51，使用独立补充分支；不向已合并PR53继续推交付。
- 新文件architecture_tlm/LLM_PAPER_TASK_METRIC_MAP_ZH_20261019.md，11项主表、1项非LLM补充、3项待全文；任务含义、指标方向、AFM shot、GLUE口径与原文不明确之处均单列。用户资料目录同字节副本。
- 实际验证：原文与官方评分配置核对、UTF-8/LF、表格结构、相对链接、SHA及用户副本一致；独立复核通过并已发布，Git blob与用户副本逐字节一致。文献任务无新模型/PPL/训练/TLM/RTL/PT/PPA/Slurm。
- 正式文档58aaa7a已原样发布，补充PR56待审未合并（https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/56）；Issue51保持开放直到补充验收。Projects此前缺read:project，待同步。既有任务状态保留为历史，不据其推定运行状态。

- 最终同步：原PR54已被并行审阅合并e0abc39；新文件入口改从该最新版本另起task/51-task-map-memory @0027d2c，PR57待审未合并（https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/57）。没有force更新、没有覆盖主维护/根副本；Issue51已更新，PR56正文远端/本地/用户副本逐字节验证通过。下一步审阅PR56/57；Projects仍待权限。

以下为继承的历史状态，时间与PR状态以对应任务最新回执为准。

# Issue46：多档＋分层完整结果已发布，PR47待审未合并

2026-10-19，jieruiz；task/46-fixedw-multiscale，base c1555ae；tmp/qwen-fixedw-multiscale-20261019。执行db27fa3，Slurm2308/2309结束，69计分/72原件/37源blob/23新发布blob核验，旧17/20清单分别验证。结果c8ea878已发布，4档fine T16/32/64=11.900826/11.736131/11.693775，2档T3211.769199；正式总表/图/LITERATURE在qwen/results/multiscale_stratified_20261019，work/jieruiz/46/STRATIFIED_DELIVERY_RECEIPT为回执。备忘录1fe0c92远端与根副本同字节，Issue46/28及PR47同步；PR47未合并、Issue46open，无新PPA，Projects待同步：GraphQL permission unavailable: Your token has not been granted the required scopes to execute this query. The 'id' field requires one of the following scopes: ['read:project'], but your token has only been granted the: ['repo', 'user', 'workflow'] scopes. Please modify your token's scopes at: https://github.com/settings/tokens.。下一步审阅验收，或独立验证RTL/能效，不重跑145输出条目。

以下历史：

# Issue46：多档＋分层69项已核验，准备发布

2026-10-19，jieruiz；task/46-fixedw-multiscale/PR47，base c1555ae，工作目录tmp/qwen-fixedw-multiscale-20261019。执行db27fa3，Slurm2308/2309完成，69计分/72原件/37源blob核验，BF1611.652735。4档T32细分层11.736131、2档T3211.769199；正式目录qwen/results/multiscale_stratified_20261019，回执work/jieruiz/46/STRATIFIED_*，旧76项保留。结果本地完成，待提交推送、PR/备忘录同步；PR47未合并，Projects缺read:project，无新PPA。下一步发布核验并交接。

以下历史：

# Issue46：多档缩放＋分层，完整WT2扫描运行中

2026-10-19，jieruiz；task/46-fixedw-multiscale / PR47，base c1555ae；目录tmp/qwen-fixedw-multiscale-20261019。冻结执行db27fa3已实际发布，Slurm2308通过、2309运行67完整配置（最多4GPU）；原BF16再次11.652735。13新核/12旧核/8range/shared通过；后处理K分组fixture通过。新PPL尚未收齐，不宣称全量完成。交接work/jieruiz/46/STRATIFIED_SUBMISSION.json；文献qwen/results/multiscale_stratified_20261019/LITERATURE_ZH.md。已追加长期备忘录§5.6，afbe90b已发布且根副本一致。下一步收回69计分/72原件逐SHA、同身份导入旧IID对照、绘图/总结、PR和备忘录同步。PR47/29未合并，Projects缺read:project。

以下历史：

# Issue46：T64全量结果已发布，PR47待审未合并

2026-10-19，jieruiz；task/46-fixedw-multiscale，base c1555ae，工作目录tmp/qwen-fixedw-multiscale-20261019。结果a4a15018，执行a7bae630，Slurm2298/2299结束。4档T6413.038027±0.010666、8档13.038505±0.012030（3seed/299077目标），BF1611.652735。新增11计分/14原件/31源blob/17发布blob核验；原65项与20发布blob保留并复核。正式结果qwen/results/fixedw_multiscale_t64_20261019，回执work/jieruiz/46/T64_DELIVERY_RECEIPT.json。备忘录c59ac5d远端与根副本同字节，Issue46/28与PR47已同步；Issue46open，PR47未合并，无新PPA，Projects缺read:project待同步。下一步审阅验收或另开硬件验证任务。

以下历史：

# Issue46：T64完整结果本地已核验，准备发布

2026-10-19，jieruiz；task/46-fixedw-multiscale / PR47，base c1555ae，目录tmp/qwen-fixedw-multiscale-20261019。执行a7bae630，Slurm2298/2299结束，11项新增计分、14原件及31源码blob核验通过。4档T64完整PPL13.038027±0.010666、8档13.038505±0.012030（3seed），BF1611.652735。正式补充及回执见qwen/results/fixedw_multiscale_t64_20261019/和work/jieruiz/46/T64_*；首批65项原证据保留。当前本地完成待上传，PR47未合并，Issue46open；无新PPA，Projects缺read:project。下一步提交推送并更新备忘录/Issue。

以下历史：

# Issue46：补测T64完整WT2运行中

2026-10-19，jieruiz；PR47未合并，任务分支task/46-fixedw-multiscale。新源a7bae630，Slurm2298/2299，9项T64三seed完整评测，原kernel未改，旧65项已发布结果不覆盖。新结果尚未收回；回执T64_SUBMISSION.json与HANDOFF记录下一步。Projects缺权限待同步，无PPA。

以下历史：

# Issue46：完整结果已发布，PR47待审未合并

2026-10-19，jieruiz；分支task/46-fixedw-multiscale，结果提交312bc4d，执行源e6f29b1。65项全部完成，68原件SHA/30执行源blob/20发布blob通过；三seed完整WT2四档T12812.309561、T25611.989865；BF1611.652735，8档无进一步收益。Slurm2234/2235/2276完成、最终本人队列空。PR47 ready for review，Issue46open等验收；交接及DELIVERY_RECEIPT在work/jieruiz/46/。长期备忘录35fc829已发布，根副本与远端同字节；无新PPA，T64仅前缀。Projects缺read:project待同步。

以下保留历史记录：

# Issue46：65项已完成，结果准备最终发布

2026-10-19T14:04:56+08:00，jieruiz；分支task/46-fixedw-multiscale，PR47，base c1555ae；主目录tmp/qwen-fixedw-multiscale-20261019。执行源e6f29b1，Slurm2234/2235/2276。65项全部计分，完整WT2三seed4档T128 12.309561、T256 11.989865；原BF1611.652735。原件SHA/源码blob和计分协议通过；正式结果qwen/results/fixedw_multiscale_20261019/，work/jieruiz/46有回执与VALIDATION。最终结果本地已整理，尚待最后提交推送；PR47未合并、Issue46open。无新PPA/TLM/物理源，T64未全量，Projects缺read:project待同步。

以下保留历史记录：

# Issue46：Slurm基线和多尺度screen已提交

2026-10-19，jieruiz；分支task/46-fixedw-multiscale，base c1555ae。执行源e6f29b113405df53f2ca32b084d9de0dc9859343；12本地kernel测试通过，服务器新12/旧8及共享counts验证通过。Slurm2234/2235，41项512前缀，最多4GPU；当前尚无完整新方案PPL，22项full计划待实测速度确认。交接work/jieruiz/46/HANDOFF.md，提交回执SUBMISSION.json。源码发布中，PR尚未创建；无新PPA，Projects待同步。

以下保留历史：

# Issue46：固定W8输入多尺度实验实现中

2026-10-19，jieruiz；分支task/46-fixedw-multiscale，base c1555ae；独立目录tmp/qwen-fixedw-multiscale-20261019。Issue46已创建，PR未创建。固定原64x64 INT8权重，输入dynamic64/pot1/pot4/pot8，T64/128/256三seed，原Attention。源码本地实现中，未部署/未运行；核实本人队列为空、8卡空闲。下一步单测、冻结、Slurm BF16 gate和screen；据实际速度运行预选full。交接work/jieruiz/46/HANDOFF.md；无新PPA，Projects待核实。

以下保留继承状态：

# Issue32：范围缩放已合并，分布审计补充

- 更新时间2026-10-19；负责人jieruiz；PR31合并d589f152，PR34合并5b71d4e，目标为pbit-tlm-attention-details-20261016。原49项输出及20文件manifest在合并提交核验一致。
- 独立目录tmp/qwen-range-distribution-issue32-20261019，分支task/32-range-distribution-20261019，base5b71d4e；此前执行和当前缩放数值不变。
- 用户追问真实分布与裁剪，并授权合并。原2165提交shell在启动前失败，已保留回执；2166同不可变源622e0ef已完成8192train-token teacher分布审计，不跑新随机/裁剪PPL，不存原始激活。
- 本地及服务器4项单测通过；模型/数据/冻结源/token hash重验通过，原BF16完整PPL11.652735复现；3原件逐SHA收回，报告与小型总表完成。旧z99.131%在q0～15，Sz减半截0.00283%值、截断SSE约2.40%。不预判裁剪改善整网。
- 合并回执work/jieruiz/32/MERGE_RECEIPT_20261019.json，原MANIFEST引用旧45063d8版本；新辅助文件将单列followup manifest。
- 下一步：发布并合入本补充PR，更新Issue32与长期备忘录；现有范围PR31/34已合并，不重复合并或重跑49项。Projects权限待同步；不改Attention成员任务。

# Issue51 新器件LLM质量指标核查

- 更新时间2026-10-19；实际登录/负责人jieruiz；Issue51；独立目录tmp/emerging-quality-issue51-20261019，分支task/51-emerging-quality，base TLM c1555ae。
- 本地报告与14项原文数值复算完成：architecture_tlm/EMERGING_LLM_QUALITY_METRICS_ZH_20261019.md及EVIDENCE JSON；用户资料目录同字节副本。5%降级为自定工程预算，未宣称会议阈值；Kelle/DS-CIM/FeFET/PCM等质量指标分开。
- 11项主表样本；缺VQT-CiM/HEIRS/DBC可核质量表的全文，已单列下载入口。不把缺数补成精确结果。
- 验证：UTF-8/LF、2本地链接、14算术项、资料副本及SHA完成，发布时核Git blob；文献整理无新模型/PPL/TLM/RTL/PPA/Slurm，不改Issue46/48/50。
- 主报告已原样发布a07d695，PR53待审未合并：https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/53；base并行推进bef83e54后仍mergeable/clean，已保留Issue46状态。备忘录向Issue28最新b347f6a提供独立小补丁，不覆盖原工作树/根副本。Projects缺read:project，待同步。
- 辅助资料work/jieruiz/51；后续实际发布状态写HANDOFF/本段。
- 备忘录补丁已发布56e417e、PR54待审未合并：https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/54；以b347f6af为base保留主维护并行更新，根阅读副本未独立改写。


以下保留旧任务状态，不作为本任务实时作业信息。

以下为原范围任务交接，日期与状态属原时点：

# Issue32：Qwen双随机范围缩放

- 更新时间2026-10-18；负责人jieruiz；Issue32；分支task/32-qwen-dual-range；独立目录tmp/qwen-dual-range-issue32-20261018。
- 依赖PR31的6102c83；目标PR base task/30-qwen-dual-iid-public；PR34已推送待审、未合并：https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/34。
- 执行源17c89c3c86f8b1c0aafe42a3eaa1d354c1e539ee；prepare Slurm2112已完成；37项数组2113已完成，39/39输出SHA核验；更长确认2142/2143已完成，10/10输出SHA核验，共49输出全部完成。
- 实际验证：9文件及冻结文件/token hash通过；服务器kernel8/8（含旧实现回归）、共享counts测试及理论方差测试均通过；原BF16完整WT2复现11.652735047455899，299077计分token。
- teacher局部诊断已收回SHA核验，输入范围是重要噪声来源：down T256总MSE NMSE old0.514987/input0.029296/weight0.251549/both0.012833；这是原teacher输入的线性投影理论误差，不能当整网PPL结果。
- 范围：全部24FFN、准确Attention；mean/fixed控制及gu/down消融；替换PPL仅128-token前缀。动态absmax及权重尺度元数据成本未做PPA。
- 成果/交接work/jieruiz/32/HANDOFF.md与提交回执；原始结果留授权服务器，本地副本在tmp/range-correction-20261019/raw，不入Git。
- 下一步：审阅PR34（待审未合并），完整随机WT2仍未做；不得把本次49输出称全语料随机PPL。Projects权限待同步。

以下保留此前阶段状态：

# jieruiz 项目进度

## Issue30：Qwen双随机IID精确短流核查

- 日期2026-10-18；实际GitHub登录jieruiz；目标rayggxia-workspace/pbit-llm-qwen-baselines。
- Issue：https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/30；公开交付分支task/30-qwen-dual-iid-public；原执行分支task/30-qwen-dual-iid-exact仅本地保存，base pbit-tlm-attention-details-20261016 @3553996bf014a29dee7fdb2250a3965e8fd881a4。
- 目录C:/Users/86134/Documents/a_P_BIT/tmp/qwen-dual-iid-public-issue30-20261018；源码ad14096615054a7ef0a72e43f670863e4a205b11已冻结部署，Slurm2111的47/47项输出已收回，单卡5090测试完成。
- 用户要求的长期备忘录已先交付Issue28/PR29，根PROJECT_MEMORY_ZH.md及AGENTS阅读入口已存在；恢复不要只读本checkout较旧状态。
- 范围：全部24FFN、准确Attention、固定Sz/W8/A8共享64；精确条件Binomial vs Gaussian vs固定W，T64/128/256/1024/4096，各3seed；完整原BF16通过后才运行128token风险检查。
- 已验证：服务器模型/tokenizer/完整train-test 9文件及token hash匹配、10个冻结源/校准hash匹配；服务器两类已有单测通过；完整BF16实际复现11.652735047455899，299077目标。45项短随机对照与BF16长/短参考全部完成，逐SHA核验。
- 成果：experiments/qwen_dual_iid_exact_20261018/；汇总和安全索引在qwen/results/dual_iid_exact_20261018/，47输出传输SHA全部核验；交接work/jieruiz/30/HANDOFF.md，SUBMISSION.json记录实际作业。公开安全分支已推送7f14b27，PR31已创建待审、未合并：https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/31。原始校准和逐case长JSON保留服务器。
- 阻塞：无数据/登录阻塞，GPU分区当前8卡idle；Projects权限待同步。无新训练、RTL/PT或TLM。
- 下一步：审阅PR31；长期备忘录PR29已同步精确短测。完整双流PPL尚未精确全量补测，不因短测完成而宣称已做；当前低T效果差，不盲目追加几十项长任务。
- 追加诊断：只读汇总已有47项，精确双流T4096平均x概率5.3492%、z0.8255%，z裁剪极少；局部总方差分解证明每连接独立权重流增加非负噪声项。ERROR_DIAGNOSIS_ZH.md核对DS-CIM偏移/分组对齐/优化序列/误差注入范围差异；没有新GPU或逐投影因果消融。

以下保留旧阶段状态，运行信息需重新查询。

更新时间 2026-10-18T17:53:23+08:00；实际GitHub登录@jieruiz；目标rayggxia-workspace/pbit-llm-qwen-baselines。

## 当前Issue19：FFN精度与短流基线

- 独立工作目录：C:/Users/86134/Documents/a_P_BIT/tmp/llama2-ffn-precision-issue19-20261018；分支task/19-llama2-ffn-precision；PR20到pbit-tlm-attention-details-20261016 @dd9f12b8cc25f474cafb54b1a58f2be20506cd9e。
- 阶段基线PR20已实际合并到pbit-tlm-attention-details-20261016，merge `40ea9f121c27ed7ea6e8a2e653e92246f3adcbfa`，源码head `1cbf4168b8d2e37dbd398d88e5823c3db009eecd`。Issue19同步评论：https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/19#issuecomment-6248484271。16/26项已交付；剩余评测未完成，Issue19仍开放。
- 已收回16/26完整FFN替换PPL：IID256三种子6.256753±0.005911，分层64为6.758371±0.008464，分层128为5.308904±0.001642；IID4096首种子5.091985，另两种子仍运行。无采样W8+A8准确SiLU为5.038305，原BF16为4.979503；Q10与enum256的完整NLL相等。
- 已实际验证：模型/语料/token/配置SHA、原BF16重新运行；服务器2082为17/17、追加2090为18/18；新收回产物全部按原manifest逐SHA核对；v4分析16项同口径通过。仅本地无Torch环境测试会跳过相关项，不代替服务器验证。
- 当前运行：原数组2084，8/9对应IID4096种子1/2运行；10-15、22/23排队，最多2GPU。执行快照a8ea21f75ae6d736b2bc0136f8ee55977b082060不变，未取消/重交/覆盖。
- 范围：只测Llama2全部32FFN；Attention仍原BF16，无PV/Ising；不测Llama1，不训练，不改RTL或工艺数据。数值恢复为FP32统计参考，非完整bit-true硬件。
- DS-CIM对照：128拍归随机舍入/混合unary；DS-CIM的二维优化PRNG、偏移编码、SRR与旧普通双流/OR不同；论文LLM为256拍误差注入且有3.4/7.2个百分点平均准确率损失。Issue5/PR6只读，不接管。
- 已知缺口：RNE低位对照、逐投影与尺度/共享粒度消融、原权重+FP32内核控制、真实PRNG及完整定点硬件。没有新PT功耗或同精度能效证据。
- 正式成果：experiments/llama2_ffn_precision/、llama2/results/ffn_precision_20261018/；辅助work/jieruiz/19/。权重和逐窗长NLL留既有服务器个人项目。
- 阻塞/待同步：无评测数据阻塞；Projects缺read:project待同步。Issue19保留开放，合并本阶段基线不等于剩余评测已完成。
- 下一步：收集剩余2084结果，先核原manifest，再从最新TLM base创建独立结果分支/PR追加；保持执行快照与原件SHA。不得重开已完成基线或把旧PR20当未合并。

## 既有交付

Llama2基线+116TLM为Issue14/PR15，已合并7a506365；三模型入口Issue16/PR17及回执PR18已合并，base dd9f12b。Llama1 Issue12/PR13已合并07d0338。治理/DS-CIM/硬件/筛选其他独立分支维持原审查状态。

合并回执记录：2026-10-18T17:57:41+08:00，独立checkout `C:/Users/86134/Documents/a_P_BIT/tmp/issue19-merge-receipt-20261018`，分支`task/19-merge-receipt-20261018`。仅同步既成合并事实，不改运行快照或数值产物。


2026-10-19接续Issue46：固定相同W8，新增experiments/qwen_multiscale_stratified_20261019，67项完整WT2+2BF16对照；扫描B1/2/3/4/6/8与K1/4/16/T，无训练/Attention变化。新13项kernel、旧12项严格IID与mean回归通过；独立审核67唯一配置及analyzer K1/K4分组和篡改拒绝通过。源码准备冻结，尚未提交Slurm，不宣称新PPL。执行前保持只读旧快照；后续提交/作业与成果另记STRATIFIED_*。


## 多档＋分层完整WT2扫描运行中（2026-10-19）

执行源db27fa3d7ed8eced13513f0cad10061a3cc59a71，Slurm2308/2309（67配置，最多4GPU），原BF16完整11.652735已复现；13新kernel/12旧multiscale/8旧range及shared测试通过。已公开冻结源码，执行快照不可改。新结果尚未收齐，不宣称分层PPL；新正式目录将为qwen/results/multiscale_stratified_20261019，旧76项不覆盖。下一步检查2309状态，收回69项计分＋3元数据，逐SHA后联合旧同源IID结果分析，更新PR47及备忘录。Projects缺read:project，PR47未合并。

## PR8 原始交付状态（历史时点）

源head：89c5725064bfa1827e28c6566e3899dbc5cb1f9e。以下保留该任务新增的历史状态；最新合并状态以Issue55/相应Issue和GitHub为准。

# jieruiz 项目进度

## Issue #7 工艺表征续接（2026-10-17）

- 负责人：核验 GitHub 登录 `jieruiz`；目标 `rayggxia-workspace/pbit-llm-qwen-baselines`。
- 本地目录 `tmp/ffn-epilogue-ppa-20261017/`，独立分支 `task/7-epilogue-ppa100`，PR base `task/7-ffn-cim-scheduling` @ `dac6e0426da6421ccc62077275e236532ca3c3da`；依赖原 PR #8（待审未合并）。
- 范围：SwiGLU Q10 单通道 100MHz TT/SS DC→端口校验门级 VCS→PT PX。保留原算术 RTL；不是完整 FFN/BF16/PPL。
- 实际验证：18 个窗口、每窗口 4096+8 测量拍，三种子/两分布/三模式，Icarus 端口逐周期值/valid/flags 全通过，测量 VCD 无 X/Z；功耗单位、逐单元汇总、负 slack 标记、截断/X拒绝、断点文件校验测试通过；Bash 语法和 Tcl 词法完整性检查通过。
- 当前阶段：已推送；[PR #11](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/11) 待审、未合并，依赖原 PR #8。工艺运行未执行，工艺库、DC/VCS/PT 由用户服务器提供；没有伪造 PPA 数值。
- 成果：[PPA说明](../../architecture_tlm/rtl/ffn_epilogue_20261017/ppa/README_ZH.md)，辅助材料/验证位于 `work/jieruiz/7/epilogue_ppa/`。
- 待同步：项目看板缺 `read:project`；原 Issue #7 已记录本次分工。下一步上传脚本包并执行 `bash ppa/submit.sh all`，下载 TT/SS 报告包审查。
- 交接：[PPA_HANDOFF](../../work/jieruiz/7/epilogue_ppa/HANDOFF.md)。下方历史状态保留，不把旧验证当本次 DC/PT 结果。

## 原任务记录

更新时间：2026-10-17（Asia/Shanghai；经典结构与 RTL 补充）；本机 Git 凭据实际身份：jieruiz。

| 项目 | 当前状态 |
|---|---|
| 本任务 / 负责人 | [Issue #7](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/7)，FFN 调度与数字 CIM 仿真；@jieruiz |
| 目标仓库 | rayggxia-workspace/pbit-llm-qwen-baselines |
| 分支 / PR base | task/7-ffn-cim-scheduling → pbit-tlm-attention-details-20261016 |
| 基线提交 | 9608c0d06cf8b421cbbd348aca4fc84c5990aae7 |
| 独立目录 | a_P_BIT/tmp/ffn-cim-issue-7-20261017/ |
| 成果 | [报告与仿真清单](../../architecture_tlm/FFN_CIM_SCHEDULING_AND_SIMULATION_ZH_20261017.md)、[经典结构与选型](../../architecture_tlm/CLASSIC_AND_PROBABILISTIC_FFN_ARCHITECTURE_ZH_20261017.md)、服务计数工具、[后处理 RTL](../../architecture_tlm/rtl/ffn_epilogue_20261017/README_ZH.md) |
| 当前阶段 | 已推送；[PR #8](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/8) 待审，未合并 |
| 实际验证 | 归档循环与公式核对；12 个资源/采样服务场景；新 RTL 经 Icarus 三种子各 12295 周期、双输出位宽验证；active/burst/idle 计数通过。最终范围与散列见 work/jieruiz/7/ |
| 不适用/未运行 | 没有模型数值推理/新 BF16/PPL；没有 DC/PT、版图或新 DRAMSys。RTL 是定点近似候选，不是 BF16 等价实现 |
| 限制 | 新后处理尚无工艺 PPA/模型回归，未启用到现有模型；原非线性、格式转换和权重驻留代理未擅自改值；完整 v5/v6 未在本任务集成发布 |
| 待同步 | Projects 缺 read:project，看板待补权限；Issue/PR 正常同步 |
| 接续 | [HANDOFF](../../work/jieruiz/7/HANDOFF.md)，先冻结 tile 的存储/格式接口，再按报告仿真 |

先前 Issue #1/PR #2 治理、#3/PR #4 架构审计、#5/PR #6 DRAM/DS-CIM 均保持各自分支、待审未合并。本任务未覆盖其文件或把 PR 创建说成合并。

## PR6 原始交付状态（历史时点）

源head：9e842bc2a25be962471e5e230c56abd097955d02。以下保留该任务新增的历史状态；最新合并状态以Issue55/相应Issue和GitHub为准。

# jieruiz项目进度

更新时间：2026-10-17（Asia/Shanghai）；已通过本机凭据核实GitHub身份jieruiz。

| 项目 | 当前状态 |
|---|---|
| 本任务 | [Issue #5](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/5)：DRAM功耗核实与DS-CIM权重供给；负责人@jieruiz |
| 目标仓库 | `rayggxia-workspace/pbit-llm-qwen-baselines` |
| 分支 / base | `task/5-dram-dscim-audit` → `pbit-tlm-attention-details-20261016` |
| 基线提交 | `9608c0d06cf8b421cbbd348aca4fc84c5990aae7` |
| 独立目录 | `a_P_BIT/tmp/dram-dscim-issue-5-20261017/` |
| 成果 | [专题报告](../../architecture_tlm/DRAM_POWER_AND_DS_CIM_WEIGHT_REVIEW_ZH_20261017.md)、核心功耗profile/预检查工具、独立计价辅助工具 |
| 当前阶段 | 已推送；[PR #6](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/6)待审；未合并 |
| 验证范围 | 13项测试通过；4份既有统计重计价残差≤1.67e-16J；16文件范围/37个链接/成果SHA-256核对通过。没有新PPL/完整DRAMSys或PT |
| 辅助与交接 | [HANDOFF](../../work/jieruiz/5/HANDOFF.md)、[源清单](../../work/jieruiz/5/source_evidence.json)、[成果manifest](../../work/jieruiz/5/manifest.json) |
| 限制 | 新profile是厂商限值核心情景，I/O/实际器件选择/完整timing尚未认证；不覆盖旧输入和历史结果 |
| 待同步 | Projects缺read:project；Issue/PR正常同步，看板待权限补齐 |

Issue #1/PR #2治理、Issue #3/PR #4架构审计仍保留原任务分支。下一步应具体确定FFN权重驻留接口，再开展实现/工艺表征；本次未宣称已实现DS-CIM宏。

## PR10 原始交付状态（历史时点）

源head：67effd8300284ffff3e49797a965a00f54fefc78。以下保留该任务新增的历史状态；最新合并状态以Issue55/相应Issue和GitHub为准。

# jieruiz 项目进度

更新时间：2026-10-17（Asia/Shanghai）；实际 GitHub 登录 jieruiz。

| 项目 | 当前状态 |
|---|---|
| 当前任务 / 负责人 | [Issue #9](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/9)，筛选＋PV 的 K 读取分析；@jieruiz |
| 正式仓库 | rayggxia-workspace/pbit-llm-qwen-baselines |
| 分支 / PR base | task/9-screen-k-traffic → pbit-tlm-attention-details-20261016 |
| 基线提交 | 9608c0d06cf8b421cbbd348aca4fc84c5990aae7 |
| 独立目录 | a_P_BIT/tmp/screen-k-traffic-issue9-20261017/ |
| 当前阶段 | 已推送；[PR #10](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/10) 待审，未合并 |
| 成果 | [正式分析](../../architecture_tlm/SCREEN_K_TRAFFIC_ANALYSIS_ZH_20261017.md)、审计工具与结果、原始校准字节归档 |
| 实际验证 | 原选择器重建两组记录一致；补充MHA/GQA区别；旧LLaMA-1 7B筛选3种子×32层候选与组并集逐项相等；没有新推理。其他检查见 work/jieruiz/9/ |
| 未运行 | 没有模型推理、训练、新 BF16/PPL、新 DRAMSys、RTL或DC/PT；不把合成输入作为真实模型稀疏率 |
| 限制 | 组级共同预算、v6 PV＋筛选、摘要压缩均为后续候选；共享随机数仅计算理论期望，未启用 |
| 待同步 | Projects 缺 read:project，看板待权限补齐；Issue/PR正常同步 |
| 交接 | [HANDOFF](../../work/jieruiz/9/HANDOFF.md) |

前序 Issue #1/PR #2 治理、#3/PR #4 架构审计、#5/PR #6 DRAM/DS-CIM、#7/PR #8 FFN/后处理均保留原分支待审。本任务没有覆盖其工作树。

## PR25 原始交付状态（历史时点）

源head：d81095f8cbd76fa496af7f294c57274d9a27734c。以下保留该任务新增的历史状态；最新合并状态以Issue55/相应Issue和GitHub为准。

更新 2026-10-18T18:30:38+08:00；实际登录@jieruiz；目标rayggxia-workspace/pbit-llm-qwen-baselines。
## 当前Issue22：Qwen短流能耗与RTL
- Issue：https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/22；负责人@jieruiz。
- 分支task/22-qwen-short-stream；base=pbit-tlm-attention-details-20261016 @3553996bf014a29dee7fdb2250a3965e8fd881a4；checkout=C:/Users/86134/Documents/a_P_BIT/tmp/qwen-short-stream-issue22-20261018。
- 本地已完成：旧Qwen A8固定W/share64协议和源SHA核对；源码提交62a34e7可复算4组同功率TLM敏感性；独立重跑4组数值一致；100MHz旧锚点与附加功率假设核算；DC/PT模板和明确回填范围。
- 条件结果：T4096/256/128/64的SC核+前端为64.496/4.046/2.031/1.023mJ/token，整模型170.495/59.802/56.724/55.395mJ/token；不是新PT、GPU、详细DRAMSys或同精度结果。
- RTL独立子目录tmp/qwen-short-stream-rtl-issue22-20261018、分支task/22-short-stream-rtl；实际36配置252帧/202496有效样本逐拍通过，7组代表活动窗口通过；已cherry-pick为87a8102且最终源码/摘要/zip逐SHA核验通过。含内/外源、帧计数复用、精确G1、seed重播和strat256无RNG更新控制。
- 正式成果：qwen/energy/short_stream_20261018/，sc_short_stream_20261018/；辅助资料work/jieruiz/22/。权重/概率由外部帧内稳定接口提供，不新增银行；SRAM与上游seed保持另计。
- 证据限制：Qwen分层64/128尚未测PPL，本轮未提交GPU训练/评测；具体xorshift序列也未做模型质量验证；没有DC/PT工具或工艺库运行，不报告新面积/功率。TLM外存为Link，成本若干仍是旧占位。
- 复现修复：Windows autocrlf改变3个旧Qwen锚点工作副本；恢复为已签SHA的Git blob字节，并用窄范围-text属性防再转换；旧源内容及manifest未改，5锚点检查通过。
- 当前远端状态：Issue22开放；任务分支已推送，PR #25待审未合并：https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/25。实际数据提交`92db8122028b0a5d329d8e9e4eccd680b7912768`；Issue评论已同步。Projects缺read:project待同步；其他工艺/模型任务不覆盖。
- 下一步：PR已上传，等待审阅；工艺方依据包内ppa说明回填PPA后再替换旧代理，精度补测另冻结协议。
## 其他仍开放任务
Issue19的阶段基线PR20已合并40ea9f1，回执PR21合并3553996；其剩余Slurm评测不因本任务而取消或标记完成，见work/jieruiz/19/HANDOFF.md。治理/DS-CIM/FFN后处理/筛选的其他待审分支保持原状态。
本地交付包：`C:/Users/86134/Documents/a_P_BIT/sc_short_stream_20261018_issue22.zip`，114436bytes，SHA256 `2963729f0886ba44623babd9a9e5a47fd28bfda59687450046919639149bdbca`；release源提交`c9c78588e706d882bb80ce99e92487ad2c654046`。

发布回执：2026-10-18T10:37:26.188552+00:00，PR #25、Issue22评论和精确head已核实；PUBLICATION_RECEIPT.json记录实际动作。无新权限阻塞，Projects待同步。

## PR24 原始交付状态（历史时点）

源head：8cd5ed17ae31dae79eb71e9c74bce0e6e84da594。以下保留该任务新增的历史状态；最新合并状态以Issue55/相应Issue和GitHub为准。

## Issue23：p-bit LLM推荐阅读清单

更新时间2026-10-18T18:26:00+08:00；负责人/实际登录jieruiz。Issue：https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/23。

- 独立checkout：C:/Users/86134/Documents/a_P_BIT/tmp/pbit-reading-list-issue23-20261018；分支task/23-pbit-reading-list；base pbit-tlm-attention-details-20261016 @3553996bf014a29dee7fdb2250a3965e8fd881a4。
- 本地文件已完成：architecture_tlm/PBIT_LLM_RECOMMENDED_READING_ZH_20261018.md，用户master_report目录有同字节副本。17项文献/官方资料，6项优先精读，覆盖动态GEMM、原生p-bit、采样注意力及非随机/系统对照。
- 实际验证：主要题录/原文及证据边界复核、UTF-8/LF、本地链接存在、同字节副本和SHA；MANIFEST与SOURCE_REVIEW在work/jieruiz/23。Current digitizer仅摘要/官方介绍，全文待下载，正文有标注。
- 无新增模型/PPL/TLM/RTL/PPA实验；未改Issue19/22运行快照或其他任务实现。文档任务的模型/数据/种子字段不适用。
- 远端发布/PR与看板状态发生后同步到本段和HANDOFF；当前不宣称已合并。下一步核对Git blob并通过任务PR交付。
- Projects已实际复核：GraphQL返回INSUFFICIENT_SCOPES，缺read:project，看板待同步；其余文档交付照常进行。
- 实际发布回执：文档提交bec35b9be8aa0bc73648e598484d3e0ae09a2d72已推送；PR #24已创建并附本任务：https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/24，open/未合并。正文SHA256为8dcacd8d944d7b32b314c001305db0e5f2cdfb208ea5c173a3b0d8a93f8da25b，4个文档/manifest Git blob原字节核对通过。待审阅后验收，Issue23保持开放。

## PR27 原始交付状态（历史时点）

源head：e848f791b11e7bc17f22d18323125f5928fbcd19。以下保留该任务新增的历史状态；最新合并状态以Issue55/相应Issue和GitHub为准。

更新时间 2026-10-18T20:52:51+08:00；实际GitHub登录@jieruiz；目标rayggxia-workspace/pbit-llm-qwen-baselines。

## 当前Issue26：17项推荐文献原文阅读总结

- 更新时间：2026-10-18T20:52:51+08:00；负责人@jieruiz；Issue：https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/26。
- 独立工作目录：C:/Users/86134/Documents/a_P_BIT/tmp/pbit-reading-synthesis-issue26-20261018；分支task/26-pbit-reading-synthesis；base pbit-tlm-attention-details-20261016 @3553996bf014a29dee7fdb2250a3965e8fd881a4。
- 阶段：补读修订0666794已推PR27；当前17项主文已齐，PR待审、未合并。并行Issue19/22/23不接管。
- 成果：architecture_tlm/PBIT_LLM_READING_SYNTHESIS_ZH_20261018.md；原清单未改，用户pbit_llm_master_report_20261012目录保存同字节副本；SHA256 41d5118da9d0b259e1ee54453362251ed020e5f2e06baa6a7179bf07844c7970。
- 阅读：17项均有全文/完整官方资料。Current Digitizers用户8页PDF已读，视觉核对p3–7；原来的主文访问缺口已消除，源PDF未上传。
- 实际验证：17行总表及17个逐篇条目、27份源资料字节SHA、UTF-8/LF、原清单SHA不变和同字节副本；独立技术复核通过，两处边界澄清已纳入。无新模型/PPL、RTL/PT、TLM、服务器任务。
- 证据/交接：work/jieruiz/26/SOURCE_EVIDENCE.json、MANIFEST.json、VALIDATION.json、HANDOFF.md；公开Git不含论文原文或受限工艺资料。
- 阻塞/待同步：无主文访问阻塞；论文原始数据/完整位片合并细节不足仍限制复现。Projects缺read:project，看板待同步。
- 下一步：审阅PR27。无需补主文；完整复现仍受论文数据/实现细节限制，未启动新模型或硬件实验。

## 实际发布回执

- 已推送文档提交 `e84b25932e293801c8ab009a02a1a448007b386f`；PR #27：https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/27，目标pbit-tlm-attention-details-20261016，open、merged=false，已附当前任务。
- Issue26验收清单与评论已同步：https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/26#issuecomment-6250003655；保持open等待审阅，不宣称已合并。
- 报告SHA256 `cfed61fc7eb8e3d12b802a50f8b601ae89c5f8a1f2a7781460a4c8ae09d03c05`；Git blob、26份源资料及本地同字节副本均通过；初次Git未选择账号的推送失败已通过固定credential.username=jieruiz解决，最终推送成功，无凭据外泄。
- Projects缺read:project仍待同步；Current Digitizers全文仍未取得。其余16项的阅读和本次报告已交付。
- 下一步：审阅PR27。本回执随后同分支提交推送；无需重跑模型或硬件实验。

补充全文实际发布回执：提交 `0666794adad1a1c6c51dcdd8a0d9d565fdac9281` 已推同一PR27（open、未合并）；Issue同步 https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/26#issuecomment-6250159763。17项主文已齐；最新报告SHA256 `41d5118da9d0b259e1ee54453362251ed020e5f2e06baa6a7179bf07844c7970`，27份源字节与用户同字节副本校验通过。此回执随后同分支上传；后续为PR审阅，不需要新模型/电路实验。

## PR4 原始交付状态（历史时点）

源head：d9993288cdba0d605733dd37ff84ff1e9608f9bf。以下保留该任务新增的历史状态；最新合并状态以Issue55/相应Issue和GitHub为准。

# jieruiz 项目进度

更新时间：2026-10-17（Asia/Shanghai）；身份已重新通过GitHub `/user` 核实为jieruiz。

| 项目 | 当前状态 |
|---|---|
| 本任务 | [Issue #3](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/3)：架构可用性缺口与调度依据审计；负责人 @jieruiz |
| 目标 | `rayggxia-workspace/pbit-llm-qwen-baselines` |
| 分支 / base | `task/3-architecture-readiness` → `pbit-tlm-attention-details-20261016` |
| 基线提交 | `9608c0d06cf8b421cbbd348aca4fc84c5990aae7` |
| 独立工作目录 | `a_P_BIT/tmp/architecture-readiness-issue-3-20261017/` |
| 本地成果 | [架构审计报告](../../architecture_tlm/ARCHITECTURE_READINESS_REVIEW_ZH_20261017.md) |
| 当前阶段 | 已完成文档检查并推送；[PR #4](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/4)待审；未合并 |
| 验证 | 6文件范围、4个相对链接、UTF-8/LF、17个本地证据哈希、5个成果提交字节散列一致通过；没有新PPL、DRAMSys、RTL/PT或芯片结果 |
| 辅助资料 | [交接](../../work/jieruiz/3/HANDOFF.md)、[源文件版本及哈希](../../work/jieruiz/3/source_evidence.json)、[成果清单](../../work/jieruiz/3/manifest.json) |
| 阻塞 / 待同步 | Projects v2缺`read:project`，看板仍待有权限后同步；不影响Issue/PR |

## 其他任务和接续

- 治理任务[Issue #1](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/1) / [PR #2](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/2)仍待审；其分支和文件没有被本任务覆盖。
- 本次读取了历史成员评审、已发布TLM索引，以及本地v5/v6实现和审计；这些本地v6代码/大轨迹未随本报告上传。
- 下一步：按报告优先级拆分后续实现任务。优先冻结数值参考、闭合SRAM至SC阵列接口和真实trace，之后再优化调度/标定PPA；本次没有将这些计划标记为已实现。

## PR40 原始交付状态（历史时点）

源head：3fc3e07d74318d83f2657d8e2f58d87aa5c9ac7c。以下保留该任务新增的历史状态；最新合并状态以Issue55/相应Issue和GitHub为准。

# Issue39：结果已推送，PR40待审未合并

2026-10-19；负责人jieruiz；独立分支task/39-ffn-clipping，目录tmp/qwen-ffn-clipping-issue39-20261019；base c1555ae。
结果提交6642594已实际发布，PR40已ready for review、未合并；Issue39仍open等待验收。65替换+6参考共71输出，79原件SHA/源快照复核、22发布文件Git blob校验通过；全部结果已齐，本人squeue为空。新10/旧8/共享/方差验证通过，两次完整BF1611.652735复现。
正式成果qwen/results/ffn_clipping_20261019/，设计experiments/qwen_ffn_clipping_20261019/；交付回执work/jieruiz/39/DELIVERY_RECEIPT.json。执行源6b57b92/e0cf563不可变；全部替换分数仍为512/2048前缀，未做完整随机WT2/新PPA。长期备忘录560f88e已推送PR29，根阅读副本相同。
阻塞/待同步：Projects缺read:project，看板未同步；没有PPL结果缺失。Slurm无sacct且旧控制器记录过期，未获得全部历史退出码，未把不可查记录称失败。下一步审阅/验收PR40；若进一步研究需独立文本或完整WT2验证温和裁剪。

以下保留历史记录：

# Issue39结果已完成，准备交付

2026-10-19T11:09:36+08:00；负责人jieruiz；分支task/39-ffn-clipping；PR40到pbit-tlm-attention-details-20261016，独立目录tmp/qwen-ffn-clipping-issue39-20261019；base c1555ae。
两批65项替换＋6项基线共71输出齐全，收集逐SHA/执行源复核通过；新10+旧8/共享/方差验证通过，两次完整BF1611.652735复现。结果qwen/results/ffn_clipping_20261019/，方法experiments/qwen_ffn_clipping_20261019/。替换分数仅512/2048前缀；无新PT/PPA或完整随机WT2。PR待审未合并，Issue保持open；下一步上传最终汇总/manifest并同步长期备忘录；Projects权限待同步。

以下保留历史记录：

# Issue39实际运行状态

2026-10-19；jieruiz；task/39-ffn-clipping；执行源6b57b92305cab5dbee2a53c0c65cb297ac976261，独立目录tmp/qwen-ffn-clipping-issue39-20261019，base c1555ae。源码已推送；Slurm2167已成功、2168数组运行；PPL结果未全部齐全。
本地10/10新kernel、服务器新10+旧8及共享/方差验证通过；完整BF1611.652735复现；8192train校准完成。无新PPA。成果experiments/qwen_ffn_clipping_20261019/，回执work/jieruiz/39/SUBMISSION.json；下一步收集/核验/PR交付；Projects权限待同步。

以下保留历史记录：

# Issue39：截断与固定分组二次幂尺度

2026-10-19；负责人jieruiz；分支task/39-ffn-clipping；base c1555ae；独立目录tmp/qwen-ffn-clipping-issue39-20261019。
已核实远端规则、身份及分工；目前本地实现中，尚未提交/上传/提交Slurm。正式代码experiments/qwen_ffn_clipping_20261019/；交接work/jieruiz/39/HANDOFF.md。
下一步：kernel与数值测试，冻结执行源，Slurm BF16门控及train校准，再跑裁剪/固定尺度PPL。无新PT/PPA结果；Projects权限待同步。

以下为继承的历史状态，不代表本任务已完成：

## PR29 原始交付状态（历史时点）

源head：d3861072ff88dbc4e66f2a7844eed4f8ec97245b。以下保留该任务新增的历史状态；最新合并状态以Issue55/相应Issue和GitHub为准。

# PR47合并回执已同步（2026-10-19）

GitHub实际操作账号jieruiz；用户明确授权合并。PR47于15:44:54（北京时间）合入pbit-tlm-attention-details-20261016，merge bef83e54b9da0081c51f393044d2156ce11a34b9；head5518a0a、base c1555ae，合并树与审核树完全相同。Issue46于15:46:38按验收完成关闭。独立审核25项核测试及145结果/154原件等通过；未重跑GPU或新增PPA。PROJECT_MEMORY对应状态已更新，PR29仍待审未合并。Projects新查询仍缺read:project，正式看板待同步。本次通过task/28-project-memory及PR29追加合并回执，最终发布head以远端分支为准；不修改原执行快照。

以下保留历史状态：

## 当前Issue28：全项目长期备忘录

- 更新时间：2026-10-19；实际GitHub登录jieruiz；目标rayggxia-workspace/pbit-llm-qwen-baselines。
- Issue28：https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/28；分支task/28-project-memory；base pbit-tlm-attention-details-20261016 @3553996bf014a29dee7fdb2250a3965e8fd881a4。
- 工作目录：C:/Users/86134/Documents/a_P_BIT/tmp/project-memory-issue28-20261018；阶段：内容提交bcda21d905a327eeb41c353808bdcc7185472fc5已推送，PR29已创建待审、未合并：https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/29。
- 成果：根PROJECT_MEMORY_ZH.md，覆盖用户决策、FFN/随机矩阵、Attention、模型、逐层架构、随机源、SRAM/DRAM、TLM、质量/PPA、负面结果和任务入口；AGENTS/README新增恢复阅读规则。混合根同名备忘录及AGENTS阅读入口已同步。
- 验证：FFN和TLM独立事实复核通过；内部链接、原规则保留、UTF-8/LF、源资料hash和阅读副本一致核验；详见work/jieruiz/28/VALIDATION.json。未产生新PPL、训练、PT或TLM结果；Git blob校验和发布回执随后补充。
- 关键发现：旧双随机完整PPL为Gaussian参考，精确二项仅短片段；旧本地test raw不符合完整WT2 hash，必须重新核验服务器数据。
- 并行任务：Issue19剩余Llama2评测继续，不接管/重交；Issue22/PR25短流RTL、Issue23/PR24清单和Issue26/PR27全文总结均open待审。PR27当前17篇主文已齐，head e848f791b11e7bc17f22d18323125f5928fbcd19，不能沿用旧“缺全文”状态。
- 阻塞/待同步：Projects此前缺read:project，本次未重新验证看板权限，待同步；无备忘录文件阻塞。运行队列没有本次实时查询。
- 后续实际进展：备忘录交付后已单独建立Issue30/PR31，Slurm2111的47输出全部完成，完整BF16复现、45项短测逐SHA收回；精确双随机短T仍差。新结果和边界已同步PROJECT_MEMORY第5.1节。安全公开分支task/30-qwen-dual-iid-public只含代码/汇总/索引，原始校准及逐case原件留服务器；原执行快照不变。
- 后续Issue32/PR34完成范围修正49输出，模型实验属于Issue32；第5.2节已追加，原始范围和新数值/硬件成本边界同时保留。
- 范围合并回执：PR31/34/38已实际合入TLM，Issue30/32关闭，当前集成c1555ae；真实分布/裁剪审计同步备忘录5.3。Projects重新查询仍缺read:project。
- 下一步：审阅PR29（备忘录仍待审）；完整精确随机WT2尚未做，不因短测完成而宣称全量完成，不盲目开几十个长任务。Issue28/30在PR合并前仍open。

以下保留之前阶段交接；日期较旧的任务运行状态不当作实时队列。



2026-10-19追加Issue39/PR40：65项裁剪/固定PoT替换＋6基线共71输出齐，79产物SHA与源快照复核；512/T256动态13.9529、0.95范围13.7701（小改善、非显著结论）；2048动态10.6569、0.75裁剪14.1020、固定PoT A/W333.2295。完整随机WT2未做，无新PPA。第5.4节和Issue索引已更新；本任务仍是文档维护，实验属于Issue39。根阅读副本一致。PR40最终结果22文件blob核验通过，未合并；PR29仍待审未合并，Projects缺read:project。


2026-10-19补充Issue46/PR47：固定W8输入多尺度65项已完成，完整WT2四档T12812.309561、T25611.989865，原BF1611.652735；68原件SHA/30源blob复核。备忘录§5.5记录代码/数据/Slurm与硬件边界，PR47未合并，无新PPA；根阅读副本同字节。


2026-10-19 T64完整补测已发布：Issue46/PR47，结果提交a4a15018，执行a7bae630，Slurm2298/2299结束。4档T6413.038027±0.010666、8档13.038505±0.012030（3seed/299077目标），BF1611.652735；11项新增计分/14原件/31源blob核验。§5.5与§12已同步，新正式目录fixedw_multiscale_t64_20261019，旧65项不覆盖，无PPA，PR47/29未合并；Projects缺read:project。根阅读副本同字节。


2026-10-19新增§5.6运行状态：Issue46多档＋分层，执行db27fa3，Slurm2308通过、2309运行67完整配置；旧76项不覆盖。根阅读副本一致，新PPL未收齐，PR47未合并。


2026-10-19多档＋分层完成：§5.6与§12同步69新计分/72原件/37源blob，db27fa3，Slurm2308/2309结束，结果c8ea878已发布。B4细T16/32/64为11.900826/11.736131/11.693775，B2/T3211.769199；粗K16T64与fineK32T32相近。根副本一致，PR47/29未合并，无PPA。

2026-10-19追加§5.7/Issue50：34后缀主项＋12诊断/64原件完成，B4T32联合Ising128/512 PPL11.197813/11.055307，对照10.371557；完整22项Slurm2430仍在运行（53dd0ff），不称全量完成。PR52草稿、依赖PR47；根阅读副本同字节，Projects待同步。

2026-10-19§5.7.1：Ising次数15新项已完成，B4T32 S32..1024后缀12.065755/11.514886/11.197813/11.066594/11.055307/11.006579，准确PV10.970368；sourcec0fd，21新原件/49源blob，Slurm2440/2441完成。完整S128的2430与新S256/512的2461仍运行，不称完整完成。保留刚合入的Issue51质量预算补充；根副本同字节，PR52草稿/Issue50open，Projects待同步。
