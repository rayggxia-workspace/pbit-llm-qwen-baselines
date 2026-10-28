## Issue206：非线性共享组与档数受控扫描（2026-10-28）

用户要求x保持已证明可用的64共享；只调整g/u非线性共享数量和可选档数。6组为G64/B4、G32/B4、G16/B4、G64/B8、G32/B8、G16/B8。沿用e888成功risk4原四档，子组复制parent64目录；B8补齐以原最大档结尾的8个连续PoT，包含旧四档，不增大最大尺度。无新拟合、不按TEST选择、不改变入口x/固定PoTW8每64x64/GU64/K64/NLjoint32T128/正常g signed8-P8 sigmoid/准确SDPA。

每组3seed有限NL、1seed条件NL均值诊断，并重跑BF16及旧risk4一个匹配seed；主36物理计分，去重按实际标签/配置核算，另GPU门禁3份（其中8目标pilot独立列，不是主PPL）。均值仅诊断，不是可部署电路或PPL下界。CPU再GPU Slurm门禁后提交数组，旧冻结源和推荐表不修改。只1024目标后缀非完整WT2，无训练/RTL/PT/PPA/TLM默认改变，GU仍FP32oracle；分组标签/比较/对齐成本只报结构计数，不冒称实测节能。

当前实现和AST本地完成，远程实际执行/作业/结果以后续GROUP_SWEEP_SUBMISSION/COLLECTION为准，不把待跑写成已完成。沿用Issue206/PR207及同工作目录，Projects沿既有权限限制待同步；保留旧所有负结果。

## Issue206四档继续调整最终发布回执（2026-10-28）

本轮负面结果及旧补充完整原件已实际推送PR207，交付head 00428d81841c2fbe01e8dec07da0893543361e74；7关键文件远端逐字核验、Git对象/tree同SHA。32物理28唯一+1校准BF16、61核心检查、额外8有限/16均值数值比较全等；新四组不采纳，CURRENT_RECOMMENDED明确保留e888 risk4/PPL17.9215。旧3211也全部40主37唯一+5pilot完成，无本任务运行作业。PR实际为ready/open、未合并，Issue保留open待审；TUNE_FINAL_PUBLICATION保存准确回执/就绪权限状态。完整WT2/新PPA/TLM仍未新增，不重跑已完成作业。Projects待既有权限同步。

## Issue206四档继续优化未改善，保留risk4 17.9215（2026-10-28）

主科学源d825f7d6e0757a5f847693922cf0d3018ea3a00d，78源blob且旧75不改；3254共61 CPU/CUDA通过、3255校准/3256四片全部完成，32物理28唯一+1校准BF16，三seed及旧risk4三seed逐值复现。大样本对角145.8641、组内Gram137.5114、Gram阈值169.9111、偏重偏差118.7165，均不采纳；条件均值仍68.74–110.79，提示系统偏差而非仅计数噪声。不能把局部目标改善当整LLM PPL改善，也不能据此判四档极限。四档/shared64/PoTW8/GU64/NL128/准确SDPA/正常g sigmoid不变，无权重训练/新RTL/PPA/TLM。

校准32窗2048、每窗后半32行=1024观察/层，768拟合256验证，仅TRAIN；候选8→10、4初值4轮。相对旧17.92同时改变多项，不能只归因样本变多。组内Gram仍漏组间项，方差0.5是启发式。额外代表层0/12/24/35各16行，3261辅助源359c8d24d838c90a094617e06fa1be1cad087761：8项有限parent、16项直接解码mean逐元素全等。3260相对导入先失败记录保留，原PPL代码不改。不是全链bittrue，GU仍FP32oracle。仅1024后缀非完整WT2。

CURRENT_RECOMMENDED.json明确保留e888 risk4（17.9215±.2662），不启用d825新目录；报告TUNE4_REPORT_ZH.md与TUNE4_SUMMARY，交接work/jieruiz/206/TUNE_SUBMISSION/SOURCE/COLLECTION及TUNE_SANITY。校准原字节gzip/SHA/单份归档齐。旧3211补充本次全部核验40主/37唯一+5pilot（legacy非PoT），不再运行，早先pending属历史。当前本任务无运行作业、无自动回查；PR待审不自动合并/关闭Issue，最终上传状态以TUNE_FINAL_PUBLICATION为准，Projects待既有权限同步。

下方保留历史阶段。

