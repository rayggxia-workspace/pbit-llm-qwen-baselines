## 2026-10-29 Issue198：数字P8 Softmax双采样主基线完成

owner rayggxia，task/198-attention-compare，draft PR199，基线01270f9c50d9475017603bf2ee7148193280ded7；主基线本地完成，远端发布状态以P8_PUBLICATION.json为准。共用FP32→fixed11/F4、max/exp/sum/公共倒数/保质量P8；128候选/S128、4lane、100MHz、SS1.08V125C。门控前端/完整systematic/完整独立R8比较：0.83015/0.85651/6.37028nJ，面积原始88347.24/94850.28/165121.56µm²，单次×0.81后0.0715613/0.0768287/0.1337485mm²；内部概率132拍就绪，完整输出166/166/294拍。含转换/存储/紧凑Bivium/直方图/ICG，不含QK、token映射、V/物理熵/全局复位时钟树。

ICG实际182/189/353个，空闲0.2084/0.2211/0.4021mW，不视寄存器保持为零功耗。v3原Bernoulli reset recovery−0.366158ns保留；v4复用同网表，启动时停钟释放复位并等20ns后启钟，仅rst_n使用setup2/hold1合同，正常数据时序不放宽；最终setup最小0.000469ns/hold0.145801ns、ICG检查非负，余量极小、无CTS/SPEF/SDF，非后布局验收。PT表外slew/load警告保留。

Systematic总数固定128、相关；P8/S128仅1bit相位影响计数。独立比较总命中可变并按固定128平均。8bit概率不是Ising8bit阈值的同精度证明，合成Gaussian2平均TV7.44%、四峰6.66%，无新GPU/模型/PPL。紧凑Bivium也可供Ising复用，不能将旧完整服务端点差额当数字算法独占收益。

正式architecture_tlm/attention_compare_20261027/digital_p8_20261029，README/REPORT/RESULTS/源快照SHA及EVIDENCE齐备；中央run attention-digital-p8-198-eda-20261029和22功耗专题已同步，91条元数据check/render通过，原90条record原字节保留。v2完成4配置/30PT，v3三门控配置24PT，v4三网表复用/启动合同24PT；已完整归档80功能回放/81920计数比较/78PT，另三个16lane12次RTL预检通过。REPORTS本机644+557+573成员逐SHA核验，v3 RAW584成员也已本机验证；v2/v4大波形仅保留授权服务器原字节归档，不谎称已本机下载。

补充16lane 38459583_2/_4/_6仍在综合，完整收集依赖作业38459807；不取消/重交健康任务，不把它们列为已测PPA。当前已完成数据来自collection_v2_completed、collection_v3、collection_v4；后续完整v2必须另存新归档/摘要，不能覆盖本次已登记SHA。SUPPLEMENTARY_STATUS.json为带时戳快照。远端根/public3/home/t6s011227/pbit_chimera_pipeline_20260920/llm_digital_p8_issue198_20261029；ops入口work/rayggxia/198/.eda_private/p8ops.py。PR待审/Issue开放，Projects沿既有限制待维护者同步；下一步为补充扫描收集、模型匹配质量和共同KV闭环。

---

## 2026-10-29 Issue198：数字Softmax后的采样纳入公平对照

owner rayggxia，task/198-attention-compare，draft PR199；本轮只读源码/文献，无新EDA/GPU/PPL/run。SANTA v2 §2.1/附录P算法5及官方commit2e5f8611两个CUDA核已核实：每头/tile偏移、warp前缀scan、floor差得到整数次数、非零压缩、保留次数进行V累加；实际CUDA有cf*V，不能按“No-mulT”名称认定所有乘法为零。PyTorch2.7.1有放回多样本路径含归一化/CDF/Philox/二分并输出索引，不推广到所有单样本实现。

对照统一为同128候选分数→可用索引/次数→共同token映射/V接口。独立Bernoulli多bit不能直接替代每次恰好选一个位置的categorical；当前Ising原始候选bit还要公平仲裁/赢家保持。数字不必生成128bit one-hot再编码；IID每样本一个均匀值，systematic每分布/tile一个偏移并直接产生计数，样本相关须匹配质量。指数权重CDF按总质量缩放随机阈值可避免物化逐项归一概率；直接计数也不必先生成S索引再直方图，端口/融合/流水不能被旧串行模型固定。

旧P0/P2的core.py:93与schedule.py:101–119已包含CDF_scan/systematic_counts/histogram费用，缺口是后半段同工艺采样PPA和同质量闭环，不能说以前所有模型均未计采样。标准dense Attention直接pV无采样，另留为质量/整条路径基线。新增DIGITAL_SAMPLING_BASELINE_ZH_20261029.md、源pin/本地SHA、功耗面积19专题；原结果和质量默认不改。发布见DIGITAL_SAMPLING_PUBLICATION.json；PR待审/Issue开放，Projects沿既有限制待维护者同步。

---

## 2026-10-29 Issue198：采样前端占整模型的条件预算

