## Issue182：标准DRAM、SRAM接口和跨组预取（2026-10-25）

接续用户质疑阵列过小/分批过多与访存设置。正式仓库rayggxia-workspace/pbit-llm-qwen-baselines，Issue182/PR183，task/182-memory-hierarchy，main基线5273e5d9；实现与验证完成，PR待审未合并，不接管其他成员#118/#117或暂停#116/#123。

统一unified_v6采用实际DRAMSys Micron DDR4-1866双64bit通道、双rank16GiB，理论29.851GB/s、长DMA实测模拟吞吐约27.59GB/s。旧Link16GB/s每32突发排空实际约9.85GB/s，不能再作为优化硬件性能。SRAM仍8MiB/128个55nmSS80MHz宏，16→64bank、公共读写16→64GB/s、本地接收256→1024B/corecycle；后两项是接口设计假设，尚无STA/PPA。

SC权重4KiB/tile，每层FFN71.25MiB，有限容量分批正常；8/16/32/64阵列2280/1216/704/352波每层，所有配置656640tiles/36层且权重payload相同。单份本地权重＋显式一波DMA暂存；旧首轮只跨输出波预取，使E64 Wd单波组无法预取，baf0aab1进一步跨输入组而不覆盖编码/权重/系数状态。最终8/16/32/64为516.97928/468.98478/462.11397/438.47604ms/token，旧Link1412.97926ms、同DDR4旧SRAM1091.74616ms。数字W8参考432.19629ms仍为512MAC/拍宏假设；不是同面积最佳ASIC。完整结果与两轮边界见architecture_tlm/unified_v6/RESULTS_MEMORY_ZH.md。

93tests、18独立小形状、8DRAM微基准、4tiny门禁及22完整36层case核验完成（19真实DRAMSys，PV/校正拒绝各3seed）；Slurm2913/2925/2931均已结束。无训练/PPL/RTL/PT新增。源码0855/7e44/fe3f/baf四版本分开封存；原大trace位于/home/Hongjie_Zeng/projects/pbit-memory-issue182-20261025/，Git仅小JSON/SHA索引。交接work/jieruiz/182/HANDOFF.md，最小待审目录tmp/memory-hierarchy-issue182-20261025。

功耗审计发现core-current上限组合在DRAMPower6.3.1产生负ACT增量，首轮E8合计−1.38109mJ（总core的0.0934%，不是总误差界），实际源码/命令数复算吻合；不反馈时序，能量仍是未校准模型输出，不改零。完整芯片能耗/面积null；新接口/CDC/本地权重/DMA缓存PPA、数字参考优化及算法质量未闭合。Projects缺read:project待同步；没有宣称全局最优。

## Issue179 时间/token审计：不能把保守搬运合同当优化后性能（2026-10-24）

用户质疑1.4秒/token后，检查确认8个SC阵列同波并行，全部36层GU/Wd阵列合计77.976ms；并非串行8倍。整机普通MAC38.862ms，DRAM busy581.491ms，单SRAM fabric busy764.926ms。权重5.355GB/token，全部DRAM5.663GB，SRAM读写12.002GB；16GB/s单fabric仅流量下界750.126ms。

关键保守合同：DRAM每32×64B窗口排空，80ns延迟＋128ns数据，标称16GB/s变有效9.846GB/s；权重DRAM整块完成→SRAM整块写→整块读至阵列，没有同块流式流水；最新FFN下一波预取只在阵列结束后开始，未与采样重叠。local_weight_program与SRAM consume是重叠资源，不能再相加171ms。不得把这些时序当已优化ASIC预期。

同Qwen3-4B/2K/同资源，旧SC1596.708→新1412.979ms，改善11.5%；历史Qwen2.5-0.5B oldSC201.722ms不能横比4B。应先实现并验证滚动DMA、流式填充/消费、双缓冲及bank通路；若保持12GB单16GB/s片存通路不变，不能声称优化后降至几十ms。还须同W8数字控制，隔离量化减少权重流量的收益。本次仅审计封存结果，未修改调度/重跑/产生新性能结果。

PR180已实际合入main5273e5d9。额外回执PR181已推送、未合并：自动审批拒绝额外默认分支合并，理由为超出原明确授权且非必要；没有绕过。Issue179已同步实际交付，Projects仍待权限。当前最小工作目录暂留以供待审PR恢复；merge回执/后续审计的本地增量需在后续授权中同步。

## Issue179 / PR180 已实际合入 main（2026-10-24）

PR180于2026-10-24T14:41:06Z合并，main提交`5273e5d9fdae811a714f1a278fee6e776c5675af`，交付head`0d97e2b5a2c01270568835964b2f4d581133a197`；GitHub父节点/文件树及109个变更blob核验通过。Issue179本轮统一TLM交付完成，后续研究缺口不冒充已验证。

统一入口`python -m architecture_tlm`；流程/宏/数制见`architecture_tlm/unified_v6/FFN_CURRENT_ZH.md`，结果见`RESULTS_CURRENT_ZH.md`。74检查、7组完整36层、8组单FFN敏感性、15组三seed夹具、12封存SHA均通过。实际校正拒绝1152行/147456输出/441346 proposals（平均2.993次），无运行中本任务作业。2K准确Attention/筛选PV/筛选拒绝整机条件时间分别1412.979/1366.264/1585.054 ms/token。

保留未知边界：GU定点编译/舍入、NL独立随机源映射、权重保持宏和代表性STA/PPA；完整面积/能耗null，DRAM本轮link非DRAMSys，不继承PPL。Projects缺read:project，待维护者同步。工作副本回收时以project_archives/latest_ffn_tlm_issue179_20261024/RECOVERY.json恢复；本轮不创建全量副本。其他训练/算法PR未被本任务合并。

## Issue179：统一TLM最新FFN进入main的交付（2026-10-24）

用户明确要求更新通用整机TLM，使用最新固定尺度、随机非线性直连Wd的FFN，并在独立分支后合入main。本人jieruiz；Issue179/PR180，分支task/179-latest-ffn-tlm-main，独立稀疏目录tmp/latest-ffn-tlm-issue179-20261024。原main fae12982没有TLM，本轮仅导入d6d3399的最小运行/校准闭包，40个导入文件原字节不变；不合并训练PR178或其他研究PR。统一入口python -m architecture_tlm，继续unified_v6，今后不要另复制v7。合并状态以PR180和Issue179最终回执为准。

最新路径：W8；x固定四档T64/K64共享64；g/u独立固定[S/2,S/8,S/32,S/128] P8＋符号；真实尺度signed8 g驱动256x9 sigmoid ROM；4x2x4联合分层AND T64/128直接送Wd；7桶、q16系数、64位部分和与最终BF16。无在线absmax、无连续z落盘或再编码。GU原训练仍FP32恢复，TLM显式提供目标定点恢复宏并计费，但系数编译/舍入对齐待验证，不能继承PPL。可调周期、吞吐和局部状态都有字段，不把采样次数当整层周期。

保留Attention筛选/采样实现、真实Issue95源以及SRAM/DRAM接口；Qwen3补head_dim128、Q宽4096、O输入4096及QK norm。新NL消费者不能沿用shared64：64通道三轴需192个R8字/拍，1216随机低bit，跨输出wave重放同一子流。新增有限源宏默认II2、10个20字端点等效容量，5拍暖机(800步条件)、显式seed/重放/局部状态；它还没有实际接入全局seed仲裁/验证独立性。完整随机PPA仍未知。

默认8个64x64 SC阵列、32KiB全宽权重保持宏、512B响应弹性；权重/系数scratch分离，GU2F×8B部分和，NL F×4B码；每层W8权重71.25MiB分波加载，不是假定整层驻留。普通SRAM不能自动成为全宽保持阵列。慢速sram_reread对照仅支持local_prng_interface，未冒称集成逐拍源已实现。整机SRAM8MiB为条件参数、非优化结论；本次DRAM是link，不是新DRAMSys/DRAMPower重跑。

正式时序执行3a9ddfb1；7组完整36层Qwen3 decode、8组单FFN敏感性、15组三seed小整机及74项机制检查的实际封存以RESULTS_CURRENT_ZH.md/各MANIFEST为准。第一轮1152拍源warmup结果独立保留，最终采用5拍；漏独立参考测试依赖的一次失败保留，补齐74项通过。无模型权重加载、训练、PPL、RTL/PT或新GPU任务。当前完整面积/能耗null，价格小计不能用作节能倍数；新模块对应电路入口、缺口与假设见FFN_CURRENT_ZH.md。

Projects缺read:project，待维护者同步。没有新增定时，未取消或重复昨天训练。后续优先GU整数恢复与训练oracle对齐、NL实际独立源接合、权重保持及代表性4/7桶M64/T64/128 STA/PPA；读PR180/main最新入口及work/jieruiz/179/HANDOFF.md恢复。


## Issue177：可训练随机非线性FFN已交付PR178（2026-10-24）

用户要求给远程agent实际训练代码，接续昨天FFN权重，把精确非线性换为随机三流AND。用户确认昨天结果未全出，checkpoint/训练交接未提供；没有重复启动或取消昨天训练。新实现 qwen3/training/stochastic_nonlinear/，默认W8、x固定四档共享64 T=K64、g/u固定四档[S/2,S/8,S/32,S/128] P8＋符号、signed8真实g尺度驱动与P8 LUT、32联合分层AND T128（另有T64）、事件直接固定Wd整数累计/BF16RNE；支持W4/6，需分别校准。只训练gate/up/down共108张量，其余冻结；不采用失败FSM。Wg/Wu恢复仍FP32参考，不宣称整链bittrue。

硬前向保持真实有限随机分布，反向明确有偏STE：Wd梯度用采样z，上游用量化条件均值代理；不会在前向用FP32 SiLU回退或z重新编码。包含TRAIN固定尺度校准、旧权重精确键名导出/接续、严格SHA断点恢复、CE最小入口、随机键与checkpoint重算、远程agent完整说明。昨日checkpoint可作warm start，但要重校准且重新做同轮对照，不继承原PPL。代码不是4B训练已完成，也未证明新PPL。

验证：CPU13项（12过1CUDA跳过），Slurm2906的34项全部通过；tiny两层HF Qwen3 CUDA五步、三seed合成训练完成。DDP2907默认NCCL超时；2908禁P2P在长初始化后已封存完成（中途停止请求不覆盖最终完成证据），2909以本机socket隔离配置也三步通过，权重跨rank一致、冻结参数不变，失败日志保留。不将诊断配置/小模型时间当H200性能。所有作业结束，无新增定时。封存validation/results-2906及ddp-results-2909的documents SHA核验；远端本人projects/pbit-trainable-and-20261024-issue177；a3f5a4ac为单卡执行、4ab8350e为DDP成功执行。无RTL/PPA/full WT2。

本人jieruiz，task/177-trainable-and-ffn，独立sparse tmp/trainable-and-issue177-20261024；Issue177/PR178待审未合并，PR base为依赖PR174的task/173-and-direct-wd。入口AGENT_HANDOFF_ZH.md、VALIDATION_ZH.md、work/jieruiz/177/HANDOFF.md及PUBLICATION.json。Projects缺read:project待维护者同步。下一步由原agent待昨日结果齐全后核对checkpoint/数据SHA，先2步再200步pilot，T128→T64，然后W6/W4，最后同轮BF16与三seed完整PPL。不要把已推送代码写成已完成4B训练。


## Issue175模型结果发布回执（2026-10-24）

结果与实现已推送PR176，提交bce0ee906ebb8c22ea3f97742df458fd3271a821，待审未合并；全部变更文件远端Git blob/长度核验，六核心文件原字节回读通过。MODEL_PUBLICATION.json含Issue175评论和准确校验索引。首次逐文件回读网络断开，发布本身成功，后续补齐核验，未重复实验。Issue、STATUS、交接和长期备忘录已同步，Projects缺read:project待维护者。三路短流结果同时已发布PR174，head b41ee008；无本任务运行中作业或新增定时。

## Issue175固定g范围FSM：完整模型试测失败结果（2026-10-24）

Slurm2898/2902八片完成；128份/118唯一配置，13项预检每片通过、documents/sidecar SHA、36层全前缀、1024目标位置和8份BF16一致核验。Qwen3-4B后训练，准确Attention、前级固定W8/x四档共享64 T=K64。后级FSM是逐拍IID随机过程，不是Binomial或均值替代。g固定G=1/2/4/8/16、4或8状态、T64/128，真实尺度进入SiLU拟合目标；无g在线max/选档，u仍TRAIN固定四档。原2894在编译预检失败、模型未启动，旧快照保留，新执行462d4fe1/3ac8bfdb。

BF16=13.566049。实际FSM最佳G8/N4/负输出单位.5/T128 PPL1757.8026；对应FSM期望623.0500，T64期望22906.145。G8/N8/负单位8的精确SiLU表期望13.2860，FSM128期望615.4719、实际1785.7054；G16/N8/.5的精确表期望13.3085。说明固定g数制并非必然失败，但当前小状态链函数拟合严重不足，不只是采样噪声。G1/2/4截断叠加劣化；不能用SMURF正半轴0..1 MAE代替LLM证据。所有结果是8×128后缀，不是完整WT2；无训练/RTL/PPA，gate/up恢复仍FP32参考。T各自有限时长拟合，改变T同时改变系数，不把差异全归采样方差。

报告qwen3/results/smurf_swish_20261024/model/REPORT_ZH.md，SUMMARY/RAW_INDEX含三seed、逐层分布、模型/数据/校准/源码SHA。原件project_archives/smurf_model_20261024/sealed-2898-2902.tar.gz，远端与本地SHAf53c05e9e65d50e0a329bddd0c75380f728c48c2ae8c93a9c8e61b0046e60ba8。无本任务运行中作业或新定时，不重交。建议保留三路AND为当前主线：Issue173最佳联合128=15.3647，仍非无损；FSM另需改变表示/拟合或训练。

本人jieruiz，task/175-smurf-swish，目录tmp/smurf-swish-20261024，Issue175/PR176待审未合并；新结果发布以MODEL_PUBLICATION.json为准。Projects缺read:project待同步。恢复先读最新Issue/PR及本交接，原件可按RAW_INDEX恢复，不修改执行快照，不把条件均值当可部署路径。

## Issue175：固定g数制FSM进入模型试测（2026-10-24）

用户明确要求实际测试FSM以减少g分档。新模块qwen3/smurf_swish/model_*，固定G=8/16、幅度P8＋符号，无在线max或g逐值选档。真实G写进SiLU目标；有限T状态占用拟合，theta0=0、复位0，无预热；逐拍R8输入更新→状态系数比较→独立u比较AND→固定W8 Wd，仅最终整数统计恢复。负输出单位Sf=.5或G另测，不保证可拟合。u沿用TRAIN固定四档，前级x固定四档共享64 T=K64；准确Attention。四组(G,N,Sf)=(8,4,.5)/(8,8,.5)/(16,8,.5)/(8,8,8)，各含BF16及LUT均值/FSM64和128均值/实际64和128，概率三seed，64份后缀计划。IID FSM基线，未混称分层；模型前级恢复仍FP32参考，非整链bittrue/PPA。

Slurm2894四片均在CUDA编译预检失败，模型未启动；uint32随机键类型已修复，新冻结462d4fe168fbb7168a5cd742ec1270f02f6ce466、Slurm2898_[0-3]已提交。源包SHAf50ebe7c4b00a7c599bd86fedb677f9c3eddcf5c7bdc28b369a67759ef12180c，原失败快照保留。当前无封存新模型结果；本机7项通过、3项CUDA待服务器。个人目录pbit-qwen3-smurf-model-20261024-issue175，MODEL_SUBMISSION.json含准确快照/作业/日志，健康任务不重交。无新定时。

负责人jieruiz，task/175-smurf-swish，tmp/smurf-swish-20261024，沿用Issue175/PR176待审未合并；新发布以MODEL_PUBLICATION.json为准，Projects缺read:project待同步。完成时核对complete/documents/sidecar SHA、36层全前缀、同轮BF16和1024目标位置一致，再汇总；不是完整WT2，不用函数MAE冒充PPL。

## Issue173短流三路AND结果核验完成（2026-10-24）

Slurm2891三片封存完成，48份/46唯一配置、documents/sidecar原字节SHA、36层全前缀、每片27项预检通过。执行c44c2edc不变；同轮BF16及原尺度mean/IID64三seed与旧结果逐值一致。Qwen3-4B后训练、准确Attention、8×128后缀，非完整WT2。前级W8/x固定四档共享64 T=K64；后级4×2×4联合32区间，各1/2/4次。整体减半固定四档[S/2,S/8,S/32,S/128]的mean/IID64/联合32/64/128 PPL为13.4034/27.4020/103.8940/21.8821/15.3647；BF16=13.5660，最佳128仍高13.26%，不能称无损。gate/up恢复仍FP32参考；无训练/PPA。

报告qwen3/results/and_direct_20261024/short/REPORT_ZH.md及SUMMARY/RAW_INDEX。原件project_archives/qwen3_and_direct_20261024/short-sealed-2891.tar.gz，服务器与本机SHA均e498dc55cfe0dea649f52c3c4635272f32af33d67114b1270328f69ca9587467。不重交、无新增定时。本人jieruiz，task/173-and-direct-wd，沿用Issue173/PR174待审未合并；发布以SHORT_PUBLICATION.json为准，Projects缺read:project待同步。FSM另属Issue175/PR176，不混用结果。

## Issue175发布回执（2026-10-24）

Swish FSM独立重建已通过PR176上传、待审未合并；结果提交8d7ce13b，核验提交2f56108b。全部变更文件Git blob/长度核验，小于64KB另原字节回读；51函数配置、8测试，无新模型PPL/训练/RTL/PPA。PUBLICATION.json含准确SHA/Issue评论和校验索引。Projects查询实际因缺read:project权限失败；Issue、STATUS和交接已同步，看板待维护者。Issue173短流封存结果另行汇总，未改其冻结执行。

## Issue175：Swish状态机函数级重建（2026-10-24）

用户要求复现64拍Swish并核验固定权重位平面接口。已独立重建SMURF，冻结ba7ff03d（完整SHA见MANIFEST）；51配置、3seed、P8整数比较及逐拍状态，8项功能/统计测试，有限时长Markov二阶矩与结果SHA交叉核验。正半轴0..1的4状态IID T32/64/128 MAE=.062395/.044052/.031188；32层打乱输入T64=.033992，属于我们变体，排列成本未计，不是论文精确复现。按序分层均值曲线偏差.032165，顺序不可忽略。原论文0.033是MAE，不是相对误差；图9只有0..1。16状态64拍更差.057807，不能用更多状态保证短流效果。

带符号固定S扩展未用真实模型分布；S64负分支P8系数全零，低平均误差不代表保留SiLU。固定W8可保留，但原始位平面不等于单Bernoulli流，进入普通FSM前需带权/符号/尺度合并并形成g幅度码或另研整数流FSM；权重双随机也不免除矩阵求和。建议先保留中间g/u定点统计、FSM输出接独立u流AND再Wd；不存在本次整FFN/PPL/PPA证据。前级64拍后再FSM64拍至少128拍加归约等，不能说全FFN64拍。

负责人jieruiz，Issue175，task/175-smurf-swish，独立稀疏目录tmp/smurf-swish-20261024；base PR174@bec546d4，报告qwen3/results/smurf_swish_20261024/REPORT_ZH.md。发布以work/jieruiz/175/PUBLICATION.json为准，未合并；Projects尚未确认。无新GPU/定时，不修改Issue173 Slurm2891冻结执行；其完成结果需单独按封存SHA汇总，不能从队列消失直接宣称交付。

## Issue173：短流分层Slurm2891已启动（2026-10-24）

固定执行c44c2edc23a9a66c9e48c7f9cf99300fa34cefb0，Slurm2891_[0-2]均RUNNING、每片27项CPU/CUDA/模型预检通过，三次BF16同为13.566049199388152；概率结果尚未收齐，不能称完整PPL交付。45配置＋3BF16，四档位置三方案、32联合区间(4x2x4)、每区间1/2/4次，总T32/64/128；前级四档共享64 T=K64不变。无FSM实现/训练/PPA。源包SHA46e52b88ed8b0ee7bdecd4f23ce4896a19ecaa1179664974fe194c40c7bca42b，已归档project_archives/qwen3_and_direct_20261024/source-c44c2edc23a9.tar.gz，无额外解压副本。

服务器个人ROOT pbit-qwen3-and-short-20261024-issue173，snapshot-c44c2edc不可变；SHORT_SUBMISSION.json含回执，SHORT_RECOVERY.json可恢复。不重交健康任务，不建立未请求的定时；完成后仅依据complete.json/documents/sidecar SHA核验48物理/46唯一结果、36层全前缀，并对original均值/IID64三seed与原Slurm2886做同值复核。交付仍Issue173/PR174待审未合并，Projects未同步。

## Issue173：固定四档与32联合分层短流准备（2026-10-24）

用户明确固定S不能随输入变化，要求非线性分层、采样不超过128；可32层每层重复。新增original=[S,S/4,S/16,S/64]、lower_half=[S/2,S/8,S/32,S/128]、lower_floor=[S,S/4,S/16,S/128]三固定四档。前级x/Wg/Wu保持固定四档W8共享64 T=K64。后级为4(g)*2(sigmoid)*4(u)=32联合等体积区间，各取1/2/4次，总32/64/128；不是每支各32段，同序边际分层会偏置乘积。7类边界Binomial严格压缩、Wd直连及整数移位路径不变。状态机仅调研，未实现。

22项CPU功能通过，3项CUDA与缺本地Transformers的runner留Slurm预检；45三seed配置＋3BF16后缀计划。正式qwen3/and_direct/short_core.py、short_run.py、SHORT_STREAM_ZH.md。待冻结上传与Slurm提交，作业ID/准确执行和实际进度以work/jieruiz/173/SHORT_SUBMISSION.json为准，未有回执不得宣称已运行。沿用Issue173/PR174、本人jieruiz及现有目录；无训练/PPA，不改旧快照，不合并，Projects未同步。

## Issue173：前级64次核验与SiLU状态机调研（2026-10-24）

已核验PR174当前head 0c94a2d8、Issue173与本人jieruiz；五个关键源码与冻结执行8249fad6原字节相同。g/u有限AND实验前级是固定W8、TRAIN固定四档x、共享64随机字、T=K=64分层；后级三流IID，两者不能混称。首层x/g/u给出的是RMS而非均值；gate/up恢复仍FP32参考。文献SMURF(2405.02356v1, ASP-DAC2025)实际测试Swish的64/256比特近似，但没有Qwen验证；候选可直接拟合p*sigmoid(sign*S*p)，保留尺度/符号，与独立u流AND。FSM状态/初始化/相关性必须实际模拟，不能用IID Binomial冒充，也不自动改善同量程的IID采样方差。

详细调研和四档位置/两档空缺分析追加在qwen3/and_direct/MULTISCALE_ZH.md；FSM_RESEARCH_AUDIT.json记录复核。没有新增PPL、训练、RTL/PPA或作业；下一步是状态机微测试与TRAIN选档，尚未执行。沿用Issue173/PR174与现有工作目录，不合并；本节远端发布以该PR提交及Issue回执为准，Projects未同步。

## Issue173多档发布回执（2026-10-24）

PR174已更新多档结果、ready待审未合并；科学提交a1e81c1d，发布核验head b079f455。42个文件经提交树blob SHA/长度核验，40个另原字节回读；两个大型文件使用内容寻址校验，HTTP中断未导致重复实验。Issue173已同步，MULTISCALE_PUBLICATION.json记录回执。Slurm2886已退出队列，无定时；Projects未同步。

## Issue173多档g/u直连Wd完成（2026-10-24）

用户提出幅度多档与输出移位对齐。已接续PR174实现，冻结8249fad60203679f6fc51f0661aaaac2889c86f1，Slurm2886五片完成；每片18项功能（含CUDA整数对照）通过。45份封存计分/41唯一配置、36层全前缀与SHA核验通过；无训练/RTL/PPA。Qwen3-4B后训练，准确Attention，8×128目标后缀；BF16五次一致13.566049，旧z重编码三seed及B1均值与前轮完全一致。

g/u每64通道的TRAIN固定S不变，通道选择固定档位：B2=[S,S/64]，B4=[S,S/4,S/16,S/64]，B8=[S,S/2,...,S/128]，无在线absmax。三seedPPL：B2 T64/256=2482468.68/2294.6095；B4 T64/256/1024=42.34168/14.46628/13.71393；B8=15.97791/13.90611/13.46984。均值对照B1/2/4/8=13.49820/13.45553/13.44746/13.43162。B8同时增加密度与低端覆盖，不把收益全归档数；不是完整WT2，不据略低于BF16声称能力提高。

首层x/g/u RMS=0.115725/0.211005/0.178412：g/u确实较x大，但相对量程占空比仍低。平均AND概率B1/B4/B8=.0009104/.123414/.227285。sigma必须按真实g驱动：幅度8+符号+指数经整数移位/RNE/饱和转signed8 field，再P8 LUT+独立比较器；不是sigma(g/Sg)。Wd同局部scale域的乘积指数合并B4为7类、B8为15类；先同指数归约再对齐，64倍=6位，双边64倍=12位。无z恢复/重采样；16位scale系数沿用，signed64容器/实际上界检查。gate/up恢复仍FP32参考，未完成全FFN bittrue或TLM/PPA接入。

报告qwen3/results/and_direct_20261024/multiscale/REPORT_ZH.md；方法与一手文献qwen3/and_direct/MULTISCALE_ZH.md。原件project_archives/qwen3_and_direct_20261024/multiscale-sealed-2886.tar.gz，SHA9d7fbc40697ebbd6e4a80194778308784e6b2b803864438fbbd5b34675935b4b；MULTISCALE_RECOVERY.json恢复源码包。负责人jieruiz/task/173-and-direct-wd，沿用tmp/qwen3-and-direct-issue173-20261024，PR174待审未合并。无定时、勿重交；Projects未同步。最终发布见MULTISCALE_PUBLICATION.json。

## Issue173发布回执（2026-10-24）

PR174已转ready、待审未合并；结果提交898ba797，23个文件远端原字节核验一致，Issue173已同步。Slurm2881已退出队列，五片封存核验完成；无定时/健康任务遗留。FINAL_PUBLICATION.json记录回执，Projects未同步。

## Issue173有限AND直连Wd完成（2026-10-24）

Slurm2881五片完成，执行098c7a00db27dded1b7047dc5828871e4b057f70。每片12项检查通过，包括GPU有界整数GEMM与逐拍事件累加参考。27份封存计分/23唯一配置、documents与sidecar SHA、36层全前缀覆盖通过。后训练Qwen3-4B，8×128=1024目标后缀，非完整WT2；准确Attention。BF16五次完全一致13.566049，W8 13.414964；旧8位均值z再编码三seed13.428421，直连均值原尺度13.517797、有限系数13.498204。有限三流直连T64/256/1024/4096三seed分别8949057.252807/7735.004324/30.692997/14.937278。首层平均AND概率0.000910389，T64零事件95.02%；不能用旧均值PPL支持短流直连，也不能认为8位门限只需256次就充分。

新路径：幅度8+符号/驱动signed8/概率8+true-one，独立三流AND事件跨Wd输出共享；Wd固定W8，有限恢复系数16位、signed52输出累加、整数RNE BF16。无z重新统计/定标/采样。gate/up恢复仍FP32参考，无训练、RTL或PPA。建议先解决SgSu和稀少事件问题，再冻结训练硬件前向；勿把当前T64直连直接当可用训练配置。

负责人jieruiz/task/173-and-direct-wd，目录tmp/qwen3-and-direct-issue173-20261024，PR174依赖PR172，待审未合并。报告qwen3/results/and_direct_20261024/REPORT_ZH.md；归档project_archives/qwen3_and_direct_20261024/sealed-2881.tar.gz，SHA1f87f6f00a9ffda47ca03b0bca0d55d2236e6fe99cacd5c6bf88f9eed4d54309，RECOVERY.json包含源包恢复。无运行任务或新增定时；Projects未同步。结果远端发布以FINAL_PUBLICATION.json为准，勿重交。

## 2026-10-24 用户接受先用8位；三流输出直连Wd证据边界

用户接受先使用Issue171测试的8位接口，并询问训练应采用该接口还是精确FP32，以及三流AND输出直接进入Wd。读取确认：Issue171 core.py先算量化非线性条件均值z，再_stage(z)重新编码/采样；因此其+0.584%不是有限三流AND直连Wd的PPL。旧20261009 FixedFFN确有三流事件计数直接送Wd、无z再采样的分布级模拟，但FP32累加/理想sigmoid，旧0.5B长流结果不能继承给新4B八位短流。建议部署学生训练前向采用八位量化+实际有限三流采样直连Wd，FP32仅教师/诊断；该新路径仍需验证，不表示用户已授权启动新训练或远端已改。幅度8另符号、驱动8含符号、概率8另true-one；符号及SgSu仍需随流处理，删除z重编码后旧z尺度/Tz扫描不能直接沿用。

## Issue171发布回执（2026-10-24）

PR172已转ready、待审未合并，科学提交7a8b5e6e；23文件远端原字节回读一致，Issue171已同步。28项结果核验完成，Slurm2880已结束；无定时、无待运行任务。原始结果和源码包归档未解压复制，RECOVERY.json记录位置/SHA。Projects未同步。

## Issue171非线性位宽初筛完成（2026-10-24）

Slurm2880已结束，执行71cb58d0；28/28封存documents/sidecar SHA、36层全前缀覆盖通过。后训练Qwen3-4B，16×128=2048目标后缀，不是完整WT2。BF16 12.791943，W8原非线性12.584887；g/u幅度6/7/8/10/12分别13.041899/12.607359/12.607722/12.581222/12.577710；组合8/8/8为12.662423(+0.616%)，8/10/8为12.602765(+0.142%)。固定四档T64矩阵三seed：原非线性12.599698±0.016841，8/8/8为12.673273±0.066138(+0.584%)，10/10/10为12.586853±0.026572(-0.102%)。幅度位不含符号，驱动含符号，概率另true-one；TRAIN固定PoT尺度2..256，非线性只有条件均值，无有限AND采样。矩阵恢复仍FP32参考，不是整链bittrue/PPA或训练。

负责人jieruiz/task/171-nonlinear-width，PR172依赖PR169，待审未合并。报告qwen3/results/nonlinear_width_20261024/REPORT_ZH.md；原件project_archives/qwen3_nonlinear_width_20261024/sealed-2880.tar.gz，SHA5ea60da95c0d186f5ac1b20b68ff4348fb04107fb411340a93762cda2b889ac4，成员索引RAW_INDEX。无运行任务/定时，不重交；候选8位幅度+符号/驱动8/概率8，10位留余量，下一步有限AND噪声与全链有限恢复仍待验证。远端发布以FINAL_PUBLICATION.json为准，Projects未同步。

## Issue171 Qwen3非线性位宽初筛（2026-10-24）

负责人jieruiz；task/171-nonlinear-width；目录tmp/qwen3-nonlinear-width-issue171-20261024；base PR169@1d16d8cc，拟PR base task/168-qwen3-fixed-scale，依赖其推理源码。Slurm2880已运行，执行71cb58d0冻结；服务器6项预检通过，28项后缀PPL（16×128目标），36层全部替换。非线性使用有限码/LUT的条件均值，不是有限三流AND采样；矩阵恢复仍为FP32参考。W8单因素扫描及固定四档T64三seed组合；无训练/RTL/PPA。模型/数据复用已验证manifest。成果root与包SHA见SUBMISSION.json。完成后核验complete.json的documents SHA、28唯一配置和层覆盖，勿重复提交。Projects未同步；发布回执待补。

## 2026-10-24 用户确认：功能模拟与TLM共用数制契约

Python可用FP32/FP64作为模拟容器，不能把dtype直接当电路格式；必须模拟定点比较、尺度、舍入/溢出、随机相关性与响应。TLM引用同一契约SHA，对每一步有宏/电路映射及时间/资源/存储/能耗依据；暂无RTL允许定义功能宏、用有来源的条件PPA估计，未知不为零，未定义功能不得理想化。W8/N64/T16/32/64局部同尺度精确计数需18/19/20位；输出可另缩放量化A8（另符号）或signed8，质量未验证。完整跨档/tile位宽另计，不宣称8位累加足够。

接续Issue159/PR170，分支task/159-hardware-forward-contract；正式NUMERIC_BOUNDARIES_ZH.md，18组整数上界/最小位宽校核见work/jieruiz/159/ACCUMULATOR_BOUNDS.json。无新PPL/训练/RTL/PPA，未改完整TLM代码。下一步先定功能宏、8/10/12接口对照再联合质量/代价验收；发布状态见同目录NUMERIC_PUBLICATION.json。Projects未同步，历史证据保留。

## Issue159硬件前向纠错已发布（2026-10-24）

PR170待审未合并；科学提交d519baec0ff016bcf242526141f3bc74311513ba，15文件远端原字节回读一致，Issue159已同步。3项门禁测试通过，无新训练/PPL/RTL/PPA。HARDWARE_PUBLICATION.json记录回执；部署前向尚待实现，远端Agent是否采用须执行任务确认，Projects未同步。

## 2026-10-24 Issue159：硬件前向纠错

