## Issue206：64共享完整WT2三seed已完成（2026-10-28）

同后训练Qwen3-4B/准确SDPA，窗口2048-stride1024，每seed299077目标、292窗，各恰一次；所有36层及前缀FFN替换。BF16=11.537160；原G64/B4三seed=14.862785, 14.893867, 14.895327，均值14.883993±0.018381，相对BF16+29.01%。x64/固定PoTW8/GU64/NLjoint32T128/正常g signed8-P8/冻结e888 risk4不变，无训练、无新拟合/RTL/PPA/TLM默认变化；GU仍FP32oracle非全链bittrue。与旧后缀17.92的绝对差异不能解释为质量改善。

科学源5d49ea97502d2c11bf0745d50689b4c558c384d1，86文件旧82不变；CPU3307共77项（10跳过）、GPU3308旧后缀准确回放及首尾窗通过；3309全部18片/36分片分数封存，1BF16+3seed完整PPL，源/配置/模型/语料/目标/36层/NLL/SHA核验。RNG按seed+窗口SHA键固定且不依赖分片数量，与旧后缀连续RNG分开标注。报告qwen3/results/group_shared_20261028/FULL_WT2_G64B4_REPORT_ZH.md及SUMMARY；W/FULL_WT2_SOURCE/SUBMISSION/COLLECTION、收集审计脚本可恢复。无本轮运行作业，不重跑、不自动回查；PR207未合并/Issue开放，实际上传以FULL_WT2_FINAL_PUBLICATION为准，Projects待既有权限同步。

## Issue206完整WT2阶段：第一个seed已齐

3309首六片/seed0已封存并核验全部299077目标、36层与SHA；本轮BF16=11.537160499310174，G64B4seed0=14.86278468624107（+28.8253%）。其余两seed仍运行，不能把单seed当三seed最终均值。所有配置与原冻结目录不变；不是旧1024后缀。准确回执FULL_WT2_COLLECTION_5d49ea97.json；最终等待18片，约还需9分钟；不重交，不自动回查。

## Issue206完整WT2门禁已通过、3309运行中

CPU3307共77项（10 CUDA跳过）通过；GPU3308四个计分文件封存，旧1024后缀BF16=13.566049199388152/G64B4seed0=18.20000779048508准确复现，首尾完整窗仅门禁，不是完整PPL。86源文件含旧82字节不变，模型/文本/tokenizer/冻结表SHA核验。正式3309共18片、每seed六片，6GPU并行；按当前约6秒/窗，预计15～20分钟完成三seed，不自动回查、不重交。完整PPL待全部299077目标覆盖核验后报告。

## Issue206：64共享完整WT2已提交Slurm

科学源5d49ea97502d2c11bf0745d50689b4c558c384d1；CPU 3307→GPU门禁3308→18片数组3309，最多6GPU并行。匹配BF16+G64B4三seed，context2048/stride1024，每seed299077目标；准确SDPA/原冻结四档/采样数保持。新PPL未完成，不重交健康任务、不新建定时。回执FULL_WT2_SUBMISSION_5d49ea97.json，结果/home/Hongjie_Zeng/projects/pbit-qwen3-group64-scale-20261028-issue206/results/5d49ea97502d/full_wt2。

## Issue206：64共享完整WT2评测准备（2026-10-28）

用户授权补测当前G64/B4完整WT2，准确SDPA；x64/固定PoTW8每64x64/GU64-K64/g-u分别64共享四档e888 risk4/正常g signed8-P8/NLjoint32T128均不变，不训练不重新选表。匹配BF16及三个随机seed，context2048/stride1024、299077目标每个恰计一次，无BOS/chat/cache；全部36层和窗口前缀均替换。每seed六片、最多六GPU并行；CPU和GPU门禁后正式提交，实际作业以FULL_WT2_SUBMISSION为准。门禁复现旧后缀BF16/G64B4并检查首尾全窗；门禁分数不当完整PPL。

新完整协议使用seed+全局窗口号的SHA256随机键，不反复重用同一窗口种子，分片数量不影响同一窗口随机流。不同于旧后缀连续消耗RNG的调度；不能要求完整PPL等于旧17.92。GU仍FP32恢复oracle、非全链bittrue，无RTL/PPA/TLM更改。原推荐不变；沿Issue206/PR207，未合并，Projects仍待既有权限同步。

## Issue206分组/档数扫描最终发布回执（2026-10-28）

主结果已实际推送PR207，交付head b402cd323f89daf8b8a083d0cdeb1fe967a1cc71；6关键文件远端原字节回读、Git对象/tree一致，115份本轮原件/压缩索引Git字节核验。G16/B4最佳PPL16.999183±0.118233，原G64/B4=17.921546。六组36物理/25唯一配置seed（另3门禁）全部完成；71 CPU/GPU、源/配置/模型/数据/目标/36层及SHA核验。只改g/u分组/档数，x64及其余保持。候选索引单独保存，CURRENT_RECOMMENDED和TLM/RTL默认不变。仅1024后缀、GU FP32oracle、无新PPA；PR未合并/Issue开放，Projects待既有权限同步。本轮无运行作业。准确回执GROUP_SWEEP_FINAL_PUBLICATION.json。

## Issue206：g/u共享数量/档数扫描完成（2026-10-28）

用户要求x保持64共享；六组G64/32/16×B4/8全部三seed完成。最好G16/B4 PPL16.999183±0.118233，原G64/B4为17.921546；同轮BF1613.566049。各组均值：g64_b4=17.921546, g32_b4=17.647903, g16_b4=16.999183, g64_b8=17.659725, g32_b8=17.574396, g16_b8=17.370886。均仅1024后缀目标，不是完整WT2或任务准确率；不能宣称无损。输入x四档/共享64、PoTW8每64x64、GU64、正常g signed8-P8、NLjoint32T128、准确SDPA、所有36层/前缀均不变。

执行源df758fba20949b8493c75394afb2c7ae560b06e4，82源/旧75字节不变。四档继承成功e888；缩小子组复制parent64目录，八档嵌套补齐且最高尺度不变，无新TRAIN拟合或TEST选表。CPU71（10跳过）/GPU71通过；3291/3292/3293全部完成，主36物理/28标签/25唯一配置seed，另3门禁独立列。SHA、36层/目标/NLL/档号同组核验通过。报告GROUP_SIZE_LEVELS_REPORT_ZH/JSON，候选GROUP_SWEEP_BEST_CANDIDATE.json；原CURRENT_RECOMMENDED和TLM/RTL默认不自动替换。每活动FFN标签状态从G64/B4的76B变化到最佳304B，仅结构计数，无新PPA；GU仍FP32oracle非全链bittrue。

无本轮运行作业；准确上传状态以后续GROUP_SWEEP_FINAL_PUBLICATION为准，未合并/不关闭Issue，Projects待既有权限同步。下方保留历史。

## Issue206分组/档数扫描已提交Slurm

科学源df758fba20949b8493c75394afb2c7ae560b06e4；CPU 3291、GPU门禁3292、6片数组3293。源82文件已传输SHA核验，先CPU再GPU再正式数组；结果目录/home/Hongjie_Zeng/projects/pbit-qwen3-group64-scale-20261028-issue206/results/df758fba2094/group_size_levels。当前结果未完成，不重交健康任务，不自动回查；提交回执GROUP_SWEEP_SUBMISSION_df758fba.json。

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

## 2026-10-28 Issue201最终发布确认：PR202已ready

最终结果已实际推送，科学成果提交4134a3629bf2d08610a303ed6e13057f562fd441；PR202 ready/open、待审未合并（依赖PR174）。40份主计分/37唯一、108原始JSON与sidecar的Git字节SHA全部一致，八个关键远端blob回读一致。FINAL_PUBLICATION.json含准确提交、回读SHA和Issue201评论链接；不是此前草稿/运行中状态。Issue验收项已更新，保持open待审，不合并；Projects缺read:project待同步。

核心结果：联合256拍PPL15.8951±0.1856，固定W同T15.2405±0.2481（+4.30%）；原BF1613.566049（+17.17%）。仅1024目标后缀、非完整WT2；未训练，无新PPA，GU恢复仍FP32oracle。当前用户要求的扫描和报告已交付，无需再收3200或重交。后续可审阅该PR，若扩充完整WT2/共享W源/Ka×Kw扫描须显式作为后续研究；不建立新自动回查。

## 2026-10-28 Issue201：Wg/Wu双随机40项已完成核验

2026-10-28T09:51:41+08:00；负责人jieruiz，task/201-dual-gu-short，PR202依赖未合PR174，目录tmp/dual-gu-issue201-20261027。Slurm3200四片各10份完成，40物理/37唯一主计分、三seed齐全；pilot4份独立。58源blob、模型/数据/token/目标/TRAIN表、documents/sidecar SHA与36层各8次/17400词覆盖核验通过，18项CPU/CUDA通过。此前运行中/单seed数字仅历史；未重跑。

后训练Qwen3-4B、1024目标后缀（非完整WT2），BF16四次13.566049。T32/64/128/256固定W均值15.6137/15.3647/15.6853/15.2405，W-IID76.2007/25.5600/18.8150/16.8902，A/W联合29.9061/18.3942/16.5566/15.8951。联合256 std0.1856，相对同T固定W+4.30%、BF16+17.17%；不能称无损。仅Wg/Wu权重取随机，Wd固定W8、原随机NL128、准确SDPA不变；联合分配同时换A/W层数，W独立未共享。GU恢复FP32oracle，非全链路bittrue，无训练/RTL/PPA。256是GU长度非整token周期。

成果qwen3/dual_gu、qwen3/results/dual_gu_20261027/REPORT_ZH.md、FINAL_SUMMARY/RAW_INDEX；work/jieruiz/201/ARTIFACT_AUDIT与HANDOFF。科学源2cd6d360不变，b0仅诊断/测试补丁。当前本地最终汇总完成，待更新同一PR202；正式发布以FINAL_PUBLICATION回执为准，不合并、不关闭Issue。旧控制器3200记录已失效，完成依据封存文件，未虚报Slurm历史退出码。无新定时；Projects缺read:project待同步。

## 2026-10-28 Issue201发布回执：PR202草稿，扫描继续

2026-10-28T00:48:34+08:00，身份jieruiz。源码与阶段报告已实际推送到workspace的task/201-dual-gu-short，PR202（https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/202）为draft/open、未合并；base为尚未合入的PR174分支。首次发布head98530eaa，九个关键远端blob原字节回读一致，PUBLICATION/REMOTE_VERIFICATION保存回执。Issue201验收项只勾选已通过部分，主扫描及最终三seed对比仍未完成，Projects缺read:project待同步。

Slurm3200_[0-3]保留，不重复提交。18项验证、pilot封存完成；主协议未封存观测及剩余流程见同目录HANDOFF和REPORT。当前不是256拍质量验收、完整WT2、训练或硬件PPA结果。后续收齐四片后运行audit_artifacts.py --write-final，更新同一PR，不另建任务或重跑健康作业。

# Issue201：Wg/Wu双随机扫描运行中，尚无最终结论

## 2026-10-28 Issue201：仅Wg/Wu双随机短流扫描运行中

