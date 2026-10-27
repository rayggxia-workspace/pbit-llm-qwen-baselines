## 2026-10-27 OR4及矩阵对照验证清单

- 用户要求OR4验证，已补STOCHASTIC_METRIC_AUDIT_ZH.md第8节和下一配置JSON。历史G4已做旧4096拍PPA，约50%活动比G1降10.28%，不是新T32/共享R8结果；旧DFF/四SRAM完整模块还有hold/X/Z限制。当前T32精确树未接OR4。
- 首轮T32/N64/M1→M8/SS100：S0精确树、S1窄位平面精确、S2先计数后加权、S3普通OR4、D0成熟INT8、D1确定位串行；S4互斥OR4定义清楚后补。先数值/功能筛选，再STA/PT，胜出候选扩N256/1024及M64。
- 普通OR4按符号/有效位权分组，必须测共享源相关偏差；S2计数与S3 OR不能交换。新电路run仍为0，未改其他任务RTL/冻结执行。发布按PR189最新head与Issue评论，待审未合并，Projects待权限。

## 2026-10-27 DS-CIM等随机矩阵指标审计

- 用户后续明确新矩阵对照T=32，已记录MATRIX_COMPARE_NEXT_CONFIG.json；单路计数6bit、64路位平面累计12bit、B4完整带符号累计25bit，原始W8存储位不变。未修改他人T64固定top/历史结果，无新RTL/PPA；当前发布状态按PR189与Issue评论。
- 发布确认：源ea35c581e876fba69ebfa0f037eff92b202eb5be已上传PR189，7源文件逐字/blob/tree及本地同一SHA通过；准确Issue评论与18探针范围见STOCHASTIC_AUDIT_PUBLICATION.json。仍待审未合并，无新硬件节能结论。
- 新报告STOCHASTIC_METRIC_AUDIT_ZH.md及JSON。核对DS-CIM一位归一化/T64效率与T256质量/CMR64并发、SRR丢低位和缓存边界；交叉uGEMM、SASCHA和tubGEMM。上轮数字投影与CNN吞吐换算降为风险参照，旧价格数字保留，不当同质量胜负。
- 当前B4T64三级显式数据状态374bit/输出（非实际综合DFF计数）；概率/权重/档号在固定帧内静态，当前计数DUT外部存储不能重复归因。精确累加有文献依据，不判作根本错误。
- 发现固定W/bin线性tile可严格重排为每输入先计数再加权；B4/B7×T32/64/128×三seed共18软件探针，逐事件/计数/带位权切片整数全等，不跨SiLU/FSM/反馈。尚未实现新RTL或测得PPA收益，不新增数字run/服务器任务。
- 沿用Issue187/PR189，发布状态/准确源提交见STOCHASTIC_AUDIT_PUBLICATION.json（生成后）；PR待审未合并，Projects待权限。后续可新增严格等价硬件对照，不自动启动昂贵实验。

## 2026-10-27 SC/数字矩阵定量估算追加

- 发布确认：科学提交d23dd91a3c8b2bc6337aa7502fd553f326b5c598已推送PR189，7文件逐字/blob/tree通过，本地导入相同SHA；Issue评论6442717767。原INT8投影未含bin对齐/宽累加，不能声称同质量胜负。回执SC_DIGITAL_ESTIMATE_PUBLICATION.json；开放待审未合并。
- 用户要求先估算跨工艺各指标。报告SC_DIGITAL_ESTIMATE_ZH.md、完整机器表SC_DIGITAL_ESTIMATE.json；输入原件SHA在SC_DIGITAL_INPUTS.json，复算estimate_sc_digital.py。原55/28nm文献数据和历史实验不改。
- 最有利B4/T64三级核64输出复制＋共享前端代理：1.744mm²、43.47mW、701.25ns/向量、30.48nJ/4096有效MAC；64×64 GEMM约44.88µs/1.951µJ。相对55nm MobileNet任务等效能量高26.7%，相对LeNet低21.6%；数字时间列均为吞吐换算，非目标矩阵实测。
- 同吞吐64数字MAC的粗55nm投影约0.068–0.089mm²/3.89–4.50nJ，仅情景，不是已实现RTL。T32/128、B7与ICG、权重存储成本另列，质量未验证，外围未闭合。
- 本轮只有算术后处理，无RTL/EDA/TLM/服务器/模型运行、不新增数字run。沿用Issue187/PR189，发布准确提交/回读状态见SC_DIGITAL_ESTIMATE_PUBLICATION.json（生成后）与Issue阶段评论；PR待审未合并，Projects待权限。实际硬件实现仍按独立任务接续。