## Issue206四档继续优化：实现及Slurm准备

## 保持四档：扩大样本、组内Gram误差及PoT选档阈值优化（2026-10-28）

用户要求继续调整，四档/共享64/GU64/NL128/准确SDPA/正常g sigmoid不变。新tune_core/tune_run：32个TRAIN2048窗口，各在后1024位置均匀取32行，共1024观察/层（768拟合、256验证），比原256行增4倍，teacher上下文总65536token，不是65536拟合样本。依然teacher正常逐层输入后执行真实PoTW8/sharedx/GU64。

4预定方案：large_diag4（大样本、原对角风险）、large_gram4（同64通道组内Wd Gram平方偏差+精确有限NL方差）、large_gram4_threshold（再校准3个选档边界的共同PoT偏移delta=-1/0/+1，g/u各组独立）、large_gram4_threshold_bias（方差权重0.5以优先幅度偏差，启发式）。Gram只补组内交叉项，仍忽略组间偏差项，非整层/整模型最优。

每组从10 PoT指数候选选4，4初值4轮坐标搜索。阈值仍为2^(尺度指数+delta)，可用阈值比较/OR，不需浮点乘法；实际尺度值不随delta变化。偏移由TRAIN拟合，验证只报告，测试PPL不选表。近相等风险（相对1e-12）按较窄指数跨度和delta0消歧，避免无意义累加位宽。实际signed64边界继续检查。

预期新9+旧52共61 CPU/CUDA检查，校准完成才运行四片，每片BF16+旧risk4一个匹配seed+新方案有限三seed/条件NL均值三seed，共32物理/29唯一，另校准BF16。全部仅1024目标后缀非完整WT2。无权重训练/新RTL/PPA/TLM，GU仍FP32oracle。旧75执行blob不改，不重跑健康任务；执行以TUNE_SUBMISSION为准。

暂无新PPL，不宣称优于17.9215；下方历史保留。

## Issue206重新校准最终发布回执（2026-10-28）

源e8888a26的24计分/22唯一+1校准BF16已实际推送PR207，交付head 45ce805a87984be1042229bf369692d993600d6d；6关键远端文件逐字核验、完整Git对象/tree同SHA，原始JSON/gzip/log字节一致。52 CPU/CUDA；3250校准/3251全完成，不重跑。新risk4 PPL17.9215，旧共享表64.7554，仍比最接近逐元素g/u参考16.2740高10.12%；无训练/新RTL/PPA/TLM。RECAL_FINAL_PUBLICATION.json含准确回执。PRdraft/open未合并，旧3211独立补充仍运行，Projects待既有权限同步。

## Issue206：重新校准共享g/u四档有效，PPL17.9215（2026-10-28）

jieruiz/task206/PR207；最终科学源e8888a26dacec4fd5e5afe3e7dabb0e4964e3e6d、75源blob，旧72不改。3249共52 CPU/CUDA通过；3250 TRAIN校准、3251三片24物理22唯一+校准1BF16全部封存核验。原BF1613.566049四次相同，旧表正常g三seed复现。GU64、NL joint32T128、PoTW8每64x64、x共享64、准确SDPA、36层不变，无权重训练/RTL/PPA/TLM修改，1024后缀非完整WT2。

新dense2 PPL87.660860；独立risk4四档17.921546±0.266163；risk4_active18.162080±0.411486。旧共享64正常g表64.755351，最公平x共享/g-u逐元素参考16.274044，新risk4仍高10.12%，BF16仍高32.11%，不能称无损。重新校准确有效，不能再据旧表要求逐元素；仅相邻2倍无效，需要偏差+实际采样方差拟合。risk4条件均值15.870195，有偏差/方差权衡，非整LLM期望。active本次未见额外收益。

TRAIN teacher正常逐层输入后实际PoTW8/x共享GU64，16窗512/窗取16行=256观察/层，192拟合64验证；测试不选表。各层/64组g/u分别从8 PoT候选选4，离线两初值坐标拟合；目标是Wd列范数加权对角风险，忽略偏差交叉项，非全局最优/完整Wd MSE。部署仍每64一个2位档号；约42.75KiB离线指数/方案，不是PPA。sigmoid保持正常g signed8/P8。新恢复公共载体指数/最小monobit系数严格整数，上界最多55位，GU仍FP32oracle非全链bittrue。