继续task/198-attention-compare，owner rayggxia，draft PR199。复用公开PR192/91f68416的Qwen3-4B后训练形状36层B1/2K整模型锚点：57.445385ms/token，原始计价面积192.738839mm²，按0.81等效156.118460mm²；片上数字门控候选2.5162W、加旧外存粗预算8.6823W，完整芯片仍未校准。只为占比敏感性移除旧Attention RNG一行，再加新前端，其余动作/时序保持，不能宣称真实新Ising整机替换结果。

32头并行、36层复用、128节点/R8、100MHz：GF64两端点/头＋已测12位阈值库=1.06467mm²/87.803mW活动；Bivium七端点/头＋阈值库=3.80473mm²/270.758mW；128小SRAM bank/头=4.44062mm²/261.472–265.344mW。条件面积占比分别0.678%/2.381%/2.768%。端点已含比较器，不再叠旧比较核；9位q用12位库计价不是最小P8版，独立模块相加非集成PT。

以32预热＋128保留=160轮，任务间隙停钟且保留漏电的未实现情景：平均1.574/5.676/5.079–5.087mW，片上占比0.063%/0.227%/0.203%，含旧外存约0.018%/0.065%/0.059%。沿实测CE-idle不另停钟，GF/Biv为32.536/118.570mW，片上1.287%/4.535%；SRAM CEB绑0持续读以活动窗口作代理261.48–265.35mW、约9.5%，并非新增静止地址idle实测。空闲门控和并行度比只比较每轮能量更重要，不能用活动功率除整模型平均功率。GF64联合相关性已有负证据，不能据低价验收。

SRAM160轮必须在128轮后刷新32新样本，80写+160读为计价提案，未功能/质量验证。再加一套共享Bivium产样器和二次阈值装载，面积至少4.55952mm²、停钟平均5.515mW，未计打包/搬运/新门控；明确两阶段且生成写读不重叠时约3.00672ms/token，不能继续套32头同时256bit/拍的装载假设。1/4/8/32并行、128/160轮、0/10%/100%空闲动态均留96情景；不启动新EDA/GPU/PPL或新增run。正式whole_model_share_20261029目录、功耗面积18专题、源SHA和模型Git blob可复算。发布以WHOLE_MODEL_PUBLICATION.json为准；Projects沿既有限制待同步，未合并/关闭任务。

---

## 2026-10-29：补齐Attention随机前端成本口径

只读复用38322118 SS100MHz三seed原件，三个原包/summary/source_manifest SHA及五个RTL与执行快照一致；无新EDA/PPL/run。每轮128个R8按现有端点复制：LFSR128份207.957pJ/0.32703990mm²，GF64两份27.107pJ/0.02398352mm²，Bivium七份84.28pJ/0.10961040mm²；面积0.81已乘。端点已含比较/输出寄存器/控制，不再加整块旧4.71pJ；外部阈值保持、物理熵/全局分发/公平RNG未计。Bivium140字供128路、12字丢弃收费；不是6.4实例。GF64联合相关性已知，Attention默认拒绝，不能直接用其低价验收。P8与旧P12/P16精度不同；修正此前未计RNG时寄存器明显胜过SRAM的判断：Bivium与SRAM81.4–82.9pJ已接近，完整方案待匹配质量/成本。

正式rng_cost_20261029/REPORT_ZH.md、RESULTS.json、derive.py，功耗面积17专题；只新增派生参考，中央90条run原字节不变。PR199保持draft/open；远端回执RNG_COST_PUBLICATION.json。

---

## 2026-10-29：128个128bit SRAM bank测试完成

继续Issue198 / task/198-attention-compare / draft PR199；本人rayggxia。生成38454852、阵列38454992、接口38455163完成。128×1编译拒绝；实际128个64×2 SRAM加读出选位逻辑，2KiB有效容量。原始面积171320.126912μm²、×0.81等效0.13876930mm²/头；每轮128bit约81.400–82.920pJ（各模式三seed均值），32头复制4.440618mm²。12功能回放/3072向量/393216bit通过，36PT窗口（含原18）均保存。下降沿输入协议最终setup=2.418762ns/hold=0.431146ns；原上升沿输入合同hold=-0.3031ns保留。最终18窗口net活动100%；厂商memory输出无组合function提示保留。无CTS/SPEF/SDF、无GPU/PPL。

正式报告architecture_tlm/attention_compare_20261027/smallbanks_20261029/REPORT_ZH.md，台账15专题与run attention-smallbanks-198-eda-20261029；748成员证据本机归档project_archives/attention_compare_issue198_20261027/smallbanks_20261029/REPORTS.zip。生成/源搬入/外部请求驱动/仲裁/V未计；64拍装载假设上游256bit/拍。不是全概率4KiB表，也不是160轮采样质量验证。现有宏独立bank成本偏高；同时间序号可用单128×128宏，其新库提取面积0.01955676mm²、9.4921pJ/字，不支持任意128路地址。

本地已完成；远端提交/回读以SMALLBANK_PUBLICATION.json为准，未写成合并/关闭。下一步是共享时间地址宽宏的接口评估与真实随机表相关性/刷新成本；不启动昂贵GPU重跑。Projects沿既有限制待维护者同步。

---

## 2026-10-29：128字概率阈值寄存器及并行比较器EDA完成