## 2026-10-27 55nm/28nm普通数字矩阵基线调研

- 发布确认：源提交0231917514b80525c300fb5461d8a080413aebbb已推送PR189，8文件逐字/blob与tree核验通过，本地导入相同SHA；Issue评论6441943866。开放待审未合并，回执DIGITAL_MATMUL_PUBLICATION.json。
- 沿用Issue187/PR189；新增DIGITAL_MATMUL_55_28_ZH.md与DIGITAL_MATMUL_SOURCES.json，核对两篇全文、RDCIM机构摘要、作者MIT RTL固定ebe4db7d的7文件。公开SAED32与论文SMIC28工艺不同；55nm功耗为含176KB存储的后布局协处理器任务功耗。
- check_digital_matmul.py验证9文件原字节SHA及能量/峰值时间下界，结果DIGITAL_MATMUL_CHECK.json；没有执行作者RTL/EDA/PPA/TLM或模型实验，不能称已完成55nm移植。真实64维GEMV时延仍需后续测量，现有BF16核不作为强INT8唯一基线。
- 本地资料完成；上传、准确源提交与回读状态见DIGITAL_MATMUL_PUBLICATION.json（生成后）。PR待审未合并，Projects权限仍待同步；不接管#193/#186实现。

# Issue187交接

## 2026-10-27 保守调度审计追加

用户要求将当前保守调度整理为文件并核查论文惯例。沿用本Issue/PR189，不修改Issue186的实现。只读PR192@556462dc5db37582310302ed8b916d717b4d6ceb与其12项500MHz条件结果；报告CONSERVATIVE_SCHEDULING_AUDIT_ZH.md已推送源提交2a7352b767fb6966b800a04522d0650bae3864eb，6文件逐字回读/tree通过，本地同一SHA。PR仍待审未合并；回执CONSERVATIVE_PUBLICATION.json，Issue评论6435467483。

执行：python -B work/rayggxia/187/check_conservative.py --source-root C:/Users/86134/Documents/a_P_BIT/tmp/ffn-local-pipeline-issue186-20261025。产物CONSERVATIVE_CHECK.json记录8源码SHA、12结果/派生配置SHA、两任务预约微例与报告SHA。微例是软件Scheduler验证，不是新数字/PPA run；无全模型重跑。原33条证据及旧HLS验证不改。

结论：FIFO预约、宏DMA排空、SRAM整描述符占用、数字预填充关闭和SC跨窗口限制值得隔离验证；数字/SC优化不对称；保守PPA与乐观假设并存，不能称整体上界。不概括“大部分模拟器不保守”。下一步实现仍由Issue186接续，保持容量/依赖/响应/计费守恒。

负责人rayggxia；日期2026-10-25。任务为只读文献调研及正式研究文档发布，无新硬件/模型实验。

## HLS专题追加（2026-10-25）