负责人jieruiz；task/201-dual-gu-short，目录tmp/dual-gu-issue201-20261027，依赖PR174@b41ee008（未合并）。科学执行2cd6d360不可变；18项CPU/CUDA验证通过（3205仅验证），pilot3199完成。正式Slurm3200_[0-3]健康运行，T32/64/128/256，各固定W、W-IID、联合2D分层三seed。后训练Qwen/Qwen3-4B；Wd固定W8、NL固定四档/联合32 T128、准确SDPA不改，全36层及前缀覆盖。不是训练或PPA。

主协议8×128=1024目标后缀，不是完整WT2。未封存主观察：BF16四片同为13.566049；固定W T64三seed逐值复现PR174。W-IID seed0 T32/64/128/256为77.9953/25.4284/18.1963/16.6126，其他seed/联合待齐，不能宣称256已足够。权重P=abs(W8)/128，无额外量化，独立W源；联合Ka×Kw=8×4/8×8/16×8/16×16，条件二项CDF压缩有数值精度边界，无Gaussian。GU仍FP32恢复oracle，未验收完整bittrue。2cd旧diagnostics front_T/K写死64，顶层gu_samples等为准；b0a仅报告/验证修复，不重跑。

成果qwen3/dual_gu、qwen3/results/dual_gu_20261027；交接work/jieruiz/201/HANDOFF.md，SOURCE/SUBMISSION/COLLECTION及RECOVERY可恢复。旧3197类型fixture失败、3198依赖未运行已取消，健康3199/3200未取消。不重复提交；恢复先收complete.json/documents SHA，再核40物理/37唯一及三seed差异。当前阶段PR待创建，未推送/未合并；实际发布以PUBLICATION.json及Issue201为准。Projects缺read:project待同步，无新定时。更新时间2026-10-28T00:42:42+08:00。


基线分支task/173-and-direct-wd，b41ee00835b1ae385b2a7c3654df67df26eff3e3。当前本地实现/18项验证/pilot已完成；主扫描未封存。下一步仅收3200，不重交、不改科学快照；最终更新同一Issue/PR。项目看板尚未同步。

---
以下保留本人历史状态，不能当成本任务实时结论：

## Issue173短流三路AND结果核验完成（2026-10-24）

Slurm2891三片封存完成，48份/46唯一配置、documents/sidecar原字节SHA、36层全前缀、每片27项预检通过。执行c44c2edc不变；同轮BF16及原尺度mean/IID64三seed与旧结果逐值一致。Qwen3-4B后训练、准确Attention、8×128后缀，非完整WT2。前级W8/x固定四档共享64 T=K64；后级4×2×4联合32区间，各1/2/4次。整体减半固定四档[S/2,S/8,S/32,S/128]的mean/IID64/联合32/64/128 PPL为13.4034/27.4020/103.8940/21.8821/15.3647；BF16=13.5660，最佳128仍高13.26%，不能称无损。gate/up恢复仍FP32参考；无训练/PPA。

报告qwen3/results/and_direct_20261024/short/REPORT_ZH.md及SUMMARY/RAW_INDEX。原件project_archives/qwen3_and_direct_20261024/short-sealed-2891.tar.gz，服务器与本机SHA均e498dc55cfe0dea649f52c3c4635272f32af33d67114b1270328f69ca9587467。不重交、无新增定时。本人jieruiz，task/173-and-direct-wd，沿用Issue173/PR174待审未合并；发布以SHORT_PUBLICATION.json为准，Projects缺read:project待同步。FSM另属Issue175/PR176，不混用结果。

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

## Issue173 g/u多档扩展准备（2026-10-24）

用户授权接续同Issue/PR174，新增B2/B4/B8固定范围幅度编码、sigmoid整数真实尺度恢复、Wd同指数部分和移位后合并。旧执行与结果不改。5项新本地检查通过，CUDA1项待Slurm；新增45份后缀PPL计划，非训练。下一步冻结并提交multiscale.sbatch，执行/作业ID以MULTISCALE_SUBMISSION.json为准，未有回执前不得重复声称远端已运行。

## Issue173发布回执（2026-10-24）

PR174已转ready、待审未合并；结果提交898ba797，23个文件远端原字节核验一致，Issue173已同步。Slurm2881已退出队列，五片封存核验完成；无定时/健康任务遗留。FINAL_PUBLICATION.json记录回执，Projects未同步。

## Issue173有限AND直连Wd完成（2026-10-24）

Slurm2881五片完成，执行098c7a00db27dded1b7047dc5828871e4b057f70。每片12项检查通过，包括GPU有界整数GEMM与逐拍事件累加参考。27份封存计分/23唯一配置、documents与sidecar SHA、36层全前缀覆盖通过。后训练Qwen3-4B，8×128=1024目标后缀，非完整WT2；准确Attention。BF16五次完全一致13.566049，W8 13.414964；旧8位均值z再编码三seed13.428421，直连均值原尺度13.517797、有限系数13.498204。有限三流直连T64/256/1024/4096三seed分别8949057.252807/7735.004324/30.692997/14.937278。首层平均AND概率0.000910389，T64零事件95.02%；不能用旧均值PPL支持短流直连，也不能认为8位门限只需256次就充分。

新路径：幅度8+符号/驱动signed8/概率8+true-one，独立三流AND事件跨Wd输出共享；Wd固定W8，有限恢复系数16位、signed52输出累加、整数RNE BF16。无z重新统计/定标/采样。gate/up恢复仍FP32参考，无训练、RTL或PPA。建议先解决SgSu和稀少事件问题，再冻结训练硬件前向；勿把当前T64直连直接当可用训练配置。

负责人jieruiz/task/173-and-direct-wd，目录tmp/qwen3-and-direct-issue173-20261024，PR174依赖PR172，待审未合并。报告qwen3/results/and_direct_20261024/REPORT_ZH.md；归档project_archives/qwen3_and_direct_20261024/sealed-2881.tar.gz，SHA1f87f6f00a9ffda47ca03b0bca0d55d2236e6fe99cacd5c6bf88f9eed4d54309，RECOVERY.json包含源包恢复。无运行任务或新增定时；Projects未同步。结果远端发布以FINAL_PUBLICATION.json为准，勿重交。

## Issue173：有限三流AND直连Wd（2026-10-24）

负责人jieruiz；branch task/173-and-direct-wd；base PR172@38de0796，依赖task/171-nonlinear-width。独立目录tmp/qwen3-and-direct-issue173-20261024。用户授权模拟非线性随机流直接进入固定W8，在输出端累加；无z重编码。A8+符号/signed8 sigmoid驱动/P8+true-one；独立三流，事件跨Wd输出共享，定点恢复系数16位，输出signed52与整数RNE BF16。gate/up恢复仍FP32参考，不是全链bittrue。

本地9项功能通过，CUDA1项待Slurm；fixed_scale runner因本机缺transformers未运行，服务器必须通过后才启动PPL。计划8段×128目标后缀、全36层，BF16及旧路径/条件均值控制，T64/256/1024/4096各3seed。源码与SHA冻结后Slurm提交，当前未提交。无训练/RTL/PPA，无看板同步权限核验；发布回执待补，不能写成远端完成。

## Issue171发布回执（2026-10-24）

PR172已转ready、待审未合并，科学提交7a8b5e6e；23文件远端原字节回读一致，Issue171已同步。28项结果核验完成，Slurm2880已结束；无定时、无待运行任务。原始结果和源码包归档未解压复制，RECOVERY.json记录位置/SHA。Projects未同步。

## Issue171非线性位宽初筛完成（2026-10-24）

Slurm2880已结束，执行71cb58d0；28/28封存documents/sidecar SHA、36层全前缀覆盖通过。后训练Qwen3-4B，16×128=2048目标后缀，不是完整WT2。BF16 12.791943，W8原非线性12.584887；g/u幅度6/7/8/10/12分别13.041899/12.607359/12.607722/12.581222/12.577710；组合8/8/8为12.662423(+0.616%)，8/10/8为12.602765(+0.142%)。固定四档T64矩阵三seed：原非线性12.599698±0.016841，8/8/8为12.673273±0.066138(+0.584%)，10/10/10为12.586853±0.026572(-0.102%)。幅度位不含符号，驱动含符号，概率另true-one；TRAIN固定PoT尺度2..256，非线性只有条件均值，无有限AND采样。矩阵恢复仍FP32参考，不是整链bittrue/PPA或训练。

负责人jieruiz/task/171-nonlinear-width，PR172依赖PR169，待审未合并。报告qwen3/results/nonlinear_width_20261024/REPORT_ZH.md；原件project_archives/qwen3_nonlinear_width_20261024/sealed-2880.tar.gz，SHA5ea60da95c0d186f5ac1b20b68ff4348fb04107fb411340a93762cda2b889ac4，成员索引RAW_INDEX。无运行任务/定时，不重交；候选8位幅度+符号/驱动8/概率8，10位留余量，下一步有限AND噪声与全链有限恢复仍待验证。远端发布以FINAL_PUBLICATION.json为准，Projects未同步。

## Issue171 Qwen3非线性位宽初筛（2026-10-24）

负责人jieruiz；task/171-nonlinear-width；目录tmp/qwen3-nonlinear-width-issue171-20261024；base PR169@1d16d8cc，拟PR base task/168-qwen3-fixed-scale，依赖其推理源码。Slurm2880已运行，执行71cb58d0冻结；服务器6项预检通过，28项后缀PPL（16×128目标），36层全部替换。非线性使用有限码/LUT的条件均值，不是有限三流AND采样；矩阵恢复仍为FP32参考。W8单因素扫描及固定四档T64三seed组合；无训练/RTL/PPA。模型/数据复用已验证manifest。成果root与包SHA见SUBMISSION.json。完成后核验complete.json的documents SHA、28唯一配置和层覆盖，勿重复提交。Projects未同步；发布回执待补。

## Issue168已发布回执（2026-10-24）

固定四档18项后训练Qwen3-4B后缀PPL已通过PR169发布，科学提交572afbbbc75551ecab1136e5f3391e15c8bfe748；23改动文件GitHub原字节回读一致。PR已转ready、待审未合并，Issue168已同步；没有运行中本任务作业、没有新定时。原件压缩归档与44成员SHA通过后已回收解压副本，RECOVERY.json可恢复。执行679f370f/Slurm2879不变；报告qwen3/results/fixed_scale_20261024/REPORT_ZH.md，回执work/jieruiz/168/PUBLICATION.json。Projects未同步，不能把后缀当完整WT2。

## Issue168 Qwen3-4B固定四档试测完成（2026-10-24）

jieruiz/task/168-qwen3-fixed-scale，PR169；执行679f370fa09199b67052ae6f71c0811873f4ec7e，Slurm2879已结束、18项封存/原字节SHA/36层覆盖通过。Qwen/Qwen3-4B后训练revision1cfa9a7208912126459214e8b04321603b3df60c；准确Attention，W8/A8共享64、T=K分层；无训练。TRAIN16×512，W8连续+动态32两路径分别覆盖后冻结每层每64通道x/z四档S/S4/S16/S64；测试不在线absmax。

