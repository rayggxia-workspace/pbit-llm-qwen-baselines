# 最新：真实QKV采样器比较已完成，独立分支交付

2026-10-21T13:37:45.944700+00:00；jieruiz；task/78-sampler-qkv-benchmark。90/90配置、三seed×八重复完成，固定行输出MSE与更新/随机服务成本，非PPL/PPA。正式入口qwen/results/sampler_qkv_20261021/DECISION_ZH.md；最新交接work/jieruiz/78/qkv_benchmark/HANDOFF.md，原件/源码/命令见同目录manifest和回执。结果待本次任务分支/PR发布核验；原PR82和其他作业不改。本任务无运行作业。以下保留此前阶段原文：

# 发布回执：Issue78后续PR80已推送

2026-10-21T08:55:47Z；jieruiz；task/78-score-interface；科学head0d3dfa2fa107ea5925751cdb686cda089b414628已推送，PR80草稿未合并。原PR79已合并a7a2c5b。OFFSET原件GitHub blob字节SHA核验通过，前轮网络待上传已解除；分数FP32/FP64审计与建议一并发布。回执work/jieruiz/78/SCORE_INTERFACE_PUBLICATION.json。Issue78保持open，Projects待权限，无本任务运行作业；量化/模型PPL/器件PPA待新验证，不重交2628。

# 最新：PR79已合并，后续在独立分支交付

2026-10-21；jieruiz；Issue78仍open。实时核验PR79已于08:51:06Z合并a7a2c5b3cbc16390e30061329adfbebc835dc8b3，原head310feea含评审后的manifest修复与PR77集成。原分支推送非快进后已停止，没有强推。

接续分支task/78-score-interface，在同一任务独立目录保留未发布的OFFSET源820ad7e/144记录与本次dtype/定点接口审计，合入最新a7a2c5b并保留其他成员文件/规则。DIAGNOSTIC/HARD/REJECTION/OFFSET/ONEHOT的归档Git blob字节SHA核对通过，证据work/jieruiz/78/SCORE_INTERFACE_VERIFY.json。无源码算术、默认、模型、PPL或PPA改动。19CPU合同为此前2628已实际通过，本次仅文档/合并字节审计，不冒充新数值实验。

下一步推送task/78-score-interface并创建后续PR（新PR号待实际回执），不向已合并PR79追加未发布文件。Issue78继续负责，Projects待权限；无本任务运行作业，不重交2628。下方PR79“仍草稿/未合并”及旧分支发布状态为历史。

# 最新：分数数制与p-bit输入接口审计

2026-10-21；jieruiz；Issue78/PR79。只读审计确认BF16 Q/K后候选QK显式FP32，新采样诊断又转FP64；尚无真实定点/LUT/DAC接口。已将代码行号、原生p-bit驱动映射、8位logit/DAC码与R8概率阈值区别、温度/偏移校正及成本缺口补入REJECTION_ZH.md；证据work/jieruiz/78/SCORE_INTERFACE_AUDIT.json。建议先只量化score入口，再独立改Q/K INT8；位宽/范围/器件参数均待校准，无新模型/量化/PPA结果或作业。

默认未改；本轮文档和前轮OFFSET待本次Git推送核验，不能把原网络阻塞当新文件已上传。PR仍草稿未合并，Projects待权限。无本任务运行作业，不重交2628。

以下为历史：

# 本轮发布状态：结果已同步Issue，文件仍待网络恢复推送

2026-10-21T08:35:15Z；jieruiz。OFFSET_PUBLICATION.json核实本地科学head0455d0d6b0a863f0bf3136446d9d9c5f28139b9f，远端仍d6d0f321b6c5eee7c334b7bb0f1e3d070d299304。普通Git push长时间无进度后停止，重试返回低速超时；GitHub API可用，PR79说明和Issue78评论已如实更新数字及未上传状态。没有凭据或权限变化，Projects仍待权限。

144条原件/报告/源在本地已提交，CPU2628已完成且无需重交；下一步网络恢复后普通push workspace task/78-ising-broadcast，核对head及offset_diagnostic.json blob SHA6a628a537e110e6c489ad0b967fa35f7acb959a0ab2c6ad282b35cef1e57ab8c，再更新发布回执。PR仍草稿未合并；不把本地结果写成远端文件已完成。