负责人rayggxia，继续Issue198 / task/198-attention-compare / draft PR199，base main，复用tmp/attention-compare-issue198-20261027。执行父提交1f4dff93加v2/v3/v4/v5冻结SHA；未新建重复checkout，未运行GPU/PPL。7top/三seed/42条RTL与门级oracle回放，8904执行拍/8610检查拍；84最终PT窗口，全部net/leaf cell活动100%。Slurm38447688及修复38447724完成，早期失败38447560与旧slew38447569原件保留。

SS1.08V125°C100MHz、原SHARK面积×0.81。真实32个X8 ICG门控，128×12/16位阈值库单头等效0.00928746/0.012273444mm²，保持33.17/37.69μW；CE常开时钟915/1220μW。8拍装载+160拍采样完整事务84.722/102.183pJ，装载30.65/40.53pJ已计。加128路比较器：0.015184778/0.020186302mm²、605.808/796.656pJ每事务。11位score库额外0.008540964mm²/头。32头阈值库6/8KiB、0.297199/0.392750mm²，保持1.062/1.206mW；加比较器、11位score及旧控制的模块面积和1.132714/1.292763mm²。36层复用时面积不乘36，能量按1152次query-head外推。完整RNG/LUT/max/转换/地址映射/V/累加均未计，不能称完整Ising PPA。

功能通过但不是物理签核：16位门控wr_data输入hold=-0.010220ns；12位门控hold仅+0.004787ns。比较器每窗口256个低slew库表外推告警，其他五top check_power通过。无缺表/无用户false或multicycle，禁用弧是常量条件传播。无CTS/SPEF/SDF/完整延迟毛刺；合成阈值活动并非真实Qwen，不能和旧p=1/32、S128/B0的控制能量直接拼成实测总能量。8拍装载要求上游16阈值/拍，ROM端口成本没有计入。

正式代码及RESULTS/SUMMARY/REPORT_ZH.md在architecture_tlm/attention_compare_20261027/regbank_20261029；功耗面积目录10_阈值寄存器与全Q头资源估算.md提供参考。原报告1953成员、历史2031成员SHA核验；本地project_archives/attention_compare_issue198_20261027/regbank_20261029，完整RAW包21.7MB留授权EDA服务器，位置/校验在私有COLLECTION。统一run attention-regbank-198-eda-20261029，根台账87→88条check/render且旧87记录字节不改；元数据校验与本轮原件核验分开，未重验全部历史原件。

本地成果已完成，准确远端提交与回读以work/rayggxia/198/REGBANK_PUBLICATION.json为准。PR199仍待审未合并、Issue开放，Projects沿既有限制待维护者同步。下一步匹配真实接口关闭hold/低slew告警，再评估16阈值/拍LUT和合格RNG吞吐；不以本轮估计宣称整机竞争力。

---

## 2026-10-28 Issue198：定点QK与有限LUT数值/短流验证完成

rayggxia继续task/198-attention-compare / draft PR199，main为PR base；独立目录tmp/attention-compare-issue198-20261027，执行父49880d16+不可变源SHA。用户要求BF16之后测试INT8或更高定点、方便输入LUT。CPU3301/GPU3302首次全零阈值断言失败，原件保留；CPU3303/GPU3304完成46配置并暴露±32饱和；CPU3305/GPU3306完成扩大范围的62配置、10种S128/burn32×3seed局部审计及14个短流PPL case。本人本轮全部作业已结束，未动其他健康作业。

原Qwen3-4B后训练revision1cfa9a7、模型/tokenizer/WT2原字节/token SHA核验，4 train query标定、8 test query×全36层×32头=9216行，固定FP32 SparQ128候选。12/12有无诊断原生logits逐位相同；v2/v3输入与13248共用结果逐项一致。实际scaled score[-17.4184,37.5958]，±32即使高小数位仍最大TV约72%，不能只看平均。范围±64：INT8 step1/2平均TV4.3517%、输出RMS6.5730%；I11 step1/16为0.5435%/0.8329%；I12 step1/32为0.2724%/0.4115%；BF16对照0.5082%/0.8433%。均为局部指标。

推荐作为待验接口的分离位宽：11位分数（或12位增加范围余量）、4小数、整数max与差值、8位LUT地址（gap step1/16、cap255）、12/16位阈值。P12平均稳态TV0.6655%/输出RMS0.8576%，P16为0.5479%/0.8330%；P8平均丢掉约1.702%目标质量。先BF16再I11/P16为TV0.6380%/RMS0.9628%，直接从累加器转换避免额外BF16舍入。单表256×P12/P16=384/512byte仅逻辑容量，不是128并行读物理面积。

固定参考train max+2在P8/P12/P16出现1414/344/74个全零头行，P16有限采样输出RMS约80.25%对理想19.59%；不能仅凭softmax平移不变性省去在线参考控制。invalid头行明确排除稳态均值并单报，不加uniform/一LSB隐含fallback；不是全部离线标定不可行证明。