这是batch1向量化32段×128=4096目标后缀，不是完整WT2或旧cached结果。同轮BF16 10.685883；W8-only10.525384、固定mean10.498386；三seed动态32 10.533212±0.018421、固定32 10.551331±0.071962、动态64 10.517682±0.010649、固定64 10.502135±0.028439、固定x32 10.559898±0.015856。固定相对动态32为+0.172%、64为-0.148%；固定seed波动更大，不能声称更优。BF16与替换FP32内部算术不同，下降不单独归因尺度。固定2/8档、W4/W6、任务准确率及联合Attention未测。

报告qwen3/results/fixed_scale_20261024/REPORT_ZH.md，实际固定表CALIBRATION.json；归档project_archives/qwen3_fixed_scale_20261024/sealed-2879.tar.gz，SHA ca09d749353b911aa372b80b3f6aacdebe470bc7bc41be1ee4f2020814135679。19服务器测试及17本地静态测试通过，原冻结快照未改，勿重交。PR169源码已推，结果发布以work/jieruiz/168/PUBLICATION.json为准；未合并/不关闭Issue，Projects未同步。

# Issue168 固定尺度试测

2026-10-24，jieruiz，task/168-qwen3-fixed-scale；PR base task/158-qwen3-4b-posttrained@98954637。源码准备，未运行/未发布，见work/jieruiz/168/HANDOFF.md。

# Issue158：Qwen3-4B非Base替换（2026-10-23）

22:45 CST实际提交：执行e174d91，44源SHA/提取源5合同通过，CPU2869 RUNNING镜像下载，GPU2870 afterok依赖等待；原生CPU2计分+tiny重载已过，随机CPU/GPU门槛未完成。PR160 draft/open未合并，源已推送；最新远端原字节核验见work/jieruiz/158/REMOTE_VERIFY.json。ROOT pbit-qwen3-stochastic-nonbase-20261023-issue158，包SHA7d840ad5f5b09bad8419c73d88b1e23499e02f7f62f90f81ece789c820120f65，不改快照、不重交。无新PPL，旧Base结果不覆盖；新BF16完整两次+13后缀在GPU依赖任务内，完整概率WT2未提交。分工Issue157评论已成功，Projects待权限；未新建定时检查。下一步查2869/2870与HANDOFF，收齐新模型小原件后独立复算，不用Base硬编码验证器。

负责人jieruiz；task/158-qwen3-4b-posttrained；独立tmp/qwen3-4b-posttrained-issue158-20261023；依赖PR147@357db588/base task/144-qwen3-stochastic。用户明确改用Qwen/Qwen3-4B，固定revision1cfa9a7208912126459214e8b04321603b3df60c，hf-mirror，旧Base证据保持。仅换模型，原架构13配置后缀；新完整BF16两次精确重放、TRAIN重新校准、token独立绑定。PPL不加聊天模板/不生成thinking；不使用2507、不做1.7B或完整概率WT2。5本地合同测试、compileall/diff通过，CPU/GPU尚待Slurm。正式qwen3/posttrained，个人新ROOT pbit-qwen3-stochastic-nonbase-20261023-issue158。PR尚未创建/作业尚未提交；冻结后追加ID和SHA。Issue157 SparQ属amlink1219，本任务不接管；Projects待权限。

# Issue144：Qwen3概率架构迁移（2026-10-23）

22:00 CST发布闭环：结果b8cc1daa已推送，177个GitHub原字节回读、77提交原件SHA通过；PR147 ready/open、未合并，Issue144清单已更新但未关闭。26项已完成，无在跑作业；本对话heartbeat qwen3已实际删除。最终回执work/jieruiz/144/FINAL_PUBLICATION.json；下一步审阅，不自行跑完整WT2。下方“准备发布/运行中”为历史。

21:50 CST：全部26/26后缀配置完成并独立核验，Slurm2828/2829结束，两complete.json齐全，执行8c35145不改。1.7B BF16/FFN/screen/rejection/winner=7.590088/7.666993/8.067234/8.249476/8.091915，4B=6.331575/6.365253/6.676899/6.810810/6.700177；随机三seed、4096目标，不是完整WT2。78小文件/37 sidecar/27源码/26全层覆盖和17篡改负例通过，成果qwen3/results/stochastic_20261023/{REPORT_ZH.md,SUMMARY.json,checkpoints/complete}，包SHA a3d0df3f043d4a1fee23f9da547d585bcde0f28e9c325d665880fdd5c1a2ace3。完整预算约156 GPU小时，未提交。负责人jieruiz/task144/PR147/base task136，目录tmp/qwen3-stochastic-issue144-20261023不变；当前准备最终发布与停表，实际回执见work/jieruiz/144/FINAL_PUBLICATION.json。不合并、不关闭Issue，Projects权限待同步。下方运行中均为历史。

2026-10-23 20:54 CST用户要求“请做完全部方案”。继续已冻结两模型各13配置共26项4096目标后缀，不重复健康作业、不扩大为完整WT2；目前日志16/26已完成（1.7B拒绝seed2运行，4B拒绝seed0运行），2828/2829均RUNNING，无错误，未收取的阶段数字不作为正式结果。依据OpenAI Docs官方定时说明通过应用工具实际建立本对话heartbeat id=qwen3，名称“完成Qwen3全部概率方案”，ACTIVE每10分钟，限定收齐26项后核验/汇总/同PR147发布并通知，随后删除定时；无变化保持安静，失败/新权限或范围修改需报告。旧基线同名id曾删除，本次是新建收尾检查。需要本机及桌面应用运行以执行本地SSH/发布，服务器Slurm独立继续。发布源仍8c35145不改，最新科学结果672ad88；此前head5ce00f6的94文件GitHub逐blob原字节通过。

20:33 CST：FFN-only三seed两模型均完成并独立核验。1.7B平均7.66699268±0.00865026（+1.01322%），4B6.36525314±0.00299026（+0.53191%）；均4096目标后缀，配对BF16分别7.59008810/6.33157462。共8病例/17签名JSON已收取，模型/源码/原文/token/配置/校准/全部目标覆盖通过；checkpoints/ffn包SHA53d085047ee27025f2ef42bf04c2ee7c863ae5cb09dcd4eab733c3557af8ab63。2828/2829正跑screen-exact+FFN，后续拒绝128/赢家1024联合仍待结果；完整候选WT2未提交。55文件启动交付远端原字节验证通过；本次FFN结果同PR147继续发布，不合并。原运行源8c35145不改。

20:25 CST更新：8c35145冻结源已发布，PR147 draft/open未合并。CPU2827通过；GPU2828/2829运行各模型首个FFN seed0，不重复提交。两真实模型原生SDPA bitwise、GPU核oracle/分布/仲裁/cap、原始完整BF16精确重放均通过，TRAIN校准完成。后缀4096目标BF16分别7.5900880974/6.3315746169，概率增量尚未完成；13配置/模型、三seed，完整候选WT2未提交。首批26原件/11sidecar/执行源及模型数据绑定/覆盖通过，8篡改负例通过。报告qwen3/results/stochastic_20261023/REPORT_ZH.md，恢复命令与ID见HANDOFF顶部。收取/验证工具为后加不修改冻结源。canonical长期记忆与根同字节同步，未新增定时，Projects缺read:project。

负责人jieruiz；task/144-qwen3-stochastic；base task/136-qwen3-bf16@0829b9c，依赖PR137/Issue141固定执行7a286ec。独立稀疏tmp/qwen3-stochastic-issue144-20261023。已实现Qwen3 QK-Norm/GQA/非等Q投影适配、固定W8 B4/T32/K32 FFN、max4+拒绝128/赢家1024、全层计分审计、TRAIN独立标量校准、13配置每模型4096目标三种子后缀先导。仅语法与diff检查通过，CPU/GPU门槛和PPL尚待Slurm，不能称结果完成。个人新ROOT /home/Hongjie_Zeng/projects/pbit-qwen3-stochastic-20261023-issue144；既有权重/venv只读复用。正式实现qwen3/stochastic；HANDOFF work/jieruiz/144/HANDOFF.md。下一步冻结源、CPU预检通过再GPU；PR未建、未合并，Projects缺read:project待有权限成员同步。

# Issue136：Qwen3-1.7B/4B Base BF16基线已提交（2026-10-23）

最终发布：科学结果60d6947已上传，35远端文件原字节核对和11已提交原件SHA通过；PR137实际ready/open、未合并，Issue136待评审，定时qwen3已实际删除。FINAL_PUBLICATION.json和Issue评论6364341645为回执；不再等待结果或重复提交。

19:50后结果核验：两模型基线完成，1.7B PPL8.3673395166、4B 7.0386116013，均299077目标/292窗口；GPU16.92/32.92秒。源码968046f不变；11服务器原件SHA、模型/数据/配置/源绑定、完整覆盖和NLL重放、10损坏负例通过。报告qwen3/results/bf16_20261023/REPORT_ZH.md，HANDOFF顶部是最新状态；2797失败/2798取消/2799恢复历史保留，无本任务运行GPU。PR137结果发布/待审及停止heartbeat qwen3以FINAL_PUBLICATION.json回执为准，不合并、不重跑、不动其他任务2804/2805。Projects仍缺read:project。下方为历史准备状态。

19:20 CST更新：2797在1.7B校验后遇4B镜像RemoteDisconnected失败，2798依赖取消；恢复2799只重试4B下载，2801_1依赖其成功。2800_0已完成1.7B，日志PPL8.36733952/299077目标/16.9s，结果及SHA sidecar一致，待本地收取与独立汇总。原源码968046f不变、失败原件保留。用户要求的heartbeat qwen3已启用每10分钟检查，结果验证完成后停用。PR137仍draft/open；详情RECOVERY_20261023.json和HANDOFF顶部。下段为先前提交时点。

负责人jieruiz；task/136-qwen3-bf16；base pbit-tlm-attention-details-20261016@6966739；独立稀疏tmp/qwen3-baseline-issue136-20261023。按用户要求使用hf-mirror固定revision，未修改FFN/Attention。源码968046f已上传冻结快照；CPU2797已通过隔离环境/计分覆盖/原生Qwen3保存重载，镜像下载中；GPU数组2798已提交依赖afterok2797、暂无新PPL。服务器train/test原字节SHA通过。成果qwen3/，交接work/jieruiz/136/HANDOFF.md。API已按原SHA发布，PR137为draft/open未合并；下一步监测下载和两个GPU BF16完整WT2（2048/1024），归档真实结果后转审。Projects本轮实测缺read:project待同步。旧模型/环境/并行任务未改。

# Issue55第八轮：七项阶段成果审核通过（2026-10-23）

负责人jieruiz；review/55-pr-round8；base e8705765；独立稀疏目录tmp/pr55-review-round8-20261023。119/120/122/125/126/127/130按限定范围通过，359测试中358通过、1个Windows符号链接测试跳过；原件与GQA发布源码映射复核通过。45条台账/964行是原任务记录并集，无新硬件实验。修复未公开旧commit导致的新检出审计失败；不改旧manifest。116/123保持暂停，不启动全尺寸/GPU/EDA。成果work/jieruiz/55/round8/REVIEW_ZH.md；集成PR发布、实际合并及目录回收以Issue55最终回执为准。待用户工艺环境SS/T32最小PPA；Issue107独立进行，避免重复任务。