报告qwen3/results/group_shared_20261028/RECALIBRATION_REPORT_ZH.md/RECALIBRATION_SUMMARY。校准原表SHA9a26ddde7c2ed935e652cefbadd5bf63b9f5b4f23a269775f47d38f0963987f7，gzip原字节保存，COMPRESSED_ARTIFACTS索引和archive单份原件；audit_recal.py可核验。6909/3244系数guard与44fc/3247变量名失败保留，依赖3245/3248仅未执行取消，新3251无须重跑。旧3211三片legacy独立运行，不新增自动回查。通过同PR207发布，实际以RECAL_FINAL_PUBLICATION回执为准，draft未合并；Projects待既有权限同步。

下方保留历史阶段。

## Issue206重新校准g/u共享四档：实现及Slurm准备

## 面向共享64的TRAIN独立四档校准（2026-10-28）

用户要求重新选择g/u四档。新recal_core/recal_run分别校准各层、各连续64输出组的g/u四个PoT指数。候选为训练拟合组最大幅度指数附近8档，从中选4档，不再固定四倍间隔。dense2为相邻2倍四档；risk4为有限误差拟合；risk4_active另允许选档时忽略sigmoid码严格为0的无贡献通道。g/u表不同，不在线搜索16组合，不排序，不动态生成新尺度；部署仍按最大有效幅度从4档选择最小能容纳的档（最大档不足时饱和）。

校准以BF16 teacher提供正常逐层输入，再实际执行固定PoTW8、x共享、GU64/K64采样，采16个训练512token窗口中每窗16行，共256行/层。前12窗192行拟合、后4窗64行仅报告验证；测试文本/PPL不参与表选择。sigmoid仍原g signed8/P8。目标是Wd列范数加权的逐通道平方偏差+精确joint32NL128方差，明确忽略通道/组间偏差交叉项，不冒称完整Wd输出MSE。两初值、三轮坐标离线选g/u目录；指数范围/四档和结果全部封存。实际GU恢复仍FP32oracle。

计划校准门控成功后，dense2/risk4/risk4_active各三seed有限NL128+条件均值诊断；三片各BF16及旧表正常g一个seed完整控制，共24物理/22唯一1024目标后缀计分，非完整WT2。PoTW8/准确SDPA/x groupmax/GU64/NL128不改，无训练/RTL/PPA/TLM。系数16位精确PoT与signed64归约边界不放宽，失败需保留快照另修。源75blob，测试新8+既有41共49。

尚无新PPL，执行以RECAL_SUBMISSION为准；保留旧版本。

## Issue206正常g门控最终发布回执（2026-10-28）

新36项/34唯一已实际推送PR207，交付head 90f084e147e1ef39acd277b44bc7ee29018d2576；6关键文件远端逐字核验，原始结果Git原字节核验通过。源32b5ed92，41 CPU/CUDA，3240三片完成，不重跑。GATE_FINAL_PUBLICATION.json保存回执，正常g输入不受幅度裁剪影响；原四档简单饱和未取得可接受效果，不伪称已完成共享尺度表优化。PRdraft/open未合并，旧3211独立扫描仍运行。Projects待既有权限同步。

## Issue206正常g门控36项已完成（2026-10-28）

用户确认sigmoid使用正常g：幅度裁剪前g→原signed8 field/P8 LUT，不调用浮点sigmoid。新执行32b5ed929ff14f9f1a55c22e0805bf213ccb3cc9，72源blob且旧69不改；3239共41 CPU/CUDA通过，3240三片36物理/34唯一封存核验通过，旧耦合三seed逐值复现，BF1613.566049三次一致。准确SDPA、x groupmax、PoT W8每64x64、GU64/NL联合32层T128不变；1024后缀目标非完整WT2。

五规则finite PPL（3seed均值）：max=64.755351, g_trim1=72.027506, u_trim1=118.765281, both_trim1=238.552854, both_trim4=813.535696

已分开g/u幅度饱和与真实g门控；五规则finite及条件NL均值、clip、事件密度均保存，具体结论以报告主表为准，不能只看概率增大。四档相邻4倍沿用旧逐元素表，后续需专门校准共享组尺度，尚未实现；无擅自新训练/RTL/PPA/TLM。GU恢复仍FP32oracle，硬件需等价定点field转换，不是全链路bittrue。