短流256目标（4等间距窗、prefill2047、每窗64步、context2048增长2111），全36层每目标实际替换，原FFN保持。原生/包装8目标门禁逐字节、512 LUT项独立公式通过；各量化case 37748736 score、0饱和。PPL BF16 17.70427，纯SparQ16.50503，理想winner16.94690±0.41999，INT8step1/2 17.32488±0.63733，I11+U8+P12 17.42265±0.49642，P16 17.34924±0.21394。三seed均值约高理想2%–3%、波动明显，未证明无损/显著优劣；不是旧完整WT2，可用小样本筛查而非验收。范围选择参考test局部观察，属探索性选型。

正式experiments/attention_fixedpoint_20261028/REPORT_ZH.md、SUMMARY、PPL_SUMMARY、CALIBRATION、RAW_INDEX、provenance、COMPLETE、REPEAT_CHECK；源码audit/quantize/quality，辅助report_fixed/write_fixed_report/deploy_fixed_v3。原始11.8MB结果与逐case PPL在project_archives/attention_compare_issue198_20261027/fixedpoint_20261028_v3及个人服务器fixed3-6539a4ea8baf，27文件SHA校验；v1/v2归档不改。执行来源FIXED{,2,3}_SOURCE/CPU/SUBMISSION/COLLECTION；失败FIXED_FAILURE。实际推送/回读见FIXED_PUBLICATION.json。STATUS/HANDOFF/长期记忆增量同步，PR待审不合并、Issue不关闭，Projects沿权限限制待维护者同步。

无新RTL/EDA/PPA、无全WT2、未量化Q/K乘法，不新增数字电路台账run、不替换当前默认。下一步匹配完整PPL与11/12位分数转换/整数max/ROM/比较器/随机供给联合PPA，现有控制0.923nJ不包含这些成本。

---

## 2026-10-28 Issue198：Qwen3-4B softmax入口BF16/FP32审计完成

用户要求确定QK分数是否必须FP32；rayggxia继续task/198-attention-compare / 草稿PR199，base main，本次执行父提交0d8a6f1a加不可变5文件SHA快照；工作目录tmp/attention-compare-issue198-20261027。GPU3290已完成、本人队列为空，无全量PPL/新RTL/PPA，统一电路台账不新增run。

同Qwen3-4B后训练revision1cfa9a7、权重/tokenizer及WT2原文/token SHA核验，BF16原生SDPA参考每窗复跑两次，4/4词表logits逐位一致。WT2起点0/4096、长度512/2048，层0/12/23/35、全32头，16个query-layer/512头行；另对同一批固定SparQ128候选诊断，共32张量比较。无随机采样，单seed0确定性测试，不冒称独立1024原生行或全层PPL。

RTX5090/torch2.7.1+cu128/transformers4.51.3，全部32个被测decode调用profiling确认FlashAttention。PyTorch2.7.1固定子模块979702c8源码表明QK acc_s为FP32并直接进入softmax，之后概率片段才转BF16用于PV；没有完整score矩阵必须落盘的要求。只对本批batch1/query_len1形状实测，不冒称历史batch32/prefill所有调用都已追踪。BF16输入输出不代表全部内部BF16；eager原生BF16 score→FP32 softmax也可执行。因此FP32是原生融合内核选择，BF16 score接口可行但不逐位等价。

仅将同一FP32 score舍入BF16再用相同FP32 softmax/PV：完整KV平均/最大单头TV0.360387%/1.607700%，128候选0.357265%/1.606836%；128候选输出相对RMS跨16张量平均0.606232%、最大张量1.004689%，argmax6/512变化。不是逐头最大输出误差，不是PPL变化，不含LUT/概率阈值量化或有限随机误差。可将BF16 score作为后续接口候选、FP32保留参考，不自动修改当前默认或声称模型无损。

正式experiments/attention_score_dtype_20261028/REPORT_ZH.md、SUMMARY/RESULTS/provenance/COMPLETE/REFERENCES；源码audit.py，辅助work/rayggxia/198/deploy_dtype.py/report_dtype.py。DTYPE_SOURCE/SUBMISSION/COLLECTION绑定原始6文件SHA及3290；本机project_archives/attention_compare_issue198_20261027/score_dtype_20261028。实际上传回读查DTYPE_PUBLICATION.json；PR199待审未合并，Issue开放，Projects沿权限限制待同步。下一步在同协议下验证BF16分数＋有限LUT接口质量；本轮不启动全量PPL。

---

## 2026-10-28：128节点控制EDA已完成，按能量与时间联合选型

负责人rayggxia；Issue198 / task/198-attention-compare / 草稿PR199，base main，执行源父提交5f4f5bde及CONTROL128_SOURCE.json精确SHA。工作目录tmp/attention-compare-issue198-20261027复用，未新建重复checkout。

用户明确不能为了面积牺牲功耗和时间。8个top重新DC；本机168回放106227拍，服务器336个RTL/门级回放212454拍通过；56个PT窗口、8top额外时序审计完成。G16融合、binary winner、10位计数、弹性流水主候选：原面积0.014409360mm²×0.81=55nm折算0.011671582mm²；稀疏p=1/32三seed、S128/B0全query平均0.922946nJ、161.667拍/1.61667μs、570.833μW，7.210516pJ/输出。串行2.246279nJ/415.667拍且面积更大，排除；G32能量仅低0.83%、面积高10.79%且setup余量更小，保留备选。提前保持dense有收益但setup仅0.052158ns，暂不主选；公平随机源本体仍未计。