# Issue129 SRAM与DRAM节省总结 2026-10-23

负责人jieruiz，task/129-memory-savings-summary，base pbit-tlm-attention-details-20261016@e8705765。独立稀疏目录tmp/memory-savings-issue129-20261023。7页Word与正文已完成，20来源/8封存情景复算、64检查与7页目视通过；无新实验。成果architecture_tlm/memory_savings_20261023，交接work/jieruiz/129/HANDOFF.md。已通过PR130上传待审，未合并；发布字节核验与原字节属性修复见PUBLICATION.json。暂停的116/123未恢复。Projects查询缺read:project，待同步；Issue/PR已更新。

# Issue68：10个已结束工作副本回收与恢复复核（2026-10-23）

负责人jieruiz；review/68-cleanup-receipt-20261023；base pbit-tlm-attention-details-20261016@46804fb3；独立稀疏目录tmp/cleanup68-review-receipt-20261023，仅用于回执交付。已实际回收10目录1,182,605,540 B，64独有文件和3增量bundle保留并验证；模型/仿真原件/活跃任务保持。35记录157原件26归档成员SHA通过，无新实验。

成果maintenance/storage_cleanup_20261023_review；本地恢复project_archives/cleanup_20261023/REVIEW_REMOVAL_RECEIPT.json、REVIEW_FINAL_VERIFICATION.json。Issue68实际回执评论6355946207；本报告PR发布/合并以Issue68最新回执为准，当前为提交前冻结。LLM对话继续新增清理范围；本10项不重复执行，不关闭总体Issue68。报告合并后回收本人小型回执目录，原Git refs保留。Projects沿既有read:project限制未同步。

以下保留历史时点：

# Issue55第七轮：8项审核通过、原head集成交付

负责人jieruiz；review/55-pr-round7；base eb317e4f；唯一tmp/pr55-review-round7-20261022。本轮103/105/106/108/109/111/113/114通过，109最终82b17a1。整合109代码测试＋8登记守卫、336query全层重放通过；修正观测/真实源冲突和过时说明，旧台账原哈希在固定归档恢复。正式审核/证据work/jieruiz/55/round7；实际远端合并、源Issue和目录回收以Issue55最终回执为准。无新GPU/Slurm/PPL/RTL/DC/PT；其他来源状态/分支不接管。

以下保留有日期历史：

# Issue96：真实随机服务已接入整机（2026-10-22）
# Issue104：架构可视化与全面检查
# Issue107后续：最新TLM的Verilog仿真缺口（2026-10-22）

负责人jieruiz，沿用task/107-tlm-cycle-digital-rtl和原独立checkout/PR109；远端初始aedc08d。原23e8d65f RTL/66功能组及12870输出不改。本次只读核对PR103@b05fb36d、台账PR111@2b7935f4，新增11组硬件表征需求、机器任务JSON和回传模板，无新RTL/EDA/TLM/模型运行。

正式入口architecture_tlm/digital_ppa_v1/LATEST_TLM_RTL_GAPS_ZH.md，区分既有PPA、已有RTL待工艺、需新增整合；优先SC64×64四档T32的归约/计数与32KiB权重驻留、编码/恢复、普通512MAC吞吐、Attention前端/完整控制和读写。明确6KiB/tile计数状态与640B/tile精确档内累计对照只是状态位数，不是PPA结论；单发射64B@100MHz为6.4GB/s，不能证明16GB/s。

来源/声明核对在work/jieruiz/107/latest_gap/SOURCE_INDEX.json和VALIDATION_FINAL.json：32个源Git字节、路径/位宽/单位、288组逐档整数等价均通过；9626内部断言大部分是循环边界检查，不作为9626电路测试。完整执行验证无新工艺结果、无新模型PPL。新增源码顶层只标拟议，不伪称已提供Verilog。已实际推送同PR109，科学交付e7b5d256ca00a725394c4ee8decf4d562a672f5c，8关键远端blob原字节核验通过；PR109/Issue107已同步，待审未合并，回执latest_gap/PUBLICATION.json。下一步等评审与用户工艺表征；Projects沿read:project不足待同步，不自动合并/关闭。以下旧交付为此前快照。

# Issue107：TLM周期/存储审计与非随机数字RTL
# Issue110 数字电路仿真统一台账

负责人jieruiz；沿用task/96-unified-tlm、PR103，独立目录tmp/unified-tlm-issue96-20261022；base已合入eb317e4f。代码、40项结果与报告已实际推送，科学交付f3cf9b98f38a3cb47c40cb86669a2f180e637d0d，9个关键远端blob原字节核验通过；PR103已更新、待审未合并，Issue96不关闭。完整回执integrated/PUBLICATION.json，后续metadata提交不改变执行或结果。
2026-10-22；负责人jieruiz；Issue104；task/104-architecture-inspector；base eb317e4f6fb1b0d8844887401f3275f128ef8a83。独立工作目录 tmp/architecture-inspector-issue104-20261022。交付阶段：科学成果1909c542a1c454a9e219a5482c9b493fa678b340已推送，PR105 ready/open待审、未合并；8关键远端blob原字节核验通过。后续本提交只补回执，不改模型/观测/页面。
2026-10-22；jieruiz；task/107-tlm-cycle-digital-rtl；base eb317e4f6fb1b0d8844887401f3275f128ef8a83。目录tmp/tlm-digital-issue107-20261022。科学成果7b12fea03bd2596cc206f3f0c32571196688e665已推送，PR109 ready/open待审、未合并，9关键远端blob原字节核验通过；后续只补交付回执。
2026-10-22实际交付：PR111 ready/open，待审、未合并；科学payload a31e010d08e4afe3292316d476d99b1509d10603 已推送，9关键远端blob字节一致，47元数据Git/本机/固定入口一致。Issue110已同步，Projects GraphQL实际INSUFFICIENT_SCOPES/read:project，待同步。没有新电路或模型实验。后续回执提交只更改状态/索引，不改原件。

FullDecode默认integrated_service，计算/SC/源/种子总线/采样器统一100MHz；SRAM已校准80MHz保留。FFN流式SAVE/RESTORE/RELEASE、Attention真实有限端点输出/种子/预热/回压，原Issue95模型/RTL未改。40/40完整模型情景、93机制/回归和1421归档/模型契约核对通过；12项为S8采样器诊断，不冒充全预算质量。原52项未改，104宽扫描0完成/0失败主动取消并留痕。
成果 architecture_tlm/inspector/README_ZH.md、model-inspector.html、CHECK_REPORT_ZH.md。76项CPU功能/接口检查通过；52旧封存情景686模型不变量、4新观测16组检查通过；新Qwen24层336query与旧序列化字段严格相同。浏览器五页、模型/模式/上下文/seed/层控制及截图已核，Node语法通过。观察执行124d37d2；没有新PPL/GPU/Slurm/PT/DRAMSys/物理PPA。完整能量/面积仍null。
52封存条件情景全量周期CSV/JSON、Qwen2K/8K与Llama1/2汇总和阶段明细，报告明确MAC/向量/非线性/SC驻留/随机源/CDC/Link等时序假设，真实访存与局部状态边界。源码23e8d65fbd84cf548ab82a6c9cfe423d37e59ae4，66功能组、12870逐位输出、63活动模式预检通过，29源文件与Git原字节相同；功能latency不是STA。Verilog23类配置含21KIND及SRAM/DMA外围，另有数组。FP32非线性和融合恢复为候选，不自动替换TLM或继承PPL；没有新模型/GPU/Slurm/PT/STA/DRAMSys。
2026-10-22；jieruiz；task/110-circuit-simulation-registry；基线eb317e4f，PR base pbit-tlm-attention-details-20261016。独立稀疏tmp/circuit-registry-issue110-20261022。本地完成35批次/模块记录、516配置行、117数字原始归档索引；入口digital_circuit_simulation_registry/README_ZH.md，原件地址/源绑定/PVT/范围/限制和实际阶段分开。8守卫测试、157独立文件SHA和26tar成员SHA通过，无新仿真、无大原件移动/复制。根同名目录为同字节阅读镜像；AGENTS/长期记忆新增每次仿真登记规则。推送/PR实际回执见work/jieruiz/110/PUBLICATION.json，未合并前不标任务完成。Projects缺read:project待同步；HANDOFF保留后续登记命令，不重跑已有健康任务。

正式报告architecture_tlm/unified_v6/RNG_INTEGRATION_RESULTS_ZH.md，执行31aa4fa31fbfb7d74629b54811936ac30a41c250；新40项/results/integrated_rng_20261022_v3及manifest。Qwen2K SC/screenPV seed0为198.00316ms，旧接口197.93816ms；仅合成条件TLM，q/256新响应无继承PPL。100MHz原生端点PPA来自任务38322118/中央记录PR111，额外前端/全局种子等仍未知，完整随机/整机能量面积null。无新PPL/训练/GPU/Slurm/RTL/PT/实际DRAMSys。
首要未闭合：32KiB/波驻留权重并行供给、48KiB局部计数状态、源后端整机连接和格式转换；PR103仍open，仅薄接口。Projects沿实际read:project不足待同步，不影响repo admin/push。主任务保留最小工作树；自己的已完成hooks helper与两轮比较器诊断已逐SHA归档回收，恢复索引在work/jieruiz/104。下一步：等待PR105评审，按检查台逐项落实硬件合同；HANDOFF及PUBLICATION/REMOTE_VERIFY为实际状态入口。
入口architecture_tlm/digital_ppa_v1/README_ZH.md、CYCLES_MEMORY_AND_RTL_ZH.md、PPA_TASK_ZH.md。113124B源码包在本机digital_ppa_v1_20261022.zip，SHA d8004f0fdf586dc020e99c3d6e6ed3b29050a652a55af037220af898c03aafb2。大波形/编译临时件本地逐SHA归档后回收，见RAW_ARCHIVE。下一步用户55nm库运行STA/DC/PT、按实际实例/latency/II回填新TLM情景；当前完全物理能量/面积仍未知。Projects本轮GraphQL实测见PROJECTS_CHECK，缺read:project则待同步，不影响repo推送。

下一步等待同PR103评审；质量和尚未知PPA后续另补。Projects沿read:project权限不足待同步，架构检查台旧52快照不自动刷新。HANDOFF和integrated/验证目录可恢复；无本任务运行作业。以下旧“仅小接口/未接入”是此前快照。

# Issue96 RNG接口核实补充：小接口连通，整机默认保持

2026-10-22；jieruiz；沿用task/96-unified-tlm及独立目录，接口补充另开PR103待审。原整机PR99在本轮工作期间已合并0575a633，实际head仅a7a4829，不包含本次接口补充。读取最新GitHub集成5dbd9e39，随机源整个Git树/采样器与本地一致。新增rng_frontend.py：K32分层阈值拼接＋64共享、保留exact-one；uniform32按实际原生宽度计帧。赢家/拒绝接TimedSamplerSource，各三seed连通，512路真实26端点和种子总线检查通过；后端/RTL/其他成员STATUS未修改。