用户明确要求从电路出发。确认旧训练清单及近期固定尺度PPL仍使用FP32 g/u、SiLU与乘积；x/z A8不等于非线性量化。任意实数W scale、恢复/跨tile累加亦待统一。已有FP32数字RTL/PPA只证明其自身路径，不能代替随机非线性证据。FP32已降为诊断oracle，部署前向必须先冻结有限位宽/缩放/舍入/随机响应与流相关性契约。训练主权重/优化器/反向可保留浮点。W4/6/8和57项计划保留但不可启动部署验收；3项门禁测试通过，无新训练/PPL/RTL/PPA，无作业取消。

负责人jieruiz，Issue159，分支task/159-hardware-forward-contract，base d6d33995，复用tmp/qwen3-qat-plan-issue159-20261023；旧PR161已合并，新纠错PR见work/jieruiz/159/HARDWARE_PUBLICATION.json。正式审计qwen3/training/sc_qat_20261023/HARDWARE_FORWARD_AUDIT_ZH.md；交接REMOTE_AGENT_START_HERE_ZH.md，必填HARDWARE_CONTRACT.example.json。发布不代表远端Agent已修改训练，需执行任务回传计划/实现SHA；Projects未同步。不修改历史封存证据，不覆盖其他成员。

## 2026-10-24 数字PPA后续修复（Issue107/146）

追加核查：38374869_1也完成12功能场景/9功耗窗口，KIND2 SS100MHz setup=-26.219376ns，hold=0.086982ns，覆盖99.67991%；与index0合计24场景18窗口，2/3仍运行。不改RTL/约束掩盖违例。脚本已上传超算并提交，但本轮GitHub push两次遇超时/连接重置，不能称已发布PR；回读结果及Issue同步以各FOLLOWUP_PUBLICATION.json为准。

用户优先核查近期数字模块，300/400MHz后仿准备暂停。CIM的threshold[0]同时间戳0->1->0造成脚本14次/PT12次；保留raw VCD与计数，另按时间戳最终状态核对，不忽略X和非零宽度脉冲。38374763四个含RNG SS/TT smoke全部完成（8窗口、net coverage100%、STA非负，仍有check_power/库表外推告警）；以前kind2/3不重跑，非M64完整表征。15单测及591bit原报告重放通过。台账cim-38374763-delta-recovery。

数字38371792前几项功能通过，功耗被综合残留X拦住；新dead_bits逐bit用DC无叶端点或内部wire位无引用证明，未知真实连接仍拒绝。20单测及真实10400ns窗口重放通过。v3二次截窗衔接错误保留，v4修复后38374869_0已12功能/9功耗窗口完成，但SS100MHz setup=-11.985239ns是真实时序不达标，不能宣称100MHz可工作；不降uncertainty隐藏。38374869其余项仍运行，38374995 afterany:38371792恢复余下失败项，已通过跳过、无DC检查点阻塞、绝不重做综合。原健康作业/旧KIND21/计数器结果保留。原件与回执project_archives/remote_job_audit_20261024/followup/REPORT_ZH.txt；统一记录digital-ppa8-20261024-xz-recovery。后续读最新队列、Issue107/146与各HANDOFF，不能按此快照重交作业。后续PR发布状态见FOLLOWUP_PUBLICATION.json；不自动合并，Projects待同步。

## Issue168已发布回执（2026-10-24）

固定四档18项后训练Qwen3-4B后缀PPL已通过PR169发布，科学提交572afbbbc75551ecab1136e5f3391e15c8bfe748；23改动文件GitHub原字节回读一致。PR已转ready、待审未合并，Issue168已同步；没有运行中本任务作业、没有新定时。原件压缩归档与44成员SHA通过后已回收解压副本，RECOVERY.json可恢复。执行679f370f/Slurm2879不变；报告qwen3/results/fixed_scale_20261024/REPORT_ZH.md，回执work/jieruiz/168/PUBLICATION.json。Projects未同步，不能把后缀当完整WT2。

## Issue168 Qwen3-4B固定四档试测完成（2026-10-24）

jieruiz/task/168-qwen3-fixed-scale，PR169；执行679f370fa09199b67052ae6f71c0811873f4ec7e，Slurm2879已结束、18项封存/原字节SHA/36层覆盖通过。Qwen/Qwen3-4B后训练revision1cfa9a7208912126459214e8b04321603b3df60c；准确Attention，W8/A8共享64、T=K分层；无训练。TRAIN16×512，W8连续+动态32两路径分别覆盖后冻结每层每64通道x/z四档S/S4/S16/S64；测试不在线absmax。

这是batch1向量化32段×128=4096目标后缀，不是完整WT2或旧cached结果。同轮BF16 10.685883；W8-only10.525384、固定mean10.498386；三seed动态32 10.533212±0.018421、固定32 10.551331±0.071962、动态64 10.517682±0.010649、固定64 10.502135±0.028439、固定x32 10.559898±0.015856。固定相对动态32为+0.172%、64为-0.148%；固定seed波动更大，不能声称更优。BF16与替换FP32内部算术不同，下降不单独归因尺度。固定2/8档、W4/W6、任务准确率及联合Attention未测。

报告qwen3/results/fixed_scale_20261024/REPORT_ZH.md，实际固定表CALIBRATION.json；归档project_archives/qwen3_fixed_scale_20261024/sealed-2879.tar.gz，SHA ca09d749353b911aa372b80b3f6aacdebe470bc7bc41be1ee4f2020814135679。19服务器测试及17本地静态测试通过，原冻结快照未改，勿重交。PR169源码已推，结果发布以work/jieruiz/168/PUBLICATION.json为准；未合并/不关闭Issue，Projects未同步。

## 2026-10-24 第十轮审核已合并（Issue55 / PR167）

161/164/165/166通过PR167合并到TLM集成分支，merge d6d33995754fcdcea99286e4ce43f91647aa231a；远端已回读4个来源PR merged，review HEAD dedfd7d346ef7535f45404c7e456c77fed9fef2b，tree 8319d260f64b89a8258b0e974a7cc671485b8e13一致；main仍fae1298。60本地单测、50原件/2087成员SHA、34功耗窗口核验；正式台账56条。161仅训练方案无训练器/新训练；digital外推、counter活动缺口/M1、CIM随机源四项翻转率失败保留。160/163仍draft；六个Base PR继续迁移门禁。没有新GPU/EDA作业，不重复提交既有任务。审核报告work/jieruiz/55/round10/REVIEW_ZH.md；本地审计及恢复索引project_archives/pr_review_issue55_round10_20261024/。原Issue有剩余工作保持开放，Projects待维护者同步；临时review副本核验干净后回收，保留refs/原始证据。

## 2026-10-24 Paracloud任务核查与补交

本机密码SSH已通过DPAPI本地助手工作，交接PARACLOUD_LOGIN_HANDOFF_ZH.txt；只引用helper，不在文档记录凭据。最新EDA核查归档project_archives/remote_job_audit_20261024/REPORT_ZH.txt和DOWNLOAD_INDEX.json；原件逐SHA下载，未重复已有RNG报告。Issue107：数字v2 KIND21 SS/TT活动覆盖100%，仍有外推告警；38371792剩余14项已提交，index0七个CO/SUM X/Z失败，其余运行/排队。Issue133：38372030四项仅PT恢复全部完成、8窗口暂定功耗，未标注覆盖/库表告警未关闭；不重跑DC/VCS。Issue146：38372265_2及38372313_3/6/7四组合预检通过，含随机源四项threshold[0] PT/VCD翻转率不一致，未扩大全尺寸。三个中央run记录名称含20261024/38372030，任务分支/PR实际状态见各work/jieruiz/<Issue>/PUBLICATION_20261024.json；未自动合并。不要再提交已完成组合预检，也不要取消其他成员38371942。原始失败和快照保留。

## Issue159 v2已发布（2026-10-23）

远程执行交接与INT4/6/8三套扫描已通过同PR161发布，科学提交12137b19ae6a3e7d862e5785676c200ab6d910fd；19改动文件GitHub原字节回读通过，Issue159范围/进度已同步。PR待审未合并；57项仍是计划，无本任务训练器或GPU结果。完整回执work/jieruiz/159/remote_agent_v2/PUBLICATION.json。入口REMOTE_AGENT_START_HERE_ZH.md可直接交给远程Agent；实现认领与PR160模型/基线复用按该交接执行。其他任务记录保留。

## Issue159远程执行交接v2：INT4/INT6/INT8（2026-10-23）

用户要求面向远程Agent，并增加INT4/INT6，其他设置不变、工作3倍。正式入口qwen3/training/sc_qat_20261023/REMOTE_AGENT_START_HERE_ZH.md，附环境/逐seed结果JSON模板。每项实验36层gate/up/down统一Wb，三套各19项=57计划（48随机+9控制，A总114亿有效token）；BF16三个是配对重复，不是三位宽结构或三训练seed。输入仍A8、共享64、原尺度/采样/优化器设置保持，跨位宽清单一致性通过。

补明确源码/依赖、待实现模块、独立120步G2课程、checkpoint随机重放、位宽/容器区别、Slurm及回传门槛。PR160已有非Base准备，revision1cfa9a7208912126459214e8b04321603b3df60c；依赖读取head98954637，22:45交接的2869/2870状态不当实时队列，恢复先查避免重复。本任务无新训练器/GPU/Slurm/PPL；v2清单/模板/启动拒绝与独立审阅通过。继续同PR161，实际发布见work/jieruiz/159/remote_agent_v2/PUBLICATION.json；不合并不关闭，Projects待权限。

## 2026-10-23 第九轮最终合并回执及模型版本规则

用户确认后续采用Instruct／后训练模型，Base指模型，不是Git基线。规则已通过PR162进入正式AGENTS与备忘录，并写入本机AGENTS；历史Base证据保留原标注，不继承为新模型结果。

132/134/135/140/148/156六项实际均为merged，汇总PR162合并e1b23d7766303a502934d8b6eb45b9209bbb58b9，目标pbit-tlm-attention-details-20261016。远端完整树df40463e与审核head4acfcd4一致；main仍fae12982e0a92dea1f81648a5eeee148974c4a87。54单测、204来源blob、518硬件归档成员及RNG1269结构/算术与216 Pearson复核通过。无新GPU/PPL/RTL/DC/PT/Spectre实验；脚本准备与已测PPA仍分开。

137/143/147/149/153/155六项保持open并已评论后训练迁移门禁；143仍draft。160为后训练Qwen3-4B草稿、结果未齐；收尾新出现161后训练训练方案，未纳入本轮完整审核，保留后续。未取消健康作业或自动昂贵重跑。Issue55保留后续审核入口，最终状态以远端回执为准。

本轮正式台账50记录/1228配置行通过；本机镜像已有54记录/1264行，包含Issue107三条待合记录、152 APS v2待合记录和133较新记录，逐字节核对各任务正式checkout后保留，避免旧已合版本覆盖并发新工作；不得把这五项混称本轮已合。索引project_archives/pr_review_issue55_round9_20261023/ROOT_REGISTRY_SYNC.json。

本人唯一review目录已确认干净、含ignored检查0额外文件后回收约6.8MB；分支、Git对象、其他作者任务、原实验均保留。恢复project_archives/pr_review_issue55_round9_20261023/RECOVERY.json；报告work/jieruiz/55/round9/REVIEW_ZH.md、回执PR162及Issue55。本机canonical备忘录与根阅读副本同字节追加，保留其他任务全部增量。下方“准备发布／未合并”为历史时点。

## Issue159 实际发布：2026-10-23

Qwen/Qwen3-4B非Base训练设计已推送PR161，科学提交6991c97f9d54c1d9ea17ee2ce87f44d08b6677f4；远端设计文件原字节核验通过，Issue159已同步。PR待审未合并，无GPU训练/新PPL；后续执行需模型revision/数据/训练器/H200环境。19项是计划配置，不是已运行结果。work/jieruiz/159/FINAL_RECEIPT.json为回执；Projects待权限同步。

## 2026-10-23 Issue159：Qwen3-4B非Base随机FFN训练设计

用户改为Qwen/Qwen3-4B，教师/学生均非Base；PR147 Base后缀结果仅机制参考，不能继承基线。负责人jieruiz，task/159-qwen3-sc-qat-plan。全模型36层FFN W8+真实共享64/分层随机前向、主权重STE训练；动态/固定/可学习静态/固定x动态z，T8/16/32/64共16配置，加3同预算控制。B2/4/8、gap1/2/3后续分阶段；必须区分K=T与IID。

正式方案qwen3/training/sc_qat_20261023/TRAINING_PLAN_ZH.md，SCAN_MANIFEST有19项planned；清单/语法/未就绪拒绝守卫与独立审阅通过。尚无训练器、非Base基线、模型下载或H200/Slurm作业；需绑定revision/数据/环境并验证重算随机重放。上传状态见work/jieruiz/159/PUBLICATION.json及FINAL_RECEIPT，不自动合并。保留其他任务及既有证据。

## 2026-10-23 用户新增硬约束：后续采用Instruct或后训练模型

用户在本轮PR审核明确要求“不要用base版本”，并确认指模型版本：后续用Instruct／后训练版，不是Git基线。后续新实验、模型选择及PR审核都执行此要求；检查准确模型ID/revision、tokenizer/chat模板与计分协议，不能只改名称或继承Base结果。历史Base源码与原始结果作为有版本证据保留，不删除、不重标为Instruct；模型迁移须重新建立匹配基线。本轮137/147的Qwen3 Base与149/153的Qwen2.5 Base评测、155依赖的20层准备保留待迁移，不合并；143仍draft且同样涉及Base。通用随机源/电路/分析继续审核。此决策优先于下方历史“采用Base”记录，不取消他人健康作业或自行启动昂贵重跑。

## 2026-10-23 Issue150：FFN固定多档完整PPL

负责人jieruiz，task/150-fixed-multiscale，PR153待审未合并；执行49bc6bd1356413585c99dad6513d25cc34cff090。Slurm2840/2841/2842已产出全部封存结果：21项完整WT2、12候选selection、4holdout，0缺失/无效，299077计分token、24层所有forward输入覆盖通过。固定W8/A8共享64随机分层、原准确attention，非物理IID或RTL性能。无需重跑。

TRAIN独立拟合/选优后冻结d2_h0：每层每64通道x/z各自固定S、S/4、S/16、S/64，无在线absmax/扩档。BF16 11.652735；W8 11.681130；固定mean 11.691441。三seed均值：动态32 11.736131、固定32 11.851810、只固定x32 11.746519、只固定z32 11.838450；动态64 11.693775、固定64 11.736412。全固定64接近原动态32；省前端但采样翻倍，尚不能称能耗更低。主要质量差距在z，未测联合随机attention/跨语料。

正式报告qwen/results/static_multiscale_20261023/REPORT_ZH.md，完整数值SUMMARY；实际表SELECTED。原件83文件9.95MB已压缩为510435B，project_archives/fixed_multiscale_20261023/SEALED_RESULTS_49bc6bd1356413585c99dad6513d25cc34cff090.tar.gz，SHA6829e50ba08f8c25d7611c5aac5eba6b96232df46ad652dc8a35fd06ed7dd13e，逐成员核验；Git只留必要摘要、固定表和RAW_INDEX。服务器ROOT /home/Hongjie_Zeng/projects/pbit-qwen-static-multiscale-20261023-issue150不改，按索引恢复。交接work/jieruiz/150/HANDOFF.md。Projects查询缺read:project待同步；sacct关闭，完成依据签名校验JSON而非sacct。无新RTL/PPA/TLM，不自动合并/关闭Issue。

## 2026-10-23 PR142可训练两采样器已进入main

用户明确要求合入main。赢家保持WinnerHoldAttention与校正拒绝CorrectedRejectionAttention源PR142/bac0e04已审核并合入TLM分支2f233449；经独立main移植PR154，main实际merge fae12982e0a92dea1f81648a5eeee148974c4a87。正式代码experiments/trainable_pbit_attention/，历史NumPy单文件测试依赖一并移入；回读main19个来源文件SHA一致。22/22测试与两方案各3seed共6合成训练复核通过，源码/原结果未变；未做真实LLM训练、PPL、CUDA或物理RNG/RTL/PPA。最新完整TLM和FFN分档/分层仍在集成分支，不能因本次main更新误称全量已合入。Issue138保留；最终回执见PR154及Issue评论。本地归档project_archives/pr142_main_20261023，个人干净review目录回收，来源作者工作树保留；恢复分支review/138-main-port-20261023@9f1c9c0。未合并任务与长期备忘录原增量完整保留。

## 2026-10-23 Issue146：CIM前端PPA批处理v2

继续PR148/task/146-cim-frontend，保持原RTL/TB字节不变，补SS/TT100MHz八项smoke/正式Slurm、三seed、真实buffer自动验证、互斥叶子面积/功耗汇总与失败小包。修复原Tcl `$i(a)` 被当作数组变量的生成错误。11辅助检查、4个实际小RTL与48波形窗口通过，未运行DC/VCS/PT，不能写成已测PPA。包sc_cim_frontend_ppa_20261023_v2.zip，49471B，SHA f2ef9036c30adcbccd4a2c2c24543fe27061ff04facb3d6a27948f294b701228；manifest34d5b2031c141b41d8b8f14096d12539a969c5a1dbeb9027219f70b0d0caf856。台账cim-frontend-146-ppa-v2-prepared；旧v1证据不覆盖，原manifest移到project_archives/cim_frontend_20261023/SOURCE_MANIFEST_V1.json同字节保留。下一步用户依RUN_BATCH_ZH先smoke，回传reports包和logs；源码发布结果见work/jieruiz/146/V2_PUBLICATION.json，未运行服务器任务，Projects待同步。

## 2026-10-23 Issue146：SRAM邻近SNG/驱动/W8门控

新增architecture_tlm/sc_cim_frontend_20261023，任务task/146-cim-frontend，PR148已推送待审、未合并；科学提交74979fc。N64共享R8、W8固定权重、T32/K32，显式库buffer绑定，不加概率/权重副本寄存器；完整前端、SNG、门控、Q缓冲四种探针。旧计数器已有AND，初估只再加SNG/分发，避免重复；SRAM保持/装载另计，32768并行权重Q仍是CIM接口假设。附DC/VCS/PT流程及真实bitcell加载SPICE模板，无工艺模型。

最终27组13620周期、5流程检查、12窗口×115位活动检查通过；较早N64/M64前端本地/外部源各三seed通过，独立大门阵列Icarus180秒超时保留。无新DC/PT/SPICE/PPA/PPL，包根sc_cim_frontend_ppa_20261023_v1.zip，36990B，SHA73bee486fd7d1f0fff0b3ba6bf915836715ed9496e92902351f86c18c68bda6d。统一台账cim-frontend-146-functional，原件project_archives/cim_frontend_20261023，交接work/jieruiz/146/HANDOFF.md；先用户SS/TT M1 smoke再M64。发布与逐blob核验见PUBLICATION/REMOTE_VERIFY，Projects待权限/维护者同步，无运行作业。保留其他任务镜像记录。

## 2026-10-23 Issue158：切换Qwen3-4B非Base

用户明确改用Qwen/Qwen3-4B，不使用Base。jieruiz/task/158-qwen3-4b-posttrained，PR160 draft/open未合并，base PR147@357db588；独立tmp/qwen3-4b-posttrained-issue158-20261023。官方revision1cfa9a7208912126459214e8b04321603b3df60c，经hf-mirror下载；只换4B权重，保留原动态W8/B4/T32/K32共享64、max4/64token/8块、拒绝128和赢家1024参数，不引入Issue150固定幅度。原文teacher-forced PPL不加聊天模板/不生成thinking；新token绑定和TRAIN校准独立生成，Base结果不替代新基线。

执行源e174d91cfcdb318da6481884bbf17ff37c1e3797冻结，44源SHA/5本地及提取快照合同通过、17发布文件GitHub原字节验证通过。新ROOT /home/Hongjie_Zeng/projects/pbit-qwen3-stochastic-nonbase-20261023-issue158；CPU2869基础2覆盖+tiny重载通过，下载新模型中；GPU2870 afterok等待，仅1GPU。将先新模型完整BF162048/1024及精确复跑，再13项4096目标后缀（BF16+4方案三seed）；没有新PPL、没有完整概率WT2。包SHA7d840ad5f5b09bad8419c73d88b1e23499e02f7f62f90f81ece789c820120f65。旧Base快照/环境不改、不重交健康任务；未新建定时检查。SparQ是amlink1219的Issue157，分工评论6367526124已登记，本任务只提供只读模型manifest接口。恢复先读work/jieruiz/158/HANDOFF.md及最新2869/2870；独立新模型原件核验，不能直接用旧Base硬编码验证器。Projects权限待同步。

## 2026-10-23 Issue144：Qwen3最新概率架构迁移已启动

22:00 CST实际发布闭环：科学结果b8cc1daaec9bb46d992fb867dc05c117d1e4bd6f已推PR147，177个GitHub文件逐blob原字节核验和77服务器原件Git blob校验通过；PR147 ready/open未合并，Issue144清单更新、保持open待审。26/26全完成，无在跑作业；应用实际删除heartbeat qwen3，deleteStatus=deleted。回执work/jieruiz/144/FINAL_PUBLICATION.json。下一步PR审阅，完整WT2仍未提交；其他任务条目保留。下方准备发布/运行中为历史。


21:50 CST最终26项已完成并独立核验：BF16/FFN/screen-exact+FFN/rejection128+FFN/winner1024+FFN均值，1.7B=7.590088/7.666993/8.067234/8.249476/8.091915，4B=6.331575/6.365253/6.676899/6.810810/6.700177。随机三seed；全部4096目标后缀，不是完整WT2。FFN增量1.0132%/0.5319%，赢家联合6.6116%/5.8217%，拒绝联合8.6875%/7.5690%；筛选是主要先导退化来源，128与1024不等成本。2828/2829结束、两个complete齐；8c35145执行快照不改，78小原件/37 sidecar/27源码/26病例全层覆盖与NLL复算通过，17篡改负例通过。最终包SHA a3d0df3f043d4a1fee23f9da547d585bcde0f28e9c325d665880fdd5c1a2ace3，checkpoints/complete及REPORT_ZH/SUMMARY。完整26项外推156 GPU小时、两卡固定分模型约3.7天（±30%规划2.6–4.8天），未提交全量。当前准备同PR147最终发布/停表，实际状态见work/jieruiz/144/FINAL_PUBLICATION.json；不合并不关闭Issue，Projects待权限。后加审计不改变运行；legacy burn16/spacing4未消费，实际winner burn0/spacing1。下方运行状态均历史，勿重交任务。


2026-10-23 20:54 CST用户要求“请做完全部方案”。继续已冻结两模型各13配置共26项4096目标后缀，不重复健康作业、不扩大为完整WT2；目前日志16/26已完成（1.7B拒绝seed2运行，4B拒绝seed0运行），2828/2829均RUNNING，无错误，未收取的阶段数字不作为正式结果。依据OpenAI Docs官方定时说明通过应用工具实际建立本对话heartbeat id=qwen3，名称“完成Qwen3全部概率方案”，ACTIVE每10分钟，限定收齐26项后核验/汇总/同PR147发布并通知，随后删除定时；无变化保持安静，失败/新权限或范围修改需报告。旧基线同名id曾删除，本次是新建收尾检查。需要本机及桌面应用运行以执行本地SSH/发布，服务器Slurm独立继续。发布源仍8c35145不改，最新科学结果672ad88；此前head5ce00f6的94文件GitHub逐blob原字节通过。

20:33 CST新增已核验FFN-only：两模型3seed齐，1.7B后缀均值7.6669926785、样本std0.0086502594，较7.5900880974为+1.013223827%；4B均值6.3652531446、std0.0029902575，较6.3315746169为+0.531913935%。每配置约156/204秒；都是4096目标后缀且Attention仍原生SDPA，不是完整WT2或联合结果。checkpoints/ffn包SHA53d085047ee27025f2ef42bf04c2ee7c863ae5cb09dcd4eab733c3557af8ab63，38小文件/17签名JSON/8病例执行和覆盖核验通过。2828/2829已转screen-exact+FFN，后续拒绝/赢家待跑；原执行8c不改，不重交任务。55文件启动交付GitHub原字节通过，FFN结果同PR147继续同步。下方20:25首批状态保留为历史。

用户授权两个Base模型迁移最新概率架构并比较PPL。负责人jieruiz；task/144-qwen3-stochastic，[PR147](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/147) draft/open未合并，base task/136-qwen3-bf16@0829b9c（依赖PR137）；原型采样核只读复用Issue141已发布7a286ec。执行源8c35145e0073e48581640cd07c770631412a3f99冻结，CPU2827全部通过；GPU2828=1.7B、2829=4B正在运行，勿重复提交。个人ROOT /home/Hongjie_Zeng/projects/pbit-qwen3-stochastic-20261023-issue144；复用基线venv/权重/原文，不重下载或更改其他任务。

架构：W8/64x64固定权重、B4/T32/K32共享64 A8；max4/64token/8块/首末2强制；Qwen3 TRAIN独立16拟合+16holdout标量bias、temperature1；拒绝128接受样本、赢家1024更新，argmax/burn0/spacing1，理想FP32 Philox数值参考。原生QK-Norm→RoPE/GQA/cache/QKV/Wo保留，4B Q投影4096≠hidden2560已适配。FFN prefill+decode全层替换，Attention仅所有计分单token decode，prefill原生SDPA；不称物理RNG、RTL/PPA或等成本比较。

每模型13配置：BF16一次；FFN-only、screen-exact+FFN、rejection128+FFN、winner1024+FFN各3seed。4096目标后缀/batch2，完整候选WT2未提交。CPU/GPU tiny与两个真实模型SDPA包装bitwise、kernel独立oracle/分布/仲裁/cap检查通过；完整BF16锚点原源码复现精确同NLL。后缀BF16已验证1.7B 7.5900880974、4B 6.3315746169；概率配置运行中，没有最终增量。首批26小原件归档、11sidecar/源码/模型/数据/覆盖验证、8篡改负例通过。正式入口qwen3/stochastic/README_ZH.md、qwen3/results/stochastic_20261023/REPORT_ZH.md、work/jieruiz/144/HANDOFF.md；收取工具/验证器为后加审计，不修改执行快照。恢复检查上述作业日志/results，不按旧基线heartbeat重复跑；旧qwen3定时已删除，此任务未新增定时。Projects缺read:project待同步。

## 2026-10-23 Issue138：可训练赢家保持/校正拒绝模块

负责人jieruiz，task/138-trainable-samplers，基线6966739，源码b6e3d034。新增experiments/trainable_pbit_attention；真实Bernoulli提议、均匀仲裁/保持、2^-m全零校正和自适应拒绝；全部轨迹score-function训练，有偏Softmax代理显式分离，量化禁冒称精确梯度。22/22合成数值测试，81条有限赢家轨迹/梯度穷举、三seed分布对照和6个小训练通过；无Qwen/Llama新PPL、CUDA、物理随机源或RTL/PPA。训练源码/配置/结果SHA见results/VALIDATION.json，交接work/jieruiz/138/HANDOFF.md。科学交付42beb199已推送PR142（https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/142），14文件远端原字节核验通过；PR待审、未合并，回执PUBLICATION.json/REMOTE_VERIFY.json；未改正式TLM/硬件默认，后续真实LLM集成和梯度方差/内存仍待验证。复用现有本地Torch2.4.1 CPU，无新服务器作业。

## 2026-10-23 Issue136：Qwen3 Base 双模型基线已提交

发布闭环：科学结果60d6947已推送PR137，35远端改动文件原字节核验、11提交原件SHA通过；PR现为ready/open、未合并，Issue136仍open待评审。heartbeat qwen3已实际删除，不继续轮询。work/jieruiz/136/FINAL_PUBLICATION.json记录真实回执；请勿按下方历史状态重跑。

最终实验结果已核验：Qwen3-1.7B-Base完整WT2 BF16 PPL8.3673395166、4B-Base 7.0386116013，均299077目标/292窗口且token序列SHA相同；2048/1024、seed0、原生SDPA/FFN不变，GPU评测16.92/32.92秒。源码968046f，11服务器原件SHA、源码/模型/数据/配置绑定、计分覆盖/NLL重算和10损坏负例通过。入口qwen3/results/bf16_20261023/REPORT_ZH.md；PR137结果交付待审，不合并。2797镜像失败/2798取消、2799恢复与2800_0/2801_1成功日志保留，任务没有待跑基线，勿重复提交；定时qwen3目的已完成，停表/发布见work/jieruiz/136/FINAL_PUBLICATION.json。无随机替换、训练或硬件PPA；后续方案仍需匹配控制与至少3seed。以下为历史过程。

19:20 CST更新：原CPU2797完成1.7B校验后遇4B镜像连接中断失败，GPU2798依赖取消。原冻结968046f不变，恢复CPU2799仅重试4B、GPU2801_1依赖其成功；GPU2800_0已完成1.7B完整WT2，日志PPL8.36733952/299077目标/16.9秒，服务器结果SHA与sidecar一致，仍待本地独立重放/正式结果发布。用户要求设置定时，当前对话heartbeat qwen3每10分钟检查，完成或失败通知、全部验证后停用。恢复以work/jieruiz/136/HANDOFF.md顶部及RECOVERY_20261023.json为准，不重交健康任务。下方为旧提交时点。

用户要求先通过镜像在服务器建立Qwen3-1.7B/4B基线，采用Qwen/Qwen3-1.7B-Base和Qwen/Qwen3-4B-Base。任务分支task/136-qwen3-bf16，[PR137](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/137)为draft/open、未合并；代码qwen3/，交接work/jieruiz/136/HANDOFF.md。固定revision与train/test SHA、完整WT2 window2048/stride1024、原始BF16 SDPA、seed0、无chat/BOS/cache；没有FFN/Attention替换。服务器个人项目pbit-qwen3-baseline-20261023-issue136，源码968046f冻结；隔离Transformers4.51.3环境及CPU原生Qwen3/save-reload预检已通过，CPU2797镜像下载中，GPU数组2798依赖其成功后启动。尚无完整模型PPL，恢复不要重复提交/下载。旧模型环境未改；Projects实测缺read:project待同步。后续随机方案另做匹配基线/至少3seed，不把新模型原始PPL当成替换收益。

## 2026-10-23 Issue133：计数器PPA v2运行包

用户要求对sc_counter_compare_20261023.zip做功耗面积，沿用Issue133/PR135/task/133，不重复建任务。RTL/TB不变；修正scalar VCD输出位宽被后续声明覆盖导致漏核验，补提交源码快照、A/B×SS/TT100MHz的M1 smoke与M64正式四项、数值面积/内开关漏电功耗/完整帧能量与互斥单元分类。源/新解压包9测试、Bash/Python3.6/Tcl检查及小RTL A/B四窗口90bit校验通过；没有DC/VCS/PT或完整M64新结果。zip为根sc_counter_ppa100_20261023_v2.zip，47271B，SHA 84169483a9175f7a12a1a5c5540c237fe85d501826b793b1da300ea56d7aad7f；原始小验证归档project_archives/counter_rtl_20261023/PPA_V2_VALIDATION_RAW.tar.gz。原统一record补索引，仍待跑PPA；先上传跑smoke回传4包。具体指令RUN_PPA_ZH.txt，远端状态以work/jieruiz/133/PPA_V2_DELIVERY.json及后续回执为准，本条不宣称已合并。保留其他任务镜像。

## 2026-10-23 Issue133：FFN精确计数A/B电路

用户要求暂按SRAM全并行，优先比较计数器。architecture_tlm/counter_rtl_compare提供A逐位/符号/档计数＋最终恢复，B每拍整数和＋每档累计；均精确、相同协议，排除权重存储/随机前端/浮点恢复，不改主TLM。40组RTL/13408输出、6流程及8台账测试通过；完整64输出Icarus展开超600秒未完成，待用户VCS，不冒充工艺结果。T32 PIPE1完整帧36周期；6144B/640B只是主计数状态，含流水/输出后10368B/1760B，不是面积能量倍率。ZIP根sc_counter_compare_20261023.zip，SHA3a9b84019b1e41f51f198601a57fd969c7dbbb4de896b1bd4951221b378c94b5；原件project_archives/counter_rtl_20261023/LOCAL_VALIDATION_RAW.tar.gz。四项A/B×SS/TT100MHz工艺待跑，登记counter-ab-133-functional；无新PPL。已推送，[PR135](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/135)待审、未合并。 本轮无服务器作业，Projects权限待补；详情work/jieruiz/133/HANDOFF.md。保留现有其他任务镜像，未覆盖。

## 2026-10-23 Issue107：v2只重检PT

脚本源66cb8b3，包digital_ppa8_ss_tt_100_20261023_v2.zip（2184127B，SHA067efe07b99ee85f09569198363be8a7a5155ed98e45a8b4ed698f7b05a887a4）。14单测、Python3.6 AST/Tcl/Bash通过，221冻结RTL/向量/综合约束与v1一致。VCD所有位逐一保留并对照PT有效输出活动率，PWR-981仍出现则失败；库范围9位精度及受影响单元功耗占比，不把占比当误差界限，不改负载/slew或豁免。submit_power_recheck.sh只读复用v1/results/38339971_7/15，新目录重做波形转换与18窗口PT，无DC/VCS重跑。本机无真实EDA，本次重检待用户提交。统一台账48条，保留最新集成6966739的45条原字节；身份jieruiz/Issue107 open已实时核验。发布状态见任务V2_PUBLICATION回执，不自动合并。旧结果和包保留。

## 2026-10-23 Issue107：首轮实际PPA结果