全1压力首帧至首输出3拍、稳定II1、完整query133拍，不能视为独立有效样本。S64/256/512、burn32功能/周期已测，没测相应能量；不由硬件结果决定模型必须burn0。候选局部7位index不等于KV物理地址；不包含概率驱动/随机源/token映射/V读取/累加，也没有给其附加串行调度。

SS1.08V125°C100MHz、IO delay0/slew.1ns/load.02pF/setup uncertainty2ns/hold.1ns；无SDF/SPEF/CTS/毛刺完整建模。全部整体hold负；主候选−0.056977ns来自cfg_ready→configured，内部reg-reg setup/hold为+2.801410/+0.134473ns。仅SS内部通过，不是全接口/FF hold/物理签核。PWR-981虽100% net/cell标注仍保留；禁用弧p/C/c、无loop-breaking/user false/multicycle。不缩放功率/时序。时钟持续空闲445.9μW，未实现/假扣ICG。

正式结果architecture_tlm/attention_compare_20261027/control128_20261028/RESULTS_ZH.md及RESULTS/COMPARISON/TIMING_AUDIT.json。本机原报告2426成员、额外时序96成员SHA核验，完整大包仅授权EDA远端；恢复索引work/rayggxia/198/CONTROL128_ARCHIVE.json，私有原件project_archives/attention_compare_issue198_20261027/control128_20261028。统一台账新增attention-control128-198-eda-20261028；84→85条增量check/render通过，旧记录不变。仅schema check不冒称对全台账原件重哈希，本轮新原件核验单列。

DC38444217/38444227，replay/PT38444238/38444263，timing38444334，collection38444378；无本轮GPU/PPL。首次依赖提交在创建job前拒绝，已有作业完成后重提，原失败回执保留。当前本地实现/测试/归档/台账完成；准确分支上传SHA和回读见CONTROL128_PUBLICATION.json。PR199待审、未合并，Issue保持开放，Projects沿既有限制待同步。下一步修接口hold和标注，再结合真实候选激励及外部接口成本，不启动未经要求的昂贵模型重跑。

---

## 2026-10-28 128候选反馈／仲裁控制进行中

用户明确只做控制，不纳入概率驱动、随机源本体、V读取和累加，不施加这些模块的保守调度。rayggxia继续Issue198/PR199，基线5f4f5bde。8top比较G8/G16/G32融合、G16两级/提前保持/one-hot/32位计数器/串行参考；其他10位计数器、总更新上限1023。168项本机Icarus/flat oracle、106227拍通过，含1023边界/溢出/无效配置、rank cap失败、三seed压力、S64/128/256/512和burn0/32、输入/输出等待；未改变旧512源码。

源362文件manifest8b71c9bb83cc87b7d1302c23a4324086638d65f81cde3a806c2acead15c13552，执行快照v1不改。EDA DC预检38444217完成，余7项38444227、VCS/PT预检38444238已提交；首次replaypre的Slurm历史依赖被拒绝，未创建作业，保留回执后无依赖提交。准确状态查CONTROL128_SUBMISSION及私有ops128.py poll，不重复作业。计划56功耗窗口，SS100MHz旧同约束、面积×0.81，hold/标注未验收。新目录architecture_tlm/attention_compare_20261027/control128_20261028；统一台账待完成后登记，不称现有完整PPA。

## 2026-10-28 SparQ＋Ising完整WT2三seed完成（Issue198 / PR199）

负责人rayggxia；task/198-attention-compare，原独立checkout继续复用，PR待审未合并。GPU Slurm3270_[0-2]完整结果均已收齐，独立SHA/回执、299077目标恰好各一次、36层计分覆盖及每头160更新/128保留采样审计通过。执行源a7108f8cba2c72ad319114af34557f4cec2b793d；短流源d9b64717641ae8f7efeaa2e9375a1b01a30361d0。模型Qwen/Qwen3-4B后训练revision1cfa9a7208912126459214e8b04321603b3df60c，权重/tokenizer/原始train-test/token SHA在provenance中核验。原BF16 FFN/投影/归一化不改，dense prefill、全36层单query Attention替换；无chat模板、无BOS，window2048/stride1024、batch32。

完整PPL：BF16 11.538153；纯SparQ 10.797926；SparQ＋winner S128 11.177429±0.006594（三seed样本标准差），相对BF16 -3.126%，相对纯SparQ +3.515%。固定r32/k128/local32、burn32/spacing1，赢家地址直接V读出；理想FP32 sigmoid/Philox行为参考，不是器件或q/256实测。完整结果不同于1024目标初筛，短流S32退化/S512≈IID128的负结果保留。

完整平均每KV组唯一V 54.594行。理想标量读取、候选K维度复用、4Q完整去重下，K+V逻辑元素需求为dense的17.41%、纯SparQ的87.91%；不是实测DRAM字节或速度。SparQ第一阶段全N近似softmax和top-k仍存在，只替换候选上的第二阶段softmax/PV。当前说明质量可行但未证明同质量完整硬件PPA胜出；完整缓存、布局、仲裁、累加及有限相关采样成本待补，不继承旧控制RTL为整机PPA。无新数字电路台账run。