冻结36d5e1085e82a982c9e689a467b3b2042ca36f4d，11新＋21整机＋19源目录测试通过，共51，0失败/跳过；无新PPL/PT/GPU/DRAMSys。报告architecture_tlm/unified_v6/RNG_COMPATIBILITY_ZH.md，原件work/jieruiz/96/RNG_INTERFACE_VALIDATION.json。代码/报告/51项回执由PR103交付；最终head及远端字节核验见Issue96回执。PR103待审未合并；下方原99待审文字为历史快照。

结论：能拼，仍需全模型流式消费/统一时钟和累计账本适配、筛选896路容量选择，以及新q/256 sigmoid数值验证。当前未把随机源后端接入FullDecode默认，未改旧52情景；不能混称已完成整机源调度。下一步按报告边界做可选backend，未知PPA不填零；看板read:project待同步。
以下保留此前历史：
PR105（Issue104）检查台仍ready/open，headfa4ef7b，未被本任务合并；PR103随机接口仍独立，Issue95/7不接管。以下保留历史：
以下保留此前任务状态原文：

# Issue55第六轮最终补审PR99 ready

2026-10-22；jieruiz；review/55-pr-round6。93/94/97/100已进入集成5dbd9e39，PR99新heada7a48297转ready后49检查/52情景清单与两项完整Qwen24层重放通过，原head随本次补充PR交付。旧草稿记录保留为fba时点。最新报告work/jieruiz/55/round6/pr99_ready/；实际远端合并与本轮目录回收以Issue55最终回执为准。无新模型/GPU/Slurm/PPL/PT，TLM条件结果不继承质量或PPA。

# Issue55第六轮收尾：4通过、1草稿保留
# Issue96 unified TLM: 52 scenarios complete, PR99 awaiting review

追加100协议33检查/关键一手口径核对通过，99仍draft保留；93/97已原生合并，94/100作者原head随本人集成PR交付，无作者分支更新。详见work/jieruiz/55/round6/和Issue55最终回执。
2026-10-22; jieruiz; task/96-unified-tlm; base83e15289, executionfba22b192ab914046e50cc405f6dd473bf30d154. Independent sparse checkout tmp/unified-tlm-issue96-20261022. Implementation, all52 scenarios, reports and validation are published at9621e1db35491e530d35b86e0ef884572b1df0a6; PR99 is ready/open, awaiting review, not merged. Five critical remote Git blobs read back and byte-verified; PUBLICATION.json and REMOTE_VERIFY.json record that snapshot. Full implementation/design/results: architecture_tlm/unified_v6/README_ZH.md and RESULTS_ZH.md.

# Issue55第六轮审核交付
21 new mechanism +18 existing v5 +10 existing v4 checks pass; navigation anchors/dry-run pass. 48 Qwen2K/8K three-seed cases and4 full Llama1/2 single-seed cases complete;62 archived artifacts/22 source blobs/764 model contracts verified. New upstream97 default sampler overlay49 checks pass, no backend switch. No new PPL/GPU/Slurm/PT/DRAMSys run. Unknown complete energy/area/PPL staynull. Local source interface has0 random-stream SRAM/FIFO/extra probability copies. RNG backend remains Issue95;37/78 untouched. Projects real query missingread:project, pending.

2026-10-22，jieruiz，review/55-pr-round6；基线83e1528、当前远端27bf9c48。93/97已原生合并，94的45检查/90模型/134包/15逐文档/成本重放通过，原head424b4206经本人双亲合并集成；待本报告PR发布。97的47CPU、8100沿及FFN250沿/120帧通过。没有新服务器/GPU/模型PPL/PPA。成果work/jieruiz/55/round6，实际远端/清理结果以Issue55最终回执为准；只有一个本轮稀疏工作树，原负责人状态只继承原提交blob。
Next: PR99 review and module cost/timing characterization; do not merge automatically or close Issue96 before acceptance. Implementation checklist and delivery links are updated in Issue96; Projects remains pending permission. Handoff work/jieruiz/96/HANDOFF.md; original failures preserved in FAILED_PREFLIGHT and compatibility V1/V2, fixes/tests recorded. No running jobs remain. Earlier in-progress/draft statements below are historical snapshots.

以下保留历史：
# Issue96 unified TLM in progress

2026-10-22; jieruiz; task/96-unified-tlm; base83e15289; independent sparse directory tmp/unified-tlm-issue96-20261022. Main code/Chinese design done; 20 mechanism checks pass, Qwen24 exploratory smoke done. Frozen runs, result manifest and workspace PR pending. No new PPL/PT or source-backend implementation. Handoff work/jieruiz/96/HANDOFF.md.

# Issue55第五轮最终：6项成果已合并

2026-10-22；jieruiz；初始82/83/85/86/88，收尾89一并审阅通过，最终科学集成9bd908b5d06a4dd72af67655a4c4a30a2c72e1c0。89直接合并作者原head，未改写他人分支；作者STATUS/HANDOFF更新按原blob继承。Issue73/84/87已关闭，78/37继续；83官方26项验收已完成、新全组合质量/PPA仍未验收。报告work/jieruiz/55/round5/，memory SHA256 9ef4fc794fd2fbd51993849972346b90153b36e971cd8731e78a10919880f049。报告交付/本轮目录回收实际结果查Issue55最终回执。

以下为追加89之前的五项阶段记录及更早历史：

# Issue55第五轮：5项成果PR已合并

2026-10-22；jieruiz；review/55-pr-round5；目标pbit-tlm-attention-details-20261016，科学集成8d4ce51be7ecace716bc83688dc4768eb2574d38。本轮82/83/85/86/88通过并逐项原生合并；报告/证据入口work/jieruiz/55/round5/。审计报告由本PR交付，不计入5成果；原始head/base/merge、验证和限制逐项记录。

83已26/26，54782题/109564官方指标逐题一致，输入/源/32层封存覆盖与配对统计通过；不是旧19/26或oracle pending。已删除的回查不重建。82仅局部场诊断，86仅真实QKV/V-MSE，85仅文献；88补可选tlm-parallel入口及4项24层合成Link组合，未继承PPL/PPA或最新B4/T32硬件参数。继续研究78/37，有限任务73/84/87已实际验收关闭，回执见Issue。

CPU各组25/7/14/18/10通过（含历史复用，不相加宣称全部为新测试）；Windows临时目录和精简检出依赖均显式补齐。没有新推理/GPU/Slurm/PT、冻结源改写或定时变更；私有QKV/捕获与原PDF不上Git。原生门禁checks列表为空，不伪称CI跑过；Projects沿历史read:project待同步，本轮未重测。

memory SHA256 d092a7b580007a3d21932c911dc82b1aea3eda1b89efc66d226b6daa4415bc19，canonical原有有序增量先归档并完整保留，HEAD仍a71e4bc01ef67f604008325c80e8d58a766ef02c。仅本轮本人tmp/pr55-review-20261022和tmp/pr55-round5-artifacts在报告合并后回收，实际执行见Issue55及project_archives/pr_review_issue55_20261022/RECOVERY_INDEX.json/CLEANUP_RECEIPT.json。其他成员STATUS、模型和共享Git对象保留。

以下保留此前有日期的状态原文：

# Issue87 交付回执：PR88草稿已上传、未合并

2026-10-22；jieruiz；task/87-parallel-sampler-tlm。科学交付head8687c1d8124af192e82ec13aa3dbe12ccaa240b7已推送workspace，PR88草稿开放未合并；两个采样器、公共接口、中文说明、结果报告及验证文件6份远端原字节SHA已读回核验，详见work/jieruiz/87/REMOTE_VERIFY.json和PUBLICATION.json。

18新＋10旧检查通过，执行f6c6bd8；30三seed合成模块＋2单层decode连通完成。全宽候选一次读取、随机源后端未定；未知完整能量/面积null，不冒充PPL/PT/DRAMSys或实际源结果。下一步填源/数字模块成本或做真实模型质量与调度验证，现阶段等待PR评审；Issue87保持open，不自动合并。看板本轮未写，沿既有权限限制待同步；Issue73/78作业不改。

以下为此前阶段记录，待发布描述不代表当前阻塞：

# Issue87 全宽并行采样器TLM：本地完成、发布以回执为准

2026-10-21；jieruiz；task/87-parallel-sampler-tlm；base5b26c80；独立稀疏tmp/parallel-sampler-issue87-20261021。赢家保持/原校正拒绝、源后端抽象、全候选一次读取、时序/反馈/回压及未知PPA契约已实现；18新＋10旧检查通过。执行f6c6bd8215c2d702ab42e6a3078f64e0888cade8；30三seed合成模块＋2单层decode情景完成，非模型PPL或芯片结果；无新Slurm/训练/PT/DRAMSys运行。

正式说明architecture_tlm/PARALLEL_SAMPLERS_V5_ZH.md；正式结果architecture_tlm/results/parallel_sampler_v5_20261021；交接work/jieruiz/87/HANDOFF.md。源技术不决定，完整能量/面积null；公共偏移与逐驱动重写是可调前端模式。推送/PR/远端SHA以本任务PUBLICATION及Issue87回执为准，未合并；看板沿既有权限限制待同步。本任务不接管Issue37、不重跑Issue73/78。

以下保留此前各任务记录：

# 发布回执：真实QKV比较已推送PR86

2026-10-21T13:41:36.925189+00:00；jieruiz；task/78-sampler-qkv-benchmark。科学head346bbb12f1181ab1b974940d79f052d0757fec80已按相同Git commit/tree/blob实际上传，草稿PR86开放未合并：https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/86 。90/90统计与报告齐全；本次仅补发布回执，科学结果不改。原始QKV/长曲线留服务器，无本任务运行作业。Issue78保持open，Projects本轮未写。最终分支head与远端字节核验见Issue78最新回执；下方待发布字样是此前阶段状态。

# Issue78：真实QKV采样器90配置完成，待发布回执

2026-10-21T13:37:45.944700+00:00；负责人jieruiz；task/78-sampler-qkv-benchmark；base5b26c80，独立稀疏tmp/sampler-qkv-issue78-20261021。90/90配置、3seed×8重复，原BF16 QK/V及筛选派生，源4ec2613；最终摘要/固定预算源25cfd9d/2733。正式报告qwen/results/sampler_qkv_20261021/DECISION_ZH.md，SUMMARY SHA b95c40f5098fca632e28d420e96399189e59c6f80d8ed6da048fa8ebf9ef1261。

赢家c=max与校正拒绝主表典型约288轮；单p-bit Barker仅46/90到IID128目标。赢家argmax初始化B0/S512为89/90、S1024为90/90均值达标。更新/服务波非芯片周期，无新PPL/PT/训练/GPU占用或TLM默认改动。捕获六窗口逐位一致，本地13检查、服务器8核心/4汇总通过；CRLF执行源/配置原字节封存，修复汇总绑定但不改旧结果。

最新HANDOFF在work/jieruiz/78/qkv_benchmark/HANDOFF.md；原78 HANDOFF加入口，其他原文保留。科学成果本地完成，下一步明确文件提交/推送、PR草稿及远端字节核验；以PUBLICATION/Issue78回执为准。无本任务运行作业，不重跑健康任务，不接管PR82。Projects本轮未写，沿既有权限限制待同步。

以下保留此前各任务状态原文：

# Issue84：SANTA++精读报告已上传，PR85待审