用户下载38339971_7/15两个reports包，只是KIND21 FP32→BF16 SS/TT100MHz。24门级功能场景通过、18PT窗口算出功耗且STA正slack；668成员SHA、交付manifest原字节、单元功耗/面积/能量回算通过。连续模式总68.82/91.01uW、0.7312/0.9670pJ每完成转换，包含边界寄存器；纯转换核心分类6.419/8.171uW。PWR-981 result[2047:0]部分映射和2load/1ramp超表范围未闭合，标provisional，缺原mapped.v/VCD证明；没有SDF/SPEF/CTS。中央新增digital-ppa8-38339971-smoke，旧prepared保留；报告architecture_tlm/digital_ppa_v1/results/PPA8_SMOKE_38339971_ZH.md。本轮未改EDA脚本或重跑，先复用已有波形诊断后再remaining14项。GitHub刷新连接异常，本地完成、远端同步待办；保留根台账其他任务记录，不用旧基线覆盖。沿用Issue107/task/107-digital-ppa8-ss-tt。

## 2026-10-23 Issue129 SRAM与DRAM节省报告

新增architecture_tlm/memory_savings_20261023/REPORT_ZH.md及7页Word，8个已封存v6情景复算、20源SHA、64文档/数字检查。W8减半权重不是随机独有收益；Qwen已记账2K/8K外存读写少31.95/35.52%，SRAM读写少29.82/33.49%，未闭合局部保持/计数未包含；条件存储能量不是整机PPA。采样不自动缩小完整KV缓存。PR120的48→5KiB是逻辑状态，PR127加宽读口不减少字节；新周期/完整FFN暂停保持。本轮无新实验，成果通过PR130已推送待审、未合并；Word及来源JSON原字节已核验。来源/回执见Issue129与work/jieruiz/129/PUBLICATION.json，Projects缺read:project待同步。

# p-bit LLM 项目长期备忘录

## 2026-10-23 Issue107：8类数字模块SS/TT 100MHz脚本包

沿用Issue107；PR109/111已合并，本批使用task/107-digital-ppa8-ss-tt后续分支，正式architecture_tlm/digital_ppa_v1/ppa8，脚本源6bc3389de08fba8250a17f0991849a4368898205，原RTL23e8d65f未改。KIND0/2/4/5/6/7/8/21，各SS1.08V125C及TT1.2V25C，100MHz、setup uncertainty2ns。自包含RTL/ROM/转换/TB/参考向量包在本机根digital_ppa8_ss_tt_100_20261023_v1.zip，SHA ace9d1657e67f2db6ab8064c59fce071247fe9fdf768e6fd4044fe44eeea39d4。最终解压96场景17070输出逐位通过、6流程守卫/Tcl/Python兼容/Bash检查通过；没有本地DC/VCS/PT，没有已测面积功耗。建议smoke两角KIND21后remaining14项，不重复运行健康任务；快照/阶段SHA恢复，结果自动小包。

中央台账新增digital-ppa8-20261023-prepared，功能是本地RTL证据，16工艺配置仍not_run；已合入最新集成e8705765，保留已审核原35条，新记录随本批后续PR登记。零延迟门级不含CTS/布线/毛刺，PT时序独立；含边界寄存器，SwiGLU为近似PWL，不继承PPL。KIND4/5按64元素一组、KIND6完整恢复不得再乘64/72；累加采用混合帧，非单独S128能量。原始验证含失败在project_archives/digital_ppa8_20261023/LOCAL_VALIDATION_RAW.tar.gz。上传状态以work/jieruiz/107/ppa8/PUBLICATION.json为准；任务未自动合并，Projects read:project待同步，暂无本任务BSCC作业。本条同步本地canonical、根阅读副本及本任务分支；不发布canonical中其他未提交改动。当前脚本和台账本地完成，Git推送受网络阻塞，远端状态以回执为准。

## 2026-10-22 Issue107：真实RNG接入后的Verilog仿真需求

jieruiz沿用task/107/PR109，未新开复制。对照最新PR103 b05fb36d和中央台账PR111，正式文件architecture_tlm/digital_ppa_v1/LATEST_TLM_RTL_GAPS_ZH.md及同目录机器任务表/回传模板。分已有PPA、现成RTL待工艺、新整合RTL三类，共11组：SC64×64四档T32/计数与权重驻留；BF16/FP32动态分档、恢复/累加/窄化；普通阵列/lm_head；共享比较与q/256前端、完整赢家/拒绝FSM；筛选/CDF/稀疏V；实际SRAM/CDC/DMA；普通非线性；顶层状态/互连。

重要边界：当前逐位/符号/档计数映射为6KiB/tile、8tile48KiB；每档signed20整数和对照可为640B/tile，理论状态差9.6倍不是功耗面积结论，尚无新RTL。单波次32KiB权重需明确SRAM可见输出/保持，不能认为SRAM里有就是免费驻留；单64B命令/拍100MHz只有6.4GB/s，不证明16GB/s。完整赢家需要0..512真计数/均匀选秩，KIND17的0/1/多树不能替代。源字R8，实际drive−255..255是9bit signed，q256需满幅表示；LUT/阈值保持未由原native端点PPA覆盖。

本次仅需求分析/来源位宽校核：32源Git SHA、路径和288组档内整数等价通过，无新RTL/工艺仿真/TLM/模型PPL。旧源23e8d65f及66组功能证据保持；拟新增顶层未冒充可执行包。成果已通过同PR109实际推送科学head e7b5d256ca00a725394c4ee8decf4d562a672f5c，8关键远端blob原字节核验通过，Issue107/PR说明已更新；latest_gap/PUBLICATION.json为回执，待审未合并。Projects待read:project，不自动合并。

## 2026-10-22 Issue96：真实随机架构已接入完整TLM

负责人jieruiz，沿用task/96-unified-tlm/PR103（原PR99已合并）。FullDecode默认integrated_service，core/SC/RNG/sampler/seed100MHz，SRAM按SS宏80MHz保留。原Issue95模型/RTL未改；FFN LFSR32/R8共享64、B4/T32/K32、流式消费与SAVE/RESTORE/RELEASE，Attention有限Bivium池+fair源真实输出进入筛选/PV/赢家/拒绝。源跨层/查询保留epoch与计时，种子总线/预热/到期换种/锁定延后/回压计入一次；无随机流SRAM/额外FIFO/第二概率副本，native状态/阈值保持不是免费。

执行31aa4fa31fbfb7d74629b54811936ac30a41c250；40/40完整模型情景、93机制回归、1421归档/模型契约核对通过。12项S8、赢家倍率1是整机连通诊断，非默认S128/8倍质量；其余2K/8K、三seed筛选PV、Llama1/2完整32层。原52结果不改；104宽扫描0完成/0失败主动取消并留CANCELLED，不混计。Qwen2K SC/screenPV seed0旧197.93816→新198.00316ms；BF16准确对照时延/存储/阶段一致。新q/256 sigmoid改变分布，无继承模型PPL；全部为合成事务，非真实推理/芯片时间。

正式入口architecture_tlm/unified_v6/RNG_INTEGRATION_ZH.md和RNG_INTEGRATION_RESULTS_ZH.md，原件results/integrated_rng_20261022_v3及work/jieruiz/96/integrated；代码/40项原件/报告已推送科学交付f3cf9b98f38a3cb47c40cb86669a2f180e637d0d，9个关键远端blob核验通过；PR103及Issue96已同步，待审未合并，publication回执在integrated/PUBLICATION.json。100MHz native端点PPA取38322118/中央记录PR111，有条件active/idle插值；前端/全局seed/长线和SC等未知，完整能量/面积null。512MAC/64向量/16非线性吞吐仍假设，默认Link非本次实际DRAMSys。无新PPL/GPU/Slurm/RTL/PT。旧界面52项快照不自动刷新；Projects read:project不足待同步，PR103不自动合并。当前无本人本任务运行作业。

## 2026-10-22 Issue92：小网部署计算成本

负责人amlink1219，接续Issue92/task/92-pbit-gate-pilot/PR94。新增部署运算账本qwen/results/pbit_gate_cost_20261022/README_ZH.md、COST.json及compute_cost.py。每自由块32连续乘法/40加法/8bit门控/9概率事件、两阶段；原三位置混合F21，层0/12/23候选QK省378/−165/379 MAC，小网第一层新增672乘法，不能称整体节能。含公共特征/动态归一化、GQA并集与固定S的PV边界。9模型形状、2304隐藏态门控等价、6项均值回算及独立只读审阅通过；没有新训练/Slurm/完整PPL/RTL/PPA，原质量结果保持。发布随PR94，待审未合并；上传核验以work/amlink1219/92/compute_cost/PUBLICATION.json实际回执为准。Projects沿同日已验证read:project不足待同步，不自动合并/关闭Issue。

## 2026-10-22 Issue92第二轮：直接目标与冻结盲评

用户要求持续优化小网：max4 warmup后直接最小化期望遗漏mass，准确TRAIN平均8块及隐式梯度；加入query-relative输入、温度扩展与TRAIN全局硬阈值。新192/48/48篇排除旧48篇，54原候选＋9长pbit＋27max4控制，CPU45项、先冻结90配置再一次blind全部通过；GPU2744/2746/2748/2751完成，无在运行作业。

盲集pbit三seed平均遗漏1.978%/2.021%/24.845%，原T1 4.253%/3.550%/31.365%，验证选强max4 2.069%/2.163%/24.723%。层0候选和局部质量均改善，层12多0.5%候选换质量，层23遗漏略差/候选少/PV好，不称全面胜出或隐藏随机性独有优势。确定性网仅300epoch，pbit6000；未做完整学生PPL/W8/物理PPA，约33–39% mask超512容量。blind已看，后续不得复用它调参仍称独立测试。

结果qwen/results/pbit_gate_optimization_20261022、代码experiments/pbit_gate_pilot_20261022、交接work/amlink1219/92；执行cfa19622/cfad3902/6241ab7f/f66b65ac，CPU包装727ed629，135文件SHA回传通过。完整32MB冻结/NPZ/长日志留本人服务器。原负结果和旧回执保留；第二轮科学成果64848a345c7926881f0c4b1ff543954fcc851eea已通过PR94上传待审、未合并，263项远端Git对象/8项关键SHA256已核，Issue92已同步；实际回执work/amlink1219/92/optimization_v2/PUBLICATION.json。看板因read:project不足待同步，不改正式Attention默认。


## 2026-10-22 Issue92：小型p-bit筛选网络首轮训练

用户要求先在现有服务器做简单训练；冻结Qwen2.5-0.5B，4→8→1每层49参数（8个条件独立隐藏p-bit），256态精确边缘训练，评估真隐藏/输出bit采样。32/8/8个WikiText训练文章隔离，0/12/23层、3head、3位置、3训练seed，1296完整组。Slurm2740 CPU16项通过、2741单5090训练完成，总45.90秒，训练评估30.05秒。执行53c24f28，正式代码experiments/pbit_gate_pilot_20261022、结果qwen/results/pbit_gate_pilot_20261022、交接work/amlink1219/92。

这是明确的局部负结果：训练BCE下降，但49参数网holdout遗漏6.173%/4.493%/37.082%，max4为4.552%/3.319%/32.298%，网络预算8.021/8.016/8.061块略高仍差。每层8篇留出文章配对均未改善；候选PV误差亦更差。不能称方法极限或隐藏随机性优势；当前代理BCE未证明与实际质量目标对齐。可变mask约35%–40%超过512token，不能默认现有512宏容纳。无学生完整PPL、Ising/FFN联合或PPA。后续调参须新留出协议，避免复用已看holdout。小网训练已完成且代码/报告已通过PR94上传待审、未合并，Issue92已同步；payload074172c9的82项Git对象及8项关键SHA256回读一致。看板因read:project不足待同步；不改正式默认。


## 2026-10-22 Ising评估更新（Issue37，amlink1219）

入口：[并行采样实现与结果评估补充](architecture_tlm/attention_comparison/ISING_UPDATE_20261022_ZH.md)。核查基线5b26c80c；PR79/80已合并，PR82驱动量化、PR86真实QKV、PR88全宽TLM仍开放未合并，分别按固定head读取。旧互斥Ising不能按旧状态独立同步提交；新赢家保持/校正拒绝改了规则，允许全候选独立并行提议。赢家仍是相关链；拒绝在理想响应与空态校正下直接采类别。

广播PPL仅128后缀目标（BF16 20.212326、全同步κ12约104.556）；最新赢家/拒绝仅90配置真实QKV局部V误差，无新模型PPL。v5展开源/归约/仲裁/反馈/回压；每帧全宽、帧与查询有顺序依赖，示例周期未物理标定，完整能量/面积null。旧100ns/样本表仅历史条件结果，不能与新链按同S拼接。详细来源、数值与范围见报告；本次46项来源/已保存摘要检查，无模型/Slurm/PT重跑。不接管jieruiz的Issue78/87，保留其默认和原件。

## 2026-10-20 四条训练路线讨论入口

用户要求将W8短流FFN、三投影tanh激活、四子块分数输入的p-bit随机筛选网、有限Ising观测适应整理为服务器讨论稿。Issue76入口architecture_tlm/training_plans/four_tracks_20261020/TRAINING_PLAN_ZH.md，含Word与PLAN。按可信训练收益难度3→1→4→2；第3条沿用原始variable输出，fixed8是当前联合PPL评测配置而非用户架构要求。稿件只有计划和文档验证，没有训练任务或新质量/PPA结果；资源、数据版本、质量与容量约束待执行前冻结。其他研究建议未写入方案。

更新日期：2026-10-20。负责人：GitHub `jieruiz`。本次整理任务：[Issue 28](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/28)，通过 [PR 29](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/29)交付，2026-10-19已实际合并`20a2565e0465846891c0a4ad0976e4395e7d3ecf`，实际合并回执见[Issue55](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/55)；Issue59记忆追加[PR64](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/64)已实际合并`679fd269ecaa4883bd79619d2f39d6ade2a7daca`；研究PR63已合并`4f2d953395a7335e0f15b0546c91cdac73c81169`。旧任务索引保留日期并由第12.1节更新。

本文件保存项目目标、用户决策、算法分支、实验口径、架构与证据入口，用于长对话压缩、换会话或换人后的恢复。它不替代原始结果、manifest、最新 Issue/PR 和运行日志。历史讨论不等于已实现；以下明确区分已验证、情景估计和待验证。

## 2026-10-19 可训练能量p-attention调研

接续Issue61/PR63，核查PR52 e3c5e957c3769b5fc6867b42a52facace647a83b仍开放未合并。现有screen_ising已经不显式计算Softmax，直接score差热浴CTMC；新路线是蒸馏筛选器＋低维/低位条件能量＋实际有限链训练，独立mask与binary/tree作为另一结构。报告architecture_tlm/p_attention_feasibility_20261019/README_ZH.md；计划未执行，没有新模型/PPL/GPU/PPA。现有原始/负面证据保持，Issue50/59作业不重交。数学核验与文献入库回执在work/amlink1219/61/p_attention/。Projects仍按既有scope待同步。

## ReMix v1精读，Issue70（2026-10-19）

用户指定v1正文和附录核查完成，Zotero原条目/PDF保持，唯一机器note25FR4EFX；24例独立数学校核通过。入口architecture_tlm/research_readings/REMIX_V1_ZH_20261019.md，工作资料work/amlink1219/70/。没有模型复现、训练/PPL/PPA；研究原任务61已关闭，本任务独立交付待审。

## 0 恢复工作先读这里

> 第七轮最终实际回执（北京时间2026-10-23）：103/105/106/108/109/111/113/114八项均已合并。审核PR115合并0968ccd9；113在收尾补6行元数据的新head be766ba另经原生合并46804fb3a1c50b29a19a7d0a3da6bb8f8b59af7d，当前开放PR为0。来源分支未改写。109联合＋8登记守卫、3完整Qwen及整合后336query重放通过；新q/256/PPA/资源搜索仍按各自边界。1966临时文件逐SHA归档11,167,900B（SHA d9ee7b4598ff166cc04b1e8e2796caab973bf0813f89de6682432e6ef66f1383），本人review/helper已实际回收53,149,901B。恢复project_archives/pr_review_issue55_round7_20261022/；共享对象/模型/其他任务保留，台账镜像48文件同字节。Issue55最终回执覆盖合并前pending文字，Source Issues保持原负责人及后续研究。

> 第七轮审核（合并前冻结）：103/105/106/108/109/111/113/114均通过，109补审最新82b17a1。联合109代码＋8登记守卫、40项1421合同、3项完整Qwen及整合后336query重放通过；修正真实源/观测冲突、旧页面状态与临时台账引用。来源head保留；实际合并/回收见Issue55最终回执和work/jieruiz/55/round7。没有新GPU/PPL/RTL/DC/PT。

> 数字电路仿真统一台账：digital_circuit_simulation_registry/README_ZH.md。新增仿真必须登记原件路径/SHA和实际阶段；35记录/117归档初版见文末Issue110。

> Issue107周期/访存假设和非随机数字RTL入口：architecture_tlm/digital_ppa_v1/README_ZH.md；周期是条件模型，功能RTL延迟不等于STA达标。详见文末Issue107。

> Issue104最新检查入口：architecture_tlm/inspector/README_ZH.md；可点击模块/周期/存储/证据与明确未闭合项，详见文末Issue104。模型账本检查不等于物理PPA或新PPL。


> Issue96 RNG interface follow-up: PR103 (open, unmerged) carries the new compatibility frontends/checks. Original PR99 merged0575a633 at a7a4829 during this work, excluding36d5e108/ac971e1. Check Issue96 latest receipt; do not confuse the merged52-case baseline with this interface proof.

> Issue96随机源接合核实（2026-10-22）：对照集成5dbd9e39的Issue95/PR97，FFN分层共享前端、PV打包及赢家/拒绝小接口已实际连通，执行36d5e108共11新＋21整机＋19源目录检查通过。报告unified_v6/RNG_COMPATIBILITY_ZH.md。整机FullDecode默认仍未启用新后端，旧52项不改；正式拼合需处理供给消费重叠、跨查询源时钟、筛选896路宽度、账本去重及q/256数值验证。上传回执见Issue96/PR99，不将小接口连通冒称整机已换源。

> 2026-10-22第六轮最终实际回执：93/94/97/99/100五项均已合入pbit-tlm-attention-details-20261016，最终eb317e4f；报告101与补审102已合并，99按最终a7a4829而非旧fba草稿处理。Issue55已验收关闭，最后开放PR为0。本轮本人唯一稀疏目录/helper已逐SHA归档回收；恢复project_archives/pr_review_issue55_round6_20261022/。下方草稿/待发布为历史时点。

> 第六轮最新追加：PR99已于新heada7a48297转ready并完成审核，旧fba22b1草稿分流仅为历史。49检查、52情景/62原件/22执行blob/764合同与中文报告字节核验通过，另独立重跑Qwen24层BF16与SC准确情景、26输出字段全等。其原head随本次补充集成PR交付；本轮93/94/97/99/100五项均已审阅通过，远端实际合并以Issue55最终回执为准。统一TLM仍是条件decode/合成事务，非新PPL或物理PPA。

> Issue96最新交付回执（2026-10-22）：PR99的完整实现、52项条件decode结果与报告已全部推送，科学交付head9621e1db，远端五个关键blob原字节已核验；PR已转为ready/open，待审、未合并。下方本日早先审核记录中的“99仍draft/结果待补”是此前快照。冻结执行fba22b1未改，Issue96保持open，Projects缺read:project待同步。

> 第六轮收尾新增99/100：100协议文档33检查和关键一手口径核验通过，原head5a89ced1纳入本人集成分支；99仍为draft，整机同资源情景最终结果待补，保留不合并。本轮共审核5项、通过4项（93/94/97/100），实际远端集成回执查Issue55。

> 2026-10-22第六轮审核：PR93/97已原生合并129ae823/27bf9c48；PR94的90配置冻结盲评、45检查与成本重放通过，原head424b4206纳入本人review/55-pr-round6，唯一STATUS冲突保留作者原blob9ee7dbdd，无作者分支改写。将通过本轮集成PR交付，实际远端合并/目录回收结果查Issue55最终回执和work/jieruiz/55/round6/。本轮未启动服务器/GPU/Slurm/PPL/DC/PT；旧定时不恢复。

> 2026-10-22第五轮收尾追加：PR89评估补充已直接合并作者原head，现共82/83/85/86/88/89六项成果已合并；下方五项记录为追加前快照。Issue37/78仍开放。完整回执work/jieruiz/55/round5/。

> 2026-10-22第五轮最新验收：PR82/83/85/86/88均已实际合并。Issue73的26项推理与官方逐题oracle已全部核验（54782配置内题、109564指标），不是旧19/26/pending；回查已由用户要求删除，不重建。新采样器仍无整模型PPL/物理PPA；PR88补齐可选tlm-parallel入口和4项24层合成组合验证，旧tlm默认保留。详见文末第五轮回执及work/jieruiz/55/round5/。

> 2026-10-21最新审核：PR75/77/79/80均已合并，Issue76已按用户明确授权关闭；Issue73仍收集26项最终结果、Issue78继续有限精度/模型/硬件验证。详见文末“第四轮PR审核与合并回执”及work/jieruiz/55/round4/。旧draft、GPU修复pending和未上传描述是历史快照。

> 2026-10-20 17:40 Issue73更新：旧2572三项FFN-only初始化OOM，失败日志保留、只撤回15个尚未执行FFN项；健康8项保留。新309ca9c无损把W8码INT16存储压为INT8，FP32恢复/算术/RNG不变、省4.03GiB；CPU2583七项通过，GPU2584待资源，18项补跑2585依赖其成功（尚未完成GPU验证）。请求/模板/Harness一致，最终8旧+18新=26唯一项。PIQA原BF16正式完成；其余分数未齐。预计1卡40～55h/较快2卡22～32h。用户要求的本对话heartbeat llama2-7b已设每24h，首检预计10/21 17:35北京时间，核验完成后停用；本地关机不能SSH、即时补跑未保证。恢复先读work/jieruiz/73/HANDOFF.md最新顶部，不重交健康任务。

> 2026-10-20 Issue73/PR75：Llama2-7B代表任务已启动。PIQA1838/ARC-E2376全量，各BF16＋FFN-only三seed＋Attention S128三seed＋联合S128/S512各三seed，共26项。冻结022db6828c0caba96ae3d620f80b27c1ae3774b9；CPU2570六项与GPU2571完整WT2 BF164.9795028452/335686目标、独立cached评分0差/SDPA等价/真实7B概率pilot通过。正式Slurm2572_[0-25]已运行，分数pending；不重交。FFN为B4/T32/K32共享64，Attention短题保留all K、仅计分token32层decode替换，前缀准确。Apple PR67既有FP32双模型完整基线仅复用索引；不是p-bit或Llama同权重因果对照。源码experiments/llama2_task_accuracy_20261020；结果llama2/results/task_accuracy_20261020；交接work/jieruiz/73/HANDOFF.md；PR75 draft/open未合并。

> 2026-10-20最新审核：本轮PR49/52/62/67/69/71/72已全部实际合并；科学集成18b887bd2d0cd6c06d070d8dafaf8b979742fdcf。旧完整WT2“仍运行/未收齐”已经过时，现有25项完整结果与39项任务准确率均已核验发布；仅3项B4T16联合是用户授权取消。恢复先看新增§5.7.2、§5.8.2及§12.0，不重跑已完成矩阵。研究实现/如实结果验收不等于质量无损或PPA验收。

1. 目标是利用物理随机源/p-bit降低LLM的能量、面积，同时保持可接受的质量与速度；不能为了利用随机源就假定随机计算一定胜过定点计算。
2. 正式仓库是 `rayggxia-workspace/pbit-llm-qwen-baselines`，当前主要集成分支为 `pbit-tlm-attention-details-20261016`。`main` 和历史个人仓库都可能落后。2026-10-19 PR47按用户授权实际合并后，集成提交为 `bef83e54b9da0081c51f393044d2156ce11a34b9`；其Git树与已审核head `5518a0a23e2bfec2b428542a9e4ce94b27c78d4a` 相同。
3. 三个模型入口是 [qwen](qwen/README.md)、[llama1](llama1/README.md)、[llama2](llama2/README.md)。Qwen3.5是另一组历史实验，不能默认已并入本分支。
4. FFN有两大方向：重新训练的P-DNN/多阈值AND网络；保留预训练权重、改变矩阵算术的随机计算。不能把前者N=4/16路径与后者T=256/4096拍混用。
5. 当前随机矩阵参考使用INT8权重、概率幅度码和单独符号；主接口/残差保留BF16。固定权重随机输入、双侧随机、普通OR、互斥OR是不同算法。
6. 已做过双侧随机FFN。固定Sz和8位共享64路版本的完整PPL有明显短流退化，但双侧权重噪声的全量结果用了条件高斯近似，不能叫逐连接精确实测。见第5、10节。
7. 物理随机源不需要特定种子才能用于矩阵乘法。AND两侧的独立性、时间相关和概率偏差仍需检验。区域互斥可以由组合逻辑保证；优化PRNG前缀只是一种有限样本优化。
8. Attention的准确Softmax后PV采样已有质量基线；筛选可进一步减少QK。当前max4筛选不是耦合Ising退火。随机Q/K投影不等于随机动态QK点积。
9. TLM是宏级系统估计：Python计算/片上调度，外存可接真实SystemC/TLM DRAMSys+DRAMPower；Ising仍有宏级参数。不能把情景结果称为芯片实测或最优设计。
10. 开始或恢复任务必须核对远端Issue/PR、个人STATUS及HANDOFF。这里的运行状态只是记录时点快照，不能据此断言作业今天仍在运行。

## 1 用户已经确定的方向与约束

| 方面 | 已确定的要求 |
|---|---|
| 主要目标 | 尽可能用概率计算替换FFN和Attention，两者可以叠加；整体比较质量、能量、面积、速度，而非只报告AND门数量 |
| 物理随机源 | 应允许自然随机输出；不能将精心预设的确定序列或挑选种子作为必须条件。受控映射和共享是否合适需说明成本 |
| 当前编码 | 新版优先0/1幅度流，独立处理符号；历史bipolar checkpoint缺coding字段时仍按原规则解释为-1/+1 |
| 偏置/温度 | 温度缩放容易；器件无需额外偏置端，但输入驱动可已经包含矩阵偏置。原Qwen FFN无bias，学生网络新增bias需单独说明 |
| 采样长度 | 重点探索小于256拍；4096不是硬件必然要求。128拍分层保留作基线，但不能冒称纯物理IID |
| 训练 | 先看算法和数值效果，再决定误差感知训练；不要用“必须重训”跳过当前无训练验证 |
| 存储 | 权重写入后驻留SRAM抽象模块；不接受默认用海量DFF保持全部权重并称为SRAM方案。SRAM外围及读出成本需计入 |
| 随机源分发 | 已有分层随机源和FFN本地PRNG、A8共享64路；Attention也应有随机服务，不能把全模型简化成只有FFN一个PRNG |
| 数制接口 | 固定权重可以离线准备；动态BF16/定点/概率转换必须收费。当前保留BF16残差是允许的 |
| 评估 | 完整WT2滑窗PPL优先；按需要补基础任务。单独测试FFN时Attention保留原模型；不要把后缀PPL叫完整PPL |
| 远程执行 | 新实验通过Slurm提交；个人项目目录存临时checkpoint；不覆盖已提交执行快照，不重复提交仍运行的任务 |
| 报告 | 总括表清晰可读，再给细节；结果与方法逐项对应；不能用操作数比例直接冒充整机能量比例 |
| 协作 | 一任务一Issue、独立分支和目录，通过PR交付，维护progress和handoff；正式成果与个人辅助资料分开 |

## 2 模型与逐层结构

| 模型 | 结构与当前定位 | 入口/证据 |
|---|---|---|
| Qwen2.5-0.5B Base | 24层；D=896，FFN=4864；14个Q头、2个KV头，head_dim=64；GQA；约494,032,768参数；原FFN为SwiGLU | `qwen/`、`results/base_bf16/`、本地 `pbit_llm/model_config/config.json` |
| LLaMA-1 7B | 32层；D=4096，FFN=11008；32个Q/KV头，head_dim=128，MHA；已迁移当前标准TLM | `llama1/`；Issue12/PR13已合并 |
| Llama 2 7B Base | 核心层宽/头结构与LLaMA-1 7B接近，模型权重、tokenizer/上下文规范必须独立核验；已有BF16完整基线及116项TLM | `llama2/`；Issue14/PR15已合并 |
| Qwen3.5-0.8B | 24个FFN，18个Gated DeltaNet、6个完整门控Attention；FFN/固定投影实验与Qwen2.5分开。线性状态更新不可套普通KV/QK流程 | 本地 `qwen35_publish_20261013/`，另有分支；未自动集成 |

Qwen2.5每个decoder层的主流程：

```text
BF16残差x
 ├─ RMSNorm → Q/K/V固定权重投影 → Q/K RoPE → 更新KV cache
 │            → 全部或候选QK → Softmax/Ising → 准确PV或采样V累加
 │            → O投影 → 与x相加
 └─ RMSNorm → gate和up两分支 → SiLU(g)×u → down投影 → 残差相加
重复24层 → 最终RMSNorm → lm_head → logits/下一token
```

硬件可以时分复用同一组算子执行不同层，但每层有不同权重、尺度和KV/状态；并行度、SRAM驻留、权重搬运和状态容量必须调度。不能把“重复24次”理解为容量和带宽也只有一层。Embedding与lm_head权重共享并不取消词表读出运算。

## 3 FFN算法路线与演进

原模型三个矩阵的关系为 `g=Wg·x`、`u=Wu·x`、`z=g·sigmoid(g)·u`、`y=Wd·z`。gate/up为D→F，down为F→D；三个均为稠密线性投影。

| 路线 | 计算方式 | 需要记住的结论 |
|---|---|---|
| 初版P-DNN | 连续输入→矩阵→p-bit隐藏→读出矩阵→平均 | 整个FFN换成两矩阵student，p-bit承担隐藏非线性；第一矩阵仍接收连续数，改变原SwiGLU结构 |
| 全路径P-DNN | 输入p-bit→矩阵→隐藏p-bit→矩阵→末端平均 | 每个矩阵入口二值；中间不能随意平均再称全路径二值 |
| 逐层编码/联合训练 | 学习尺度、阈值、温度；从单层扩展10/20层 | 单层局部MSE不能预测组合质量；layer0/部分末层特别敏感；联合训练有效但不能消除结构误差 |
| 门控/宽度/入口多位 | 双分支、更宽网络、K位/多阈值编码 | 曾做过，不能重复当全新方案；增加容量并非保证解决多层累积误差 |
| 多阈值AND拟合SwiGLU | 两分支p-bit bank，单比特项及AND交叉项，经读出恢复 | 曾有较好的20层及24层联合训练版本；K与输出路径N是不同参数 |
| 固定权重随机算术 | 输入幅度比特选择固定量化权重，空间/时间准确累加 | 不必把权重也随机化；消掉通用乘法后仍有计数、尺度和采样成本 |
| 双侧随机算术 | 输入、权重幅度各转独立随机流，AND再准确计数 | 已测过；短流权重噪声明显，完整精确分布验证仍需补 |

P-DNN原理和后续变更的正式长期文件继续是 [P_DNN_FFN_DESIGN_ZH.md](experiments/pdnn_ffn/P_DNN_FFN_DESIGN_ZH.md)，不能被本备忘录替代。

历史训练式多阈值AND：20层N16完整WT2 PPL为12.741809（单seed）；24层N16为13.587396±0.003214（3 seeds），N4为15.128474±0.007446。这些使用连续投影/读出，不代表4096拍随机矩阵已被压到16拍。来源：本地 `pbit_llm_master_report_20261012/PBIT_LLM_MASTER_REPORT_ZH.md` 第3.1节及其结果索引。

### 3.1 面向现有硬件的训练研究增量：Issue61（2026-10-19）

用户说明有较充足H100，希望针对硬件训练/微调，重点为SiLU与p-bit sigmoid/tanh。负责人amlink1219；[研究计划](architecture_tlm/HARDWARE_AWARE_TRAINING_PLAN_ZH_20261019.md)和[结构化矩阵](architecture_tlm/hardware_training_plan_20261019.json)明确为待执行，尚无新训练/PPL/PPA。

`x*sigmoid(x)`本来就是SiLU；保持函数的有限Bernoulli/双极均值，与sigmoid/tanh GLU及两矩阵tanh是不同实验。Extropic Z1T确有原生tanh/稀疏结构从头训练，但扩展曲线未含激活量化，不能据其32样本延迟估算宣称有限采样质量已验收。

优先三线：现有B4/T32/K32下的真实共享短流感知微调，目标T16；教师蒸馏QK筛选器，再微调有限Ising；原生激活转换与从头训练。已有sigmoid/tanh P-DNN、多阈值AND和方差正则不可重复当新尝试；20层K4/N4方差正则三seed未胜过control，见报告原件。

本轮用户限定三投影＋连续up＋仅激活p-bit；精确A/B/C未找到执行/PPL，A只在历史§27提案。旧双支/AND/SC不得按名称迁移结论。activation_only报告、结构化计划、21tip/506历史对象审计、StochA直接负面先例和Zotero本批核验已整理；未训练。

用户再次核实门控历史：双路gate/value及三投影K4 AND-bank均已做，不能把保留门控/多位编码当新主线。当前优先训练B4/T32/K32随机计算FFN；旧结构须明确新增条件和数字/原实现对照。报告§4.2与JSON已纠正，未启动训练。

用户随后纠正：旧两投影全路径扩层已失败，不能因改量化重新优先推荐。匹配20层取消入口量化仍N4=27.127764（sigmoid入口38.764105）；4位入口只核到四层12.909709，hidden仍单bit。新试验先分离表示/隐藏/结构及训练，再决定W8，旧两矩阵降为诊断对照；详见计划§4.1。