报告qwen3/results/group_shared_20261028/INDEPENDENT_GATE_REPORT_ZH.md，准确值INDEPENDENT_GATE_SUMMARY；交接work/jieruiz/206/GATE_SUBMISSION/GATE_SOURCE/GATE_COLLECTION与audit_independent_gate.py。旧3211三片legacy独立运行，不混计；无自动回查，不重跑新36项。通过同PR207发布，实际head以GATE_FINAL_PUBLICATION为准；PRdraft未合并，Projects待既有权限同步。

下方保留早期运行状态。

## Issue206正常g门控对照：41项通过，Slurm3240运行

用户确认sigmoid使用正常输入：从幅度裁剪前g生成原signed8 field/P8 LUT，不调用连续浮点sigmoid；g/u共享尺度与饱和不能改门控输入。科学源32b5ed929ff14f9f1a55c22e0805bf213ccb3cc9，72执行blob；测试3239共41 CPU/CUDA通过。主3240_[0-2]运行，计划36计分/34唯一，未收齐、暂无最终质量结论。原BF1613.566049复现，旧耦合控制已逐值复现前两seed，完整三seed以封存记录为准。

五规则max/g_trim1/u_trim1/both_trim1/both_trim4各三seed有限NL128及条件NL均值诊断。x只groupmax、PoT W8每64x64、GU64、NL joint32T128、准确SDPA不变。只复用原四档，没有专门重新校准尺度表；正常g输入仍signed8量化，GU恢复仍FP32oracle，不是全链路bittrue，无新训练/RTL/PPA/TLM。1024后缀目标非完整WT2。只按complete/documents SHA判完成，不拿当前单seed作结论；不重交，不修改冻结源，旧3211继续自身legacy扫描，无自动回查。

恢复work/jieruiz/206/GATE_SUBMISSION/GATE_SOURCE、collect_independent_gate.py；三片齐后audit_independent_gate.py。代码qwen3/group_shared/independent_gate.py与gate_run.py；旧报告/失败原件保持。阶段通过同PR207上传，实际head以GATE_STAGE_PUBLICATION回执为准，PRdraft未合并。Projects待既有权限同步。

## Issue206：sigmoid正常g独立输入，g/u共享幅度裁剪对照准备

## sigmoid独立读取正常g（用户2026-10-28确认）

新independent_gate.py：sigmoid从Wg累加恢复的g直接RNE到原signed8 field（步长1/8、饱和[-128,127]），再查既有P8 LUT；不经过g幅度编码的裁剪/尺度，也不调用浮点sigmoid。g/u幅度各连续64共享四档PoT，分别允许0或1/4项超出所选尺度，选最小可用档。所有元素仍参与乘积，不是丢弃异常值。

gate_run五规则max、g_trim1、u_trim1、both_trim1、both_trim4，各有限NL128三seed及条件NL均值诊断三seed；另旧耦合all_max三seed逐值回放＋每片BF16。共36物理/34唯一，1024后缀目标非完整WT2。x只用groupmax，不裁剪；固定PoT W8、GU64、NL联合32层T128、准确SDPA不变。只复用原冻结四档，尚非专门校准的新尺度表。条件均值仅定位偏差，不能当部署电路。GU恢复仍FP32数值oracle，硬件需由定点累加器作等价移位舍入得到field；本轮无RTL/PT/PPA/TLM变化。

待Slurm回执，未有新PPL；下方历史记录保留。

## Issue206共享尺度最新发布回执（2026-10-28）

新33项PoT权重澄清方案及旧固定/均值/细分层对照已实际推送PR207，科学交付head c7bf71e076c80b2e576adb243eefc2065d7d7b02；8个关键远端文件逐字核验、Git tree/对象同SHA。34 CPU/CUDA通过，33计分/27唯一。PR仍draft/open未合并，旧3211三片legacy双随机待齐。准确回执work/jieruiz/206/FINAL_PUBLICATION.json；无新PPA/TLM或训练。Projects待权限同步。

## 2026-10-28 Issue206：完整澄清方案33项完成，g/u共享64短流退化

jieruiz；PR207仍draft/open未合并，task/206-group64-scale，tmp/group64-scale-issue206-20261028；依赖PR202@fbd67c39。用户确认x及Wg/Wu输出g/u各64连续通道共享四档PoT；Wg/Wu/Wd各64x64静态PoT权重LSB。旧权重absmax/127不是PoT，4d/be/a1结果仅legacy控制，不与本轮混算。新科学源aa43d00d0b8c1c9efbd981d00e45dffd358865ce，Slurm3231共34项CPU/CUDA通过；3232四片33物理/27唯一计分、原件及SHA已核验，不重跑。后训练Qwen3-4B、准确SDPA、36层全覆盖、1024目标后缀非完整WT2，GU64/NL128三seed。