正式源码及报告：experiments/sparq_ising_20261028/results/REPORT_ZH.md、SUMMARY.json。准确SOURCE/SUBMISSION/COLLECTION见work/rayggxia/198/QUALITY_*；原始结果保留本人GPU目录/home/Hongjie_Zeng/projects/attention-sparq-ising-issue198-20261028和本地project_archives/attention_compare_issue198_20261027/quality。report_quality.py可按封存原件重建。下一步以纯SparQ为硬件主要对手，在匹配质量下接有限KV读出和控制费用；未自动启动额外全量扫参、未合并PR或关闭Issue，Projects权限待维护者同步。发布以QUALITY_PUBLICATION.json和远端实际head为准。

## 2026-10-28 SparQ + Ising Attention-only：短流已完成，完整WT2运行

负责人rayggxia，继续Issue198/草稿PR199，不接管PR163。用户明确授权GPU实验。Qwen/Qwen3-4B后训练revision1cfa9a7，原BF16 FFN/QKV/Wo/norms不改。论文GQA概率求和r32/k128/local32；赢家保持argmax初始化、burn32、spacing1、理想FP32 sigmoid/Philox，不是q/256器件实测；实际赢家地址直接V读出，没有第二次PV抽样。

短流科学源d9b64717641ae8f7efeaa2e9375a1b01a30361d0，CPU3263/GPU门禁3264/三seed3265已完成。8窗context2048，每窗128目标，共1024；所有计分目标全36层单query，非完整WT2。BF16原生/包装logits逐字节相同，5CPU测试、960帧GPU逐帧oracle和稳态TV门禁通过。三seedPPL：BF16 13.562400；纯SparQ12.822322；winner S32 14.741226±0.637781；S128 13.342155±0.145833；S512 13.006869±0.027843；IID128 13.002485±0.031817。相对纯SparQ仍有有限采样损失，S512接近IID128提示相关性成本；不能称无损或PPA胜出。S128四Q共享KV组平均唯一V55.11行，仅理想逻辑去重，不是实际DRAM流量。

完整WT2源a7108f8cba2c72ad319114af34557f4cec2b793d；CPU3268、GPU3269门禁通过，batch32显存<28GiB。Slurm3270_[0-2]正在运行，固定S128三seed，每32窗配对BF16/纯SparQ/winner，计划299077目标；不得将已完成分片当完整PPL，不重复提交或取消健康任务。每片随机键含起点，避免随机流重置复用。GPU数值运行耗时不作ASIC周期。

源码experiments/sparq_ising_20261028；阶段报告results/REPORT_ZH.md、SUMMARY.json。准确SOURCE/SUBMISSION/COLLECTION均在work/rayggxia/198/QUALITY_*；原字节本地project_archives/attention_compare_issue198_20261027/quality及本人GPU独立目录/home/Hongjie_Zeng/projects/attention-sparq-ising-issue198-20261028。collect_quality.py按源前缀下载校验，report_quality.py核三seed完整回执/目标/层/采样计数；完整结束后再次收a7108f8cba2c并生成完整表。未训练、无新RTL/EDA/数字台账run；PR待审不自动合并，Projects待既有权限同步。

发布确认（2026-10-28）：KV读取与数字Attention基线调研源1f3ce3ee63653e1a88fb0b73f65eba5cd59ac2d0已推送草稿PR199；13文件完整tree/本地同SHA、7关键文件逐字读回通过。Issue198评论6461917653；100地址核验/18旧单头案例布局推导、功耗面积09三文件同字节，不是新GQA模型/时序/PPA。真实4头QKV与同质量完整链仍待补；82run不改，无运行作业。回执work/rayggxia/198/KV_BASELINE_PUBLICATION.json。

2026-10-28 KV读取与经典数字Attention基线调研：正式KV_DIGITAL_BASELINE_ZH_20261028.md/SOURCES。锁定FlashInfer和vLLM布局文档；主TLM已做GQA并集/在线融合，不另造整机。本次100地址几何核验、18旧2K/d128/S128单头案例原ZIP/成员SHA复核并做布局换算；无新抽样/模型/DRAMSys/RTL/EDA。P0旧轨迹V连续行32KiB→指定通道交错页示例456KiB，不是GPU实测/同质量GQA；真实4头QKV/同质量S/有限SG与bank访问仍待确认。Qwen3-4B形状2K全KV每层8MiB、36层288MiB；下界不等于时延。功耗面积目录09与两份数据已同字节同步，旧文件和82run不改。仅只读Issue186/PR192@91f68416，未改统一入口/默认资源。发布见KV_BASELINE_PUBLICATION.json及Issue198最新评论，草稿PR199待审；无运行作业，Projects待维护者同步。