训练保持分层/共享相关结构，不能只训练期望或独立Gaussian后宣称部署有效。T（FFN）、N（激活）、S（Ising）分别记录；W8 shadow/QAT或LoRA合并后要重新导出量化。两矩阵同参数比较宽度为原GLU的1.5倍；DyT含初始化/embedding缩放对照，后续单独消融。

Issue50/PR52联合质量和Issue59代表任务仍属jieruiz，本任务只读公开成果，不重复其作业或改变其状态。执行训练前另明确子任务、数据revision/SHA、scheduler资源与本人存储；本研究未申请或验证H100分配。协作/来源/数值校核与Zotero摘要入口 `work/amlink1219/61/`。

## 4 随机矩阵运算的定义

### 4.1 编码与数制

幅度v以固定尺度S表示：`q=clip(round(|v|·256/S),0,255)`，概率 `p=q/256`；符号另存。比较器每拍取均匀8位整数R，输出 `R<q`。因此这里A8是**8位幅度加另一个符号**，不等于传统总共8位的有符号INT8。最高码概率是255/256。

BF16有指数和尾数，转概率不是直接截取某8位。动态输入需经过符号提取、尺度对齐、舍入/饱和，随机输出经过计数、符号/尺度恢复再转BF16。tile尺度若不是2的幂，不能把恢复一律当免费移位。

固定权重保留二进制INT8，可按位与输入随机位做AND，或在每拍选择权重/零。精确线性归约时 `平均(W·b)=W·平均(b)`；这说明可把噪声理解为随机输入量化，不证明某一种硬件必然胜出。

双随机把权重幅度也编码成概率；对独立输入/权重位，`E[A AND W]=pA·pW`。权重仍可以二进制存SRAM，只在计算时产生权重流，**不存储全部T拍流**。正负贡献分别计数或采用严格等价的带符号恢复。

历史双随机权重概率为 `|INT8码|/127`，对应事件幅度为127个权重步长；这不是直接拿同一码和0～255整数比较。若新版权重侧也严格采用R8比较器，分母/端点/恢复幅度必须重新定义并单独命名，不能暗中改变后继承旧PPL。

### 4.2 必须分开的归约结构

| 结构 | 空间求和 | 主要影响 |
|---|---|---|
| 精确APC/压缩器 | 统计每拍1的数量，再时间累加 | 对给定比特流无额外近似；保留随机采样噪声 |
| 权重位平面 | 各位分别popcount，最后按2的幂加权 | 可避免每条输入先扩展为多位权重再搭大加法树；需要核对符号、跨位和时间存储 |
| CSA/压缩器时间归约 | 先保留sum/carry或小块计数，延后大进位更新 | 改电路活动，不改变正确结果；节能不能只凭减少更新次数断言 |
| 普通OR2/4/8/16/32/64 | 同组贡献碰撞后只留1 | 独立事件时 `P(OR)=1-∏(1-p)`；共享流须求联合并集概率，一般不等于概率之和；增加T不能消除碰撞偏差 |
| 互斥区域OR | 重编码让每拍最多一个事件，再OR | 需要编码/缩放及量化分析；可由物理随机字驱动，无需固定顺序 |
| MUX缩放求和 | 随机选择一条贡献 | 电路简单但输出被除以组大小，可能增加方差和所需拍数 |

缓存若干拍再更新累加器的RTL已经存在；旧PT中缓存并不总省电。不能将OR64的节省百分比套到OR2/4混合结构，也不能将旧P12/DFF权重核心直接当新版A8/SRAM阵列。

### 4.3 非线性仍是关键边界

曾用 `|g|`幅度流、`sigmoid(g)`概率流和`|u|`幅度流三者AND，恢复乘积尺度 `Sg·Su`。尺度过大时事件太稀少，恢复幅度大，方差显著。

另一版先准确算 `z=SiLU(g)·u`，用更紧的 `Sz`重新编码，再送down矩阵。它改善事件密度，但保留了中间连续估计、sigmoid和逐元素乘法；不能宣传为全部非线性免费或全程纯比特流。固定Sz必须说明是每层、每组还是全局一个常数。

## 5 双侧随机流的现有结果与当前任务

以下Qwen均为全部24个FFN，Attention保持原SDPA，完整WT2 test，context=2048/stride=1024，299077个目标token。

| 固定每64通道Sz、A8共享64路 | T=256 | T=1024 | T=4096 |
|---|---:|---:|---:|
| 固定INT8权重、随机输入 | 31.6484（1 seed） | 14.0534（1 seed） | 12.4535±0.0057（3 seeds） |
| 输入、权重都随机 | 81366.1658（1 seed） | 33.6119（1 seed） | 14.1483±0.0132（3 seeds） |

BF16原版为11.652735。来源：本地 `pbit_shared_rng_ffn_20261015/results/RESULTS_ZH.md`。固定权重使用准确输入联合计数；双侧全量评估的权重残差采用条件高斯压缩近似，**不是完整逐连接精确随机实验**。128-token前缀已有精确条件二项与高斯的差异对照，不能由此直接校正完整PPL。

更早A12固定分组Sz双随机完整结果：T4096为13.948997±0.011665，T1024为42.762909±0.164946，T256为127803.483024±358.103878，也是条件高斯参考。动态Sz可改善质量但增加在线缩放成本；每层仅一个固定Sz效果明显更差。来源：本地 `pbit_sz_dual_ffn_20261014/results/RESULTS_ZH.txt`。

用户当前授权：**先完成本备忘录，再检查/尝试双侧自然随机流的性能影响**。备忘录交付后，已单独建立Issue30并完成下述精确短片段测试；后续完整PPL仍按已有证据决定预算。不要把旧高斯结果包装成新实验；不要依赖挑选seed、预设低差异序列或先重训。

已有可复用精确实现是 `pbit_shared_rng_ffn_20261015/run_shared.py --backend binomial`，条件于共享输入计数，对每连接独立权重位做准确二项抽样，与本阶段IID随机流的精确分布等价，省去展开时间顺序。旧128-token前缀T4096耗20.64秒，高斯0.56秒；原样完整滑窗粗估需20～30 GPU小时/配置，必须先小测和估时，不盲目开几十个全量任务。

### 5.1 备忘录之后实际完成的精确补测

2026-10-18，Issue30/PR31，Slurm2111：47/47输出齐全，包括未改BF16完整参考、BF16短参考和3后端×5长度×3seed的45项短测。模型/tokenizer/完整train-test共9文件及token hash重新核验，完整BF16再次精确复现11.652735047455899。**所有随机结果仅为同一test前128token、127个预测目标，不是完整WT2**；该段BF16为14.329108。

| T | 固定W＋随机输入 | 双随机精确二项 | 双随机Gaussian |
|---|---:|---:|---:|
| 64 | 35642.1 | 3410820.7 | 3081853.5 |
| 128 | 472.925 | 394262.8 | 477122.5 |
| 256 | 40.8736 | 55019.2 | 66118.4 |
| 1024 | 17.3462 | 42.6911 | 43.0987 |
| 4096 | 14.8830 | 17.3134 | 18.4728 |

表为预先固定seed0/1/2的均值，标准差及逐项SHA见结果。当前编码短T退化在精确分布下也存在；不能只归因于Gaussian近似，也不能据此否定其它权重共享/编码/互斥设计。没有新训练、OR、SRR或物理源回放。

公开安全交付分支 `task/30-qwen-dual-iid-public`，目录 `tmp/qwen-dual-iid-public-issue30-20261018/`；原执行SHA `ad14096615054a7ef0a72e43f670863e4a205b11`仅本地和服务器保存，公开源码逐SHA对应。原始校准数据推送被自动审批拒绝后，已改为仅发布代码/汇总/校验索引：两份校准与逐case长JSON留既有服务器个人项目，未绕过拒绝或将旧执行历史推送。PR31于2026-10-19实际合入TLM，merge `d589f152b46d0d4db6f2036af53f967fc5942faa`，Issue30已关闭。完整精确随机WT2尚未补测。

## 5.2 独立范围修正：Issue32 / PR34

2026-10-18，执行源`17c89c3c86f8b1c0aafe42a3eaa1d354c1e539ee`，单独目录`tmp/qwen-dual-range-issue32-20261018`、分支`task/32-qwen-dual-range`；[PR34](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/34)依赖PR31；二者于2026-10-19已实际合入TLM，PR34合并提交`5b71d4e2d00dca0d493576c60849b5ef14ddd17e`；分布/入口补充PR38也已合并`c1555ae6594c863011a70845d88c950a68de732b`，Issue32已关闭。源码和[结果报告](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/task/32-qwen-dual-range/qwen/results/dual_range_20261018/RESULTS_ZH.md)在独立实验目录及qwen/results/dual_range_20261018。Slurm2112/2113完成首轮39输出；2142/2143完成2048token确认10输出，49原件逐SHA收回。原BF16完整WT2重新复现11.652735047455899（299077目标），所有模型/语料/token/冻结源hash及8项kernel/旧实现回归、共享counts和方差测试通过。

输入和权重**原本已有独立尺度**。修正的是范围利用率：A从训练固定包络改为每token/64通道absmax；W从64×64 tile改为每输出行/64输入absmax，从相同旧W8解码值重编码。新概率为8位q/256加独立符号，S=maxabs×256/255；自然IID、A共享64、W逐连接独立、准确计数；准确Attention、无训练、无OR或种子挑选。

| T256三seed、同128token前缀（127计分目标） | PPL均值±总体标准差 |
|---|---:|
| old | 55019.203877±11876.079226 |
| 只改输入 | 20.272866±1.456530 |
| 只改权重 | 426.375111±91.667913 |
| 两者修改 | 15.723897±0.533414 |

同128token BF16为14.329108；both的T64/128/1024分别为30.448111±2.791960、18.925999±1.185136、14.832534±0.313483。gu-only为15.719206±0.880520、down-only为14.734595±0.445133；分支中未采样投影使用相同编码的期望，不能称恢复原BF16。

2048token确认（2047计分目标）：BF16为9.328747；both无采样期望9.365257±0.000000、T128双流12.667931±0.419085、T256双流10.656912±0.014438。这些仍是测试前缀PPL，**不是完整WT2随机PPL**，也不能与11.652735完整参考直接比较。

teacher同输入局部理论T256 NMSE（24层等权）gate10.12%→0.95%、up21.11%→2.26%、down51.50%→1.28%；只改A时down约2.93%、只改W约25.15%。旧down新增W方差39.81%，A共享方差11.04%，均值偏差0.648%；收紧A同时降低两类方差，因此A范围是更有效干预，但W噪声仍重要。输入平均p从gate/up4.93%、down0.761%变为20.40%、16.588%，W约14～16%变为29～30%。这是train前16teacher-token的线性投影理论误差，不能外推为全层因果贡献。

数值改善有硬件成本：在线absmax/概率尺度恢复、权重尺度元数据增加64倍；新W概率阈值8位外加符号，布局尚未定稿，不能默称原signed INT8存储不变。本轮没有新PT/TLM或节能实测。剩余短流误差更偏向SwiGLU前g/u路径，需更广语料/完整PPL再确认。原始长诊断/校准留授权服务器，teacher激活仅临时GPU张量、未持久化。

## 5.3 实际编码分布与裁剪审计（2026-10-19）

用户认为可牺牲罕见大值以改善多数小值精度，并明确授权将缩放合入项目。范围PR31/34和补充[PR38](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/38)均已实际合并；当前项目首页与qwen/README提供入口。合入版本为分组absmax，不主动百分位裁剪；没有把新数值方案直接作为TLM默认或宣称新PPA。

新审计源`622e0efd9d64ea73e27a9a213edb3a238b6ef688`，Slurm2166，前8192train-token、4×2048窗口、24层原BF16 teacher；9模型/语料与冻结文件/token hash通过，原BF16完整PPL11.652735047455899复现，4项分布单测通过。仅统计，不跑随机/裁剪模型PPL，不保存原始激活。原2165在shell启动处失败、Python未执行；重交同不可变快照已记录。原49项结果不变。

旧SwiGLU输出z按元素数加权：q=0约29.537%，1～3约54.156%，4～15约15.438%，16～63约0.837%，64～127约0.028%，128～255约0.002872%。共99.131%落在0～15；高码实际27462个，不能说只有一个极端值。旧平均q2.04156、中位1、90分位5、99分位14、99.9分位40；dynamic64平均q43.57899、零码2.605%。这是8192token计数加权统计，不与此前16token层均值1.949/30.93%混作同一批样本。新q99=255是每64组最大值映射到满幅的结果，不代表大量数值裁剪。

旧Sz乘0.5时只截约0.00283%值，但它们承载约22.384%原平方能量；实际截断SSE/原能量约2.400%，含8位舍入的总编码NMSE约2.594%，旧未缩紧的编码NMSE约0.562%。被截值能量不等于实际损失，平方能量也不等于语义/PPL贡献。标量重构误差不能直接当矩阵输出误差或PPL。

裁剪仍值得独立测试：目标是裁剪偏差＋有限T采样方差，然后用独立PPL验收。可考虑温和百分位或少数极值确定性旁路；不能仅因占比小就删除。阈值由train校准，测试文本不用于选最佳值。本次没有验证裁剪能改善整网。

[报告与入口](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/pbit-tlm-attention-details-20261016/qwen/results/dual_range_20261018/DISTRIBUTION_ZH.md)，新小型总表/索引为DISTRIBUTION_SUMMARY/ARTIFACT_INDEX。旧work32/MANIFEST以45063d8为版本边界，新DISTRIBUTION_MANIFEST单列11文件。Git传输网络失败后经同一jieruiz账号Git Data API上传，4个commit/tree SHA逐个完全相同；没有改执行历史。2026-10-19再查Projects仍缺read:project，Issue/PR已同步，看板待同步。

## 5.4 截断与固定二次幂范围：Issue39 / PR40

2026-10-19用户授权：牺牲少数大值、提高低幅度概率利用率，实际测试PPL；研究离线分组二次幂范围及权重分布。新[Issue39](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/39)/[PR40](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/40)，独立分支task/39-ffn-clipping，目录tmp/qwen-ffn-clipping-issue39-20261019，base c1555ae。不接管Attention成员任务，不修改TLM默认。

主执行6b57b92305cab5dbee2a53c0c65cb297ac976261，Slurm2167/2168：8策略+mean/3seed，512前缀，预注册3策略2048确认，共53替换。补充执行e0cf563daceb4e8528d9b1ca38da58e434907811，Slurm2185/2186，.95/.90温和裁剪和dynamic100恒1端点，共12替换；补充在最早.75无采样失败后注册，属于相同测试文本上的探索，不是独立最终评估。各自原BF16完整WT2再次复现11.652735（299077目标），新10/旧8/共享/方差测试通过；模型/语料/冻结源/token hash重验。主数组先4卡，补充期间降3，补充1卡，总并发4。最初caf4193导出受autocrlf影响，sbatch在作业创建前拒绝DOS换行；LF快照修正另记，未覆盖提交源。

编码：幅度超S时真正p=1，另有普通q/256格点；8bit q最高255本身不表示恒1，须显式饱和旁路/端点码。负数幅度截断后符号仍独立。A组共享64/W逐连接独立，准确计数、无OR/Gaussian/训练/挑选seed。仍先恢复FP32 g/u，准确SiLU(g)×u，再按独立Sz重编码给Wd；不是全比特流非线性。

固定阈值来自前8192train-token、原BF16 teacher、4×2048上下文，每层64通道分组的99.9/99.99绝对值分位；2幂向上取整，W从同一旧W8重新编码。静态激活可能分布漂移，不能保证所有新文本不过界。概率目标不是强行0.5/均匀，而是减小恢复单位下的偏差+采样方差。

硬件：权重尺度可离线，激活固定需校准。每组先计数，按eA+eW−log2T移位后跨组累加；不能将不同尺度的计数直接合成一个总数。Qwen全FFN313,786,368权重，每row64共4,902,912尺度；8bit指数4.676MiB，占原W8容量1.563%，只是容量比例，非总面积/功率。x/z全模型2160个组尺度仅2160字节。专用常数移位可接线，复用PE需指数配置/可选移位/宽累加；BF16转换仍有对齐、舍入、饱和。数字幅度是数值解释，不要求不同逻辑电压。权重不是均匀：旧gate/up/down平均p13.66/15.72/14.64%，row64约29%；旧p≤1/4比例79～85%，但比旧z低码拥挤轻。