更新时间2026-10-21T12:10:56.373304+00:00；负责人jieruiz。Issue84，task/84-santapp-novelty；PR85草稿开放未合并；base pbit-tlm-attention-details-20261016@5b26c80c28ab22383f12ab31046dd723ca985abb。工作目录tmp/santapp-novelty-issue84-20261021，科学head ad92485c9f98cc50fdb706f620c96d681fb339e9已推送。

正式报告architecture_tlm/research_readings/SANTAPP_V1_NOVELTY_ZH_20261021.md，SHA96f123e75e48212956fc50f740956310b06d61d5e95766b625f7976548834f05。结论：筛选/随机选组/GQA并集已重合；具体p-bit类别采样器、短流FFN和存储协同仍有研究空间，但缺长上下文/匹配PPA证据。当前max4筛选未做选择校正。

实际验证：PDF32页身份与SHA、正文和附录方法核查、4页渲染检查、8个项目源blob/字节SHA、10项预算/算术/编码核查；无模型/GPU/训练/RTL/PT/TLM运行。源版本/证据见work/jieruiz/84/SOURCE_MANIFEST.json与VALIDATION.json。原PDF/权重/工艺/私有capture不上传。

本轮科学文件已由GitHub API按相同commit/tree/blob上传；交接及备忘录随收尾提交同PR，最终远端以Issue84评论为准。Issue保持open待评审，无运行任务，不改默认数值核。Projects本轮未写入，沿既有权限限制留待同步。下一步评审PR85；不要重复昂贵实验或接管其他任务。

以下保留此前各任务状态原文：

# 2026-10-22：26/26任务推理完成，定时回查已删除

Issue73/PR83（草稿开放未合并）；jieruiz；task/73-results-followup。北京时间12:43只读检查：26份完整JSON均completed，逐题文件SHA/大小/路径及声明32层守卫通过，当前Slurm队列空。按用户最新条件指令已删除llama2-7b回查，工具回执deleted、本地配置已不存在；不因官方oracle待做而重新创建定时。

最新报告llama2/results/task_accuracy_20261020/PROGRESS_20261022_ZH.md；原始状态checkpoints/20261022T044323Z/STATUS.json，停止回执work/jieruiz/73/AUTOMATION_STOP_20261022.json。此次只检查/汇总已有结果，未重跑推理或改冻结快照；没有新的完整32层独立复核或官方process_results复算，最终验收仍待这些步骤。不要把summary聚合当官方oracle已完成，不关闭Issue或合并PR。

下一步：同Issue73/PR83继续官方oracle、逐题源/输入/层覆盖完整复核及配对统计，已有26项不再推理。状态/报告推送以本次PUBLICATION_STOP_20261022.json为准；看板沿既有权限限制待同步。

以下为旧检查点与历史回查状态，不代表仍有推理任务运行：

# 2026-10-21 18:25用户回查：19/26已核验

Issue73/PR83（草稿开放未合并），jieruiz，task/73-results-followup。CPU2634复用源86ccedc封存核验完成exit0：19completed、2running（2585_12/20）、5pending（21～25），无无效或缺项。比18:11新增ARC-E FFN-only seed2，故PIQA/ARC-E的仅FFN三seed均齐。PIQA acc/acc_norm77.80196%/78.99891%，ARC-E76.27666%/74.32660%；相对原BF16分别−0.05441/约0与−0.02806/−0.33670个百分点。只重聚合已存逐题metrics，官方oracle仍待26项齐全，不作为最终验收。

报告PROGRESS_20261021_ZH.md已更新；新原件checkpoints/20261021T102541Z/CHECKPOINT.json，SHA c3e1ac52858d6f3cb3006e1e36c032c0c20eb0bf4df93858e7dc708a42da4871。旧18项检查点不改。五项排队约6.71GPU小时，另有两项运行尾部；保持两卡估计仍需4～6h。Qwen39/39服务器status全completed（PIQA/ARC-E/Hella1000题子集各13），未重复跑GPU、未改旧推理snapshot。

本次报告待随本提交同步PR83并核验远端blob，发布以Issue73新评论为准。继续同目录/分支收齐26项，最终官方process_results/配对统计后再停每日回查。旧18/26与旧running16为历史时点。Projects待既有scope。

# 发布回执：18/26检查点已在PR83核验

2026-10-21；jieruiz；Issue73。科学结果提交7a75c53eb4db9dc261bdba76ba6ad86f4e61a4b6已通过GitHub Git对象API上传，blob/tree/commit SHA完全等于本地，非强制更新任务分支；PR83 draft/open未合并。检查点原件GitHub字节SHA7f894690ee8482dbf98d019df2a272cb4ac0c6d9f138350a6975a7b22bba65b4一致，Issue73评论6313631692已同步，回执PUBLICATION_CHECKPOINT_20261021.json。此前原生Git超时已通过替代传输解决，不能再写作报告未上传。26项仍未齐；原推理任务和每日回查继续。下文“发布以新回执为准”由本回执覆盖。

# 2026-10-21 18:11 Llama2检查点：18/26，后续PR83

jieruiz；Issue73 open；后续分支task/73-results-followup，PR83 draft/open未合并，base5b26c80c28ab22383f12ab31046dd723ca985abb；独立目录tmp/llama2-task-accuracy-issue73-20261020。原PR75已合并3fe790ecc2d4849662b60216922fd45dc4300848，只验收代码/提交/恢复阶段，旧“未合并/GPU2584 pending”不再代表当前状态。

CPU Slurm2632、源86ccedc1f14432fc993b4032a9af7873bbf579c6完成exit0；7项本地/远端合同通过。18份sealed full JSON及documents SHA/全量唯一id/候选token/32层与active-dummy/输入与源身份链通过，逐题已存metrics重聚合一致；官方process_results尚未独立复算。未重哈希14GB权重，只核对已验identity manifest绑定，不冒充新模型完整质量验收。

2026-10-21 10:11:23Z：completed18（旧8＋修复10）、running2（2585_12/16）、pending6（2585_20～25），无无效或缺项；本轮比08:39检查点新增ARC-E FFN-only seed0/1。PIQA联合S512仍2/3、ARC-E FFN仍2/3，不算组均值。六项待运行按实测吞吐约7.98GPU小时；保持现有两卡估计还需4～6h，若单卡约8～11h，不是排程保证。原2572健康八项和2585十八项不动，没有新GPU推理或冻结源修改。

正式入口llama2/results/task_accuracy_20261020/PROGRESS_20261021_ZH.md；原件/checksum/ETA见checkpoints/20261021T101123Z/；命令work/jieruiz/73/CHECKPOINT_SUBMISSION_20261021.json。源码已用GitHub Git对象API逐SHA一致上传（原生Git两次连接超时）；后续报告发布以PR83/Issue73新回执为准，不宣称本地文件自动已远端。

下一步沿用同目录/分支和最新Issue73状态，只读收集26项；收齐后加官方lm_eval0.4.8/parquet/YAML逐题oracle和同轮BF16配对统计，再验收最终结果。现有checkpoint的complete仅指封存合同齐全，不替代官方指标复算。Apple FP32两模型单列；当前Attention是原有限CTMC/all-K短题，不是8位p-bit新驱动。heartbeat llama2-7b仍ACTIVE/每日，提示已纠正PR75关闭状态，完整26项核验交付后删除。Projects缺read:project依旧待同步。

以下为历史：

# 最新：sigmoid输入8位驱动分析完成，后续分支待发布

2026-10-21；jieruiz；Issue78；task/78-field-int8；独立目录tmp/ising-broadcast-issue78-20261021；base e24414b8f0ba47e8df46ba64475dbbf45568e2f4。PR80已经实际合并e24414b，原head0d73671；本次新成果后续PR号待创建，不向已关闭PR追加。

CPU Slurm2630源757fb90完成，25项本地/远端合同通过。保存输入24层2688行的范围统计＋42行/三seed/S64理想轨迹的局部条件分布分析；不是新PPL、训练、RTL或PPA。完整sigmoid驱动a中位约−8.70，5/95%约−26.15/−4.70，极小约−97.86。负幅度8位h1/8局部TV均值1.262%；h1/16本批0.631%，但强制m14负尾钳位明显，因此优先h1/8、负范围−31.875～0，10位h1/16作对照。都是解析局部偏差，不是模型质量承诺。

正式报告qwen/results/ising_broadcast_20261021/FIELD_INT8_ZH.md；原始JSON、manifest与work/jieruiz/78/FIELD_SOURCE/SUBMISSION/VERIFY.json含输入/源/配置/结果SHA。私有logits不上传，旧快照不变，模型默认不改，无本任务运行作业。SOT文章核查到局部场电流映射/偏移斜率校准，但未披露局部场INT8/PPL；论文INT8/4对照指输出概率。

下一步在独立校准样本确定a/m范围，接模型PPL验证负幅度8位和10位，不重交2630。发布前核对远端，普通push新分支、创建PR并核验原件Git blob SHA；Projects沿用缺read:project待同步。当前科学成果本地已完成，尚待本次推送核验。

以下是旧时点：
# Issue55第四轮：4项成果PR已实际合并

2026-10-21；负责人jieruiz；review/55-pr-round4；本轮稀疏目录tmp/pr55-review-20261021（报告合并后按恢复索引回收）。目标pbit-tlm-attention-details-20261016，科学集成e24414b8f0ba47e8df46ba64475dbbf45568e2f4。PR75/77/79/80已按单项原生门禁合并，精确head/base/merge和测试边界见work/jieruiz/55/round4/REVIEW_ZH.md、REVIEW.json、receipts。审计报告通过后续独立PR交付，报告PR不计入4项成果。

PR75是实现/远端提交阶段验收，08:39:24Z为16/26完成，2运行8排队；GPU2584修复已通过，不是26项最终质量已完成。Issue73与既有回查继续，不重交健康数组。PR79派生文档索引SHA/大小已修复，原件不动；PR80后续OFFSET144记录/接口已审核交付，非新模型PPL/有限精度/硬件验证。Issue78继续。PR77仅训练计划，Issue76用户额外明确授权后已关闭。

7+4项Llama tiny32层CPU检查、Word/MD121块与196方向梯度、广播19合同/独立数学与原件重放均通过；旧11与19重叠不相加。没有新GPU/Slurm提交、训练、完整模型推理或PT。仓库admin/push/merge已核实成功；可选code-review服务无法连接GitHub，已直接核验原生checks/status/reviews/threads；Projects沿历史read:project限制待同步，本轮未重测。

备忘录SHA256 94574325bd018d0a79229471d202d88111550ead163fbc309e520a137072da55；canonical原有全部有序增量保留，HEAD仍a71e4bc01ef67f604008325c80e8d58a766ef02c，未reset。只回收本轮本人review/scratch，逐SHA本地归档project_archives/pr_review_issue55_20261021，实际结果以Issue55最终回执/RECOVERY_INDEX为准。原始privateNPZ仅授权本地归档，不进入Git。下一步完成报告PR及收尾回执，后续实验仍由73/78原任务跟进。

以下保留各任务此前有日期的状态原文：

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

## 同期已合入的历史任务状态（保留原文）

