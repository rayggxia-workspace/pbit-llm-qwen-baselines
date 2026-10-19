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