原文[SC-CNN2020§4.3](https://pmc.ncbi.nlm.nih.gov/articles/PMC7793640/)直接采用饱和裁剪及2幂尺度，但乘法为确定优化位流，不能继承为自然IID精度；OCP MX支持组尺度/组间对齐，ACIQ与SmoothQuant提供校准/误差折中启发。具体来源和成本说明在PR40的SCALING_HARDWARE_ZH.md。

两批65替换+6基线共71输出全部齐，逐SHA和源代码复查通过。512前缀BF1612.0892，control13.9529±0.4795，.95/.90/.75范围13.7701/14.4005/19.2372；固定99.99分位132.1361，固定PoT A/W446.3353。2048前缀BF169.328747，control10.6569，.75裁剪14.1020，固定PoT A/W333.2295。温和范围改善小、仍需独立全量验证；强裁剪/简单静态分位明显退化。**所有替换分数仍非完整WT2。**

固定99.99分位无采样传播路径layer2的z只截约0.01237%元素，但该层总编码NMSE89.53%；相对该路径未编码z，不是原BF16 teacher，也不是证明全PPL仅由此层造成。少数大值可主导损失，不能只按个数裁剪。

正式结果/实现见[PR40](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/40)，qwen/results/ffn_clipping_20261019/RESULTS_ZH.md和SUMMARY/ARTIFACT_INDEX，交接work/jieruiz/39/。原始校准、长JSON留授权服务器，无新PT/PPA/完整采样WT2。PR待审未合并，Issue39保持open；Projects仍缺read:project待同步。

## 5.5 固定INT8权重＋输入幅度分桶：Issue46 / PR47

2026-10-19用户授权：权重保留固定INT8，只对输入按幅度选择不同二次幂范围，测试自然随机T<=256。新[Issue46](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/46)/[PR47](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/47)，分支task/46-fixedw-multiscale，目录tmp/qwen-fixedw-multiscale-20261019，base c1555ae。与Attention成员PR42-45分开，不修改TLM默认。

全部24FFN，Attention保留原BF16 SDPA。固定相同历史64×64 symmetric INT8解码矩阵，**没有再做权重概率重编码**；不能用此前row64概率再编码的decoded矩阵冒充同一W8。gate/up共用一次x采样，FP32 SiLU(g)×u后z独立编码；输出转BF16。无训练、无OR、无Gaussian、无分层/枚举或种子挑选。

dynamic64为历史每token64路absmax对照；pot1/4/8的顶档S由当前每token/64通道maxabs向上取二次幂，后续档为S/4、S/16等，每元素选择能容纳自己的最小档，不物理重排通道、不主动截断大值。四档需2bit档号，八档需3bit，另外保留幅度q8、符号和恒1端点语义。跨档仍共享同一R8；shared_counts准确模拟自然IID联合计数，不是lane独立二项。先恢复各lane的sign×Si×Ci/T再F.linear，与按档精确归约实数算术等价，尚非有限宽bittrue。**动态顶档与此前失败的静态分位范围不同。**

执行源e6f29b113405df53f2ca32b084d9de0dc9859343。Slurm2234核验9个模型/语料文件及源/token hash，12项新kernel、8项旧range与共享counts测试通过；原BF16完整WT2再次精确复现11.652735047455899，299077目标。2235完成41项512前缀；2276完成预注册22项完整WT2。合计65项计分、无skip/pending，68原件逐bytes/SHA收回，30项执行Git blob复核；本人最终squeue空。服务器来源为既有个人项目，模型revision/语料均未改变。

| 完整WT2，3seed均值±总体标准差 | T64补测 | T128 | T256 |
|---|---:|---:|---:|
| dynamic64 | 14.559275±0.005839 | 12.925563±0.006728 | 12.257885±0.003676 |
| pot4 | 13.038027±0.010666 | 12.309561±0.001471 | 11.989865±0.002580 |
| pot8 | 13.038505±0.012030 | 12.315184±0.003122 | 11.990151±0.004012 |

原BF16完整11.652735；同W8、无A编码、FP32 FFN控制11.681130。四档无采样编码控制11.680940；mean是确定性编码路径，不是非线性随机网络整体的数学期望。四档T128/256相对原BF16 PPL约增加5.64%/2.89%；八档未显示进一步收益。T64此前仅512前缀，因此未进入首批完整主表；用户追问后已补完完整WT2，四档相对BF16增加11.888%，八档仍无明显收益。64次更激进，128次为当前折中候选、256次精度更好；未声明任务性能几乎无损。没有新基础任务或Llama结果。

T64补测执行源a7bae630c62f08165a01192fe4226d9beac34e7c，Slurm2298/2299全部完成，11项新增计分（2BF16＋9完整T64），14服务器原件逐SHA与31源码blob复核。两批模型/文本/token/冻结依赖一致，kernel与测试文件同字节；原BF16完整再次精确复现11.652735。新结果提交a4a15018b9fd7344be916a21c3bf098c929fc5eb已实际发布PR47；正式补充qwen/results/fixedw_multiscale_t64_20261019/，新原件位于同个人项目outputs/a7bae630c62f08165a01192fe4226d9beac34e7c/。首批65项原件与SUMMARY/ARTIFACT_INDEX保持不变，首批RESULTS新增64/128/256联合表。合计76项输出、82服务器原件，需分别用两批manifest核验。

硬件边界：T是每个x/z采样阶段流长度，不是整层或整token周期；幅度档号、多桶计数、符号/端点、跨档对齐与存储需收费。旧W8量化步长并非强制二次幂，故输入PoT不等于全部尺度恢复只有移位。本轮无PT/PPA、物理随机源回放或新TLM能效；GPU参考耗时不能当ASIC周期。W侧随机共享是此前提出的候选，**本轮固定W没有权重随机流，因此没有测试双随机W共享PPL**。

正式结果qwen/results/fixedw_multiscale_20261019/{RESULTS_ZH.md,SUMMARY.json,ARTIFACT_INDEX.json}，实现experiments/qwen_fixedw_multiscale_20261019/，交接work/jieruiz/46/。原件服务器/home/Hongjie_Zeng/projects/pbit-qwen-fixedw-multiscale-20261019-issue46/outputs/e6f29b113405df53f2ca32b084d9de0dc9859343/；Git只发布代码/汇总/索引，不发布权重、文本或校准。PR47已于2026-10-19 15:44:54（北京时间）合入TLM，merge `bef83e54b9da0081c51f393044d2156ce11a34b9`；Issue46验收后已关闭。Projects新查询仍缺read:project，看板待同步。后续优先四档RTL/归约/尺度恢复PPA；T64全量已完成，不重复已验证76项。

## 5.6 多档缩放＋粗细分层：Issue46完整结果（2026-10-19）

接续用户要求同协议比较分层和缩放、档数、粗细分层及真实语言PPL文献。仍为Issue46/PR47、task/46-fixedw-multiscale，未接管Attention Issue48。实现experiments/qwen_multiscale_stratified_20261019，正式总表/图/文献qwen/results/multiscale_stratified_20261019/{COMPARISON_ZH.md,COMPARISON.json,COMPARISON.png,LITERATURE_ZH.md}。

执行db27fa3d7ed8eced13513f0cad10061a3cc59a71，Slurm2308/2309全部完成，本人队列空。67完整配置＋2BF16共69计分、72服务器原件逐bytes/SHA及37执行源blob通过；13新核/12旧multiscale/8range/shared测试通过。新后处理K分组与cfg篡改fixture通过（合成测试，不是PPL），图已视觉检查。模型/文本/token/固定依赖与前两批一致，原BF16完整再次11.652735。结果提交c8ea878c5bf2dc9c37e12a1b4595d8f2fc5c45ed已实际发布。原76输出不覆盖，合计145输出条目、154服务器原件，各批计分协议不同分别保留manifest。

全部24FFN、同固定W8、原Attention、无训练；mean控制不是全网络期望。B为幅度档数，S/S4/S16等；K为均匀门限分层数，层内T/K次有放回，跨层独立、同64路/跨幅度档共享。K1严格原IID；K=T是受控细随机分层；K256完全覆盖无随机。局部恢复方差S²×u(1-u)/(TK)，两机制可叠加，但整网PPL不保证单调。

| 同T64，三seed均值±总体标准差 | IID K1 | 细分层K64 |
|---|---:|---:|
| B1 | 17.800039±0.013904 | 11.861552±0.003298 |
| B2 | 13.324329±0.008113 | 11.703316±0.001176 |
| B3 | 13.064200±0.014960 | 11.692746±0.000593 |
| B4 | 13.038027±0.010666 | 11.693775±0.001432 |
| B6 | 13.036766±0.011718 | 11.694073±0.000768 |
| B8 | 13.038505±0.012030 | 11.693854±0.000628 |

dynamic64仅改细K64为11.768589±0.003298，K128为11.700228±0.000201。单PoT档与dynamic absmax的顶档/端点不同；不要将其混为一行。各档mean约11.680～11.687，支持有限流是主要可改进项，不等于纯权重量化损失。

缩放后粗分层仍有效：T64/B4，K4/16/64分别11.893101±0.003607、11.736863±0.004758、11.693775±0.001432；B2分别12.015205±0.002574、11.773086±0.002320、11.703316±0.001176。K16已接近细覆盖，但同质量可缩短T：B4细T16/32/64/128分别11.900826±0.003825、11.736131±0.000243、11.693775±0.001432、11.683928±0.000383；B2细T16/32为12.048887±0.000542、11.769199±0.001183。

当前建议：B2/T32为简化候选（相对BF16约+1.00%），B4/T32为更低损失候选（+0.716%），B4/T16为激进短流（+2.129%），B4/T64为低损失（+0.352%）。B3～4后增档无明显收益，未宣称B3显著优于4；未测B3的T16/32，未测T16/32同T IID。此前IID“128次折中”不能继续作为分层方案的结论。B4/T64/K16与B4/T32/K32几乎同PPL，优先考察较短T而不只减少K。

细K=T可理解为幅度码低位随机舍入；使用物理随机低位加区间控制，不是自然IID精度已被解决。区间计数器可研究复用现有流计数器；档号/准确跨档归约/移位/符号端点仍收费，W步长未保证PoT。GPU数值参考不是有限宽RTL或ASIC时序；无新PPA/能量面积实测，无基础任务或Llama新评测。

文献：DS-CIM LLaMA六任务未报告PPL；SCOPE小型字符RNN与XNOR-LSTM有真实语言PPL但非预训练LLM直接替换；SCMP公开代码采用Sobol/Owen、局部尺度/敏感INT旁路，归档未获取，仅方法线索。详细primary链接见LITERATURE_ZH。PR47已按用户授权合入TLM（merge `bef83e54b9da0081c51f393044d2156ce11a34b9`），Issue46已关闭；PR29仍待审未合并。Projects新查询缺read:project待同步。原件位于既有个人项目outputs/db27fa3d7ed8eced13513f0cad10061a3cc59a71/，Git仅汇总/索引，无权重/文本/校准原件。

## 5.7 三种短流FFN＋实际筛选/有限Ising/V采样：Issue50（2026-10-19）

用户要求确认§5.6三种较好FFN叠加真实Attention后的质量。新Issue50/PR52草稿（未合并），task/50-joint-ffn-attention，目录tmp/qwen-joint-issue50-20261019；原始base为PR47@5518a0a，PR47已由并行会话合并bef83e54后，PR52已改为集成分支pbit-tlm-attention-details-20261016。复用Attention成员Issue48/PR49的冻结执行源11f1d6ee，只读导入并保留来源/原字节，不接管amlink1219的独立Attention扫描或个人服务器目录。

三FFN固定W8：B2T32K32、B4T32K32、B4T16K16；全24层prefill与decode均替换。每个被计分token的24层Attention实际执行max4 train校准sigmoid/Bernoulli筛块＋固定8块修补→候选准确QK→burn16/spacing4有限hard-onehot CTMC Ising→输出索引直接V gather/平均。PV采样即最后一步，不重复抽一次。筛选不是耦合Ising退火；CTMC是理想硬互斥行为模型，不是物理电路实测。多token prefill Attention保留原SDPA，FFN前缀也替换，未用干净原FFN缓存。

旧完整FFN scorer每次q_len>1会绕过decode Attention补丁，故不能直接拿来测联合。本次建立cached计分器：逐目标单token、分别hook Attention和FFN，核对24层按序调用及目标数；对照匹配batch与目标位置。GPU门禁复现原BF16完整299077目标11.652735，但它只是环境参考；原FFN和B4T32下同BF16 SDPA包装器的计分logits SHA均完全相同。38上游＋10联合＋13FFN测试通过，另2完整计划测试通过。

主执行d61b2861edc91e00495268d39a738edb3599f87f，Slurm2381准备、2382主34项、2412诊断12项均完成。以下**全部仅为同一4096目标后缀**（32段×128、起始context2048、batch8），不是完整WT2；每替换组3seed，PPL算术均值：

| FFN | 原Attention | 筛选＋Ising128＋V采样 | 同路径Ising512 |
|---|---:|---:|---:|
| 原始 | 10.371557 | 11.163005 | 10.980212 |
| B2T32 | 10.476808 | 11.232234 | 11.066401 |
| B4T32 | 10.427377 | 11.197813 | 11.055307 |
| B4T16 | 10.628582 | 11.402422 | 11.201607 |

联合交互以每seed平均NLL计算Ljoint−Lffn−Latn+Lbase，六组均值约−0.0045～+0.00145，未见明显额外放大。主要损失来自Attention；B4T32较稳，但S512时与B2差值小，不能宣布显著优势。准确Softmax＋IID PV128诊断在原FFN下仍为11.094049，B4T32为11.166155，说明不能把误差全归Ising；尚无同协议筛选后准确PV，不能继续把剩余全部归筛选。实际QK候选22.756%，GQA的K候选并集约44.5%，不能混用或直接等于能耗节省。

54项计分原件（8小pilot、34主项、12诊断）＋10准备文件共64原件保留本人服务器/home/Hongjie_Zeng/projects/pbit-qwen-joint-ffn-attention-20261019-issue50/outputs/d61b2861.../。正式报告/逐seed逐段NLL/输入版本/SHA索引为qwen/results/joint_stratified_attention_20261019/。代码experiments/qwen_joint_stratified_attention_20261019/；collect_results.py和summarize_results.py可继续收集。固定公开train校准moment.pt为85917字节，SHA fefbb90c4f38c5f7a6d51a672550bd684ffe3a1415d36dc115a8ca5e05c5db0b，不重上传。

完整cached确认已提交，**尚未收齐**：新冻结源53dd0ff6a04218dc9f2b692464d5b16da284cf17，Slurm2429显存门禁成功（16×2047、32×1023前缀峰值16.23/16.31GiB），Slurm2430运行22项（新cached BF16×1、3FFN单独各3seed、原FFN及3FFN配Ising128各3seed）。batch32、window2048/stride1024、292窗口覆盖299077目标，每个目标实际走24层；固定S128不是逐query固定L/16。此前Slurm2425在实际full计划没有的32×2047-prefix pilot上OOM，未提交full worker，失败快照保留。新显存门禁覆盖实际批形状，没有修改旧执行快照。

完整原件在同本人项目outputs/53dd0ff6.../；已对其45项执行源Git blob与服务器SHA核验。恢复按work/jieruiz/50/HANDOFF.md核实Slurm2430，22项齐后生成FULL_SUMMARY.json并追加结论，不重复提交。当前仅阶段结果完成，Issue50/PR52保持open/draft，PR47已合并；Projects缺read:project，看板待同步。无新PPA/TLM能效结论。

### 5.7.1 固定B4T32、只改变Ising观测次数（同Issue50）

2026-10-19用户要求只用PPL判断次数变化。新源c0fd54446d843f0b21e94bf138c692048e518c86；Slurm2440重新核验模型/语料、49项执行源Git blob和原BF16后缀10.37155678462956，采样计划2测试通过；Slurm2441完成15新项（S32/64/256/1024各3seed＋筛选后准确PV三seed）。旧B4T32 S128/S512和FFN-only不重跑；原FFN六档参考复用成员Issue48/PR49公开summary，publication8dd1b06a、execution11f1d6ee、Slurm2380，未访问其个人服务器目录。

以下为固定32段×128目标=4096目标、batch8的**后缀PPL**均值（各3seed），不是完整WT2。burn16/spacing4、max4固定8块、FFN B4/T32/K32均不变；S为每query/head保留CTMC观测数，时刻16+4k，不是硬件更新拍或ESS。

| S | 原FFN＋相同Attention（成员已发表） | B4T32＋相同Attention |
|---:|---:|---:|
| 32 | 11.996331 | 12.065755 |
| 64 | 11.376921 | 11.514886 |
| 128 | 11.163005 | 11.197813 |
| 256 | 11.024839 | 11.066594 |
| 512 | 10.980212 | 11.055307 |
| 1024 | 10.924655 | 11.006579 |
| 筛选后准确Softmax/PV，不采样 | 10.895520 | 10.970368 |

只看本轮后缀，1024最低；256/512均值差0.011，小于各自seed标准差0.026/0.017，尚不支持明确差异或等价结论。准确PV是候选内取消采样的参考，不是PPL数学下界；不能把所有残差归Ising或把5%当发表通用标准。原FFN与本任务权重/文本/token/目标一致，原始配置/分词器部分元数据字节不同，已披露，不宣称所有输入文件逐字节相同；重叠S128/512均值完全匹配。

新正式成果qwen/results/ising_sample_sweep_20261019/{RESULTS_ZH.md,SUMMARY.json,PPL_CURVE.png/svg/csv,ARTIFACT_INDEX.json,PREPARATION.json,references/}；12公开制品Git blob/摘要字节重现/25项逐段NLL核验通过，图已视觉检查。新16计分原件＋5准备文件=21文件及旧10个对照原件均用SHA索引，留本人同一项目outputs/c0fd5444.../。原源快照不修改，没有新训练、任务基准、PT/PPA/TLM。

经后缀审阅，Slurm2461已提交6项B4T32 S256/S512各3seed完整cached确认（299077目标、2048/1024、batch32），复用53dd已验证实际显存门禁并校验数值内核未变；旧Slurm2430的S128和匹配BF16/FFN-only继续运行，不重复提交。**两组完整联合任务均未收齐**；恢复按work/jieruiz/50/HANDOFF.md核实2430/2461、按同full目标SHA合并对照，不把后缀或启动任务写成完整完成。PR52仍草稿未合并，Issue50保持open，Projects权限待同步。

### 5.7.2 完整WT2确认已收齐并核验（2026-10-20，已合并）

Issue50既有2430/53dd与2461/c0fd已收得25份封存完整结果；原22格仅3个B4T16联合S128 seed在pending时依用户授权取消，取消回执原字节保留。最佳B4T32 S128/256/512各3seed、FFN-only与matched cached BF16全部齐全，不再将旧“运行/未收齐”当作实时状态，也不重复提交GPU。新独立成果入口qwen/results/joint_full_wt2_20261020/，旧后缀报告原件保持历史。

完整计分299078测试token、299077目标、window2048/stride1024/batch32。matched cached BF16 11.652118068；B4T32-only 11.732192±0.001821；B4T32联合S128/256/512分别12.423820±0.002870、12.274153±0.005388、12.207062±0.001103（PPL逐seed算术均值±总体SD）。相对BF16的mean-NLL几何PPL变化约+6.623%/+5.338%/+4.763%，不能混作4096目标后缀或以5%阈值宣布等价。S256/S512缺同预算原FFN完整Attention-only控制，交互NLL不可计算。

原FFN Attention-only S128三seed完整12.318676±0.005035可供PR49同源代表性确认；没有原FFN S512完整原件，不泛化为六档完整曲线。49/50 model config解析JSON相同，681B LF与709B CRLF原字节不同；权重/文本/token及四个Attention核心同源，其他tokenizer元数据字节差异照实披露。准备fresh vectorized BF16 11.652735与真实B16/B32显存pilot仅作环境门禁，质量对照用本轮cached BF16。

25配置SHA、两执行94个joint/30个底层公开source blob、7300段NLL和全部24层FFN/Attention调用通过；35个门禁锁定依赖不变。本轮没有新模型推理或GPU作业、无快照修改；原始JSON用-text保留字节。实时2430/2461队列空，scontrol记录过期且sacct storage disabled，因此完成依据为封存completed/严格计分审计，不伪称取得Slurm历史终态。PR52已实际合入集成3b74375b07d16a2cb3e5d5b8ae7ceb825031472c；PR49代表性确认已合入18b887bd2d0cd6c06d070d8dafaf8b979742fdcf，Issue48/50按本任务范围验收关闭。

## 5.8 代表任务准确率与Ising次数：Issue59 / PR62（2026-10-19）

用户要求在PPL之外检查实际任务，不能将PPL增加直接等价为准确率明显下降。独立任务[Issue59](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/59)，目录`tmp/qwen-task-accuracy-issue59-20261019/`，分支`task/59-qwen-task-accuracy`；[PR62](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/62)截至本次记录为draft、未合并，base为`task/50-joint-ffn-attention`，依赖尚未合并的PR52，不是已进入集成的任务结果。

首个冻结执行源`348c8286bc8bc8e6ee00ec9876b3224b751f4800`，后续门禁诊断源为`075574ec94307202f3187845d6d7417f1e98ba48`；PPL和联合数值核未改变。0-shot官方Harness 0.4.8模板与计分：PIQA validation全部1838题、ARC-Easy test全部2376题、HellaSwag validation预先固定seed20261019的1000题子集。每任务13项：新BF16、B4/T32/K32 FFN-only三seed、同FFN配Ising S64/128/512各三seed，共39配置。`acc`按候选总loglikelihood排序，`acc_norm`沿用官方候选字符串字符长度归一；不是按token数，也不是扣除猜测基线。逐任务/seed保留原分数、相对BF16的百分点和逐题配对变化，不能把seed SD当作题集置信区间。

新cached scorer让第一答案token也由单tokendecode预测，全部24层Attention/FFN审计；候选分支恢复KV cache、RNG和筛选summary，避免分支污染。多token prefill Attention仍准确，FFN在prefill/decode均替换。准备题的prompt均小于512 token，固定8×64块预算会保留全部K，因此这些短题不能验证长上下文QK筛选效果；需同时记录每个实际计分query的候选覆盖。

初始13项scorer＋2项计划CPU测试通过，Slurm CPU2473完成；GPU2474复现原BF16完整WT2 PPL11.652735，但某两token候选的向量化/cached sumLL差0.1168触发每token0.05门禁，没有绕过。新源075574增加独立naive cached基线（各候选重算prefix，不使用cache clone或首query共享），以sumLL差1e-5及greedy严格核对；CPU2475/GPU2476现已全部READY通过，独立cached reference与分支scorer逐候选sumLL最大差0.0，新BF16完整WT2仍为11.652735，9项pilot均完成。向量化对照的最大每token平均sumLL差0.05839，12题pilot的判对错标志一致；不同BF16 GEMM/SDPA形状差异仅作诊断，不作为cached分支错误的豁免，也不从pilot得出正式替换准确率结论。

**正式39项已于2026-10-19T09:13:52Z（北京时间17:13:52）提交**：BF16三任务数组2477（indices0/13/26）；ARC-E12项2478（14～25）、PIQA12项2479（1～12）、Hella1000的12项2480（27～38），各最多2GPU且afterok2477；CPU汇总2481在全部worker afterany后执行。提交回执为本地`tmp/task59_workers_submission.json`，实际恢复入口仍为Issue59 STATUS/HANDOFF。自动collector独立源`0d4be877714ace3f1b360c4d74b62e563850e9bc`只改收集，不改075574数值快照；新增15项collector CPU测试在本地modern Python通过。

截至2026-10-19T09:19Z，**3/39项新原BF16基线已完成，36项替换评测仍运行/排队**；ARC-E/PIQA FFN-only已开始，Hella任务等待资源。下表是本次matched cached计分器的原BF16，不能与旧native-vectorized基线互换；替换准确率尚未完成，不能据此报告损失或保持不变。

| 任务与实际范围 | N | 原BF16 acc（%） | 原BF16 acc_norm（%） |
|---|---:|---:|---:|
| PIQA validation全量 | 1838 | 70.511425 | 69.967356 |
| ARC-Easy test全量 | 2376 | 64.393939 | 58.333333 |
| HellaSwag validation固定seed20261019子集 | 1000 | 41.900000 | 52.400000 |

三项原件已哈希索引到Issue59任务分支的`qwen/results/task_accuracy_20261019/`。本备忘录首轮追加`e32f7318be629de300cf2ab69854203dba516cbf`已推送至task/28-project-memory，并建立[PR64](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/64)，base为集成分支，待审、未合并；不再把这次追加写成旧PR29未合并。

失败2471为package调用错误，修复准备后2472已取消，二者没有模型运行，旧失败快照保留。用户允许停止不必要任务，已仅取消本人待排队的2430_19/20/21（B4T16联合三seed），保留已有原件与取消回执，其余最佳配置的完整确认不受影响。实时状态继续查Issue59的STATUS/HANDOFF，不能据本快照重复提交或把pilot称完整任务评测；本节为Issue28文档同步，没有新训练、PT/PPA或TLM。

### 5.8.1 首次联合任务准确率与实时估时（2026-10-19 17:51）

Issue59/PR62当前11/39完成，28项运行或排队，worker无Traceback。第一项联合S64/seed0的ARC-E完整2376题：acc63.4680%、acc_norm58.4175%，本轮BF16为64.3939%/58.3333%；这是单seed，不是三seed验收。FFN-only ARC-E三seed已齐；源码/题集/配置不变，严格collector验证与原件SHA入口为qwen/results/task_accuracy_20261019/。正式采样路径仍不发生短context的QK裁剪。

按实际解码forward而非题数外推，当前各task最多2GPU：ARC-E单S64约18.1min，PIQA/Hella约40多min。动态预计ARC-E S64三seed18:05～18:15，PIQA/Hella首seed18:20～18:40，三任务S64三seed19:00～19:20，全部S64/128/512三seed21:00～22:00（均北京时间2026-10-19）。不是Slurm承诺；长上下文尾段和资源波动可改变时间。没有为了回答状态而改作业、并行数或快照。旧09:19的3/39条保留历史时点；后续以最新completed原件为准。

### 5.8.2 39项任务全部完成并发布（2026-10-20）

Issue59的39/39配置已全部封存，Slurm2481自动汇总完成；本次只读核验时本人squeue为空。原执行075574ec94307202f3187845d6d7417f1e98ba48、collector0d4be877714ace3f1b360c4d74b62e563850e9bc不变。2026-10-20严格重放39个结果及逐题记录SHA/指标，重建SUMMARY与RESULTS逐字节匹配服务器归档；本地15项collector测试也通过，没有新训练/GPU/PPA。

完整报告提交cebba22dadb78440b210b3ec237b5e2d16c77030已推送至PR62的task/59-qwen-task-accuracy，base仍task/50-joint-ffn-attention，依赖PR52；报告已上传不等于PR合并。成果qwen/results/task_accuracy_20261019/，原件留/home/Hongjie_Zeng/projects/pbit-qwen-task-accuracy-20261019-issue59/outputs/075574ec94307202f3187845d6d7417f1e98ba48/，完整ARTIFACT_INDEX与FINAL_VERIFICATION_20261020索引源码/配置/数据及大小/SHA，旧11/39索引保留为历史。SUMMARY SHA256 be47dd60a87dfb1467add4e22c6795e02df2a80867d0085d8f1a3b70cb1e61ac；RESULTS SHA256 7fc169344d0166f938580f32fb0ce03f0f5d34465bea5a74830ccdef4d0edbde。

以下每格acc/acc_norm（%）；随机配置为3seed均值，完整SD和逐seed配对见原SUMMARY，不将seed SD混作题集置信区间。

| 方案 | PIQA全1838题 | ARC-E全2376题 | HellaSwag固定1000题 |
|---|---:|---:|---:|
| BF16 | 70.511/69.967 | 64.394/58.333 | 41.900/52.400 |
| B4T32 FFN-only | 70.421/69.840 | 64.731/58.852 | 41.833/51.833 |
| FFN＋S64 | 69.369/69.568 | 64.071/59.105 | 41.367/50.833 |
| FFN＋S128 | 69.931/69.677 | 64.534/58.474 | 41.800/51.700 |
| FFN＋S512 | 70.004/69.695 | 64.646/58.726 | 41.867/52.100 |

FFN-only变化较小，S128相对BF16的acc_norm变化−0.290/+0.140/−0.700个百分点，S512为−0.272/+0.393/−0.300；不将小幅提高称为显著优于原模型或把小变化称为已证明等价。HellaSwag不是完整10042题。FFN在prefill/decode替换，Attention仅答案单token评分decode替换、前缀仍准确；27联合配置的selected_fraction及GQA_union_fraction全部1.0，不能以本批结果证明长上下文QK筛选质量。S为burn16/spacing4下CTMC观测数，不是ESS或电路拍数。

旧3/39、11/39与动态预计完成时间保留为历史，恢复先看本节、Issue59/PR62及交接，不再重复提交已完成39项。仓库上传身份jieruiz已核实admin/push；Projects是否成功同步以最新发布回执为准。当前正式报告PR仍未合并。

## 6 随机源、p-bit与相关性

2026-10-25发布回执：Issue184/PR185已实际发布为draft/open，未合并；科学提交97ec6f12df651fc11cfa497521fe0b465cf7823a，完整tree9600d63c40808cc2236dd1a06def8fc3686ffc10与本地f7e6110bfae671b09e75d6dca7d020fbff3d85bb一致，5份关键源文件远端逐字符读回一致。实际执行源仍01d63b66，提交后快照未改。04:06:57Z观察38387635仍RUNNING，29案例已结束；首条precision_fine_seed63003为3ms总/2ms有效，实际1us采样2000次，密集输出P1=0.5109、MID=0.0068，耗时877.6s；尚无新比较器独立校准冻结或每seed2万次最终验收，不能把该短记录当正式结果。旧3seed各2万次逐位文件已在ideal_and_old_20000_v1。Projects工具未暴露，待维护者同步。Issue152接口已留言，原负责人/分支/STATUS未改。

2026-10-25新Issue184由本轮已核实rayggxia负责，独立task/184-normal-readout@d6d33995，tmp/normal-readout-issue184-20261025，不接管152/jieruiz旧任务。已把38380128三seed各20000次1us理想/旧比较器逐位CSV及单列TXT导出到analog_pbit_20261016/ideal_and_old_20000_v1，11文件SHA通过；旧MID分别1089/1145/1115，全部保留。真实源原本接旧比较器，理想判决不是完全裸核心或实际数字读出，500Hz短记录不证明IID/慢漂移。新normal_readout_v1复用未实测10MOS无输出限流拓扑，1.2V、SVT/LVT输入、10/20uA，输入反型及饱和裕量实测门禁；源01d63b66aa5653dffb4d116e1b1d5f9c951b1571，manifest743bbec6b48ee440773623698c5de423d21756ad721edc4ee1411b7082d8ec82；24文件逐个SFTP上传，无新源码压缩包，8本地/8远端测试、17Python3.6 AST、Bash和27PDK哈希通过。实际Slurm38387635已RUNNING，m3ca1003，03:54:35Z观察；8CPU16GB、APS1最多8案例、6h+15m，snapshot normal-JMJc0ox0/source不可改。4候选中SVT20u尾管VDS-VDSAT=-12.6162mV拒绝，另3正常；确定性策略选LVT20u，输入overdrive189.9/193.3mV、gm/Id11.98/11.86；1mV连接核心阶跃最坏3.5ns、10mV1.5ns，采样分辨0.5ns；不等于独立随机位率。短精度、独立cal62003/9/17冻结及新val64007/13/33每条22ms总/20ms有效/1us/2万位仍待执行结果，numeric63003/17/29与cal/val分离，fmin500Hz，本轮不自动1s/10Hz长任务或精确能耗。结果根/public3/home/t6s011227/analog_pbit_20261016/normal_readout_v1/results/38387635，结束自动normal_readout_38387635.tar.gz/.sha256。台账新增派生索引（cases空、不算新实验）与真实新run，拒绝项保留。PR实际发布以work/rayggxia/184/PUBLICATION.json为准，不虚报合并。

2026-10-25同轮派生补充：已有20ms记录固定起始相位按1us抽取，理想0.6V阈值每seed已有20000样本。三个seed的P1分别50.175%、50.80%、49.59%，lag1分别.00694、-.00371、.01008；但seed32003的lag10达到.02260，不能只看lag1就宣布独立。这是源模型的探索性证据，不是实际比较器电路产生的数字位，也不覆盖未测10Hz或慢漂移。

2026-10-25用户提出重评固定1s，目标是选足够低相关间隔后取1～4万次。已对38380128三个基准20ms波形做新派生分析，非新仿真：真实bitρ(1/5/10/20/100us)约.497–.511/.042–.057/.017–.040/.018–.035/.014–.031；核心电压1us仅.0052–.0076，理想0.6V阈值bit1us约.0029–.0051，仅未实现读出诊断。提示比较器动态/噪声值得优先检查，100us不是已证实的必需间隔；短记录残余相关不能定位慢记忆根因。建议开发候选10us/对照20us，独立校准冻结后新三seed首轮10us×1万=100ms有效+20ms启动，500Hz成本外推5.3h/seed；4万为400ms有效约18.5h。当前尚未确认新间隔或修改旧源码/协议，未提交新任务；真实bit中间电平约5.6%仍为独立读出问题。1万/4万白噪声单lag参考±.0196/±.0098不等于有相关过程CI或独立证明。计数先区分原始与VN后：公平IID VN约4原始出1位，实际需测；1万/4万原始位只够52/208个6×32bit的177bit状态包。10Hz总时长至少100ms，短记录不能覆盖更慢漂移；不同seed不拼接连续。报告results/38380128/SAMPLING_PLAN_ZH.md和SAMPLING_INTERVAL_ANALYSIS.json，中央同run追加派生索引、不增实验数。

2026-10-25已复核38380128：COMPLETED/0:0，21例0错误0告警，实际3h54m27s、累计CPU13h54m04s；8核独立案例并行。77,507,647B原包SHA c02d6ad9e148b143b906c6b3f87c151c9ce8e05e53fe26683dfaf29d4404134c及216成员、24嵌入源码文件全核，16噪声PSF重新计数/电平/sigma/100us相关一致。noise_audit、500Hz步长/带宽与APS/classic短程工程门禁全过，PILOT_PASS允许后续独立校准；不等于P50/读出/熵合格。基准三seed核心sigma12.33–12.39mV，密集P1=45.819/48.3905/47.2275%，MID=5.6405/5.582/5.5935%；真正100us对齐每seed仅200位，P1=49.5/46.5/51.5%，MID13/8/15，lag1约.0553/.1118/.0444，不能用密集20万点声称独立位数。历史Vref608.527348mV未独立10Hz冻结；调整Vref不保证修复MID。匹配100MHz/2.5ns当前基准外推1.02s单条45.04h、乘2约90.08h；六条理想并行仍约45h，校准+10Hz精度调度外推44.85h，均未实测10Hz。旧门禁用最慢200MHz速率并再加精度系数，给155/182h，96h提交会被阻断；本轮没有修改源码或绕过门禁。没有新校准/1s作业，不重交完成pilot。报告architecture_tlm/physical_rng_long_channel/results/38380128/REPORT_ZH.md与REVIEW.json；原包project_archives/analog_long_channel_20261024/results，中央同run更新完成短程检查，保留原运行回执。Issue152仍open/jieruiz负责；PR156仅v1已合并de7eae90。rayggxia连接器仅只读，v2/本轮结果本地Git尚未发布延续PR，未以另一身份写入。

2026-10-24后续进度查询再次出现认证后open_session超时；有界复查10.406s，命令未发出。38380128最后实际RUNNING观测仍为11:52:46Z，本次没有新进度或重交。SSH问题尚未根治，不能因前轮五次成功宣称永久恢复。用户询问多核/时长：8核用于8独立案例；Spectre对17MOS的2/4/8线程均因规模小退为1线程；pilot6h是计算上限，先前估算3.5897h非实测总耗时。

2026-10-24 SSH复查：原Paramiko4.0.0未改配置即恢复，认证0.312s、命令通道0.484s，hostname/id正常；后续队列查询、提交、回执与SFTP均成功。此前超时发生在认证后open_session，不能归为密码错误或已证实的固定客户端兼容问题；疑似当时网关/后端间歇阻塞，缺服务端日志尚无确定根因。保持严格known_hosts，无凭据重设。确认无既有pilot后按授权提交38380128：8核16GB，APS1×最多8独立案例，6h计算+15min收尾，19:51:35开始，观测2026-10-24T11:52:46.953657Z为RUNNING/m3ca0203；五项DC/工作点/阶跃与无噪声例已完成待审，三噪声探针实际在算。21例整体未完成，不宣称精度门禁通过，未自动提交calibrate/1s。32远端脚本检查与27PDK哈希通过。源码f1f93c608b39886ece3484421e9873bbc80d7b30/manifest4d5e031fdc4907fedb25825cdf12f9f651cf3e9b2ad9ba34acd62d8b2246499c，snapshot submissions/longchannel-nptLk3CH/source不可改；results/38380128_pilot，自动包long_channel_38380128_pilot.tar.gz。回执work/jieruiz/152/run_38380128及统一台账physical-rng-pilot-38380128，四小文件原字节SFTP校验。本轮通过rayggxia连接器只读核实Issue152仍open/jieruiz负责、PR156的v1已合并de7eae90；v2仍仅本地Git/EDA，没有以另一账户推送或改负责人，原任务GitHub写入身份待恢复，后续发布需新的延续PR，不写入已合并PR。

2026-10-24测速38371942已COMPLETED/0:0，总35m04s；原包2,365,132B SHA1abba5d2b88e06b091a615c5f92fa3c0272c128a3698938ad5d5f933fd8c275c及78成员全核，project_archives/analog_long_channel_20261024/results。classic/APS1/2/4/8耗时485.96/406.92/399.80/399.38/398.93s，全部0错误0告警；APS因电路太小关闭多线程，实际均1线程。APS1省16.27%时间，建议8独立APS1案例，而非把单例强开8线程。同seed密集阈值10000点逐bit零差，核心最大差3.96uV、比较器1.11mV，不代表三seed收敛。2ms有效密集P1=51.72%、MID=5.84%，100us实际仅20bit(P1=55%)，不能称1万独立位或P50验收。1.02s线性外推38.43h/条，乘2预算76.86h；即使6条理想并行也不是再除8，24h门禁会阻止长任务。尚无新pilot/calibrate/1s作业。报告architecture_tlm/physical_rng_long_channel/results/38371942/REPORT_ZH.md及REVIEW.json，中央同run更新完成测速/部分流程，旧运行观察保留。GitHub禁交互凭据当前不可用，结果本地提交/远端已完成，不虚报PR同步。

2026-10-24已按用户授权用现有Paracloud工具登录/上传并提交测速Job38371942，8核16GB、v6_384、墙钟1:15、计算预算1h；观测2026-10-24T04:49:27.892387Z为RUNNING，m3ca1103，首例classic已真实进入Spectre噪声瞬态，尚无完成记录/加速比。初次远端32测试过但Calibre默认python3 -c破坏引号，未提交；固定本任务STUDY_PYTHON=/usr/bin/python3(3.6.8)，不改全局环境，复测32通过。实际源码f1f93c608b39886ece3484421e9873bbc80d7b30，manifest4d5e031fdc4907fedb25825cdf12f9f651cf3e9b2ad9ba34acd62d8b2246499c；snapshot submissions/longchannel-ilF7Xifb/source不可改，results/38371942_speed，结束自动long_channel_38371942_speed.tar.gz。五模式3ms仅测速，未自动交pilot/calibrate/1s。记录work/jieruiz/152/run_38371942及台账physical-rng-speed-38371942(PARTIAL_FLOW/running)，旧prepared源码归档至project_archives/analog_long_channel_20261024/source；其他dig8作业不碰。GitHub核查仍网络/凭据超时，无本轮推送/PR更新，不把服务器已提交写成GitHub已发布。

2026-10-23 v2发布实际状态：源码be40141仅本地已提交；Git HTTPS两次connection reset，API替代渠道在credential fill超时前即停止，无远端写入。PR156最新核实时仍为v1 b40e94b，未合并；v2本地直接上传目录可用。V2_PUBLICATION.json保留失败证据，待网络恢复后正常推送当前任务分支并更新Issue/PR，不强推。没有远端EDA任务或实测加速比。

2026-10-23用户进一步要求多核及控制耗时：Issue152/PR156新增v2_aps，源码be40141b96e62b67d1bf6b5ee52a9d1fe09aa866，本地已提交待推送。上传远端上传/long_channel_v2_aps（24文件235752B），先bash submit.sh speed。五条3ms测速比较classic和APS1/2/4/8线程；默认8核、pilot4案例×2线程，按测速建议选配置，报告实际线程及投影分批耗时，不承诺17MOS能获得多线程加速。APS pilot另加三seed经典统计对照（21例），calibrate/long继承已通过的求解器/线程；仍为独立校准冻结、三seed1s及500Hz对照。阶段预算speed1h/pilot6h/cal24h/long24h，墙钟另留15min；单例不超过剩余预算，预估超预算不启动长任务。32测试/17模块Python3.6/Bash/27PDK哈希/59预览通过；没有实际Spectre、服务器JobID或加速比。中央physical-rng-long-152-aps-v2-prepared全电路阶段not_run，保留v1记录。入口long_channel_v2_aps_delivery.json及README；Projects权限限制沿用。

2026-10-23用户要求100us同源采样、每seed至少1s有效记录：新Issue152/PR156（https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/156），负责人jieruiz，task/152-long-channel，源码8f72debba6ce3b83626be7e1eb892fed8310c634，科学交付84770a1已推送待审、未合并。直接上传`远端上传/long_channel_v1/`（23文件214983B），先`bash submit.sh pilot`。选原buffers_x2旧15MOS+两MOS零外加C核心+5fF，TT25C持续供电；pilot18例检查噪声开关/500Hz精度/实测成本；calibrate27例独立10Hz校准冻结后再做三seed10Hz精度；long为10/500Hz各三条1.02s、固定20ms启动、每条10000原始bit，validation41011/41047/41077不与校准/检查混用。10Hz短记录至少120ms，保留100MHz/2.5ns/noisescale1，10us strobe每十点取100us；不以稀疏电流均值算功耗。保留MID原始判决、VN两类输出/真实时间戳、32/177bit包重复/汉明/位相关和无回退时间戳source适配器。20脚本测试、16模块Python3.6 AST、Bash、27PDK哈希、51预览及6合成包接口探针通过；尚无实际Spectre/远端JobID/长记录质量或PPA。统一台账`physical-rng-long-152-prepared`电路阶段全not_run，不把预览算实验；保留其他记录。入口`analog_pbit_20261016/long_channel_v1_delivery.json`及README，formal为`architecture_tlm/physical_rng_long_channel/`；Projects另待权限/维护者同步，不接管Issue95。

2026-10-22数字随机服务功耗结果38322118已由用户提供：原汇总`远端上传/rng_service_v1_20261022/architecture_tlm/random_service/POWER_RESULTS_38322118_ZH_20261022.txt`。本会话独立复核12归档SHA/同v3源码manifest、7920已下载阶段成员、216门级PASS及252窗口能量算术；未独立重放VCD/网表、未重跑EDA或接管Issue95。100MHz三seed(LFSR/GF64/Bivium/FFN)面积3154.32/14804.64/19331.64/12360.96um2，连续功率162.467/1355.333/1204/639.6uW，1.62467/13.55333/12.04/6.396pJ每生成帧；输出宽度用途不同，FFN为单8bit字共享64比较。SS1.08V125C布局前零延迟活动/PT，CALCULATED_PROVISIONAL；PWR-981/库表外警告、无CTS/SPEF及物理熵源/健康调理/CDC等。100MHz所有已报告配置时序过，300/500未全过；FFN不停钟idle492.3uW约77%active，门控仍待诊断，不能等同已实现收益。证据`analog_pbit_20261016/digital_rng_38322118_review_20261022/`；旧Issue95段落“PPA null”仅指交付时点，不代表现今无结果，正式TLM尚未由本会话回填。数字100MHz不证明模拟源100MHz独立位率。

2026-10-22时钟口径澄清：用户提醒阵列/数字侧初步100MHz目标；row_shared_array_v1的clock_s=50ns（20MHz）、settle4/resolve2及比较器行为延迟50ns只是独立功能演示配置，不是实测物理上限或已决定降低架构频率。后续阵列周期模型应区分100MHz/10ns控制拍、模拟选通/比较/锁存读出时长及同源去相关间隔；较慢模拟读出可用多拍ready/valid表示，100MHz不代表每拍一个独立物理随机字。本次只澄清口径，未修改旧功能包/已提交快照；最新8核Spectre包扫描0.2/0.5/1us读出槽，与50ns演示时钟无关。

2026-10-22用户要求申请8核加速当前模拟任务，已另建`远端上传/p50_shared_speed_8core_v1/`（22文件215041字节），旧p50_shared_speed_v1及已提交快照不改。`bash submit.sh both`现在只提交一个总8核16GB作业，两研究方向共用最多8个单线程Spectre(-mt)案例池；同Vref三seed并行、自适应电压顺序/冻结后独立验证不变，共享27例及供电审计并行排队。config/base_config/circuits/metrics/PDK哈希逐字未改，110预览网表与旧版及1-worker逐字一致；31测试、Python3.6 AST、Bash语法、27PDK哈希及上传逐字校验通过。并发夹具和预览不是实测加速比，尚未远端提交/运行；实际许可证与速度待远端日志确认，校准依赖阶段不保证占满8核。一个归档`p50_shared_speed_8core_JOB.tar.gz`+.sha256，内部results/JOB/lowpower及shared_fast；记录并行事件/案例耗时并保留失败兄弟结果。入口`analog_pbit_20261016/p50_shared_speed_8core_v1_delivery.json`、README和local_validation.txt；仍为独立EDA源码manifest交付，无LLM仓库Issue/PR或PDK上传。

2026-10-22用户要求同时细调现有比较参考Vref到50%并探索共享高速比较器，已准备`远端上传/p50_shared_speed_v1/`（20文件约193KB）。两独立作业：旧两款10nA仅细校准Vref；新1.2V/10MOS非限流输出比较器扫描100nA/1uA/10uA后，做4源/1比较器/1个8T列锁存的真实TG共享探针，槽0.2/0.5/1us、Cbus0/1/5fF。新cal1201/1303/1409每点20ms，冻结后新val1601/1709/1801，shared2203/2309/2411不混用；不外推、不用验证数据重调。21本地测试、Python3.6/Bash语法、27PDK哈希和110份预览网表通过，未远端执行或认定50%/100ns达标；100ns未达时仍诊断最快物理有效候选并标记未达。旧快照不改，初步使用仍需按相关性选择低速采样。入口`analog_pbit_20261016/p50_shared_speed_v1/README_ZH.txt`及delivery索引。

2026-10-22零外加C结果38237164已下载复核（更新下段历史待下载状态）：归档SHA `d57893e605adc7b1463094a6ab717afcccab76915230e35fd619400f10a29760`，728成员哈希、98案例完成、14源码/98网表/27PDK及原始87噪声＋2阶跃＋6DC＋3OP/AC/noise复算通过。裸源固定0.6V判决P1=49.99..50.39%，rho(0.5us)=.00183...00256；T32@0.5us方差1.040..1.066倍IID，T128仍1.191..1.270，不认证2M独立bit/s。两旧10nA连续比较器新seed P1=44.38..48.70%，rho(1us)=.493...541，±10mV过驱动到轨1.3..2.1us；冻结参考后50%目标未达到，不能认定完整通道统计验收。真实S形曲线已测，三seed离散不是器件/PVT范围。保留0C裸源，下一步真实列共享快速比较器与MUX负载联合验证；现有阵列模型50ns仍为行为假设，不能只改延迟冒充连续滤波动态。详细入口`analog_pbit_20261016/review_38237164/结果审阅_20261022.txt`与`review_summary.json`；原包不改、不重跑、没有改旧提交快照。

2026-10-21独立CMOS模拟电路工作：用户确定先建立选bank/选行、按列共享比较器的随机源阵列功能模型。入口`analog_pbit_20261016/row_shared_array_v1/README_ZH.txt`，直接上传副本`远端上传/row_shared_array_v1/`；默认2bank×3行×8列、48裸核心共用8个采样/保持比较器，一个8bit端口，无每源DAC/比较器/自旋保持、不强制FIFO。请求捕获地址与公共Vref，输出有效后保持到消费；核心持续演化，公共Vref不代表每列任意概率。Python功能模型和Spectre/Verilog-A生成器已写，封装现有无Ccore两MOS；28项本地检查、Python3.6 AST/Bash语法、27项PDK哈希及网表生成通过，Spectre/AHDL远端实编译未做，zero_cap作业38237164结果仍待本地核查。时序/OU/总线负载为演示假设，不能替代真实速率、熵或PPA；下方120.80µW/450MHz/16bit仍为另一路历史宏预算。源包/证据保留在独立模拟目录，未作为LLM仓库代码发布。

双流误差追加诊断见Issue30公开结果目录 `ERROR_DIAGNOSIS_ZH.md`。已有47项的T4096精确双流x概率层均值5.3492%、z0.8255%；T256/4096最大z裁剪约0.000964%/0.001767%，不支持大面积饱和是当前主因。在同一固定输入/尺度下，独立权重流增加非负条件方差；经SwiGLU和多层传播的主导位置仍待消融。DS-CIM使用加128偏移、128粒度FP8对齐、优化PRNG/seed及SRR，LLM为T256误差pattern注入和六任务准确率，不能等同本项目IID逐连接短测，也不能认为加SRR就会比现有精确计数更准。

三种服务必须分别命名：

- 原始均匀随机字：物理TRNG或本地PRNG，供数字比较器/CDF/地址抽样。
- 可调概率p-bit：根据驱动I输出0/1，典型 `P(1)=sigmoid(2I)`；直接使用器件tanh/ sigmoid响应。
- 耦合p-bit网络：如Ising类别竞争，涉及状态、反馈、更新和相关采样。

任意幅度概率p若直接用tanh器件，需要对应驱动反变换或经过其他编码；把v直接接到tanh不等于得到 `p=|v|/S`。数字随机字比较与物理p-bit一次状态更新不能共用同一成本标签。

已给物理源参数：120.80µW、450MHz、每拍16原始bit。由此 `Ebit=P/(f·16)=16.7778fJ/bit`。这是原始输出预算；没有自动包含比较、分发、网络反馈和读出。固定模块仅使用部分输出时，总功率不一定按用到的bit数线性缩小。

当前随机源层次：根熵源/种子服务→本地子PRNG→邻近算子；可配置重播种周期、每tile/每请求更新和分发。FFN本地A8、64路共享已接入TLM，输入侧概率寄存器副本可以去除，但比较器、必要激活/概率数据和流状态仍存在。权重侧暂按原方案，不能把输入随机数减少64倍说成整机省64倍。

v2具体默认是32位PRNG状态输出8位字，每新输入tile派生子种子、输出波重放同输入流，根按需约每1秒刷新256调理bit；并非每拍都需要物理熵重播种。SHAKE域分离属于软件种子参考，不是已实现的免费硬件SHAKE。Attention消费者保留本地/层次服务；Ising宏内随机成本封装一次，不能重复计费。

共享一个随机数到多个通道会制造相关性；同一乘积的两侧不可随意共用同一个阈值，否则乘积概率可能变成min型而非pA·pW。可以用两路独立物理随机字，或经验证时间独立的新随机字交替供两侧。比较器/区域映射控制相关性，不等于必须使用特定随机序列。

分层/低差异/确定性枚举作为对照单独标注：随机分层是在固定区间覆盖上加抖动，不能称完全IID；256码值范围并不意味着256次IID必然覆盖全部值，更不保证二维乘积的联合频率精确。延长流增加频率分辨率，不消除偏置或系统碰撞误差。

## 7 Attention路线与容易混淆的地方

| 方案 | QK/候选 | 概率或采样 | V阶段 |
|---|---|---|---|
| 原版 | 全部QK | 准确Softmax | 准确PV |
| PV采样 | 仍全部QK | 准确Softmax后类别抽样 | 只读所需V，按重复次数累加/平均 |
| 筛选后准确 | 摘要筛块，再计算候选QK | 候选内准确Softmax | 候选准确PV |
| 筛选加PV | 同上 | 候选内Softmax后采样 | 只读采样V |
| Ising＋V选择 | 仍需score；可先筛选减少维数 | score驱动类别竞争，含预热/更新/有效样本问题 | 读出类别后V选择累加 |
| 随机Q/K投影 | q_proj/k_proj静态权重随机化 | QK动态点积仍准确，后接对应方案 | 按配置 |

max4块筛选：64位置为一块，4个子块均值摘要与q点积，取最大分数，标准化/校准后sigmoid，Bernoulli保留；首块和近块强制保留。**这不是多步Ising退火**。固定预算修复含排序/补齐成本，也不是免费输出固定K。

Ising稠密互斥耦合可在数学上用总激活数广播实现等价局部场；物理时延、异步一致性、广播线、更新吞吐及混合时间仍需设计，不能据此宣称互连代价完全相同或为零。v4把内部细节暂抽象为宏模块，默认理想索引轨迹不验证物理网络平衡。

Qwen GQA每KV头对应7个Q头。各头候选K的并集可能很大，所以“每Q头筛30%”不等于物理K读取30%。V可按实际采样位置去重，仍需按KV组和burst统计；逻辑项数、唯一索引数、物理DRAM字节数分开。Llama7B的MHA没有相同GQA并集结构，但也有burst、重复和布局成本。

PV采样采用比例预算，当前参考为S/L=1/16：2K约128，8K约512；历史固定512保留作历史对照。`counts@V`可以是软件数值模拟，不能据此生成仍读全部V的稀疏硬件事务。采样去重/排序、burst合并、GQA复用与缓存应进入调度。

### 7.1 本地PV v6纠错结果

来源：`architecture_tlm/PV_STREAM_V6_RESULTS_ZH_20261016.txt`、`PV_ENERGY_AND_ISING_AUDIT_ZH_20261016.txt`。v6采用systematic偏移、前缀计数、KV组V并集、广播和最多32个64B请求在途，修正旧逐样本CDF和逐地址DMA排空的串行化；**没有集成筛选或Ising，也不是SANTA CUDA内核原样复刻**。

| DRAMSys情景 | 2K/128采样 | 8K/512采样 |
|---|---:|---:|
| 准确PV阶段→v6 PV阶段 | 3.405→2.756 ms/token | 13.600→10.959 ms/token |
| v6物理V读量/完整V | 34.65% | 34.55% |
| 准确完整Attention→v6 | 7.074→7.036 ms/token | 28.271→28.083 ms/token |

约19%的PV局部加速不等于整个Attention或整机19%加速。第一遍QK/指数、预算和第二遍扫描抵消较多收益；该版新比例预算的质量仍需独立PPL。v6报告标为本地，不能自动称已发布workspace。

## 8 FFN硬件与片上存储

普通调度基准：gate/up可并行或共享引擎分块执行；得到对应g/u后做SiLU和乘积；再供down；残差保留高精度。流水化需要精确的数据依赖、tile就绪和队列容量，不能凭画出流水线就认为达到最优。

权重存储分三种边界：

1. 普通SRAM→读出→计算阵列：按所需带宽分bank/端口，计读能量和必要短暂保持；不默认存在零成本全矩阵并行读。
2. SRAM/计算邻近：增加本地复用、比较器或小阵列，仍要清楚哪部分是库宏、哪部分是标准单元。
3. 定制数字CIM：存储单元或读出路径参与比较/乘法/归约，需要定制电路、寄生和接口验证；普通SRAM宏不能直接套DS-CIM全部峰值。

早期64输入×单输出小核PT，不等于64×64并行阵列；旧权重DFF、P12、T4096、100MHz、特定PVT和活动模式外推存在边界。应比较同工艺、同工作负载、同质量、相近吞吐与存储条件下的确定定点/位串行/随机方案。

不存4096拍所有结果：每拍或每小批更新压缩状态/计数，末尾恢复；所需状态与fan-in、位平面、分组和计数范围有关。缓存B拍可能减少大累加器切换，也增加局部计数器、控制和寄存器活动，必须实测PPA。

### 8.1 已有PPA应保留的负面结果

| 同一批/模式对照 | 约50%活动的能量/帧 | 含义 |
|---|---:|---|
| 37981139精确树→CSA | 25.893→45.430 nJ | 当前CSA映射更费能，面积也增加；不证明所有压缩器均无用 |
| 38015538 G1/B1→G1/B8 | 52.595→58.030 nJ | 当前无ICG缓存实现增加10.33%总能量 |
| 38015538 G2/B1、G4/B1、G8/B1 | 50.322、47.186、45.351 nJ | 普通有损OR，不能当等精度收益 |

它们的电路边界不同，不能跨批次直接排名。详细汇总本地 `sc_architecture_power_comparison_20261014/00_先看这里_架构功耗对比.txt`。

Q10 SwiGLU后处理另有100MHz单通道4级流水、II=1的工艺仿真：TT active约5.565～6.711pJ/结果，SS约4.486～5.352pJ；面积TT 0.00866412mm²、SS 0.00946620mm²。输入范围/活动模式影响能量；这不是布局后或真实模型激活测量，尚未自动接入已发布TLM。来源见第11节。

## 9 总体TLM、内存调度和功耗模型

| 层次 | 当前实现/入口 | 估计范围 |
|---|---|---|
| 系统计算调度 | `architecture_tlm/system_decode.py`、`system_decode_local_shared_v2.py` | 层/tile依赖、算子宏成本、等待、双缓冲；Python LT模型 |
| Attention v3/v4 | `attention_tlm_v3.py`、`screen_ising_tlm_v4.py`、`ising_macro_v4.py` | 稀疏地址、候选、V读取、显式更新或Ising宏参数 |
| 随机源 | `rng_hierarchy.py`、`rng_local_shared_v2.py` | 供给/分发、种子、共享、吞吐与能量；具体后端由配置决定 |
| SRAM | `sram_cacti_calibration_v1.py`、`cacti_memory.py` | 已有宏查库，其它尺寸用校准探索估计；bank/端口限制需调度 |
| 外存 | `architecture_tlm/dramsys/` | 实际DRAMSys SystemC/TLM事务后端；默认Link结果不等于已跑DRAMSys |
| DRAM功耗 | DRAMPower + memory spec/电流参数/电源策略 | ACT/PRE/RD/WR/刷新、后台、低功耗与接口；输入profile必须核验 |
| 映射探索 | `mapping_decode.py`、ZigZag相关脚本 | 受限定资源/映射空间搜索；不是全架构全局最优证明 |

SRAM已有55nm工艺SS/TT资料，CACTI采用多配置校准与独立宏验证；面积不应只按最小宏颗数机械放大。已有宏参数优先直接使用，未见尺寸给拟合误差；写能量等不确定项保留区间。库本体不得上传。

校准v1为A～F六种几何拟合、H独立验证、SS/TT分别；H验证面积误差约15%、内部读能量约9.3%、内部写能量64%～73%，因此不能称全指标校准到10%。F=4096×128宏64KiB、面积0.31216331mm²，SS最小周期约11ns；当前探索先取80MHz SRAM与100MHz计算核，CDC/读出实现未闭合。

Qwen本地v5探索起点为1MiB统一16bank、1RW、16B交织及16GB/s互连上限；有462个Link初筛点和后续详细情景，不是最终最优SRAM规模。Llama独立TLM使用8MiB等不同配置，不能机械复用1MiB结论。

DRAMPower不是无条件正确的常数表：与具体DRAM电压/IDD、VPP、接口及低功耗状态定义有关。历史PV读取减少而DRAM能量上升曾涉及VPP参数问题；修订profile与旧trace重新计价必须保留版本，不能静默重写旧结论。DRAM低功耗收益还取决于可进入空闲的持续时间、进入/唤醒和再激活。

Issue5已引入Micron厂家完整core电流限值新情景。旧统计重计价后，PV core能量仍比准确Attention高约0.566/2.340mJ/token（2K/8K），碎片化空闲减少长SREF区间仍可能增能。此前置零VPP仅是因果诊断，不能当最终校准。新Llama TLM显式使用新profile；I/O/PHY仍有未标定部分。

系统比较输出至少包括时间/token、J/token、平均功率、面积分解、SRAM/DRAM字节、采样/RNG/计算/等待占比。`E=P·t`；低功率但更慢不等于低能量。GPU平均功率、GPU J/token、ASIC估计J/token及算术节省比例分开报告。

尚未证明全部调度最优：片上bank仲裁、多DMA/回压、队列容量、NoC/时钟/CTS、真实源相关、Ising混合和prefill/decode分别建模仍有缺口。不能把未标定项置零来宣称整机千倍。

## 10 质量和硬件结果的证据口径

| 结果 | 数值/含义 | 来源与边界 |
|---|---|---|
| Qwen BF16完整WT2 | 11.652735 | `results/base_bf16/`；必须保持模型/tokenizer/语料/window/stride一致 |
| 原FFN＋PV采样 | 11.717755±0.002673 | 3 seeds，完整WT2；历史采样预算见原配置，不能与新比例预算自动视同 |
| Qwen A8共享64固定W | T4096 12.4535±0.0057 | 第5节；准确输入联合计数，准确Attention |
| Qwen A8共享64双随机W | T4096 14.1483±0.0132 | 第5节；权重残差Gaussian参考，非完整精确分布验证 |
| Llama2 BF16完整WT2 | 2K 4.979503；4K 4.895831 | `llama2/results/`及Issue14；不能与Qwen数字比较质量 |
| Llama2固定W8+A8，无采样 | 5.038305 | Issue19已合并阶段；准确SiLU，原Attention |
| Llama2分层采样128/64 | 5.308904±0.001642 / 6.758371±0.008464 | Issue19阶段，三种子；不是纯IID |
| Llama2 IID256 | 6.256753±0.005911 | Issue19阶段，三种子；其余配置以最新结果为准 |

完整WT2按目标token总NLL合并后取exp；不能平均窗口PPL。历史后缀指标是2K的32段×128目标、8K的16段×128目标等，须看各自protocol。固定前缀/探针、合成trace、RTL功能、DC/PT、器件测量各用原名称。

代码、模型revision、tokenizer、train/test文本、配置、种子、精度、采样、共享和环境均需版本和SHA256。WikiText parquet空行恢复为一个空格加LF，直接普通newline join可能破坏历史语料hash。长轨迹、权重、数据和原始PT产物留约定共享存储，Git提交索引及manifest。

Qwen正式test raw SHA256为 `173c87a53759e0201f33e0ccf978e510c2042d7f2cb78229d9a50d79b9e7dd08`，旧完整输入token hash为 `8d41d21825bb0e103dc63337727daf4b51c631cacec5937f014b119ae209081e`。本地 `pbit_llm/data/wikitext-2/wiki.test.raw`只274432 bytes、SHA `d2eaaf4cc05caaa66707285cb34c0c8aa944de4843f9f2f40fed4c6aabb1b332`，**不符合正式完整语料，不能直接拿它复现上述PPL**。本次未改写它。

### 10.1 Qwen3.5和Llama TLM的独立边界

Qwen3.5完整2K WT2原版15.661098；动态随机FFN＋PV为15.923481；再加18层DeltaNet out/z/QKV投影联合为16.124398（3 seeds），相对原版约+2.958%。固定投影替换仍保留卷积、门/状态更新、归一化等；状态每token只递推一次，不能在每个随机采样拍重复提交。已有25份投影PPL（其中4份8K），没有8K全部联合或完整DeltaNet TLM。模型revision `2fc06364715b967f1860aea9cf38778875588b17`。

该DeltaNet每层16头×128×128的FP32状态约1MiB，18层共18MiB/序列。固定投影占所列DeltaNet MAC约92.84%，但不能据此忽略状态存储/读写；其状态路径没有普通Softmax/PV可直接套用。

LLaMA-1当前标准82项TLM，Llama2为116项，涵盖Link/DRAMSys和多上下文；算法联合质量需另看对应实验。Llama2当前2K筛选PV在同SC FFN情景下整机能量约降2.16%，但相对数字W8 TLM仍约高219%，不是GPU能耗比较。它使用少量真实decode QK捕获，不是全语料筛选质量验证；Ising仍有IID oracle边界。

### 10.2 新器件与随机架构质量指标核查 Issue51

2026-10-19，独立文献任务Issue51修正此前“PPL增幅5%以内较好”的解释：它只能是本项目自定工程预算，不是DAC或体系结构会议统一门槛。报告与14项原文表值复算在[质量指标报告](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/task/51-emerging-quality/architecture_tlm/EMERGING_LLM_QUALITY_METRICS_ZH_20261019.md)及同目录EVIDENCE JSON；用户master_report目录有正文副本。

- MICRO2025 Kelle Table2：Llama2-7B WT2 FP165.47→5.74（+4.94%）；13B4.88→5.62（+15.16%）；7B PG1910.51→12.59（+19.79%）。这是W8A16/KV淘汰/eDRAM retention等整套方案损失，不是单独器件误差，也不是发表容忍线。
- DATE2026 DS-CIM：LLaMA7B FP8六任务平均66.0%，DS-CIM1/2为62.6%/58.8%，即损失3.4/7.2个百分点，不能称PPL上涨3.4%/7.2%；质量表使用T256，不与短流宏峰值混配。
- DAC2025 UniCAIM用LongChat问答F1；DAC2026 CQ-CiM用检索指标且LLM保持FP16；DATE2026光学PCM SCARLET用下一token准确率而非PPL。指标不同来自应用/验证范围，不证明新器件可以自动忽略生成质量。
- 新器件另需验证噪声、漂移、故障与校准，但局部NMSE/ENOB不能代替完整模型。我们保留BF16→匹配确定性量化→有限随机/器件路径三层参考，并报告逐任务、FFN/Attention/联合与质量匹配能量/时延曲线。
- VQT-CiM、HEIRS、DBC的可核质量表全文本轮仍缺，不引用二手精度或所谓5%阈值。报告没有新模型/PPL/RTL/TLM/PPA/服务器实验，不改变Issue46/48/50。


补充入口：[论文与任务指标对照](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/task/51-paper-task-map/architecture_tlm/LLM_PAPER_TASK_METRIC_MAP_ZH_20261019.md)，含11篇论文总表、任务解释、GLUE/AFM协议与未明确口径；用户副本在pbit_llm_master_report_20261012/LLM_PAPER_TASK_METRIC_MAP_ZH_20261019.md。原报告PR53已合并856105b，原备忘录补丁PR54已合并e0abc39；任务对照PR56已实际合并`fdceb386d9abe993f494ec09945ef8da35863bb1`；备忘录补丁PR57已合入任务28分支`d3861072ff88dbc4e66f2a7844eed4f8ec97245b`，随PR29交付。无新模型或硬件实验。

## 11 重要文件与成果位置

正式仓库内相对路径以实际任务分支为准；未合并PR的文件不要去旧main找。下列本地路径均相对 `C:/Users/86134/Documents/a_P_BIT/`。

| 主题 | 稳定入口 |
|---|---|
| 本备忘录 | 本地根 `PROJECT_MEMORY_ZH.md`；仓库根同名文件；AGENTS有必读提示 |
| 当前TLM总索引 | 本地 `tmp/project-memory-issue28-20261018/architecture_tlm/WORKSPACE_LATEST_ZH.md`；仓库路径 `architecture_tlm/WORKSPACE_LATEST_ZH.md`，工作区集成分支；混合根同名路径不存在 |
| TLM需求/全局资料索引 | `pbit_llm_master_report_20261012/TLM_REQUIREMENTS_AND_FILE_INDEX_ZH_20261014.md` |
| 旧总报告/Word | `pbit_llm_master_report_20261012/PBIT_LLM_MASTER_REPORT_ZH.md`、`Qwen概率计算方案与能效估算总报告.docx`；日期较旧，需合看本备忘录 |
| P-DNN算法设计 | 仓库 `experiments/pdnn_ffn/P_DNN_FFN_DESIGN_ZH.md` |
| 双随机固定Sz | `pbit_sz_dual_ffn_20261014/README_ZH.md`、`results/RESULTS_ZH.txt` |
| A8共享64双流/固定W | `pbit_shared_rng_ffn_20261015/README_ZH.md`、`results/RESULTS_ZH.md` |
| 新精确双随机短测 | `tmp/qwen-dual-iid-public-issue30-20261018/qwen/results/dual_iid_exact_20261018/ANALYSIS_ZH.md`；Issue30/PR31，47项齐全；原始输入/逐case结果用ARTIFACT_INDEX和CALIBRATION_ARTIFACTS索引 |
| 新短流RTL/能量 | `tmp/qwen-short-stream-issue22-20261018/`；Issue22/PR25，未合并，尚无新PT或Qwen短流PPL |
| 小核心旧PT | `sc_weighted_rtl_20261011/`、`tmp/37962470/`；核对PVT、活动与排除项 |
| 分组OR＋缓存PT | `sc_grouped_or_cache_20261013/results_38015538/结果检查与功耗总结.txt` |
| SRAM权重存储版本 | `sc_weight_storage_or4_20261014.zip`；归档不作为原始工艺库公开 |
| SwiGLU后处理PT | `tmp/ffn-epilogue-ppa-20261017/architecture_tlm/results/ffn_epilogue_ppa100_38100634/RESULTS_ZH.txt` |
| 数制转换RTL | `format_conversion_rtl_20261016/README_ZH.txt`；功能验证与工艺表征分开 |
| SRAM实测/库资料摘要 | `architecture_tlm/SRAM_PT_CHARACTERIZATION_ANSWERS_ZH_20261016.txt`、`SRAM_CACTI_EXISTING_RESULTS_SS_TT_ZH_20261016.txt`及校准报告 |
| 文献清单 | `pbit_llm_master_report_20261012/PBIT_LLM_RECOMMENDED_READING_ZH_20261018.md`；Issue23/PR24 |
| 17篇文献总结 | `pbit_llm_master_report_20261012/PBIT_LLM_READING_SYNTHESIS_ZH_20261018.md`；仓库Issue26/PR27；用户补充PDF后17项主文均已读 |
| Qwen3.5实验总入口 | `qwen35_publish_20261013/experiments/qwen35_20261013/README_ZH.md`，独立历史发布包 |
| 物理随机矩阵新文献 | `tmp/physical_rng_matmul_20261018/agent_a/NOTES_ZH.md`、`agent_b/notes.md`；尚未并入17篇原报告 |
| 远程登录材料 | 原有本机SSH配置/远程说明保持本地；备忘录不复制认证内容，恢复时使用原路径与任务handoff |

## 12 远端任务与交接索引

### 12.0 2026-10-20 第三轮7项PR审核与实际合并

- 用户授权继续审核补全结果及新PR。PR69 bc9f96d、PR71 b5e04f8、PR67 e96e54d、PR72 650c6b2、PR52 3b74375、PR49 18b887b已合入集成；PR62先入PR52任务分支992c693，再由PR52实际进入集成，不误报子PR最初的目标。
- Issue50完整2430/2461现有25项已补发qwen/results/joint_full_wt2_20261020；只有3项B4T16联合授权取消。三seed B4T32 S128/256/512完整12.423820/12.274153/12.207062，对matched BF16 11.652118；S256/512无同预算原FFN full控制，交互不可计算。PR49仅S128三seed代表性完整确认，其他S仍后缀。
- PR62的39项结果/逐题统计、PR67两模型各19965题和完整WT2、PR71 v1论文/数学、PR69恢复归档分别核验通过。Issue48/50/59/65/68/70已按各自范围关闭；Issue28继续维护。无新GPU、训练或PPA，无快照改写。Projects本轮GraphQL实测仍缺read:project，仓库admin/push及7次合并已成功，不能混为仓库权限不足。
- 完整审核与原生head/base/merge-parent回执位于work/jieruiz/55/round3，交付归Issue55。本轮仅一个稀疏review目录，原件/脚本/独有资料按SHA归档至project_archives/pr_review_issue55_20261020后回收本轮helper；长期canonical/root副本保持同字节。canonical先前12行未提交清理增量先保留原字节与patch，且在新文档中完整保留，不reset/stash或覆盖其他成员。

### 12.1 2026-10-19 待审PR审核与实际合并回执

用户授权按最新GitHub内容审核并合并。下表为Issue55本批实际回执；后面的旧索引保留为历史快照，不能据其“待审”文字撤销已发生的合并。PR47由此前单独审核合并。

| PR | 实际目标分支 | 合并提交 |
|---|---|---|
| #2 | `main` | `35db82089ea6b76f5fcf76458c37d8ee59d4c7c9` |
| #4 | `pbit-tlm-attention-details-20261016` | `7bf80c97b7a77050660e46f6b3a12d03039b4725` |
| #6 | `pbit-tlm-attention-details-20261016` | `92234f3ffc1d91a301e2da8a635ed54e29c408ac` |
| #8 | `pbit-tlm-attention-details-20261016` | `6e94bf15cb1a3523274f80a26f36e75604e3c8f8` |
| #10 | `pbit-tlm-attention-details-20261016` | `fe9238ebb2b4e19d9ffa03e5b75eaa210cdab48e` |
| #11 | `task/7-ffn-cim-scheduling` | `89c5725064bfa1827e28c6566e3899dbc5cb1f9e` |
| #24 | `pbit-tlm-attention-details-20261016` | `2ede802c3725cceca50eb3bccfdb33653c3fcde5` |
| #25 | `pbit-tlm-attention-details-20261016` | `c0ca336657757967e9c0512da17453e1f3181586` |
| #27 | `pbit-tlm-attention-details-20261016` | `1ec98aee2f28bd4f21f48bf6d31c95787e430e9b` |
| #29 | `pbit-tlm-attention-details-20261016` | `20a2565e0465846891c0a4ad0976e4395e7d3ecf` |
| #40 | `pbit-tlm-attention-details-20261016` | `e4798f70cb57a864cbbfeb20b83674e1dadc1c4b` |
| #41 | `pbit-tlm-attention-details-20261016` | `82229d54750d65b925f72050f0d8478bc2013c90` |
| #42 | `pbit-tlm-attention-details-20261016` | `ed0c7a4e8e9546ec89895135efff36aa8a00d568` |
| #43 | `pbit-tlm-attention-details-20261016` | `202eac13d17d88cf049330a620bec844b4c4037d` |
| #44 | `pbit-tlm-attention-details-20261016` | `46c12e5f6c1c07751272871abb360c35735e8d59` |
| #45 | `task/36-digital-attention-reference` | `1b0af7604037ce8a772063bd9583ce9e1f96f0e5` |
| #53 | `pbit-tlm-attention-details-20261016` | `856105beaefaee307ba1a9b1972aa61d8f82ba59` |
| #54 | `task/28-project-memory` | `e0abc39fb4fb83510fabb5c6ef22dcc8e3c39a6b` |
| #56 | `pbit-tlm-attention-details-20261016` | `fdceb386d9abe993f494ec09945ef8da35863bb1` |
| #57 | `task/28-project-memory` | `d3861072ff88dbc4e66f2a7844eed4f8ec97245b` |

PR29科学正文已审核并实际合并`20a2565e0465846891c0a4ad0976e4395e7d3ecf`；源head为`d3861072ff88dbc4e66f2a7844eed4f8ec97245b`，刷新至集成基线`fdceb386d9abe993f494ec09945ef8da35863bb1`后交付。PR29实际合并回执及本批完整报告见[Issue55](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/55)。#11随#8、#45随#44的内容已进入集成；#54与#57已随PR29进入集成；依赖合并与最终进入集成仍分别保留回执。#2的实际目标仍为main，其余正式科研集成位于TLM分支。

#49（`8dd1b06aa465b3bdaaed60ae321c5362983ae169`）与#52（最后补审资料为`e3c5e957c3769b5fc6867b42a52facace647a83b`）保留draft：完整确认/质量验收未完成，不替作者标为ready，不启动重复作业。后续恢复须重新读取实时head及Slurm。

Issue7（实际TT/SS DC/VCS/PT）、Issue22（短流硬件/质量后续）、Issue37（最终质量与硬件验收）、Issue28（持续记忆维护）继续开放；48/50随草稿工作继续。其他本批有限交付的Issue按实际验收回执处理。仓库合并权限可用；Projects看板的read:project仍待同步，不把看板授权范围与仓库写权限混为一谈。

本轮独立审核未启动新GPU/服务器/许可EDA实验。硬件TLM的13项测试、4组数值重放和84源/结果blob保留通过；最终科学集成`e4798f70cb57a864cbbfeb20b83674e1dadc1c4b`的102项CPU测试为101通过/1个Windows符号链接权限跳过，另1协议fixture通过，43/44/45/40汇总复现。后续文献/备忘录交付须核对科学blob未变。

本批有限范围Issue3/5/9/23/26/33/35/36/39/51已实际验收关闭；Issue7/22/28/37保留开放并更新剩余事项。22项审核报告和20份实际合并回执由Issue55交付，详见`work/jieruiz/55/REVIEW_ZH.md`及机器可读记录。

收尾补充PR58已审核并合入`88764ec8f6f00ed05f4ab337902bd23ad08cc4a8`：采用B4/T32/K32及B2T32/B4T16/B4T64行为参考，入口`architecture_tlm/ffn_stratified_reference/`直接复用47四个锁定核心。原TLM/PPA默认和Attention-only原FFN对照不变；25项原核心测试、4profile输出/RNG等价通过，Python3.8临时Path兼容shim限制见Issue55证据。含58后本批共23项，21实际合并、49/52仍draft。

2026-10-19新增Issue59/PR62代表任务准确率，见第5.8节及`tmp/qwen-task-accuracy-issue59-20261019/work/jieruiz/59/HANDOFF.md`。PR62依赖PR52、未合并；075574源的2475/2476已READY通过，正式39项于09:13:52Z提交2477/2478/2479/2480、自动汇总2481；09:19Z为三项原BF16完成、36替换项运行/排队。记忆追加PR64已推送待审、未合并；旧2474门禁诊断保留。该条是新任务时点快照，不改写下方早期状态或原实验原件。

2026-10-19第二轮（Issue55，用户要求继续）：审查5项，PR63研究设计已合并`4f2d953395a7335e0f15b0546c91cdac73c81169`、PR64记忆已合并`679fd269ecaa4883bd79619d2f39d6ade2a7daca`；49/52同旧head仍draft，62新draft公开11/39且依赖未合PR52，均保留。174数学检查与30评分/collector CPU夹具检查通过，不等于训练或新0.5B/GPU验证。Issue61按研究范围关闭、28持续维护，详见`work/jieruiz/55/round2/REVIEW_ZH.md`。上方PR64“待审/待推送”与任务进度保留为旧时点，最新合并状态由本条及Issue55回执覆盖。

2026-10-20：Issue59/PR62的39/39任务全部完成，完整报告已推送cebba22dadb78440b210b3ec237b5e2d16c77030，见第5.8.2节及qwen/results/task_accuracy_20261019/。逐题SHA/指标重放及15项collector测试通过；本人队列核验为空。PR62仍未合并、依赖PR52；旧3/39与11/39不是当前状态。此次Issue28仅同步备忘录，无新GPU或PPA。

### 12.2 早期远端状态快照（原文保留）

2026-10-18通过GitHub API核实，登录 `jieruiz`；有仓库admin/push权限。目标仍按项目审查流程用PR交付，不把权限等同于所有PR已批准。

| Issue / PR | 核实时状态 | 接续范围 |
|---|---|---|
| 1 / 2 | open / 未合并 | 工作区治理；保留原实验复现规则 |
| 3 / 4 | open / 未合并 | 架构可用性与调度审计 |
| 5 / 6 | open / 未合并 | DRAMPower参数、DS-CIM权重实现 |
| 7 / 8、11 | open / 未合并 | FFN调度、SwiGLU RTL及PPA |
| 9 / 10 | open / 未合并 | 筛选K读取并集与burst放大 |
| 12 / 13 | closed / 已合并07d0338 | LLaMA-1当前TLM |
| 14 / 15 | closed / 已合并7a50636 | Llama2 BF16基线与116项TLM |
| 16 / 17、18 | closed / 已合并 | qwen/llama1/llama2三目录 |
| 19 / 20、21 | Issue仍open；阶段PR已合并40ea9f1、3553996 | Llama2全32FFN精度分解；剩余作业不因阶段合并而完成 |
| 22 / 25 | open / 未合并 | Qwen短流A8共享64 RTL与条件能量 |
| 23 / 24 | open / 未合并 | 论文推荐清单 |
| 26 / 27 | open / 未合并 | 17篇原文总结；当前报告SHA为41d5118da9d0b259e1ee54453362251ed020e5f2e06baa6a7179bf07844c7970 |
| 28 / 29 | open / 已推送待审、未合并 | 本备忘录、恢复入口和状态索引 |
| 30 / 31 | closed / 已合并d589f152 | 精确短流参考47输出，完整精确随机WT2未做 |
| 32 / 34、38 | closed / 已合并5b71d4e、c1555ae | 范围49输出＋真实分布/项目入口，完整随机/裁剪WT2未做 |
| 39 / 40 | 实验完成，PR待审未合并 | 裁剪/固定PoT范围65替换；独立目录tmp/qwen-ffn-clipping-issue39-20261019 |
| 46 / 47 | closed / 已合并bef83e54 | 固定W8多档＋分层；145输出/154原件，含67新完整配置，目录tmp/qwen-fixedw-multiscale-20261019 |
| 50 / 52 | 34后缀主项＋12诊断＋15次数扫描完成；完整2430/2461运行，PR草稿未合并 | 三种FFN联合及固定B4T32的S32..1024 PPL；见§5.7/5.7.1和tmp/qwen-joint-issue50-20261019 |
| 51 / 53、56 | 原报告PR53已合并856105b；任务对照PR56待审未合并 | 质量报告与论文任务/指标对照；补充目录tmp/paper-task-map-issue51-20261019；原备忘录PR54已合并e0abc39 |
| 33 / 待核验 | open，负责人amlink1219 | Attention价值核查与实验计划；与FFN Issue32分开，不接管他人状态 |

Issue19此前交接记录的Slurm数组为2084，8/9等子项尚在运行或排队；这只是此前STATUS快照，不是本次查询实时队列。继续前必须查当前squeue与原manifest，不取消/重交已有作业。精确入口：`tmp/llama2-ffn-precision-issue19-20261018/work/jieruiz/19/HANDOFF.md`及该目录个人STATUS。

Issue30开始前另查本人squeue为空；这说明旧作业当时不在队列，不代表Issue19剩余结果已经收回/核验/合并。其余结果仍需原任务collector及manifest确认。

个人进度统一在每个任务checkout的 `progress/jieruiz/STATUS.md`，辅助资料在 `work/jieruiz/<Issue>/`。同一人多个任务checkout可能保留不同时间的STATUS，必须结合远端提交与本节导航，不能把最后读到的一份当全项目唯一最新。

## 13 已纠正的认识与不得重复的错误

- “随机计算必须用特殊PRNG序列”不成立。自然随机可以正确计算，特殊覆盖主要影响短流方差。
- “有精确并行计数就不可能省面积/能量”不成立；已有物理TRNG＋AND＋精确计数研究，但其任务、精度和基线不同。
- “随机流长度256就有8位准确度”不成立：输出网格分辨率和估计误差不同；独立随机频数存在方差。
- “OR计数天然等于加法”不成立；普通OR有碰撞偏差，互斥重映射是另一编码。
- “PV稀疏只减少乘法，KV可以仍全读”不符合本项目稀疏数据流目标；真实索引gather/去重/突发必须实现。
- “操作少了整机一定更省电”不成立；后台时间、DRAM电源profile、布局放大和重复收费要核查。
- “Ising参考模拟时间可直接当芯片周期”不成立；有效独立样本、更新/混合和物理采样频率需标定。
- “普通SRAM＋寄存器就是定制CIM”不成立；读端口、保持、比较与局部计算边界必须画清。
- “层数、模型和评估协议差不多可以直接比较”不成立；Qwen与Llama、20/24/32替换、后缀与全量、动态与固定尺度都需明确。

已有直接物理随机证据：APL2021 SOT-TRNG ANN采用输入/权重随机流、AND与并行计数；256拍45nm综合结果有面积/低功率及能量收益，1024拍能量优势消失；基线为FP32，非INT8强基线，器件rawbit实测而全ANN是仿真。DATE2017 VC-MTJ点积/FIR报告模型级能量收益；SFQ2024有低温矩阵实物功能。不要把这些倍率直接套到Qwen。

## 14 后续维护与恢复流程

1. 进入本项目时，先读AGENTS和本文件第0、1、12节，再读当前任务Issue/PR及HANDOFF；核对实际Git根、分支、diff、remote、GitHub身份和远端最新SHA。
2. 根据主题读第3～10节及原证据，不重复把曾失败/已完成的实验当新任务。发现资料冲突，以原manifest、准确版本和最新验证为准，记录替代关系，不覆盖旧成果。
3. 每次有重要结果、方案改变、任务提交/合并或阻塞，更新本文件对应章节与版本记录，并维护STATUS；保留时间、协议、证据链接和SHA。
4. 正式仓库根文件是版本化交付；本地 `a_P_BIT/PROJECT_MEMORY_ZH.md`为同字节阅读副本。发布后校验两者与Git blob一致，避免两份独立编辑漂移。
5. AGENTS入口能让在本项目目录工作的后续Codex按规则重新读取；这不是模型对所有新会话的永久内在记忆。若新会话不在此工作区或没有文件访问，用户需提供工作区或此文件路径。
6. 凭据、SSH内容、token、工艺库、受限论文PDF不进入备忘录或公开Git；只保存安全路径/来源及必要摘要。

## 15 版本记录

- 2026-10-18，Issue28：建立覆盖历史对话的首版主题备忘录，核实workspace身份/分支/任务状态，加入双随机既有结果、物理随机适用条件与后续精确验证缺口。文档任务没有产生新PPL、RTL/PT、训练或TLM仿真结果。
- 2026-10-18，Issue30/PR31：首版备忘录交付后完成47项精确短流风险检查，补充第5.1节和结果索引；该模型测试属于独立任务，不混称Issue28进行了模型实验。

- 2026-10-18，Issue32/PR34：独立A/W范围对照、逐投影理论诊断及128/2048token确认共49输出完成；自然IID低T明显改善，保留动态范围成本及前缀协议边界。

- 2026-10-19，用户授权合并：PR31/34/38均已合入TLM，Issue30/32已关闭；补充8192train-token真实直方图、极值能量与裁剪口径，保留未跑裁剪PPL/未测PPA边界。

- 2026-10-19，PR47独立审核与用户授权合并：25项核测试、145计分/154原件、98次执行blob和60次发布blob检查通过；合并提交`bef83e54b9da0081c51f393044d2156ce11a34b9`，两个父提交及与审核head同树均核实，Issue46于15:46:38（北京时间）按验收完成关闭。[审核记录](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/47#pullrequestreview-5568295057)及[合并回执](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/46#issuecomment-6262300688)已在线。GitHub集成403不等于仓库账号无权限；本机jieruiz已核实admin/push并成功合并。Projects仍缺read:project。没有新GPU推理或PPA，K>1仍为受控分层；PR29继续待审，不随PR47合并。

> 本轮合并阅读提示（2026-10-20）：以下保留Issue68/65原始交付时点记录。PR69已实际合并`bc9f96d73726a858f9bf9eb494c14b46c24f4279`；Issue65以文末“2026-10-20收齐”和完整结果已上传段为最新结果，覆盖早先六任务运行中及Draft状态快照。PR67在本提示生成时仍待合并，BF16及p-bit/PPA仍未验收。

## 2026-10-19 本地副本清理与生命周期规则（Issue68/PR69）

用户要求清理本地电脑项目文件，随后明确要求清除已结束任务的副本、以后不长期保留。接续Issue68、分支task/68-local-storage-cleanup、目录tmp/local-cleanup-issue68-20261019，PR69待审；本地已执行不等于已合并。

第一轮回收本人Issue55的17个PR刷新worktree及缓存/重复图，逻辑3.133GiB；第二轮回收42个已关闭任务/审核helper副本，逻辑7.377GiB，两轮合计10.510GiB、59个worktree。Git分支/对象库保留；42个额外恢复ref和非祖先helper的已验证增量bundle可恢复代码，440个未提交/ignored独有文件已本地压缩核SHA。第二轮恢复材料共约2.90MiB，位于project_archives/cleanup_20261019_round2；第一轮小归档仍在tmp/local_cleanup_20261019/recovery。原始模型、最优checkpoint、工艺资料、正式唯一结果和进行中任务保留；pr47-review-main因rayggxia的独有交接保留。

正式清单与恢复方法：maintenance/storage_cleanup_20261019/REPORT_ZH.md、ROUND2_REPORT_ZH.md、RECOVERY_INDEX.json及ROUND2_RECOVERY_INDEX.json，完整本地日志在tmp/local_cleanup_20261019。本备忘录此前记录的某些已关闭任务工作路径已回收；先按恢复索引重建原分支/HEAD并取出独有资料，不因目录不在而重复实验。正在进行的Issue7/19/22/28/50/59和当前68没有作为已结束目录清理。

根及仓库AGENTS.md已追加用户要求：恢复复用已有任务目录；实际并行才建立必要隔离worktree；只读审阅优先git show；新worktree先不检出、按需稀疏检出，避免每个helper复制大结果/事务轨迹；交付时归档独有资料并回收review/resolve/helper。本任务自身已稀疏检出maintenance/progress/work，其他成员设置不变。当前仅清理本地文件，未修改Windows pagefile或系统设置，没有新PPL/GPU/RTL/PT/TLM结果。项目文件与Windows虚拟内存文件分开处理。

本段从Issue28 canonical文件追加后同步到根阅读副本及Issue68 PR文件，保持同字节；发布状态以Issue68/PR69实时记录为准。canonical工作副本中的这一追加由PR69交付，后续先核实PR状态再同步，不重复编辑成另一份内容。

## Apple Sigmoid Attention 7B配对质量参考（Issue65，2026-10-19）

负责人amlink1219；独立目录workspace_projects/sa7。按用户指定DS-CIM表II确认BoolQ/PIQA/HellaSwag/WinoGrande/ARC-e/ARC-c，论文未固定所有harness细节，本次明确0-shot/0.4.8，不称复现其LLaMA数字。官方Apple两个step250000检查点和原SP已下载校验，服务器模型根/home/Weican_Chen/models/apple-sigmoid-attention-7b。SP32000词片，嵌入/输出32768；Gala原生AXLearn配置与Llama/Qwen不同。

方法/状态与索引见experiments/apple_sigmoid_7b_eval、results/apple_sigmoid_7b_eval_20261019和work/amlink1219/65/HANDOFF.md。BF16 GPU移植预检失败，未产生正式质量结果；先以未量化原始FP32权重和FP32计算建立高精度质量参考，分开列精度。当前运行状态须查实时Issue/作业，不能由本记录推断已经完成。没有p-bit采样或硬件PPA验收结论；不改Issue50/59的Qwen任务。

Issue65结果追加：原始FP32完整WT2 Softmax5.911825276082767、Sigmoid5.88607319951146，同317546计分token、2048/1024；CPU/GPU对齐及全量计分覆盖已核验。六任务仍运行于2542，PR67为Draft未合并；BF16移植失败另列，禁止称FP32软件结果为BF16或p-bit PPA。详见本任务结果与可执行交接。

Issue65于2026-10-20收齐：GPU2542原始终态COMPLETED/0:0，2543应用收尾无缺失；原始FP32两模型每模型完整六任务19,965题，raw acc均值Softmax63.692864%、Sigmoid64.823195%，PPL5.911825/5.886073。正式原件、模板、69项服务器索引及验证报告见results/apple_sigmoid_7b_eval_20261019。上传状态以PUBLICATION/PR67为准；BF16及p-bit/PPA未验证，不继承其结论。不重交已完成作业。

Issue65完整结果已上传011d46029772bb4b4e17811582a116907318ec46，PR67已转待评审、未合并，Issue65清单已同步。看板状态PENDING；精确发布回执见work/amlink1219/65/PUBLICATION.json。

## 2026-10-21 全局广播有限κ/伪异步验证（Issue78/PR79）

用户要求实际比较全同步、随机分块与原S64理想CTMC。独立task/78-ising-broadcast，目录tmp/ising-broadcast-issue78-20261021；数值源0c0d8978908e9232cb94b75ac301a8254f834645，分析344498a。公式E=κ*C*(C-1)/2-Σdelta*s，以最大logit为空参考；κ12/16在tanh输入中须除2。原FFN、准确前缀、24层scored decode；CPU Slurm2600/2601/2608已完成诊断/原BF16门禁/真实分数重放，2602数组18配置仍运行、2609结束后自动汇总，不重交。405合成/48真实重放及9合同通过。真实42行最大位置目标29.91%，全同步87.55%、随机块16约31.71%、块4约30.63%，κ12/16几乎相同；稀疏使能降低偏差但相关更强。128目标后缀BF1620.212326、原CTMC64三seed23.159115±0.418371；全同步目前两seed82.224259/129.479031，剩13项pending。不能把这当完整WT2、ASIC周期或2K全候选PPL（模型筛后最多512，2K仅合成压力）。来源qwen/results/ising_broadcast_20261021/、work/jieruiz/78/HANDOFF.md；PR79草稿已推送未合并，Issue78 open；原Issue73作业不动，Projects待权限。


### 2026-10-21 κ无穷硬抑制（Issue78续）

用户提出直接无限抑制。当前空参考编码允许C=0/1，更新规则为其他位`C-s_i>=1`时写0，否则sigmoid(delta)；唯一活跃位不得因自身被清除。随机单点精确转移验证保持Softmax；原CTMC本已有硬排斥。反馈可用any1/multi1两标志树归约和广播，不能因此把反馈时延计零或宣称可任意同步。Slurm2623以独立源2fefbb019b1b68369e7ed04932184e464fb99fa1完成42真实行×5调度×3seed配对重放，11合同通过。全同步/块64/16/4与κ16输出地址均100%相同，块64+1/8使能最小97.32%；全同步偏差不改善。这里只是分布重放、无新硬模式PPL或RTL/PT。结果DIAGNOSTICS_ZH.md及HARD_MANIFEST.json；私有捕获SHA2b6c5d851f761fc3d9749e02c9f438db6180afa4e17915f45a3d56ac8d7cb740。原18项PPL快照/任务不变，PR79仍草稿未合并。


### Issue78本轮最终运行/发布状态（2026-10-21）

18/18 CPU128目标PPL和2609自动汇总已完成、0失败，collect.py独立重放报告/汇总逐字节通过，26原件SHA索引。CTMC S64均值23.159115，块16κ12为22.621586、块16κ16为22.891973、全同步104.556286；不能把小样本块16较低视为普遍优越或完整WT2。Slurm2623硬无穷分布重放完成，暂无新增硬模式PPL。κ无穷与完整汇总在本地task/78分支已提交；本轮Git push因连接重置暂未完成，远端仍1eb01032，必须核验后补推，不能宣称这些新文件远端已完成。Issue78/PR79仍open/draft，Projects待权限；本任务无运行作业，不重交。


### Issue78少块数与多1冲突，2026-10-21

用户决定纯单1编码若增加等待就不继续，保留原空参考，重点少块数和块内并行。2624/2625的60项重放保留：512真实16/32块全收齐、2/4/8未齐；2K平坦32才齐，未做one-hot PPL。新源e52570d40d49013f11c6f3d3d16de9b20dfc9e3d实现不同规则：q_i=sigmoid(delta_i-m ln2)，独立全并行提议；单1接受、多1拒绝、全0以r=2^-m接受参考，拒绝后调m。证明每轮接受权重Cr*[1,exp(delta)]，任意拒绝历史选择m不改目标。可全局1逻辑块，属于直接类别拒绝采样，不是全同步Ising/Gibbs；无需旧burn/spacing，但器件独立性/响应精度仍待验。

Slurm2626完成19合同和18分布记录。S64三seed每地址提议均值：真实512候选2.223轮、2K平坦3.384、尖峰1.000；S2048分布TV接近同预算IID。无新PPL、有限8位概率或硬件PPA，不能用轮数当ASIC时钟。8位均匀比较器小概率/共享门限相关性是下一步限制；不能照搬FFN共享64。报告qwen/results/ising_broadcast_20261021/REJECTION_ZH.md和REJECTION_MANIFEST.json。旧编码/模型默认不变。网络恢复已补push至5e18cc5，之前“未推送”时点过时；本轮新结果发布以PR79最新head为准，仍草稿未合并。无本任务运行作业，不重交。


Issue78发布回执（2026-10-21 08:06 UTC）：科学head9b88a8da8d67450ae646372b2278deef33557889已推送workspace，one-hot两原件与rejection原件的GitHub blob字节SHA核验通过，详见work/jieruiz/78/REJECTION_PUBLICATION.json。PR79仍草稿未合并；此前“待上传/网络阻塞”已解除。无新模型PPL或PPA结论，不重交已完成CPU作业。


### Issue78偏移预设/固定/复用（2026-10-21）

用户建议一开始减近似公共值。CPU2628，源820ad7efa824b09482be52fe2df0db73bf1a70cf，19合同和144理想重放完成，保留cap失败。2K平坦S64从自适应0的3.384轮/地址，到预设11继续自适应3.227、固定11为2.663（理论期望2.717）。真实512预设2改善首地址3.770到2.833，但S64平均2.260对原2.223未提升；相同logits复用m再自适应2.217、固定2.322。固定0/2/11在部分真实行失败，尖峰固定11也失败；不推论所有固定值皆无用。复用仅重复相同logits，已有S64成本有索引，不是下一token验证。

固定/预设m需保留r=2^-m的零态校正；z_ref仍逐query计算，未验证以绝对常数替代最大参考。建议按层/头校准m0+允许修正，尚未标定部署。无新模型PPL/有限8位概率/PT/PPA；不把首地址加速当整帧或整机加速。报告qwen/results/ising_broadcast_20261021/OFFSET_ZH.md/manifest，分支PR79本轮发布以最新head为准，仍草稿未合并。无本任务运行作业，不重交。


Issue78偏移对照发布状态（2026-10-21 08:35 UTC）：本地科学head0455d0d6b0a863f0bf3136446d9d9c5f28139b9f，Git网络长时间无进度/低速超时，远端仍d6d0f321b6c5eee7c334b7bb0f1e3d070d299304；新OFFSET文件尚未远端完成。API已同步PR79说明及Issue78数字/限制/待上传，回执work/jieruiz/78/OFFSET_PUBLICATION.json。网络恢复普通push并核验blob再改发布状态，不重交已完成2628。


### Issue78分数到p-bit接口审计，2026-10-21

当前替换版Q/K与KV为BF16，但候选QK显式float()做bmm/缩放得FP32；新采样诊断转FP64，只是行为参考，不是已实现电压接口。建议先保留QK、只量化score/局部场，再独立研究Q/K INT8和INT32累加。Qwen d64的1/8可并入scale/移位。8位logit/DAC码不等于R8均匀概率阈值；后者会把约1/2K的小概率归零，不能沿用FFN R8共享64结论。物理响应须标定V0/Vs/尾概率与相关时间，数字路径须LUT+足够细概率比较。量化尺度要补偿温度，m ln2近似要与空态校正一致；mask须独立门控。2.22/3.38轮不含这些未标定接口成本。详见REJECTION_ZH.md新节与work/jieruiz/78/SCORE_INTERFACE_AUDIT.json。无新量化/PPL/PT/PPA；默认不改，新文档/前轮OFFSET发布以实际Git回执为准。


Issue78后续分支变更（2026-10-21）：并行审阅已将PR79合并a7a2c5b3cbc16390e30061329adfbebc835dc8b3（head310feea，08:51:06Z），原Issue78仍open。普通push遇非快进后已停止并核对，不强推。未发布OFFSET与本次score接口审计接续task/78-score-interface，同一任务目录内合入最新集成、保留评审manifest修复与其他成员成果。5份manifest归档Git blob SHA检查通过；无新数值实验或PPA。旧PR79未合并描述过时，新PR号待真实创建回执。


Issue78发布回执（2026-10-21 08:55 UTC）：后续分支task/78-score-interface已推送0d3dfa2fa107ea5925751cdb686cda089b414628，创建PR80（草稿未合并）；原PR79已合并a7a2c5b。旧OFFSET网络阻塞解除，原件远端blob SHA6a628a...核验通过；本次dtype/接口审计一并交付，见work/jieruiz/78/SCORE_INTERFACE_PUBLICATION.json。Issue78仍open、无新模型/量化/PPA作业，Projects待权限。


## 2026-10-21 Issue78 sigmoid驱动8位接口诊断

用户明确仅指sigmoid括号内a=(z−zref)−m ln2，而非Q/K INT8或R8概率阈值。PR79已合并a7a2c5b、PR80后续已合并e24414b；本次task/78-field-int8接续。CPU2630源757fb90完成25合同，24层2688行保存分数＋42行S64三seed真实驱动局部解析。a中位−8.70，5/95%−26.15/−4.70，负尾约−98。负幅度8位h1/8/范围−31.875~0，理想访问状态平均条件TV1.262%；signed8 h1/16范围−8~7.9375因饱和平均6.947%、最大51.475%。h1/16负幅度本批0.631%，但m14压力截断严重，不能直接外推；10位h1/16对照0.630%。均不是量化自适应完整轨迹/PPL或PPA；默认未改，原始capture私有。SOT SoftMax论文披露电流映射与平移/伸缩校准，未披露局部场INT8质量；其INT8/4图指输出概率。报告qwen/results/ising_broadcast_20261021/FIELD_INT8_ZH.md，manifest和work/jieruiz/78/FIELD_*含SHA、命令与新PR待发布状态。无运行作业、不重交2630，下一步独立校准＋模型PPL。
## 2026-10-21 第四轮PR审核与合并回执（Issue55）

PR77四条训练讨论稿、PR79广播/正确拒绝采样、PR75 Llama2任务阶段、追加PR80偏移与score接口均已实际合并。精确head/base/merge及独立证据见work/jieruiz/55/round4/REVIEW_ZH.md和receipts。旧时点的draft/未上传/未合并描述保留为历史，本节覆盖本轮发布状态。新报告本身通过后续PR交付，不计入4项成果。

PR75检查点2026-10-21 08:39:24Z：16/26完成（8旧+8修复），2运行、8排队；GPU2584已READY且8个真实7B pilot通过，旧“GPU修复未验证”过时。7原CPU测试+4独立tiny32层检查通过，打包前后前向及RNG逐位一致。仅按Issue73冻结实现/提交阶段验收，26项最终质量仍待收齐，未逐题独立重算所有官方指标。Issue73/既有回查继续，未来结果用同Issue新PR，不重交健康数组、不改快照。

PR79的18项CPU128目标后缀PPL已核，并非完整WT2；19当前合同与旧11重叠不相加。硬抑制/any-multi不修复同步偏差。正确拒绝采样依赖独立提议和零态校正，提议轮数不是物理时钟；尚无该采样器新模型PPL/有限位概率/RTL/PPA。发现并修复DIAGNOSTIC_MANIFEST中DIAGNOSTICS_ZH.md的派生SHA/大小，科学原件不改。

此前未发布的OFFSET/score接口现由PR80交付并独立审核：144条理想分布记录含cap失败，固定/预设偏移改善部分案例但非普遍收益；同logits复用不代表下一token。QK score为FP32、诊断FP64，8位驱动码不等于R8概率；接口建议尚未实现或量化验证。Issue78继续开放；不能把本次交付当完整模型或硬件验收。

PR77仅计划/文档验收，无训练已完成结论。Issue76由用户额外明确授权后已更新并关闭；未修改amlink1219个人STATUS。Issue28继续维护。备忘录canonical原有未提交增量先逐SHA归档并保留全部有序文本，HEAD保持原值，其工作文件与根阅读副本同步到本次发布文档。仅回收本轮本人稀疏review/helper，恢复索引project_archives/pr_review_issue55_20261021/RECOVERY_INDEX.json；执行状态查Issue55最终回执。


## 2026-10-21 Issue78 sigmoid驱动8位接口诊断

用户明确仅指sigmoid括号内a=(z−zref)−m ln2，而非Q/K INT8或R8概率阈值。PR79已合并a7a2c5b、PR80后续已合并e24414b；本次task/78-field-int8接续。CPU2630源757fb90完成25合同，24层2688行保存分数＋42行S64三seed真实驱动局部解析。a中位−8.70，5/95%−26.15/−4.70，负尾约−98。负幅度8位h1/8/范围−31.875~0，理想访问状态平均条件TV1.262%；signed8 h1/16范围−8~7.9375因饱和平均6.947%、最大51.475%。h1/16负幅度本批0.631%，但m14压力截断严重，不能直接外推；10位h1/16对照0.630%。均不是量化自适应完整轨迹/PPL或PPA；默认未改，原始capture私有。SOT SoftMax论文披露电流映射与平移/伸缩校准，未披露局部场INT8质量；其INT8/4图指输出概率。报告qwen/results/ising_broadcast_20261021/FIELD_INT8_ZH.md，manifest和work/jieruiz/78/FIELD_*含SHA、命令与新PR待发布状态。无运行作业、不重交2630，下一步独立校准＋模型PPL。


Issue78输入驱动分析发布回执（2026-10-21 09:16Z）：task/78-field-int8科学head08f32b2已推送，草稿PR82开放未合并；GitHub原始统计JSON与manifest字节SHA核验通过。旧PR80已合并e24414b。无运行作业，不重交2630；模型量化PPL/PPA仍未做，Projects待既有权限。FIELD_PUBLICATION.json含Issue评论和回执。


## 2026-10-21 Issue73定时检查：18/26完成

原PR75已合并3fe790e，仅为代码/提交/恢复阶段；后续task/73-results-followup、PR83草稿开放未合并。CPU2632源86ccedc完成7合同；10:11:23Z为18completed（旧8＋修复10）、2running（2585_12/16）、6pending（20～25），新ARC-E FFN seed0/1完整。逐题SHA/全量ID/候选token/32层active-dummy/源与输入绑定及已存metrics重聚合通过，尚未独立复算官方process_results、未重哈希14GB权重。PIQA S512与ARC-E FFN均2/3，不报部分组均值。待运行约7.98GPU小时，两卡保留估计剩4～6h、单卡8～11h，非排程保证。入口llama2/results/task_accuracy_20261020/PROGRESS_20261021_ZH.md及checkpoints/20261021T101123Z/；原推理和快照不动。heartbeat每日继续且提示已纠正旧PR75状态，26项收齐后需官方oracle/配对验收再停用。原生Git连接两次超时，源码通过GitHub API上传且commit/tree/blob逐SHA完全一致，报告发布以PR83/Issue73回执为准。


Issue73 18/26检查点发布回执：PR83草稿开放未合并，科学head7a75c53已通过GitHub API按完全一致的Git对象SHA发布；原件SHA7f894690ee8482dbf98d019df2a272cb4ac0c6d9f138350a6975a7b22bba65b4远端字节核验通过，Issue73评论6313631692已同步。原生Git连接阻塞已由替代传输解除。回执work/jieruiz/73/PUBLICATION_CHECKPOINT_20261021.json；每日heartbeat继续至26项及官方oracle最终验收。


## 2026-10-21 18:25 Issue73用户回查：19/26

CPU2634复用已测源86ccedc通过封存/逐题SHA/32层检查，19completed、2running（2585_12/20）、5pending（21～25）。新增ARC-E FFN seed2，两任务仅FFN三seed齐：PIQA acc/acc_norm77.80196%/78.99891%，ARC-E76.27666%/74.32660%；不是最终26项或独立官方oracle验收。新检查点checkpoints/20261021T102541Z/CHECKPOINT.json SHA c3e1ac52858d6f3cb3006e1e36c032c0c20eb0bf4df93858e7dc708a42da4871；同PR83报告更新，旧18检查点保持原字节。五项待运行约6.71GPU小时，两卡含运行尾部仍预计4～6h。服务器Qwen39项status全completed，含Hella1000子集。原推理未重跑，回查继续，结果同步以Issue73新评论为准。


## 2026-10-21 SANTA++ v1精读与创新性对照（Issue84 / PR85）

负责人jieruiz；task/84-santapp-novelty；独立稀疏目录tmp/santapp-novelty-issue84-20261021，base5b26c80。报告architecture_tlm/research_readings/SANTAPP_V1_NOVELTY_ZH_20261021.md已推送科学head ad92485c9f98cc50fdb706f620c96d681fb339e9，PR85草稿开放未合并，Issue84保留。用户PDF2609.35629v1为SANTA++，32页，SHA d9d9008174be713ba498dd96710e07552072eb4a9daf7063431a8c5c622375bf；官方demo commit9d1fdff7df65e54febc4112e99346ead0353e57c。已读正文/附录A–F方法与边界、图表渲染抽查；没有新推理/训练/PT/TLM。

本文用真实key代表、Gumbel不放回top-K选team、条件纳入概率校正及GQA并集，已覆盖前置筛选/稀疏Attention宽泛想法。我们的max4是四个均值，不同于四个真实key；当前筛选没有逆选择概率校正，候选内采样准确不等于全cache准确。其S128=32teams，不等于我们的128观测；LongBench16.68%逻辑KV/99.07%分数保留，不能转成整机能量；1.69倍仅32K单层GPU算子、无prefill/packing，demo还另存packedKV。MLA共享并集使逻辑访问仍86.18%，确认共享头会吃掉收益，但不构成我们的独创。

候选创新收窄到具体p-bit采样电路/并行调度、短流FFN及存储协同；不能因本文没做FFN就称整个领域新颖。新拒绝采样无全模型PPL/PPA，T32分层不能冒充自然IID；需对照DS-CIM/ReMix/直接随机舍入低位MAC、同模型长上下文与同质量J/token/延迟/面积。报告与来源manifest/算术核查见work/jieruiz/84。未接管Issue37/78或评测作业，无新增运行任务；下一步评审PR85，后续算法实验需原任务单独安排。


## 2026-10-21 赢家保持Softmax本地设计复核

用户提供pbit_llm_master_report_20261012/PBIT_WINNER_HOLD_SOFTMAX_ZH_20261021.html（SHA454ef7b2b6e18a2a9744f3f92c34fbb9c8362a8d54c92c881beef2d7729dd228）。已读全文/嵌入算法，独立核对详细平衡并重放内嵌纯数学脚本；源码SHA649f1d44...、输出SHA cfc8b490...与文档完全一致。12固定偏置、18成对、4XOR循环、4均匀独立核及合成IACT检查通过。GitHub核验本人jieruiz、Issue78仍open、PR82仍draft；此为只读跟进，不接管数值实现，没有新分支/远端发布/模型/PPL/Slurm/PT/TLM。原HTML未改。

并行赢家保持允许多hot，旧赢家自己的bit为1则保持，否则活跃地址均匀仲裁，全零也保持；平稳目标为odds(p_i)，理想sigmoid对应Softmax。需保持样本权重、各路/跨帧新鲜独立与准确均匀仲裁；不能套FFN共享64同随机数。它把单地址约束转入数字索引，不再依赖稠密互斥Ising网络。单p-bit分数差是已有Barker接受，XOR是受限对称提议；均匀512下132/384/896只属平稳渐近算法对照。

新增合成解析反例：512类z=[12,12,0,...]，双峰质量99.8436%，f在两峰为+1/-1。全局均匀挑战者Barker IACT1019.801，目标渐近ESS128需130535更新；并行赢家保持c12 IACT2.996875，需384更新。N4/6/8全枚举特征函数残差<=1.50e-15。不是模型V/PPL或物理周期；并行每轮512随机位+仲裁，更新比不等于能耗比。故优先保留并行吞吐候选，Barker作为低面积候选，XOR先作控制对照，真实logits/V决定选型。局部8位负驱动结果不能直接继承Barker差分驱动；可用符号和补概率映射但需单独验证量化。证据tmp/winner_hold_review_20261021/REVIEW_MANIFEST.json及two_peak_analysis.py/json，仅本地数学诊断。


## 2026-10-21 Issue78真实QK/V采样器对照完成

独立task/78-sampler-qkv-benchmark、tmp/sampler-qkv-issue78-20261021，base5b26c80；capture2640源4251660、benchmark2641/2642源4ec2613、派生2733源25cfd9d。54原始BF16 query/head/layer行＋36筛选派生，共90配置全部完成，三seed×八重复，原FFN/Attention轨迹，512/2K/8K各两窗口、层0/12/23、头0/6/13，真实64维V。六窗口捕获前后backbone/末读出逐位一致。原2639门禁失败不接受；2731因Windows archive LF→CRLF配置SHA停止，实际执行源/PLAN原字节已归档并验证只换行不同，2732/2733按真实SHA汇总，无模型/采样重跑。输入/原件/来源见work/jieruiz/78/qkv_benchmark，摘要SHA b95c40f5098fca632e28d420e96399189e59c6f80d8ed6da048fa8ebf9ef1261。

以同候选真实V输出MSE对照解析IID128：主表预热32，winner c=max中位288、90/90（范围288–1056）；校正拒绝中位288.17、90/90（约128–406）；Barker46/90、中位16416，仅成功输入统计；两比特19/90；XOR67/90。winner cmax+2较慢，+4多不达标，真实Attention有效类别中位约7–15；均匀理论最优偏置不直接适用。赢家8位负驱动h1/8/[-31.875,0]档位基本不变，非物理/R8验证，精度更高会有约4.95e-4归一化偏差地板。

从argmax初始化，winner B0/S256到IID128均值67/90，S512 89/90（MC95 83），S1024 90/90（MC95 90）；IID512目标B0/S2048均值90/90但MC95 81，S4096才90/90上界。本批MAP-V无行满足IID128，不是只测容易尖峰。更新数不等于芯片周期：P64处理N512每帧至少8服务波，S512即至少4096服务周期，另计加载/稳定/计数仲裁/反馈；全N并行也未证明II=1。两主候选能量胜负未定，Barker/纯XOR先不作长候选主线。

不是完整模型PPL/准确率/PPA/能量，原始V访存去重/GQA并集未实测；筛选遗漏另计，部分保留质量很低。正式报告qwen/results/sampler_qkv_20261021/DECISION_ZH.md及SUMMARY，13本地、8服务器核心/4汇总检查通过，无本任务运行作业、无新GPU或训练/默认/TLM改变。任务分支/PR发布待本次实际回执；Issue78继续open，PR82不接管。


Issue78真实QKV比较发布回执：科学head346bbb12f1181ab1b974940d79f052d0757fec80已推送，草稿PR86开放未合并，task/78-sampler-qkv-benchmark。90/90配置的结果、来源、原执行字节和报告均发布；摘要SHA b95c40f5098fca632e28d420e96399189e59c6f80d8ed6da048fa8ebf9ef1261。当前无本任务作业，Issue78继续，后续硬件/PPL未代做；待最终Issue回执确认新metadata head及远端字节。


Issue78比较口径补注：直接校正拒绝法的IID128/512误差匹配是理想独立性下的解析期望，90/90表示服务完成与期望律，不表示24次MC经验均值都过线；赢家/Barker等达标为MC网格观察。正式DECISION已明确，不能把二者的覆盖率当同一种统计证据，或据此宣称精确能效胜负。


Issue78发布视图口径修正：原服务器SUMMARY SHA b95c40f5098fca632e28d420e96399189e59c6f80d8ed6da048fa8ebf9ef1261仍完整归档；公开SUMMARY视图SHA0b6aa1f2a5f2b44d28ef4eb1351a533f415beb37da3138887182991d8ebca38c。仅将IID/拒绝法40项MC95字段改为不适用/null，并增加父制品/转换源码SHA；所有误差/预算/输入/配置/原件SHA不变。publication_view.py断言恢复注释后与父摘要完全相同。14本地检查通过，服务器仍8核心/4汇总，新2汇总守卫仅本地；不虚报为新服务器评测。PR86继续草稿未合并，本轮视图以最终推送/Issue回执为准。


Issue78本轮最终发布核验完成：PR86草稿开放未合并，最终head 4f8a1b4f12876ece8f73f6c304509747eff011b6；DECISION/SUMMARY发布视图/RESULT_MANIFEST三文件均经GitHub原字节SHA读回核验，公开摘要SHA0b6aa1f2a5f2b44d28ef4eb1351a533f415beb37da3138887182991d8ebca38c。Issue回执 https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/78#issuecomment-6319266942 。上方待推送/待回读描述为历史，自动审批超时后一次重试已成功，无用户待处理权限阻塞；本任务无运行作业，后续PPL/PPA与Issue78仍开放。


## 2026-10-21 全候选并行赢家保持/校正拒绝TLM（Issue87）

用户明确要求候选N路足量一次读取，随机源前端先不决定。独立task/87-parallel-sampler-tlm，base5b26c80，稀疏tmp/parallel-sampler-issue87-20261021；未接管amlink1219的Issue37。新增winner_hold_tlm_v5.py/corrected_rejection_tlm_v5.py，共用parallel_sampler_v5.py后端无关源接口，并经screen_parallel_tlm_v5.py接回完整decode。每查询赢家N路、拒绝N−1路并行；公平随机辅助单独统计，不能套FFN同阈值64共享。阻塞单帧FSM计源服务/间隔、计数/均匀仲裁、空态2^-m校正、偏移重写或共享标量、单项输出回压；不是一拍完成更新。

执行f6c6bd8215c2d702ab42e6a3078f64e0888cade8，18新＋10旧检查通过，30三seed合成模块和2单层decode情景完成；结果architecture_tlm/results/parallel_sampler_v5_20261021，说明architecture_tlm/PARALLEL_SAMPLERS_V5_ZH.md，交接work/jieruiz/87/HANDOFF.md。不是PR86全部真实QKV重放/完整PPL/Slurm/PT或DRAMSys实测；未知完整能量/面积null，时序为明确资源参数的情景。v4原默认保留，只加3扩展点。代码本地完成，推送/PR状态以Issue87最终回执为准；旧Issue73/78作业不改。


Issue87发布回执（2026-10-22）：科学head8687c1d8124af192e82ec13aa3dbe12ccaa240b7已上传workspace；PR88草稿开放未合并，6份关键模块/中文说明/报告/验证文件的GitHub原始blob逐SHA-256读回一致。PUBLICATION和REMOTE_VERIFY在work/jieruiz/87/；后续仅交付状态元数据，实验执行仍f6c6bd8。上方待推送描述为历史，无用户待处理权限阻塞；看板沿既有限制未同步。Issue87保持open，源后端/真实能耗面积与新模型质量仍待后续标定，未调用新Slurm或改Issue73/78任务。原型36文件已逐SHA压缩核验至本地project_archives/parallel_sampler_issue87_20261021/prototype_before_f6c6bd8.zip（SHA1c6ae1c9367f4e67634283fc68c5d31c4ee35e0187d11f3e7a7edaf24503bb51），原型目录回收，当前仅最小稀疏任务工作树。


## 2026-10-22 Issue73：26项推理完成，按用户要求删除定时

北京时间12:43（04:43:23 UTC）SSH只读检查：Llama2任务26/26 completed，PIQA1838/ARC-E2376各13项，逐题文件SHA/字节数/路径及声明32层计分守卫通过，当前Hongjie_Zeng的Slurm队列空；旧2572健康8＋修复2585十八项均按原计划保留，没有重跑或取消。原件llama2/results/task_accuracy_20261020/checkpoints/20261022T044323Z/STATUS.json，汇总PROGRESS_20261022_ZH.md。此次只重聚合已存summary指标，官方逐题process_results与最终完整层/输入源合同复核仍待做，不将推理完成等同最终科学验收。

用户本轮明确任务跑完即结束定时；automation_update(delete,id=llama2-7b)返回deleted，本地配置确认已不存在，回执work/jieruiz/73/AUTOMATION_STOP_20261022.json。尽管最终oracle待做，不得因为旧交接提示而自动重建此定时。Issue73/PR83继续open/draft未合并，后续同任务完成验收与同步；报告发布以PUBLICATION_STOP_20261022回执为准。其他暂停的p-bit抢救回查没有改动。


Issue73 publication receipt (2026-10-22): completed26 status/report and automation-deletion receipt pushed to PR83, scientific head 6acac58eac394b940907a5e4265db39fd043a761; three GitHub blobs read back SHA-identical. Issue comment: https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/73#issuecomment-6332960590. PR83 remains draft/unmerged; oracle pending, daily follow-up deleted at user request. PUBLICATION_STOP_20261022.json records exact evidence.


## 2026-10-22 第五轮PR审核与模块接入边界（Issue55）

本轮82/83/85/86/88已按精确head/base实际合并，见work/jieruiz/55/round5/。82是既有logits的完整驱动量化局部条件律：25检查/9格式重放及冻结源核验，非量化自适应整轨迹或模型质量。85是SANTA++ v1原PDF/公式/表格/官方源码的文献对照，不是新模型或全领域查新。

83的26项已完成最后官方验收：原8＋修复18、54782道配置内文档、109564指标，与固定lm_eval0.4.8原process_results和原始YAML/parquet标签逐题一致，源/输入/文档封存与32层覆盖通过；三seed及BF16逐题配对统计见llama2/results/task_accuracy_20261020/FINAL_RESULTS_20261022_ZH.md和FINAL_METRIC_ORACLE_20261022.json。旧19/26与oracle pending是历史。未重复推理/重哈希14GB权重、未恢复已删除定时；原CTMC/FFN任务验收不等于新采样器/q8、长上下文筛选或质量无损保证。

86核验90行=54原始+36派生、3seed×8重复、122归档执行源字节与CRLF等价、90原件SHA/源输入计划和V参考方差；固定预算/组表只读重算通过。14本地检查通过；解析IID/拒绝的40个MC95注释修正不改任何数值。局部V-MSE和经验网格预算不能继承为PPL/ASIC周期。

88的18新+10旧检查通过，审阅补做两采样器×数字FFN/历史fixed_sc_exact共4项24层/context512/S16合成Link连通。新增python qwen/run.py tlm-parallel --attention可选入口，原tlm/v3保留；FFN历史参数不是最新B4/T32/K32重标定。采样后地址直接V读取，无重复PV采样，完整能量/面积未知仍null、quality_reference_ppl仍null。接入通过不等于最新FFN＋新采样器＋8位驱动的整模型质量/物理实现已经完成。

本人元数据冲突保留双方有序历史，其他成员STATUS和原科学blob不覆盖。继续研究归Issue78/37；有限任务73/84/87验收状态以Issue原生最终回执为准。仅本轮本人稀疏review/helper目录在报告合并后逐SHA归档回收，恢复project_archives/pr_review_issue55_20261022/RECOVERY_INDEX.json。canonical原未提交资料先备份、HEAD不reset，根阅读副本同字节同步。

2026-10-22原生验收回执：Issue73（最终26项官方逐题）、84（文献）、87（可用TLM）已按各自有限范围实际关闭；Issue78/37继续开放。旧待审与pending文字仅为历史。

第五轮追加PR89：19固定源、8组TLM中位数/单位/null及3组固定预算覆盖核验通过，旧数字全上下文D0与原评估保留，局部误差/合成时序没有冒充新PPL/PPA。自动审批曾拒绝向其他成员分支推送刷新；未执行该推送，已改为原head69b1accc的无冲突原生合并9bd908b5，无作者分支改写或STATUS/HANDOFF手工改动。作者自己的新状态按原blob继承，Issue37不关闭。

2026-10-22第五轮最终发布/回收回执：报告PR91已原生合并83e15289434af50fc09c35e699d8b39965389d98，收尾开放PR为0，Issue55于05:31:46Z验收关闭；Issue73/84/87已关闭，78/37继续开放。唯一review稀疏目录和helper已于05:30:52Z逐SHA归档后回收，逻辑移除35,991,762B；525份临时文件压缩10,041,404B，project_archives/pr_review_issue55_20261022/review_scratch.zip SHA256 fd9cec6bab3955cdd9100e9eba82fb4fb5c01ae41060bb5b7b17265c4818e339，恢复/清理实际回执在同目录RECOVERY_INDEX.json、CLEANUP_RECEIPT.json及FINAL_ISSUE55_RECEIPT.json。保留review/55-pr-round5 head80e712eac8c28a413c06dd8b8927e66b644c8e78；其他成员目录、共享对象、模型与原始证据未清理。含私有NPZ的归档仅限授权本地。此最终回执为报告合并后的Issue28维护增量；报告冻结备忘录SHA9ef4fc794fd2fbd51993849972346b90153b36e971cd8731e78a10919880f049不改写。
<!-- llm-env-issue90 -->
## 2026-10-22 Issue90：两台4090备用LLM环境

个人隔离Python3.12.3/Torch2.6.0+cu118/Transformers4.45.2/lm_eval0.4.8已安装并验证。A CPU9041/GPU9042、B CPU14101/GPU14104均COMPLETED/0:0，每台19CPU检查及6GPU synthetic smoke通过，27参数/3非持久RoPE buffer逐位相同、重载logits差0.0。94包freeze两台原字节相同SHA636ea0599fc983e7c003c3a8881aefa2f05d8167f2877dcab8992dfc3f145ae5；正式入口为个人环境bin/llm-python进程wrapper，旧glibc兼容层不改系统或共享环境。

## 2026-10-22 随机源统一操作模型与核心RTL（Issue95 / PR97）

用户要求准确操作统计、基础LFSR/共享扩展/非LFSR后端、启动新种子与慢速换种，并由用户自行仿真PPA。本轮实际GitHub连接器身份rayggxia，独立task/95-rng-service-rtl、tmp/rng-service-issue95-20261022，基线83e15289434af50fc09c35e699d8b39965389d98。源码提交970260e21ebcf98822b9cf47b643fb8360a31e2f已发布PR97，开放待审未合并；Issue95继续open，Projects未核实/待同步。原生Git本机连接失败不影响连接器已发布事实，本地/远端状态以work/rayggxia/95/PUBLICATION.json及最新远端head为准。

入口architecture_tlm/random_service/：LFSR32 1×8bit、现有GF扩展64×8bit、Bivium177bit状态/160bit展开20×8bit；端点/种子入口Python与7份SystemVerilog，统一valid/ready、q/256阈值、响应保持、SAVE/RESTORE/RELEASE。默认1亿拍换种（10ns约1s），0仅启动；每端点每epoch独立取得新总线材料，无免费根种子派生或固定种子回退。LFSR每次32bit、Bivium192bit总线包保留177bit并明确丢15bit，预热5拍。FFN锁定重放时延期记账；无源不输出。OS/fixture/有来源trace严格区分，软件OS不宣称物理熵。操作数/总线/等待分开，PPA null。

现有parallel_sampler_v5.py只加可选计时源适配，旧理想默认保留；26个Bivium可供512路帧（额外8路收费），公平辅助另端口。核心与入口逐周期不等于整个Attention/互联RTL周期精确。GF64总秩32、两两秩16，不保证64路联合/跨时IID，Attention默认拒绝。概率LUT量化改变目标，未继承旧PPL。模拟读出、健康调理、CDC、共享仲裁器和sigmoid LUT完整RTL仍缺，记录DESIGN_QUESTIONS_ZH.md；优先综合top/活动场景见POWER_SIM_ZH.md。

47项Python检查通过，3后端×3seed×900=8100沿及连续活动6000沿逐沿一致，FFN250沿120帧通过；便携包独立19检查/fixture示例通过。有限3seed统计诊断不等于质量验收；没有DC/PT/PPL/GPU/Slurm/新Spectre。包远端上传/rng_service_v1_20261022.zip，SHA7b067edb8dfd452242830ac6f01c068d6200e76ae0d9a0711f2ab4a9097c8f45；原始验证ZIP在project_archives/rng_service_issue95_20261022/verification_raw.zip，SHA684e69f452933b05abaeafab8963f26367c313015940b49208facee2cc6d3524；失败/成功记录按成员SHA保留，PR待审保留最小工作树，不重复旧实验。
正式入口[环境报告](maintenance/llm_env_4090_20261022/README_ZH.md)，原执行源scripts/llm_env_4090_20261022，私有原件hash/脱敏视图及交接work/amlink1219/90。原失败与恢复各阶段保留，70wheel恢复包仅LLM扩展层，不含Torch底座。服务器地址/连接配置/凭据不发布。Torch版本不同于5090的2.7.1cu128，未下载真实权重/语料、未训练或产生真实PPL/准确率/PPA，后续真实实验需匹配数字基线。5090优先、备用当次告知、个人目录/Slurm/跨服务器单GPU规则继续适用。上传与PR状态见该任务PUBLICATION.json，Issue保持open等待审阅，不自动合并。
<!-- /llm-env-issue90 -->

## 2026-10-22 第六轮PR审核（Issue55）

PR93环境交付32源/5报告与94包冻结逐SHA通过，Windows git archive/checkout会受core.autocrlf影响；本轮改用git cat-file原blob核验，不改作者字节。作者两台19CPU/6GPU记录仅核对冻结报告，本轮没有重新登录/安装/申请GPU或重新取得13份私有原件。PR94的45CPU检查通过（本地Python3.8补等价Path.is_relative_to运行时shim，作者3.12源码不改），134包成员/90模型SHA、先冻结再评估及VAL预选强max4通过，15逐文档原件按48篇×3eval seed重聚合；2304隐藏态门控等价/6均值回算的成本JSON逐字节重放一致。强max4下是分层权衡且33–39%超512容量，不改默认或冒称PPL/PPA。PR97的47CPU、三后端三seed8100沿与FFN250沿/120帧均重放一致，27源blob/向量SHA/操作账本和便携包26文件一致；数字核心不等于物理熵/IID或工艺PPA。93/97合并回执与94原head集成证明在round6；90/92/95仍由原负责人按Issue验收接续，不自动关闭。旧材料与canonical原未提交增量完整保留。


<!-- issue96-unified-v6 -->
## 2026-10-22 统一整机TLM v6（Issue96 / PR99）

用户同意整机保留tile/事件粒度，关键机制先验证，差异足以改变结论再细化。jieruiz独立task/96-unified-tlm、tmp/unified-tlm-issue96-20261022；基线83e15289，冻结执行fba22b192ab914046e50cc405f6dd473bf30d154。入口architecture_tlm/unified_v6/README_ZH.md与RESULTS_ZH.md；三个模型可选tlm-unified，历史默认不改。

本版将固定W8、动态四档PoT、T32/K32、gate/up共享x与跨输出波重放、FP32 SwiGLU后z独立编码接入完整decode；包含embedding/全部层/最终norm/lm_head/选词。Attention有数字在线GQA、比例PV（systematic CDF）、max4筛选后准确/PV、赢家与校正拒绝；K/V按GQA并集和物理burst收费。采样器内部FSM/反馈/输出等待复用v5；直方图采用明确但保守的逐地址RMW，不声称最优。独立BF16残差/x/z/宽部分和区域；SRAM容量/端口/fabric、权重ping-pong和有限32请求窗口显式计入。初始KV和摘要已存在，不含prefill/TTFT。

52项整机情景全部完成：Qwen2K/8K各8方案×3seed共48；Llama1/2各数字BF16、SC/PV两项完整32层单seed连通。21新机制+18原并行采样器+10原v4检查通过；62原件、22执行blob、764模型契约核查通过。原门禁4e0d26b的W8尺度寻址越界已修复，失败前缀与EXEC原件保留，不计正式52项。无新PPL、训练、GPU、Slurm、PT或实际DRAMSys运行。

条件100MHz核/80MHz SRAM/16GBs：Qwen2K BF16准确234.360ms、W8数字163.565ms、SC准确201.677ms、SC筛选PV197.946ms、SC拒绝286.556ms、SC赢家303.646ms；8K分别260.453/189.658/227.770/202.770/551.715/622.894ms。赢家预算是PV/拒绝8倍，不按同S比较。QwenSC主采样波约3.411ms，64路通用向量恢复约55.158ms，恢复/搬运/接口是优先核查瓶颈；不能把短流阵列收益等同整机收益。相比同W8数字SC更慢；完整物理能量/面积、新组合PPL均null，部分已定价小计禁止当总能量比例。默认Link外存64pJ/B/50mW是条件值，不是新DRAMPower。Qwen1MiB/Llama8MiB是配置预算，未证明最优。

随机源按用户要求仅本地PRNG接口，随机流SRAM/FIFO/额外概率副本均0；必要编码/计数/映射仍保留。有偏候选独立需求、种子/新帧/重放/并行服务需求单列，未标定成本不置零。本任务期间PR97随机服务已合并27bf9c48，但本轮不启用该后端或其量化；采用新上游采样器默认接口覆盖49项也通过（前两次本地temp/脚本导入问题保留）。后续可由Issue95接口适配，不使用FFN共享门限替代Attention独立提议。Projects本轮GraphQL实测缺read:project，待同步。

源码已上传PR99，成果/文档发布以Issue96、work/jieruiz/96/PUBLICATION.json/REMOTE_VERIFY.json最新回执为准；PR待审，不自动合并或关闭Issue96。后续优先表征B4恢复/编码、权重驻留接口、采样器偏移与直方图流水和本地源。当前TLM不是周期精确芯片、GPU模拟或质量验收。
<!-- /issue96-unified-v6 -->


## Upstream Issue90 complete receipt (27bf9c48; prior local history preserved)

<!-- llm-env-issue90 -->
## 2026-10-22 Issue90：两台4090备用LLM环境

个人隔离Python3.12.3/Torch2.6.0+cu118/Transformers4.45.2/lm_eval0.4.8已安装并验证。A CPU9041/GPU9042、B CPU14101/GPU14104均COMPLETED/0:0，每台19CPU检查及6GPU synthetic smoke通过，27参数/3非持久RoPE buffer逐位相同、重载logits差0.0。94包freeze两台原字节相同SHA636ea0599fc983e7c003c3a8881aefa2f05d8167f2877dcab8992dfc3f145ae5；正式入口为个人环境bin/llm-python进程wrapper，旧glibc兼容层不改系统或共享环境。

正式入口[环境报告](maintenance/llm_env_4090_20261022/README_ZH.md)，原执行源scripts/llm_env_4090_20261022，私有原件hash/脱敏视图及交接work/amlink1219/90。原失败与恢复各阶段保留，70wheel恢复包仅LLM扩展层，不含Torch底座。服务器地址/连接配置/凭据不发布。Torch版本不同于5090的2.7.1cu128，未下载真实权重/语料、未训练或产生真实PPL/准确率/PPA，后续真实实验需匹配数字基线。5090优先、备用当次告知、个人目录/Slurm/跨服务器单GPU规则继续适用。上传与PR状态见该任务PUBLICATION.json，Issue保持open等待审阅，不自动合并。
<!-- /llm-env-issue90 -->

第六轮追加PR100评估协议：33项结构/来源SHA/内部链接/数值复算通过；独立核对lm-eval0.4.8字符长度acc_norm、SANTA batch分母、HSA输入输出token、MLPerf5.1版本质量门槛、DRAMPower时序边界及Kelle Table2；本机MBA第6节/HBM3.9pJ-bit与技术缩放文字核对。16篇矩阵/CSV一致性不冒充重新穷尽全文查新。协议为未批准未执行提议，不改变用户质量预算或启动模型/PPA。PR100与97仅负责人STATUS冲突，直接继承100作者原blob，旧97状态保留Git历史，无作者分支改写。PR99读取fba22b19仍draft、最终整机情景报告未齐，保留待审，不因已有机制测试通过而合并。

第六轮PR99 ready补审：冻结52项已齐，21新＋18旧v5＋10旧v4=49检查通过；最小导出首次缺SRAM校准JSON，补齐同Git blob53,770B后通过，未改源/测试。原52结果清单62文件、22执行blob、764契约和汇总逐字节重建一致；独立Qwen2K/24层BF16 234.36001ms与SC准确201.67681ms全部26核心输出字段一致，均为TLM。旧入口命令不变，新增tlm-unified。原PR97后端未启用，新FFN/采样组合质量和完整能量/面积仍null。原heada7a48297按本次本人分支交付，不改执行快照。


第六轮最终发布/清理回执：报告PR101合并5dbd9e39，补审PR102合并eb317e4f6fb1b0d8844887401f3275f128ef8a83；93原生129ae823、97原生27bf9c48，94/100/99以原head通过本人集成PR进入，GitHub确认MERGED（2d3ec2e4/748450ad/0575a633）。Issue55于2026-10-22T09:45:20Z关闭，最后查无开放PR。原任务状态{90: 'OPEN', 92: 'OPEN', 95: 'OPEN', 96: 'OPEN', 98: 'OPEN'}，原负责人不变。972份临时文件逐成员SHA归档为5,749,927B，ZIP SHA256 aa28da037b9955e739ca57315fb8863b16e48a62067bcc4cfa6c42c3130e1931；本轮本人tmp/pr55-review-round6-20261022和tmp/pr55-round6-artifacts已实际回收，逻辑35,687,315B。恢复索引/清理回执/Issue55最终回执保留project_archives/pr_review_issue55_round6_20261022/，Git ref review/55-pr-round6@49fad91f6da868cfc85fac243e985f76e08c5cb4与共享对象/他人树/模型/原始数据保留。报告冻结备忘录SHA85c77d094a8e91f162cb615242961d764b297e01bcd72f4b4d2f5815a12c1c8e保持；此为Issue28在原目录的合并后维护增量。49检查/52清单与两项完整24层重放不等于模型PPL/物理PPA，未知项仍null。

<!-- issue104-inspector -->
## 2026-10-22 架构检查台与全面审计（Issue104）

jieruiz，task/104-architecture-inspector，独立tmp/architecture-inspector-issue104-20261022，集成基线eb317e4f。入口architecture_tlm/inspector/README_ZH.md、model-inspector.html、CHECK_REPORT_ZH.md。21模块/5视图，52封存情景、完整phase、存储/精度/源代码SHA；旧底层事件每项只有80条，禁止假造完整微观轨迹。

新增旁路stage/query账本，不改时序、动作或数值；观测执行124d37d2，Qwen24层336query与旧序列化字段严格相同，另三tiny共6query。76CPU检查、686模型内部不变量及16组观测检查通过，浏览器与Node语法已核。128输出的示例实际387提议/25983服务周期，其中16835为驱动重写；S、sweep、attempt、lane工作与FSM周期必须分别报告。

权重32KiB/波驻留并行供给、48KiB局部计数状态、新源后端整机接入与部分格式转换尚未闭合；PR103仅小接口，完整decode默认LocalRandomService。Link非新DRAMSys，总物理能量/面积/PPL仍null。没有新GPU/Slurm/PPL/PT。科学成果1909c542a1c454a9e219a5482c9b493fa678b340已推送，PR105（https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/105）ready/open待审、未合并，8关键blob原字节已核验；PUBLICATION/REMOTE_VERIFY封存该科学head，最终任务分支head见Issue104回执。不自动合并或关闭。辅助hooks目录与失败v1/v2逐SHA本地归档后回收；待审主目录最小保留。Projects仍沿read:project不足待同步。
<!-- /issue104-inspector -->

<!-- issue107-digital-ppa -->
## 2026-10-22 完整TLM周期/访存审计与非随机RTL（Issue107）

jieruiz，task/107-tlm-cycle-digital-rtl，独立tmp/tlm-digital-issue107-20261022，基线eb317e4f。入口architecture_tlm/digital_ppa_v1/README_ZH.md、CYCLES_MEMORY_AND_RTL_ZH.md、PPA_TASK_ZH.md。52封存情景周期/阶段/物理字节只读重聚合，不是新模型或TLM运行；100MHz核/80MHz SRAM必须分开，MAC512/周期、向量64lane、非线性16lane、SC驻留供给、局部状态、源/CDC/Link等仍有假设，不是只缺功耗面积。

最终源码23e8d65fbd84cf548ab82a6c9cfe423d37e59ae4，66功能组/12870逐位输出/63活动预检通过，29源输入与Git原字节一致。21KIND及SRAM/DMA控制、4lane数组；不含PRNG/p-bit/随机矩阵阵列。FP32非线性与融合恢复为候选，不继承PPL；probe功能延迟1拍不证明组合路径10ns。新最后一次归一化/转换输入隔离避免无效翻转；恢复器一次输出不能按72个完整核计费。

113124B本机源码包digital_ppa_v1_20261022.zip，SHA d8004f0fdf586dc020e99c3d6e6ed3b29050a652a55af037220af898c03aafb2；Git保留正式源码、验证和索引。原始波形/编译/失败逐SHA本地归档回收，仅保留待审主目录。没有新GPU/PPL/Slurm/DC/PT/STA/真实DRAMSys，完整能量/面积仍null。科学成果7b12fea03bd2596cc206f3f0c32571196688e665已推送，PR109（https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/109）ready/open待审、未合并；9关键blob原字节已核，最终任务分支head以Issue107和本地FINAL_REMOTE_VERIFY为准，不自动合并/关闭。用户下一步55nm工艺表征先查STA，再按实例/latency/II和正确计费单位更新新TLM。PR105/103保持独立，Projects本轮实际查询见work/jieruiz/107/PROJECTS_CHECK。
<!-- /issue107-digital-ppa -->


## 2026-10-22 数字电路仿真统一台账（Issue110）

用户要求集中记录已有数字电路PPA并每次新增登记。正式入口digital_circuit_simulation_registry/README_ZH.md，本机同名固定目录为同字节阅读副本；任务task/110-circuit-simulation-registry，独立稀疏tmp/circuit-registry-issue110-20261022。35条批次/模块记录、516行配置/seed/窗口；117个数字原始归档逐SHA发现索引，不把发现未审等同成功。精确结果地址见01_结果地址索引.md及artifact_locations.csv；records保留源绑定/PVT/频率/边界/限制和各阶段状态。

已纳入37962470/37981139/38015538随机矩阵、SS SRAM/DFF主模块与S0–S5、14组SS/TT宏库提取、CACTI估计单列、38100634 TT/SS Q10 SwiGLU、38322118四随机服务核心×三频率252窗口，以及转换/短流/Issue107功能证据与失败历史。共享p-bit后端独立交叉索引，较新38165794/38215256/38263376归档待完整审核，不能用旧报告断言其未完成。120.8uW旧预算缺直接绑定原件，未冒列为本次确认PPA。

157个可访问独立文件原字节SHA与26个tar成员SHA核对通过，8项登记守卫测试通过，无原件缺失；未重新运行RTL/DC/PT/STA/GPU/PPL，不重放全部VCD。所有已算PPA仍保留前/后布局、时序/X/库表告警等限制；新数字v1没有PPA。未搬移/删除/复制大原始结果。AGENTS新增每次仿真登记规则；新结果同任务PR更新台账/总览，清理目录前更新归档恢复地址。已实际推送科学payload a31e010d，PR111 ready/open待审、未合并，9关键远端blob原字节核验一致；Issue110同步，Projects实际查询缺read:project待同步。回执work/jieruiz/110/PUBLICATION.json；不自动合并。

第七轮最终合并/清理（2026-10-23北京时间）：报告PR115@db17ce0bd46bc2a93ffaf8f487b0241b61833f13已合并0968ccd9，补审最新PR113@be766ba原生合并46804fb3a1c50b29a19a7d0a3da6bb8f8b59af7d；八项来源PR全部MERGED。原113科学bc85618已随115进入，追加6行只改交付元数据，没有重复模型/RTL实验。最终科学及文档发布通过正常GitHub门禁，来源refs原样保留。1966文件ZIP逐成员SHA通过，本轮tmp/pr55-review-round7-20261022、tmp/pr55-round7-artifacts已于2026-10-22T16:05:21.9821340Z回收，逻辑53,149,901B；归档11,167,900B、SHA d9ee7b4598ff166cc04b1e8e2796caab973bf0813f89de6682432e6ef66f1383。原登记README在固定registry_recovered_evidence保留原SHA，中央镜像48文件与Git同字节；恢复索引/实际清理/原生回执保留project_archives/pr_review_issue55_round7_20261022。报告发表时备忘录SHA e75d5f416552ae211fe2c087f11229b99f8235943e888053596f9e51aa7a1c5d不变，此条为Issue28原目录的合并后维护增量，不reset其原HEAD或覆盖并发内容。没有新GPU/PPL/RTL/DC/PT作业，未重建已删除定时。

## 2026-10-23 已结束工作副本回收补充（Issue68，审核github对话）

本对话00:19实际移除10个已结束任务副本，逻辑1,182,605,540 B（约1.183 GB），64独有文件/10 ZIP/3增量bundle保留；10:29复核全部原分支和恢复ref、归档SHA/bundle通过，仿真台账157文件/26成员无缺失。正式回执maintenance/storage_cleanup_20261023_review，实际恢复索引project_archives/cleanup_20261023/REVIEW_REMOVAL_RECEIPT.json和REVIEW_FINAL_VERIFICATION.json。部分包位于review_audit_collision_preimages，按最终路径/SHA恢复，不用早期计划重跑删除。并发ZIP重名已恢复对方原SHA，无源文件损失。

LLM对话先前独立压缩10网表约2.713GB及回收1个Issue19回执约0.188GB，均不包含在上述1.183GB；该对话继续新增清理，Issue68保持open。模型、唯一原件、主对象库、进行中任务和其他成员目录保留。恢复先读索引，不因工作目录已移除而重复实验。发布/合并状态查Issue68最新回执；本条随review/68-cleanup-receipt-20261023交付。

清理回执最终发布（2026-10-23 10:32北京时间）：PR128@e97ac1e932674d46f8642dc839555b8a934a927b已正常合并e8705765ed3286b225e042378d57e5d010e221ee，5个报告/索引/本人状态/记忆Git blob与已审head逐字节一致。10目录回收1,182,605,540 B，64独有文件与恢复refs/10 ZIP/3 bundle复核通过；仅用于发布回执的小型tmp/cleanup68-review-receipt-20261023亦已回收354,348 B，无未提交或ignored资料。项目持续清理由LLM对话继续，Issue68仍open；本条为Issue28 canonical合并后维护增量，已发表快照SHA不改。

## 2026-10-23 Issue55第八轮最终合并回执

PR119/120/122/125/126/127/130已通过集成PR131实际合并，集成SHA `6966739a5223680888bf0315f7bb4f73423a1ae6`，GitHub逐一返回merged=true（2026-10-23 05:49 UTC）。共359项测试注册、358通过、1项Windows符号链接测试跳过；208资源结果、48数据流轨迹、GQA74源码同字节公开映射和回执、#130存储重算均核验。公开审计旧commit缺失问题已修复，原执行manifest未重写。正式报告 `work/jieruiz/55/round8/REVIEW_ZH.md`。Issue116/123仍暂停/未完成，全尺寸2783取消无成功summary；没有本轮GPU/Slurm/PPL/EDA或新电路run。下一步优先#125 SS/T32编码恢复最小PPA，和Issue107八模块包分开；恢复完整尺寸长跑需用户明确恢复暂停任务。

根台账阅读镜像现与已合并45记录/964行同字节；此前本地未发布的 `digital-ppa8-20261023-prepared` 没有丢弃，仍保留在 `tmp/tlm-digital-issue107-20261022/digital_circuit_simulation_registry/records/`（SHA d6337affa27d757e48a60607a6971576742421f73606b30e9904c2f13612d0ad）及本轮 `project_archives/pr_review_issue55_round8_20261023/REGISTRY_READING_PREIMAGE.zip`。它未包含在PR131中，不把准备包冒充已出PPA；下次Issue107发布应基于最新45记录取并集。本人审阅临时副本归档/回收以同目录CLOSEOUT.json为准，保留共享Git及其他任务。

## 2026-10-23 Issue95 分层随机质量首轮

负责人rayggxia；task/95-rng-quality，tmp/rng-quality-issue95-20261023，基线6966739a。复用38237164已有Spectre原始9条轨迹，189案例（两端点各4096帧）与30调理/36抽样诊断完成，9机制测试及1269原件/算术/结构核对通过。质量不是自动逐层改善：旧比较器VN后P1近50%仍有负时间相关；GF64在q128前4路严格xor=0；重复种子使三后端两端点同流。无新Spectre/RTL/PT/LLM/PPL，不认证熵率或最佳换种周期；两个独立电路记录不是同一物理噪声因果链，缺同时多路阵列记录。

入口architecture_tlm/random_service/quality/README_ZH.md及results/20261023/REPORT.html；用户副本远端上传/rng_quality_20261023.html。稳定原件project_archives/rng_quality_20261023，SOURCE_MANIFEST绑定8文件，执行本地8a862a38cf6e4e46f50e719f8b2b3877db745c75。中央run rng-quality-95-20261023为DESIGN_PROOF，PPA未运行；新增record单独同步固定入口，保留其他并行记录，不用旧catalog覆盖。当前本地完成；发布前GitHub连接器出现HTTP传输错误，远端发布状态以work/rayggxia/95/quality/PUBLICATION.json为准。恢复见同目录HANDOFF，不重复实验。

2026-10-23 Issue95发布回执：网络已恢复，分层质量实现/结果已上传PR134（https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/134），开放待审未合并；科学交付1f8e1d468792b5af17d337db885b482c189c00f9。完整远端tree与本地c8162a04b3c32bd0d5615108d8dc7b93bdf0b1ee相同，报告读回逐字符一致。旧网络阻塞文字仅为先前时点，无需重复实验。

## 2026-10-23 Issue95：旧比较器采样间隔纠正

用户指出当前应较慢采样，复核确认质量主链硬编码0.5us，不能把旧比较器rho约0.72～0.74泛化为慢速采种质量。复用9条已签SHA波形，72项间隔重分析/216 Pearson交叉核验/9数组SHA通过；10us固定时间lag的两款旧比较器三seed范围0.027～0.052，20us约0.018～0.047。单相位长间隔样本少，不能宣布IID或长间隔更差；P1偏置不会随间隔自动消失。VN原负相关仅属0.5us场景。

RandomNetwork未规定同一物理源采样间隔；SeedWords.interval是调理32bit字间隔，1亿拍换种在100MHz约1s，但不决定包内原始bit间隔。下一轮需显式物理时间戳/同源间隔及调理时序，再贯穿各层。入口architecture_tlm/random_service/quality/results/sampling_review_20261023/REPORT_ZH.txt；用户副本远端上传/rng_sampling_review_20261023.txt。沿用Issue95/PR134/task/95-rng-quality与现有工作目录，不改原189案例、旧报告或正式模型默认，不新增EDA/RTL/PPL/数字实验。台账原run补充后处理索引，不虚增实验数量。补充远端交付状态以work/rayggxia/95/quality/SAMPLING_PUBLICATION.json为准；Projects未同步，PR不自动合并。