发布确认（2026-10-28）：Softmax文献参考已放入统一功耗面积目录08文件及CSV/JSON，共14点；源310c0381978957df95a391af48779bacd795cc45已推送草稿PR199，5关键文件逐字读回、完整tree/本地同SHA通过。根阅读镜像3文件同字节；82run/105旧文件未改。Issue198评论6461568004，PR待审未合并。回执work/rayggxia/198/SOFTMAX_REFERENCE_PUBLICATION.json。

2026-10-28用户要求调研也进入功耗面积文件夹：已在统一台账新增08_Softmax文献功耗面积周期参考.md及references/softmax_20261028的CSV/JSON，共14个文献点，含原工艺、整行拍数、时钟ns、面积和已有功耗/功耗频率；未知整行周期明确保留null。只列文献，不新增本机run、不跨工艺×0.81；根固定阅读副本3文件同字节，既有文件/records保持原SHA。复现build_softmax_reference.py；发布见SOFTMAX_REFERENCE_PUBLICATION.json及Issue198最新评论。PR199待审；无运行作业，Projects待维护者同步。

发布确认（2026-10-28）：普通数字Softmax调研已推送草稿PR199，源e73e50abc414c7b5ebd442a5c0f515880260236e，完整tree与本地同SHA、4关键文件逐字读回通过。Issue198评论6461443490，未合并；PDF私有归档SHA和5行周期换算已核。无新RTL/EDA/模型/台账run。准确回执work/rayggxia/198/SOFTMAX_PUBLICATION.json。

2026-10-28 普通数字Softmax调研完成：512输入公开FP16/DW/P8为199拍/45nm 0.283300mm²；fixed32/LUT/P1/2/4为1542/775/392拍、0.059/0.085/0.138mm²（NOREG，外部存储另计）。65nm小定点核与FP精度/边界不同；不据跨工艺文献宣称Ising胜出。正式SURVEY/SOURCES记录PDF SHA、页面/代码pin、失败与算术；私有原件已逐SHA归档。无新RTL/EDA/模型或registry run、无运行作业；上传状态见SOFTMAX_PUBLICATION.json。下一步同SHARK库实现明确精度/缓冲的数字及CDF采样对手，本轮未启动。Projects待维护者同步，PR199待审未合并。

发布确认（2026-10-28）：Attention服务器DC/VCS/PT已推送草稿PR199，源2c4e4bafb74d41779bbaff78e346d0800172bcc8，39文件完整tree及7关键文件逐字读回、本地同SHA通过。Issue198评论6460241999，未合并；8DC/116回放/66PT，hold违例与PWR-981保留。81联合台账，1662报告/72诊断成员SHA已核，原始大包仅服务器，本任务无运行作业。回执work/rayggxia/198/EDA_PUBLICATION.json。

2026-10-28服务器评估已完成：8DC/116VCS回放230400拍/66PT窗口及8top时序审计，所有hold违例，PWR-981保留；无签核/模型结论。主候选G16融合折算0.035969mm²、全1控制17.17pJ/输出。准确结果RESULTS_ZH.md，源/作业/原件EDA_*；原始私有大包仅服务器。本地报告包逐成员SHA与72诊断成员已核；上传见EDA_PUBLICATION.json，PR199待审。下一步IO/reset合同/hold/标注，无需重跑健康原任务。

## 2026-10-28 EDA服务器测试进行中

用户明确授权本任务EDA实测；延续PR199/task198，不接管pbit整片任务。已通过现有客户端验证登录、库SHA与本地一致；私有连接/库/模型位置仅在.eda_private。DC预检38437604因拒绝RTL先引用后声明coin_mask失败；仅调整声明顺序，新20项/90000拍独立oracle通过，旧快照保留。修正预检38437625完成，G16p2 setup约+0.44ns、hold约−0.02ns，不能称时序通过。其余DC矩阵38437668（7项，%2）及VCS/PT预检38437709/矩阵38437736已提交。SS1.08V125C/100MHz、输入slew0.1ns/输出0.02pF、setup uncertainty2ns/hold0.1ns；无SPEF/CTS/SDF。原始面积×0.81另报55nm折算，功耗时序不缩放。长任务均Slurm，已冻结v1/v2/v3且逐SHA校验；真实状态以后续收集回执为准。不得重复提交健康任务。

发布确认（2026-10-27）：完整Attention反馈/仲裁v2已推送草稿PR199，源7fe360390c01de5195e504094f36ee62735b02be；56文件完整tree与本地同SHA、7关键文件逐字读回通过。Issue198评论6445525003；待审未合并，STA/PT及后训练/全V链仍待后续，无运行中任务。准确回执work/rayggxia/198/CONTROL_PUBLICATION.json。

2026-10-27 控制v2本地完成，上传状态见CONTROL_PUBLICATION.json（尚未生成即未确认发布）。完整赢家/拒绝反馈仲裁RTL、8固定PPA top、独立oracle/数学检查、DC/PT脚本在control_v2。124RTL项422800拍及3个cap64零延迟门级1920拍通过，8个55nm SS映射0.018058–0.056112mm²；STA/功耗未跑，不把TB100MHz当时序通过。源码/原字节/公开包/台账/记忆同步见CONTROL_*。保留G16融合/两级及G32候选待STA；源供给/完整V链/后训练QKV/GQA/D1仍待补。无运行中GPU/Slurm/许可EDA作业；PR199草稿、未合并。