# 最新：公共偏移预设/固定/复用对照完成

2026-10-21；jieruiz；Issue78/PR79，task/78-ising-broadcast，独立tmp/ising-broadcast-issue78-20261021。CPU2628源820ad7efa824b09482be52fe2df0db73bf1a70cf完成19合同、144条分布重放（含明确cap失败）；源码blob核验通过，无新PPL/GPU/PPA，默认未改。

2K平坦S64：自适应0为3.384、预设11继续调3.227、固定11为2.663轮/地址（理论2.717）。真实512预设2改善首地址3.770到2.833，S64平均2.260对2.223未改善；同logits复用后自适应2.217，完全固定2.322。固定全局0/2/11在真实行有cap失败，尖峰固定11也失败。复用是相同输入接续，不是下一token，不把已有S64设置当免费标定。

可预设m，但必须保留相应r=2^-m零态校正；本次仍减z_ref，未验证以绝对常数替代参考分数。建议按层/头校准预设+必要修正，未部署、未训练。成果qwen/results/ising_broadcast_20261021/OFFSET_ZH.md和OFFSET_MANIFEST.json，提交索引work/jieruiz/78/OFFSET_*；2628不重交，无本任务运行作业。新结果待本次push核验，PR79仍草稿未合并，Projects待权限。

以下保留历史时点：

# 发布回执：本轮已推送并核验

2026-10-21T08:06:14Z；jieruiz；Issue78/PR79，task/78-ising-broadcast；科学head9b88a8da8d67450ae646372b2278deef33557889已推送正式workspace，三份新原件GitHub blob字节/SHA与服务器索引一致。PR仍draft/open、未合并；看板仍待read:project权限。回执work/jieruiz/78/REJECTION_PUBLICATION.json。无本任务运行作业，不重交；下一步是有限概率精度/模型PPL/PPA，不把理想分布轮数当硬件时钟。下方“待推送/网络失败”均为历史时点，已由本回执覆盖。

# 最新：保留空参考，单块并行提议与正确冲突重采样已验证

2026-10-21T08:04:07.351623+00:00；jieruiz；Issue78/PR79，task/78-ising-broadcast，base e4990c15b40f664cea7f9db43175b68347ce588b，独立tmp/ising-broadcast-issue78-20261021。

用户已明确：纯单1编码若增加等待则不继续，重点解决块内并行、多1冲突和最少块数。未提交one-hot PPL，run_model默认未改。2624/2625的60项one-hot/旧编码重放保留负面证据：真实512下2/4/8块不全完成、16/32完成；2K平坦32块才完成，不能当最优块数或质量验收。

新源e52570d40d49013f11c6f3d3d16de9b20dfc9e3d的2626完成：19合同、18分布重放记录全部通过；3seed S64平均每地址提议真实512为2.223、2K平坦3.384、2K尖峰1.000。S2048验证与IID噪声接近。全局1块、独立重新提议；多1拒绝，单1接受，零态以r=2^-m接受参考；公共偏移m由此前拒绝历史调节。精确枚举证明成功类别为Softmax，不是原全同步Gibbs。无新模型PPL、有限8位概率、RTL/PT/PPA验证；不能把提议轮数当时钟。源码/原件/manifest在正式实验和qwen/results/ising_broadcast_20261021/REJECTION_ZH.md。输入NPZ仍私有，源blob逐项及原件SHA4a817614...核对通过。

Git网络已恢复；之前未推送的硬抑制与18项PPL、one-hot执行源5e18cc5已普通push成功（从1eb0103到5e18cc5），旧“未推送”是历史时点。本轮新结果待本次commit/push后核验，再更新Issue/PR；PR仍草稿未合并，Projects缺read:project待同步。无本任务运行作业，不重交。

下一步：先测概率量化和完整模型PPL，再改默认；需要硬件仿真时拆出全局any/multi/m反馈及优先编码/驱动延迟。没有模型权重/训练改动，其他成员任务不动。

以下保留历史时点：