新PoT权重原逐元素PPL15.696722、只x共享16.274044、只g/u共享63.014791、全共享67.873234，BF16 13.566049。同路径W8+FP32线性/精确SiLU控制legacy13.414964→PoT13.500676，权重不是主要退化来源。条件NL均值对照g/u共享13.540598、全共享13.729721明显恢复，支持三AND稀疏事件/有限采样噪声为主；该对照不是硬件，也非整LLM期望。暂不采纳g/u共享64直接替换，不谎称质量无损。旧细联合128拍改善有限，trim1/4严重退化均保留。

GU恢复仍FP32 oracle，非全链路bittrue，无新PPA/TLM。初版a05c/3226在精确系数断言停止，3230定位CUDA ldexp一ULP误差，修复IEEE指数构造，失败原件保留。旧双随机3211_1/2/3仍运行，legacy三seed未齐；没有自动回查，不碰其他任务。报告qwen3/results/group_shared_20261028/REPORT_ZH.md及POT_WEIGHT_SUMMARY；权重/激活边界qwen3/group_shared/SCALE_CONTRACT_ZH.md；恢复work/jieruiz/206/HANDOFF和POT_SUBMISSION/SOURCE/COLLECTION、audit_group_pot.py。成果将通过同PR207上传，实际发布以FINAL_PUBLICATION回执为准；Projects待权限同步。

下方保留历史时点记录，旧ETA60～90min被实际双随机约40min/配置推翻，完整六配置分片约4小时；不可沿用旧ETA。

## Issue206澄清更新：共享激活64，三矩阵权重64x64 PoT


2026-10-28：x每token连续64通道共享一档；Wg/Wu算出的g/u各连续64通道共享一档，g与u分别选；Wg/Wu/Wd各64x64权重块共享静态二次幂LSB。前两者只从原TRAIN冻结四档选，权重LSB离线确定，不要求所有权重块共用同一指数，也不将权重指数限定为激活四档。

旧4d/be/a1实验权重LSB=absmax/127，并未强制PoT。因此结果保留为legacy权重对照，不能当本澄清方案。新pot_weight.py对原BF16每块重新量化：LSB=ceilPow2(maxabs/127)，q=RNE(W/LSB)限制[-127,127]。Wd恢复系数严格用PoT对齐，16位容器存2的幂；指数跨度超过15则明确失败，不静默舍入。代码中的整数乘系数是移位的功能参考。

新pot_run四片：各BF16、PoT W8-only精确SiLU控制、各一种lane/x_max/gu_max/all_max的finiteNL128三seed与条件NL均值三seed；片0另有legacy W8-only控制。33物理/27唯一计分。固定W GU64、准确SDPA、sigmoid真实g signed8/P8、四档与NL joint32不变；不训练。权重量化精确SiLU、条件均值均是诊断，不能宣称为电路。GU恢复仍FP32 oracle，尚非全链路bittrue。本轮无RTL/PT或TLM默认改变。

下方保留旧时点记录。

## 2026-10-28 Issue206发布确认：PR207草稿，3211扫描运行中

代码/28项验证/封存pilot已实际推送PR207（https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/207），draft/open未合并，依赖PR202分支。发布科学head d08c3732，五个关键远端blob原字节核验一致，PUBLICATION/REMOTE_VERIFICATION保存回执。Issue206已同步；主3211四片仍在运行，三seed结果及质量建议未完成，不能将阶段交付当最终验收。继续收同一任务，不重交/不改source4d6883b2、不新建自动回查。Projects待权限同步。

## 2026-10-28 Issue206：28项通过，共享尺度Slurm3211运行

2026-10-28T13:49:22+08:00；jieruiz，task/206-group64-scale，tmp/group64-scale-issue206-20261028，依赖PR202@fbd67c39。冻结4d6883b24ad27d9fa96feb84592696c374cfd808、62执行blob；28项CPU/CUDA通过，3210 pilot5项封存核验通过。正式3211四片运行，40主输出/37唯一待齐，固定W约20min、双随机60～90min；不重交，不碰3208。四次BF16同13.566049，原固定首seed15.551865复现。无新训练/RTL/PPA/TLM。