已发布：草稿PR199（https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/199），科学提交5fad0fc32f5284560c38c03f4fe28657f936f553；7关键文件远端逐字回读、完整Git tree和本地相同SHA导入通过。Issue198评论6443236705；待审未合并，广泛验收仍开放。PUBLICATION.json为准确回执。

# Issue198交接

2026-10-27，rayggxia。用户指定两份Attention资料后，本轮完成第一阶段可运行代码与功能仿真。任务更广泛的验收保持open；准确发布状态见PUBLICATION.json，不能用本文件的本地完成冒充已合并。

仓库rayggxia-workspace/pbit-llm-qwen-baselines；task/198-attention-compare；main base d83eeb1fc6b89a3dff51b5b62bf79acf665c7166；独立最小worktree C:/Users/86134/Documents/a_P_BIT/tmp/attention-compare-issue198-20261027。原GitHub CLI网络getaddrinfo失败，使用认证rayggxia连接器发布；未改变历史origin/他人分支。

正式代码architecture_tlm/attention_compare_20261027：core.py、schedule.py、run.py、quality.py、test_core.py；rtl/attention_rejection_control.sv、nr_singleton_tree.sv、tb_rejection.sv及validate_rtl.py。P3/P4复用main已合PR88三个模块，未复制改写随机算法；源SHA在INPUTS和执行SOURCE。数字参考输入BF16存储、算术FP64数学oracle，未冒称逐位BF16 MAC。

已验证6机制测试、108合成案例、72项预算探索；RTL9例22500拍通过，N16/64/512，seed17/503/1009，配置/输出/公平位等待、reset、cap、m24上限均覆盖。Icarus10.1在Windows沙箱内启动WinError623，沙箱外自动审批后短验证成功。rtl_v2打印格式失败、旧快照和负结果均归档；最终RTL为rtl_v4，未跑综合/STA/PT。cap失败会在输出若干地址后报告failed，下游必须丢弃整query部分和，不得用部分输出充成功。

原始输入为固定normal QKV，未加载真实模型/文本/tokenizer；不适用模型SHA/BF16 PPL复现门禁，不能引用旧Base证据作新模型。L512/2048/8192、d64/128，S=L/16，筛选8块。单一输入/三seed均值过解析IID128 MSE阈值仅探索；P3/P4须S512，117264/22181条件拍，对D033586；没有能量/面积胜出结论。

重跑命令见正式README，必须新输出目录。正式Python为C:/Users/86134/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe（3.12.14，NumPy2.3.5）；Icarus位于C:/Users/86134/Documents/a_P_BIT/sc_weight_storage_or4_20261014/tools/iverilog/bin，ivl-lib为同级../lib/ivl。CLI命令与环境见CONFIG/VALIDATION。

RAW_ARCHIVE.json是5.31MB原始ZIP及399成员逐SHA，包含逐case事件/地址/结果、全部bit轨迹与编译日志、历史失败；.vvp可重建不归档。Git保留小型FINAL汇总/配置/SOURCE/manifest与QUALITY/RTL VALIDATION。读取manifest中的某个case原件时，从ZIP的results/sweep_final/对应成员取出并核对SHA。输入与外部资料保持原位置，不上传用户PDF/工艺库/模型。

统一台账同PR仅新增attention-rejection-198-20261027；main缺全套工具，work/rayggxia/198/registry_check用根现有78记录增量合成79并check/render；READING_SYNC记录根镜像原记录未改的核验。本人Issue28记忆维护副本和根镜像原有历史差异，分别追加同段，旧字节保留，preimage在归档。尚未执行远端Projects同步。

下一步按优先级：

1. 将新RTL真实捕获→树→校正/反馈→配置完成→输出的边沿时序接到PR88或可替换适配器；源配置/稳定等待外供，不能删sink检查绕过PR192未实现映射。
2. 用后训练真实QKV建立同输入数学/逐位参考与质量曲线；若新增模型比较，核对model revision、权重/tokenizer、train/test SHA并同轮重跑未变BF16。旧78 Base仅诊断引用。
3. 实现赢家完整count/无偏按秩仲裁RTL；补共享V有限表/缓存/返回/累加；D1固定ITA commit/许可后移植或建立明确INT8合同。
4. 沿统一unified_v6接口补GQA集合复用和真实memory后端，报告固定资源与质量/吞吐匹配；Link宏条件模型不是新整机版本。
5. 若用户要PPA，先N512代表控制与公共算术STA/PT，不重测已有源本体；按相同PVT/负载/活动绑定计价。未知完整成本留null。

无本任务运行中GPU/Slurm/许可EDA或自动化。保留最小待审目录；恢复优先复用，不新建全量副本，不清理其他成员。PR待审不关闭Issue。

控制v2原始目录已逐SHA归档后回收，释放629349369字节；保留最终小汇总与PPA源bundle。重现report.py需从CONTROL_RAW_ARCHIVE.json所指ZIP恢复对应results成员；逐成员SHA必须一致。CONTROL_CLEANUP.json记录范围，未删除其他任务/共享库。
