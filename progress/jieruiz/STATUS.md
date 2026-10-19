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