x/g/u每token连续64项各共用一档，限TRAIN原冻结四PoT。固定W GU64及双随机联合GU256分别六配置：lane、仅x max、仅g/u max、all max、all trim1、all trim4；g/u分开选，sigmoid恢复真实g，NL128/Wd/准确SDPA不动。共享尺度可将组内对齐移到归约后；质量及能效还未验收。1024目标后缀非完整WT2；GU恢复FP32oracle。成果qwen3/group_shared及qwen3/results/group_shared_20261028，交接work/jieruiz/206/HANDOFF；collect_group_scale.py收complete/documents，audit_artifacts.py --write-final须四片齐才运行。SOURCE/SUBMISSION/RECOVERY含SHA；源码包仅project_archives/group64_scale_issue206_20261028一份。PR待创建，本地阶段成果尚未发布，实际状态以后续PUBLICATION为准；Projects待权限，无定时。

## 2026-10-28 Issue206：每64元素共享四档尺度实验准备

用户要求x及非线性g/u每64个数共享一个尺度，限于原先规定四个二次幂。jieruiz，新独立task/206-group64-scale，目录tmp/group64-scale-issue206-20261028，依赖PR202@fbd67c39，不改旧冻结扫描。Qwen3-4B后训练、准确SDPA；固定W GU64及双随机联合GU256分开测试，NL128/Wd固定W8不变。六配置lane/x_max/gu_max/all_max/all_trim1/all_trim4，各三seed；g和u分别使用各自冻结表，sigmoid恢复真实g。

选档采用64路阈值超限计数：max零超限，trim1/4允许最多1/4项裁剪，不生成新的尺度、无排序、无数据拟合。目标为减少逐元素档号与对齐，不能默认精度或PPA无损。源码qwen3/group_shared；当前本地实现和AST检查完成，GPU/CPU实际验证与Slurm尚未提交，无新PPL。计划先28项核心检查和32目标pilot，后四片40物理/37唯一1024目标后缀（非完整WT2）。执行以work/jieruiz/206/SUBMISSION为准，未有回执不声称运行；不新建定时、不碰健康3208或其他任务。更新时间2026-10-28T13:39:38+08:00。

## 后续执行

冻结当前提交，打包qwen3的必要Python和group_shared/config.json，生成SOURCE manifest，上传个人服务器路径pbit-qwen3-group64-scale-20261028-issue206。Slurm验证+pilot依赖成功后主数组四片；先验6lane控制须复现PR202，BF16须13.566049。只用complete/documents/sidecar SHA认定完成，结果40主分数/37唯一；pilot5份独立。未提交前无作业ID，提交后记录SOURCE/SUBMISSION和准确命令。

GPUruntime沿Issue201个人venv，服务器路径/权重/语料与TRAIN表按config及prepared校验，无新下载或训练。用户面积规则raw×.81只适用后续面积，本轮无RTL/PPA；原算法GU恢复仍FP32oracle，全链路bittrue未验收。Projects缺read:project待同步。PR base应为task/201-dual-gu-short，待实际创建更新；不合并。

## 恢复命令（已有作业，不重新submit）

使用bundled Python运行work/jieruiz/206/collect_group_scale.py，再运行audit_artifacts.py。四片全部封存后才加--write-final，生成FINAL_SUMMARY；主40输出/37唯一，pilot5份独立，28功能检查。g/u/X每组mixed_scale_groups必须为0；main36层各8次/17400输入词，1024目标SHA与PR202一致。固定/双随机lane三seed必须逐值复现旧15.364688/15.895140均值。

报告对比仅x、仅NL、全共享，区分max与有意裁剪；聚合clip、事件密度、零事件和逐层NMSE平均（不可伪称全局功率加权NMSE）。只测准确Attention，无训练或新PPA。旧Cim/计数PPA范围不因共享策略改变而自动验收。

## 本轮后续执行入口

新PoT权重3232已完整收齐，无需重交。audit_group_pot.py复核33份/27唯一。旧双随机3211仍在运行：collect_group_scale.py按complete/documents收集，再audit_artifacts.py；四片齐才--write-final。它的权重是legacy非PoT，不代表新澄清目标。不要重跑既有pilot/mean/grid/PoT验证；不新增监控。