已推送源提交884b9717852fa17cd2893413ea14cc614dbbc64f，9个文件读回一致，Git tree21989edb4813b87959f7508d074c241422418c44与本地index相同；精确commit已导入。PR189待审未合并，后续元数据head以PR为准。长期备忘录同字节同步并保留既有字节；其维护提交归Issue28。
用户询问功能＋工艺库如何确定周期、论文是否需要HLS。沿用本Issue/PR189，新增architecture_tlm/simulator_survey_20261025/HLS_LATENCY_ZH.md与HLS_SOURCES.json；不扩大至实现。核对5篇论文及工具官方资料，明确HLS、Chisel/SpinalHDL、手写RTL三路线，Latency/II/时钟与反压区别。只读PR190@ee21c0ce的ffn_latest/config及MATURE_SCHEDULING，引用其最新结果替代旧“186实施中”的时点，不改其他任务文件。

建议优先做桶归约/系数恢复/宽位累加的ASIC HLS小试点，同时闭合数值语义与数字基线。Catapult/Stratus许可和服务器环境未核实；本机PATH未找到命令不能推断服务器没有。本轮无HLS/RTL/EDA、TLM运行、模型质量实验；仅文档/引用/当前源码SHA及参数复算检查。实际发布回执见HLS_PUBLICATION.json，维护备忘录见HLS_MEMORY_SYNC.json。下一步等用户的实施指令与PR审核，不能据建议自动提交昂贵EDA作业。

## 基线和成果

- 仓库rayggxia-workspace/pbit-llm-qwen-baselines；分支task/187-simulator-survey；main基线5273e5d9fdae811a714f1a278fee6e776c5675af，tree bdf5aca1429971b4e2db0f4625769e11c2f37580。
- 独立稀疏worktree：C:/Users/86134/Documents/a_P_BIT/tmp/simulator-survey-issue187-20261025。
- 正式成果：architecture_tlm/simulator_survey_20261025/六个文件；源数据EVIDENCE.json，表/CSV由build_and_check.py生成。
- 本地来源PDF未上传。source_checks/保留三个渲染页供核表，已.gitignore；原PDF路径/大小/SHA见SOURCES.json。没有模型/工艺库/长轨迹。
- 引用PR183固定head0341b4acde1e0afd7decf4a48b037e6b376343d8，核查时open未合并。Issue186负责调度实现，本任务仅提供验证需求。

## 实际检查与未运行

执行：bundled Python -X utf8 work/rayggxia/187/build_and_check.py；33记录/67URL文档一致性通过。结果和文件SHA见VALIDATION.json。最终git diff --cached --check应再次执行。

三路原文证据经父任务转录、原研究分支复核；修正Kelle表定位、PIM-GPT普通DRAM/PIM时序区分、X-Former ADC来源、LLMCompass锁频、Timeloop验证集、Accelergy占比误差、SANTA v2版本及TPOT定义。

没有论文artifact运行、模型权重/语料实验、GPU/服务器、TLM执行、RTL/EDA/PPA。模型/数据SHA不适用于本轮文献任务，不能将文档检查数当性能验证。

## 发布与下一步

PR189已发布、开放待审未合并；源提交725a8e69f4f02d331f33b67e3ff1810b22f07585；11个源文件逐字远端读回，tree 1a7095817a1df079838b8b778f8104af69c95755与本地一致。回执见PUBLICATION.json。只提交本任务显式文件。远端Git网络CLI不可用（getaddrinfo线程错误），采用已核验rayggxia连接器创建Git对象/分支/PR；未改变历史origin。通过SOURCE_COMMIT.json恢复精确commit字节，经Git SHA验证后导入本地，未生成不同历史。

PR待审不关闭Issue，不自动合并。下一步按审阅意见补来源或需求；若要实现建议，接续Issue186或另立独立可验收任务，不在本文档PR混入代码。Projects权限/写入未核实，待同步。

长期备忘录唯一维护目录已有未提交更新，已在确认根镜像字节一致后只追加本任务入口并同步；旧字节保留，前后SHA见MEMORY_SYNC.json，其维护提交仍归Issue28。交付后保留此最小待审worktree，不创建额外全量副本。3个ignored核表PNG总量很小，原用户PDF仍在原路径，清理本工作副本时可重新渲染。