# 最新终态：18项PPL和硬无穷重放已核验，本轮推送待网络恢复

2026-10-21；负责人jieruiz，Issue78/PR79。Slurm2602全部18项completed，0失败；2609自动汇总完成，独立重放collect.py与服务器SUMMARY/RESULTS逐字节一致，原件26文件SHA已索引。128目标CPU后缀初筛：BF1620.212326；CTMC S64 23.159115±0.418371；同步104.556286±23.733673；块64κ12 24.501808±0.482373；块16κ12 22.621586±0.407899；lazy64κ12 27.912856±2.032967；块16κ16 22.891973±0.917848。都是3seed，不是完整WT2、PPA或硬无穷PPL；不因块16在小样本低于CTMC就宣称普遍更优。

硬无穷Slurm2623也完成，原始分数15组配对和11合同见下。数值源0c0d897、分析344498a、硬抑制2fefbb0均保持不可变。当前无本任务运行作业，无需重交。

本轮κ无穷实现/原件以及18项完整汇总已在本地任务分支完成，但Git HTTPS直连/代理/TLS后端多次连接重置，最新GitHub仍为1eb01032c3f5e0390e730172f66374fc58e209b8；不可声称本轮文件已上传。GitHub API可用，Issue/PR将单独同步这个阻塞。下一步网络恢复后普通push workspace task/78-ising-broadcast，核对远端head及manifest blob字节，再更新PR79/Issue78发布状态。PR仍草稿未合并，Projects缺read:project待同步。

以下保留早期时点，不作为最新状态：

# 最新：κ无穷硬抑制对照已完成

2026-10-21T07:28:57.253117+00:00；Issue78/PR79，jieruiz，草稿未合并。

硬更新排除自身：其他位有1时强制0，否则按sigmoid(delta)采样。空状态为最大类别，随机单点精确转移保持Softmax；不能混用禁止空态的强制one-hot编码。两位any/multi广播可以替代数值κ计数，仍需RTL/PT定时验证。

Slurm2623完成；独立执行2fefbb019b1b68369e7ed04932184e464fb99fa1，12KB源码包、旧私有捕获SHA及命令见HARD_SOURCE/HARD_SUBMISSION。11项本地/远端合同通过；15组配对真实重放（42行、5调度、3seed、S64），全同步及块64/16/4与κ16地址100%相同，lazy最小97.32%。硬化不修复同步冲突，未新增硬模式PPL/RTL/PPA。

正式小JSON与字节SHA：qwen/results/ising_broadcast_20261021/HARD_MANIFEST.json。原数值0c0d897和18项PPL快照没有改写。2623无需重交；继续核对2602/2609终态。完整WT2/PPA仍未做，Projects缺read:project待同步。

以下保留先前时点：

# 最新：诊断完成，PPL部分结果与后续运行

时间：2026-10-21T07:12:29.385386+00:00；Issue78/PR79，jieruiz，未合并。

- 数值执行源0c0d8978908e9232cb94b75ac301a8254f834645保持不变；分析源344498a6d1867cb637d6d0955a37a9c283357251。9项本地/远端CPU合同通过（6采样+3汇总）。
- CPU Slurm2600已完成405项合成配置/控制记录，2601本次CPU BF16和SDPA包装NLL一致通过；2608已完成42行真实Qwen分数的48项重放记录。真实NPZ只在服务器，不上传。
- 128目标后缀BF16 PPL20.212326；CTMC S64三seed23.245402/23.527614/22.704328，均值23.159115、SD0.418371。全同步κ12目前两seed129.479031/82.224259；不能用两seed均值冒充三seed完成，也不等于完整WT2。
- 已发布的部分SUMMARY对应5/18完成、13pending；后续2602数组继续。六路CPU并发（每项4核、不用GPU），节点64核中原GPU任务约32核，仍留空闲；scontrol对已结束3/4返回finished、pending5-17更新成功，实际ArrayTaskThrottle6已核验，不是全部更新失败。无原作业取消/快照改写。
- 2609为afterany:2600:2602:2608的服务器自动汇总，完成后写outputs/0c0d897.../collected/RESULTS_ZH.md及SUMMARY.json，不需要本地持续在线。不要重交18项。
- 真实分数最大位置目标质量29.91%，CTMC29.87%，全同步87.55%，块64 44.62%，块16 31.71%，块4 30.63%；κ12/16几乎相同。稀疏使能1/8均值接近但地址重复约67%（CTMC约23%）；不宣称同等有效样本数。详细DIAGNOSTICS_ZH.md。
- κ建议仅为平衡泄漏起点：512候选κ12，约2K候选κ16；tanh输入系数要除2并做器件标定。当前PPL候选最多512，2K只做合成压力，不把它说成2K全候选PPL。