# Issue73 2026-10-20 17:40：显存修复已补交、GPU门禁排队、回查已设

jieruiz；task/73-llama2-task-accuracy；PR75 draft/open未合并。PIQA BF16已完整完成；原2572的FFN-only三seed初始化OOM，15个同类待执行项仅本人撤回。健康8项仍在原2572（index0,4,5,6,13,17,18,19）。

新冻结309ca9c1629c364142ffdce474d5f6138da929c1无损W8码INT16→INT8，保留恢复FP32和RNG，省4.03GiB；CPU2583七项通过，GPU2584排队，18项FFN相关数组2585 afterok2584已提交。不能称修复GPU验证完成。两版正式请求/模板/Harness逐字节一致，75新源Git blob一致；原OOM/取消记录和新SHA索引已保存。

1卡剩约40～55h；较快2卡约22～32h，按真实decode步数和吞吐情景估计。heartbeat llama2-7b已建，每24h回查，首检预计10/21 17:35北京时间，核验完成后停用；本地关机无法SSH，不保证错过立即补跑。交接work/jieruiz/73/HANDOFF.md最上节，FOLLOWUP_SCHEDULE.json。下一步核2584结果，收齐8旧+18新配置，勿重复提交。Projects缺read:project仍待同步。

以下为旧时点记录：

# Issue73：Llama2任务评测已通过门禁并开始正式运行

2026-10-20；负责人jieruiz；Issue73 / PR75（draft/open、未合并）；分支task/73-llama2-task-accuracy，base18b887b集成分支。独立稀疏目录tmp/llama2-task-accuracy-issue73-20261020；冻结执行022db6828c0caba96ae3d620f80b27c1ae3774b9已推送。

PIQA1838、ARC-E2376全量各13配置，共26项：BF16、FFN-only三seed、Attention-only S128三seed、联合S128/S512各三seed。固定B4/T32/K32、共享64；Attention为unscreened有限CTMC，短题不宣称K筛选收益。Apple PR67已有FP32 Softmax/Sigmoid两完整基线已按源SHA索引复用，并非新跑或Llama同权重因果对照。

CPU2570的6项32层小模型合同通过；GPU2571完整WT2 BF164.979502845218782、335686目标严格重现，8题独立缓存逐候选差0且digital_sdpa一致；4个真实7B概率pilot及32层审计通过，最高29.89GiB。正式数组2572_[0-25]已经启动，首项运行，其余待Resources（最多2张5090，目前仅1空闲）。分数pending；没有新训练/PPA。

成果llama2/results/task_accuracy_20261020/；源码experiments/llama2_task_accuracy_20261020/；远端/home/Hongjie_Zeng/projects/pbit-llama2-task-accuracy-20261020-issue73/outputs/022db6828c0caba96ae3d620f80b27c1ae3774b9/full。SHA、执行命令、Slurm回执/READY及精确源码小归档已保留；75源核验，38个继承文件仅git archive CRLF换行差异，原始执行字节保留，未改数值。

下一步先核Issue73/PR75、squeue及HANDOFF；只读收回封存full JSON和documents，核SHA/26项/32层/3seed后汇总与配对差值。不重交仍在运行的数组，不用pilot或部分seed冒充正式结论。Projects历史缺read:project待同步。

以下保留此前状态（时间戳快照，最新合并以远端为准）：

## 同期已合入的历史任务状态（保留原文）

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

# Issue78：诊断完成，S64 PPL对照部分完成

2026-10-21T07:12:29.385386+00:00；jieruiz；task/78-ising-broadcast；PR79草稿待审未合并。9项CPU合同通过；Slurm2600/2601/2608完成。已发布5/18个128目标PPL：BF1620.212326，CTMC三seed均值23.159115，全同步两seed82.224259/129.479031。随机分块仍运行，2602并发6、2609后续自动汇总，无GPU。正式qwen/results/ising_broadcast_20261021，交接work/jieruiz/78/HANDOFF.md；所有完整WT2/PPA仍未做，Issue78 open，Projects待权限。

## Issue78发布更新

CPU2600/2601已运行，2602数组18项afterok等待；实际执行源0c0d897，31blob/81KB源码包SHA已记录。任务分支已推送，PR79草稿开放、未合并，Issue78已同步。PPL仍pending，6项远端合同通过；无GPU。

# Issue78：全局广播与有限κ同步/随机分块更新

2026-10-21；jieruiz；task/78-ising-broadcast；base e4990c15b40f664cea7f9db43175b68347ce588b；独立tmp/ising-broadcast-issue78-20261021。有限κ和合法地址服务行为模型已写，6项本地CPU合同测试通过。远端合成/模型PPL尚未执行；准备通过Slurm申请CPU，原FFN、S64 CTMC对照、128目标后缀初筛。无GPU任务改动，无PPA。PR未创建、未推送，Issue78 open；交接work/jieruiz/78/HANDOFF.md。Projects待授权。

以下保留原进度时点：

# Issue55第三轮：7项PR审核已完成，结果已实际合并

2026-10-20；jieruiz；review/55-pr-round3；tmp/pr55-review-20261020单个稀疏目录；科学集成18b887bd2d0cd6c06d070d8dafaf8b979742fdcf。49/52/62/67/69/71/72均已合并，62先入52任务分支再由52进集成。服务器25项完整WT2已回收核验发布，39项代表任务逐题重算通过；旧“仍运行/未完成”过时，不重跑矩阵。65核心CPU、30scorer/collector与独立数学/汇总复核通过，详细数量和重叠见work/jieruiz/55/round3。

Issue48/50/59/65/68/70已按范围验收关闭，28继续维护。S512完整PPL12.207062对BF1611.652118，约+4.763%，不宣称质量等价；49仅S128完整确认，S256/512无同预算full原FFN控制。AppleFP32不代表BF16/p-bit/PPA，ReMix无模型训练复现。无新GPU/快照改写。原科学blob/签SHA原件保持，amlink STATUS不改。

当前审核文档通过Issue55交付，实际PR回执以远端为准；本轮scratch/稀疏checkout归档后回收，恢复路径project_archives/pr_review_issue55_20261020。canonical/root同字节且原12行清理增量保全，canonical HEAD未reset，工作文件等本轮发布；Projects本轮read:project不足仅影响看板同步，不影响已成功的仓库合并。

## 以下保留原时点状态，不作为实时运行队列

# Issue50：25项完整WT2确认已回收核验，接续原PR52发布

2026-10-20；jieruiz；用户要求重审补全结果，Issue55审阅中只读接续Issue50现有原件。原2430保留19项、2461六项全部封存completed，2430_19/20/21三项B4T16联合按用户既有授权取消；未新跑模型或改快照。新独立报告qwen/results/joint_full_wt2_20261020/，含25原始结果、完整输入/源/取消与调度证据。

299077目标各一次/7300段NLL/25配置/24层审计与原件SHA通过；执行53dd/c0fd数值核一致，65核心CPU+4计划测试通过。B4T32联合S128/256/512完整PPL 12.423820/12.274153/12.207062，匹配cached BF16 11.652118；S256/512缺原FFN完整控制，交互不计算。原FFN仅S128三seed完整确认可供PR49有限引用。完整结果与旧4096后缀不混用，不使用自定质量阈值，不声称PPA。

当前阶段：原PR52仍draft，正追加本包与最新集成冲突解决，未把准备发布写成已合并。PR62的39任务已合入本任务base992c693；后续合并需独立原生回执。旧调度记录scontrol已过期、sacct实测storage disabled，完成依据为封存原件/逐目标审计，未伪造Slurm会计终态。Projects历史缺read:project仍待同步。恢复先核远端PR52/Issue50及Issue55第三轮回执，不重跑已收齐矩阵；本轮本地唯一稀疏审阅目录tmp/pr55-review-20261020，辅助资料归档后回收。

## 以下保留原任务交接及运行阶段快照，运行描述不作实时队列

# Issue59：39项Qwen任务评测已全部完成，完整报告已上传，PR待审

更新时间：2026-10-20；负责人：jieruiz；目标：rayggxia-workspace/pbit-llm-qwen-baselines。

- Issue59；分支task/59-qwen-task-accuracy；PR62，base task/50-joint-ffn-attention；依赖PR52。工作目录C:/Users/86134/Documents/a_P_BIT/tmp/qwen-task-accuracy-issue59-20261019。
- 服务器39/39均已封存、0待完成；当前没有本人的Slurm运行任务。Slurm2477/2478/2479/2480完成，2481自动汇总成功。PIQA1838、ARC-E2376、HellaSwag固定1000题；每任务BF16＋FFN-only三seed＋联合S64/128/512各三seed。
- 2026-10-20严格复核39项及逐题SHA，重建SUMMARY/RESULTS与服务器归档逐字节一致；原执行075574ec94307202f3187845d6d7417f1e98ba48及collector0d4be877714ace3f1b360c4d74b62e563850e9bc保持不变。没有新GPU推断、训练或PPA。
- 正式成果qwen/results/task_accuracy_20261019/：完整表、三seed波动、逐seed配对变化及原件SHA索引；大的逐题原件留原授权服务器。两份报告SHA：SUMMARY be47dd60a87dfb1467add4e22c6795e02df2a80867d0085d8f1a3b70cb1e61ac；RESULTS 7fc169344d0166f938580f32fb0ce03f0f5d34465bea5a74830ccdef4d0edbde。
- 局限：Hella不是完整10042题；短题K保留100%，前缀Attention准确，不能宣称长上下文筛选或完整prefill Attention已验证；Ising观测数不是ESS/电路拍。
- 当前发布阶段：完整报告已推送cebba22dadb78440b210b3ec237b5e2d16c77030；GitHub API核验16份结果/evidence字节与manifest相符，PR62说明及Issue59清单/进度已更新。PR仍draft、未合并，Issue保持open，不使用旧3/39或11/39代表当前状态。
- 长期记忆已同步并通过PR72提交待审（https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/72）；下一步审查/合并PR52、PR62及PR72。看板查询实测返回INSUFFICIENT_SCOPES（缺read:project），Projects待有权限者同步；仓库报告上传不受影响。实际发布回执见work/jieruiz/59/FINAL_REMOTE_RECEIPT_20261020.json。

---

以下保留历史状态与交接，不作为当前状态：

# Issue59：39项代表任务准确率已在Slurm运行

2026-10-19；负责人jieruiz；正式目标rayggxia-workspace/pbit-llm-qwen-baselines。

