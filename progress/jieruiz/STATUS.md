# PR47合并回执已同步（2026-10-19）

GitHub实际操作账号jieruiz；用户明确授权合并。PR47于15:44:54（北京时间）合入pbit-tlm-attention-details-20261016，merge bef83e54b9da0081c51f393044d2156ce11a34b9；head5518a0a、base c1555ae，合并树与审核树完全相同。Issue46于15:46:38按验收完成关闭。独立审核25项核测试及145结果/154原件等通过；未重跑GPU或新增PPA。PROJECT_MEMORY对应状态已更新，PR29仍待审未合并。Projects新查询仍缺read:project，正式看板待同步。本次通过task/28-project-memory及PR29追加合并回执，最终发布head以远端分支为准；不修改原执行快照。

以下保留历史状态：

# jieruiz 项目进度

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


2026-10-19追加Issue39/PR40：65项裁剪/固定PoT替换＋6基线共71输出齐，79产物SHA与源快照复核；512/T256动态13.9529、0.95范围13.7701（小改善、非显著结论）；2048动态10.6569、0.75裁剪14.1020、固定PoT A/W333.2295。完整随机WT2未做，无新PPA。第5.4节和Issue索引已更新；本任务仍是文档维护，实验属于Issue39。根阅读副本一致。PR40最终结果22文件blob核验通过，未合并；PR29仍待审未合并，Projects缺read:project。


2026-10-19补充Issue46/PR47：固定W8输入多尺度65项已完成，完整WT2四档T12812.309561、T25611.989865，原BF1611.652735；68原件SHA/30源blob复核。备忘录§5.5记录代码/数据/Slurm与硬件边界，PR47未合并，无新PPA；根阅读副本同字节。


2026-10-19 T64完整补测已发布：Issue46/PR47，结果提交a4a15018，执行a7bae630，Slurm2298/2299结束。4档T6413.038027±0.010666、8档13.038505±0.012030（3seed/299077目标），BF1611.652735；11项新增计分/14原件/31源blob核验。§5.5与§12已同步，新正式目录fixedw_multiscale_t64_20261019，旧65项不覆盖，无PPA，PR47/29未合并；Projects缺read:project。根阅读副本同字节。


2026-10-19新增§5.6运行状态：Issue46多档＋分层，执行db27fa3，Slurm2308通过、2309运行67完整配置；旧76项不覆盖。根阅读副本一致，新PPL未收齐，PR47未合并。


2026-10-19多档＋分层完成：§5.6与§12同步69新计分/72原件/37源blob，db27fa3，Slurm2308/2309结束，结果c8ea878已发布。B4细T16/32/64为11.900826/11.736131/11.693775，B2/T3211.769199；粗K16T64与fineK32T32相近。根副本一致，PR47/29未合并，无PPA。

2026-10-19追加§5.7/Issue50：34后缀主项＋12诊断/64原件完成，B4T32联合Ising128/512 PPL11.197813/11.055307，对照10.371557；完整22项Slurm2430仍在运行（53dd0ff），不称全量完成。PR52草稿、依赖PR47；根阅读副本同字节，Projects待同步。