正式成果：qwen/results/ising_broadcast_20261021/；原件路径/字节/SHA见ARTIFACT_MANIFEST.json。原始模型JSON留个人服务器（逐段NLL、全24层执行审计、输入revision/文件SHA/环境/源码），小型诊断原件按-byte校验后入Git。当前无RTL/PT/PPA或训练。

下一步：读取2602各JSON和错误日志、2609终态，不仅看队列消失。确认18配置各3seed；失败null保留。取回collected两个派生文件及最终artifact manifest，重放collect.py并逐字节核验后更新同一报告/PR79/Issue78/STATUS和记忆。若需要扩大质量验证，当前128目标只能初筛，另记配置，不覆盖此快照。Projects缺read:project仍待同步。

以下为较早时点的交接记录：

# Issue78 全局广播与伪异步更新

2026-10-21；jieruiz；task/78-ising-broadcast；base e4990c15b40f664cea7f9db43175b68347ce588b；目标rayggxia-workspace/pbit-llm-qwen-baselines。

独立稀疏目录：C:/Users/86134/Documents/a_P_BIT/tmp/ising-broadcast-issue78-20261021。已读根记忆0/1/7/12、远端README/AGENTS/两位成员STATUS、Issue37及最新open任务；Issue76为其他成员训练设计，保持分离。原Issue73作业2585仍运行，不取消或重交。

已完成：有限κ方程、全同步/随机分块/稀疏使能NumPy行为模型、合法输出等待、无兜底cap；6项CPU数学/转移/边界测试通过。平坦输入发现全同步2周期振荡；原固定spacing4会只读空状态，故新路线增加独立随机间隔读出，并保留逐阶段非法率。

尚未完成：远端合成诊断与模型CPU PPL、任务分支推送/PR；不得把本地脚本写成已执行结果。计划个人服务器项目`/home/Hongjie_Zeng/projects/pbit-qwen-ising-broadcast-20261021-issue78`，独立不可变snapshot；只读复用既有权重/数据/标定，不复制模型。

准备按Slurm提交CPU诊断、CPU BF16/SDPA门禁和afterok的18配置PPL数组。128目标固定后缀只做初筛，所有24层scored decode替换，原FFN和多token前缀准确；不等于完整WT2。

下一步：封存执行SHA与source包；提交后在本文件追加真实job ID、路径、哈希。核对JSON终态，失败保留null PPL，不用分布指标估造PPL。至少3seed记录，κ选择区分平衡泄漏与动态偏差。Projects历史缺read:project，待有权限后同步；Issue78保持open至PR验收。

## 真实提交与发布（2026-10-21）

执行源0c0d8978908e9232cb94b75ac301a8254f834645，31个Git blob封存为81,056字节包；SHA256 6a33d8c84c56e2b00131b8ec2fcf7a4dd8afac5b6fe10338728fca2939e12fa5。源码和未来修复不可混写。快照位于个人项目snapshots/<SHA>，结果outputs/<SHA>。

CPU Slurm2600诊断、2601 BF16/SDPA门禁已RUNNING；2602_[0-17]%2依赖2601。首次远端日志6项测试通过，诊断进行中；PPL尚pending。提交原件SUBMISSION.json、EXECUTION_SOURCE.json。

分支已推送正式workspace；草稿PR79已创建并关联本聊天，待结果核验，未合并。Issue78已同步。Git默认OpenSSL TLS失败，使用单命令http.sslBackend=schannel且http.proxy=推送成功，没有修改全局Git设置。