- 分支task/59-qwen-task-accuracy；PR62草稿、未合并，base task/50-joint-ffn-attention，依赖PR52；独立目录C:/Users/86134/Documents/a_P_BIT/tmp/qwen-task-accuracy-issue59-20261019。正式成果qwen/results/task_accuracy_20261019/，实现experiments/qwen_task_accuracy_20261019/。
- 选择PIQA1838、ARC-E2376全量，HellaSwag预先Random(20261019)抽1000题。官方lm_eval0.4.8零样本模板/边界及acc/字符长度acc_norm。B4T32 FFN固定，Ising64/128/512每档3seed，另BF16与FFN-only3seed，共39项。
- 当前3/39完成：新matched cached BF16 PIQA acc70.5114%/acc_norm69.9674%；ARC-E64.3939%/58.3333%；Hella子集41.9%/52.4%。36替换结果未齐，不能给采样准确率结论。不是历史native-vectorized分数搬用，子集不是完整Hella。
- 真0.5B GPU2476已重现完整WT2 BF1611.652735047455899；12最长prompt题独立naive cached参考逐候选总分最大差0.0、greedy一致；9项pilot完成，不当作正式任务。15CPU评分/计划检查、15汇总负面测试通过；评分CPU使用微型24层Qwen2夹具，不是全0.5B测试。
- 执行源码冻结075574ec94307202f3187845d6d7417f1e98ba48，不再修改；collector-only快照0d4be877714ace3f1b360c4d74b62e563850e9bc。原件/配置/数据/75项执行源Git blob或私有校准manifest已核验，公开索引/门禁在正式结果evidence/。
- Slurm2477三基线已全done；2478 ARC-E12项、2479 PIQA12项运行/排队；2480 Hella12项等资源；2481 afterany四数组自动CPU汇总。所有ID/命令见SLURM_WORKERS.json。sacct存储关闭，以squeue及completed封印原件确认，不用空sacct当结束。
- 服务器个人项目/home/Hongjie_Zeng/projects/pbit-qwen-task-accuracy-20261019-issue59；正式outputs/075574.../full含逐题jsonl，自动analysis/075574..._0d4be...。大原件留已授权服务器，Git只存摘要、SHA和索引。
- 旧2471包启动失败，2472依赖取消；348c828/2474因向量化和cache BF16形状差触发旧阈值，原件保留，新075574用独立cache参考严格验证后才启动正式任务。三任务均短于512，筛选保留allK，不能当长上下文筛选质量证明。首答案token及后续均真走24层decode替换；前缀Attention准确、FFN替换。
- 用户授权只取消本人未运行2430_19/20/21 B4T16冗余全量PPL，保留最佳B4T32。回执已提交。未训练/新PPA/修改Attention或FFN数值核。
- 下一步：先核实Issue59/PR62/最新本目录及本人队列；只读收集已封存full JSON+对应documents原件，按SHA核验。用collector --input下载目录 --execution-commit075574... --output SUMMARY.json --report RESULTS_ZH.md（命令参数之间需空格）；不得拼接进度冒充完整，至少三seed齐再下联合结论。继续更新PR62、Issue59及备忘录。
- 长期记忆本次补充在Issue28/PR64待审、未合并；根PROJECT_MEMORY同字节阅读副本已更新。Projects此前缺read:project，看板待同步，Issue/PR写入可用。

## 2026-10-19 17:51北京时间实时更新

已完成11/39、28项运行/排队，无worker traceback。首次联合结果ARC-E S64 seed0完整2376题：acc63.4680%、acc_norm58.4175%，参考64.3939%/58.3333%，仅一seed不作三seed质量结论。耗时1084.16s；FFN-only ARC-E三个seed已齐，原件按SHA与严格collector验证。

按真实decode前向工作量和当前每task两个并行槽估时：ARC-E S64三seed约18:05～18:15；PIQA/Hella首个联合seed约18:20～18:40；三个任务S64各三seed约19:00～19:20；全部S64/128/512各三seed约21:00～22:00。均为2026-10-19北京时间的动态估计，不是Slurm保证。按ctx长度分组、候选最长长度决定batch步数，不能用题数百分比简单外推。未调整作业/并行数/随机源，输入与快照不变。RUNTIME/DECODE_WORK为本次原始状态快照。

## 同期集成状态快照（保留原顺序及共有历史尾部）

# Issue28：Qwen39项完整任务结果已同步长期备忘录

2026-10-20；真实认证jieruiz；目标rayggxia-workspace/pbit-llm-qwen-baselines。复用canonical目录tmp/project-memory-issue28-20261018、分支task/28-project-memory，base6197f24a9cc03ab0dc5e2e72297457f638e37292。新增第5.8.2节、最新任务索引，引用Issue59/PR62已上传cebba22的完整39项，不启动或重交任何模型任务。

- 当前阶段：文档提交72c6a7ed838eadad33d94b1dcd1293f128f3711c已推送并建立PR72（https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/72），open、ready for review、未合并；PR62报告也已上传、未合并。
- 证据：qwen/results/task_accuracy_20261019/{RESULTS_ZH.md,SUMMARY.json,ARTIFACT_INDEX.json,evidence/FINAL_VERIFICATION_20261020.json}。数值与原件SHA不重写；本轮只有文档同步。
- canonical原有Issue68/PR69清理追加为已存在的未提交12行。本次只将第5.8.2/12节和日期变更写入索引，排除该旧任务增量；旧增量继续原样保留。canonical文件与a_P_BIT根阅读副本始终同字节；工作副本含PR69待审追加，不冒称与仅本次增量的提交blob整文件相同。
- 验证：39项/15组数值、两份报告SHA、UTF8/LF、插入位置及根阅读副本一致；Git staged范围与只包含本次delta；无新模型、数据、GPU、训练、RTL/PT/TLM。
- 下一步：审阅PR72及依赖的PR52/62，按实际合并回执继续同步；不重跑39项已完成评测。Projects查询实测缺read:project，看板待有权限者同步；Issue28/59仍open。发布回执见TASK59_COMPLETION_REMOTE_RECEIPT_20261020.json。

以下保留历史交接：

## 同期已合入的历史任务状态（保留原文）

# Issue68：第二轮副本清理完成，生命周期规则已写入

2026-10-19；jieruiz；task/68-local-storage-cleanup；PR69待审未合并；tmp/local-cleanup-issue68-20261019。本轮42个已完成任务副本逻辑7.377GiB；两轮累计10.510GiB/59个副本。独有资料和增量bundle共3,042,843.0bytes留project_archives/cleanup_20261019_round2，全部ref/zip/bundle/模型校验通过；保留进行中和其他负责人目录。当前任务已稀疏检出；根及仓库AGENTS追加回收规则。两轮交付通过原PR69追加，当前待审未合并；实际发布head以PR为准。正式报告maintenance/storage_cleanup_20261019/ROUND2_REPORT_ZH.md，work/jieruiz/68为交接。无页面文件/系统设置修改；无新模型/硬件测试。Projects read:project待同步。

以下继承历史状态：

# Issue68：本地清理已完成，已推送PR待审

2026-10-19；jieruiz；task/68-local-storage-cleanup；base 6197f24a9cc03ab0dc5e2e72297457f638e37292；tmp/local-cleanup-issue68-20261019。用户授权本地项目清理，实际回收逻辑空间3.133GiB。正式报告maintenance/storage_cleanup_20261019，原始日志与恢复zip留本地，work/jieruiz/68保存索引/交接。17个已合并本人审核工作树的恢复分支仍在；唯一Qwen权重SHA核验通过。本地清理实际完成，已推送并创建PR#69（https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/69），PR待审未合并。下一步审阅后验收；本次不自动合并或关闭Issue。Projects read:project待同步；无新GPU/PPL/TLM/EDA。

以下为继承的历史状态，保留原时点：

# Issue55 第二轮PR审核交付

2026-10-19；jieruiz（真实admin/push核验）；review/55-pr-round2，tmp/pr-review-r2-main-20261019；base 679fd269ecaa4883bd79619d2f39d6ade2a7daca。用户要求继续审查，本轮5项：63/64已实际合并，49/52/62保留draft。原第一轮结果保留。

174数学检查、30评分/collector CPU夹具、来源与汇总核验通过；未新跑模型/GPU/训练/PPL/PPA。PR64发布正文SHA过期已修正，源制品不改。Issue61研究范围验收关闭，Issue28/48/50/59保持开放。报告/回执/evidence见work/jieruiz/55/round2，后续文档PR实际状态以Issue55远端为准。Projects read:project待同步。

## 继承的历史任务状态（保留时点）

# Issue28：代表任务准确率记忆已发布PR64，追加基线本地待同步

2026-10-19，已同步09:19Z三项新原BF16基线；负责人/实际认证`jieruiz`；正式仓库`rayggxia-workspace/pbit-llm-qwen-baselines`。canonical目录`tmp/project-memory-issue28-20261018`，分支`task/28-project-memory`；原集成起点为`b2527f12924a53da7334afbe78c752c101814193`。PR29已实际合并，Issue28持续维护open；首轮追加e32f731已推送并建立PR64（base集成分支，待审未合并）。本次三项基线补充尚未推送，交由当前主任务统一发布，不写成远端已经包含。

已核验canonical起始clean、GitHub身份、Issue28/PR29/PR62。两次git fetch分别连接重置/不可连接；只读GitHub API核实当前integration恰为同一个b2527f1，`git merge --ff-only`确认Already up to date，未reset或覆盖并行集成。已读最新AGENTS、README、memo及历史STATUS/HANDOFF，保留Issue55的23项审核/21项合并记录。

本轮仅同步memo、本人STATUS及Issue28 HANDOFF，根阅读副本由正式memo复制并核字节。Issue59/PR62首源348c8286，PIQA1838/ARC-E2376全量、Hella1000固定子集，BF16/FFN-only/Ising64/128/512共39配置。13scorer＋2plan CPU通过；2474原BF16完整WT2 11.652735，但向量化/cached候选sumLL差0.1168触发原门禁，未绕过。新075574源2475/2476 READY，独立naive cached与scorer逐候选sumLL最大差0.0且greedy通过，向量化最大mean/token差0.05839仅作BF16形状诊断，12pilot题判对错一致；9pilot配置完成。正式2477～2480及汇总2481不变；09:19Z原BF16三项已完成：PIQA acc/acc_norm70.511425/69.967356%、ARC-E64.393939/58.333333%、Hella1000 41.9/52.4%；新matched cached基线不能与旧native-vectorized互换。36替换项仍运行/排队，无正式替换准确率，原件已hash索引到任务分支qwen/results/task_accuracy_20261019。collector-only源0d4be877，15collector本地CPU通过；075574数值源不改。短prompt不能验证长context筛选的边界保留；实验属于Issue59，本次文档维护不启动模型/Slurm/PT/TLM。

验证：UTF-8/LF、`git diff --check`、仅三项正式文件范围、根副本/Git blob字节一致（提交后复核），PR64已在线核实open/未合并且head为e32f731。下一步：主任务核实2478～2481最新状态，将本补充与主59成果统一发布并同步Issue；Projects此前缺read:project待同步，本轮没有重查或声称看板已更新。

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

2026-10-19 17:51：Issue59/PR62首个联合ARC-E S64单seed已完成，11/39；memo5.8.1追加经验证原件入口与动态ETA，其他28项继续运行/排队。root副本与canonical保持同字节；该状态补充待同PR64推送，未宣称三seed完成。


发布视图补注：原服务器SUMMARY SHA b95c40...已完整归档，公开SUMMARY视图SHA0b6aa1f2a5f2b44d28ef4eb1351a533f415beb37da3138887182991d8ebca38c，仅将IID/拒绝法MC95字段标不适用及添加派生来源；所有科学数值不变。原始制品见server_summary_originals，转换代码publication_view.py。最终本地14检查通过；服务器仍8核心/4汇总，新增2汇总守卫仅本地。本轮发布状态以最终Issue78回执为准。
