
## 2026-11-27｜FP24指数缩减与0.5B独立验证完成

Issue225/PR266，rayggxia。源00e025c4671aa61751d6585b5ab874b13e93e3af，Slurm62267/62268 COMPLETED0:0，87/5秒，各6项CPU测试PASS。4B全36层封存轨迹写回指数GU−18..7、Wd−18..12；Qwen2.5-0.5B-Instruct全24层/3上下文独立随机FFN回放为−17..3、−17..10。E6/M15(22bit)与E8/M15全部同值无上下溢；常规E5有下溢，候选22bit状态载荷12×128为4.125KiB，较FP24少8.33%(384B)，物理宏不保证同比减。E6/M17可保留24bit增加2bit有效精度。

0.5B固定后训练revision7ae557604adf67be50417f59c2c2f167def9a775，7文件/官方LFS SHA核对，未用Base。匹配原BF16完整WT2 292窗/299077目标PPL12.8361204065；3上下文×24层×2路径144轨迹，完整GU14/Wd76 K64；GPU整数oracle、144轨迹SHA、原生logits不变及账本核验通过。该新模型未作T64适配训练，数制回放不反馈后续层，不是FP24模型PPL。

FP24整数直出S/S2 P8与旧参考逐项一致，raw-g S8/F3也匹配；原模型仍用P8重建g，4B/0.5B raw路径阈值不同3.78%/3.54%，未切换。现有RTL/TLM/默认64位及PPA不改。正式experiments/fp_state_exponent_20261127/REPORT_ZH.md、RESULTS.json/sha；私有work/rayggxia/225/fp_exponent_20261127/HANDOFF.md及各run/original，远端个人/lustre/home/lgzhang/zhj/fp-state-range225-20261127。下一步候选实际FP24/22前向PPL与共享浮点流水线电路比较。PR待审未合并、Projects未操作；Issue28远端依维护流程待同步。

## 2026-11-27｜FP24真实链小测完成；24/32定点完整WT2完成

Issue225/PR266，负责人rayggxia，分支task/225-cim-bank32-20261124。FP24执行源d81f77f1，62265 COMPLETED/0:0（6分59秒）；本地/Slurm各9项CPU测试PASS。72真实GU/Wd投影样本、36层、4个token位置、完整40/152块；原GPU整数重放精确，288真实链Fraction、72 NPZ SHA及原结果汇总独立核验通过。FP24正常数E8/M15、逐tile与逐更新RNE，无溢出/下溢；g/u成对码34/27648变化（0.123%），Wd最终BF16 8/36864（0.0217%）。固定24分别15.57%/92.21%，固定32为0.0072%/1.389%，BF16部分和79.30%/86.47%。这是同事件局部重放，不是FP24前向PPL。

同环境原BF16完整WT2 PPL11.5364289819；模型/文本/源身份一致。FP24 REPORT_ZH.md、RESULTS.json位于experiments/t64_fp24_state_20261127，原RESULT SHA b8eebabe055440df04aead97dcf9f8b94f78555c32480321148b47ba1ca38cb4，私有run_v1下原件/VERIFICATION/SUBMISSION保留。

此前完整WT2已齐并核验：64位10.6283923845、32位10.6254049102（−0.0281%）、24位定点10.7427570709（+1.0760%），单seed101、每项292窗/299077目标，完整窗口与NLL/目标SHA/36层覆盖匹配；62263/62264 COMPLETED/0:0。FULL_RESULTS_ZH.md、FULL_RESULTS.json位于experiments/t64_narrow_state_20261127；私有fast_full_v1/FULL_VERIFIED.json。32位微小改善不称显著提升；没有FP24完整PPL结果。当前这些作业均结束，不重交。

未改变现有RTL/TLM默认64位或PPA，无训练/新硬件结果。FP24下一步为实际前向PPL与共享浮点流水线电路比较。PR未合并，Issue225更广工作不关闭；Projects未操作。Issue28远端备忘录仍按维护流程待同步。

## 2026-11-27｜窄位宽PPL快核已验证并切换并行

Issue225/PR266，负责人rayggxia。原T64/W8、GU16/Wd32、x/g/u组64基准+S/S2、准确Attention不变。原逐tile Python参考约93秒/窗；融合Triton核通过16独立oracle、4长K逐位及计数对照、24/32各一个真实模型原窗含NLL逐项一致，计时33.005/24.887秒。独立原件SHA/覆盖复核通过，FAST_VALIDATION.json；无新PPA或默认修改。原数值源0d1e8517，分宽度接续128432ba。

Gate62262 COMPLETED/0:0，前两次失败62260/62261原件保留。用户明确授权取消慢62258/旧接续62259后，快测62263（32位）/62264（24位）已RUNNING。32位已19窗原件复用、余273；24位292待算。预计两卡约2～3h，随连续吞吐修正。已通过的8窗9215目标PPL为64位11.4068403048、32位11.4645418153、24位11.4897787234；后两者相对+0.506%/+0.727%。完整WT2尚待核验，不当成已完成。

正式入口experiments/t64_narrow_state_20261127/PERFORMANCE_ZH.md，私有work/rayggxia/225/narrow_state_20261127/fast_full_v1/SUBMISSION.json、SWITCH_RECEIPT.json及STATUS_OBSERVED.json。根local_tools/dynamic_scale_225_20261125/check_narrow_fast_full_20261127.py只读。无训练，默认64位及RTL/TLM不改，PR不合并；Projects待同步。

## 2026-11-27｜Issue225／PR266：24/32位状态数值验证与PPL已提交

负责人rayggxia，同task/225-cim-bank32-20261124。只读审核用户ffn_narrow_state报告/RTL，19源/结果SHA匹配；32位0/5248与24位44/5248 BF16变化均为短K合成样本，不当模型精度。按报告同一保守界/逐K64 RNE/显式溢出合同新增数字参考，正确合并输出恢复指数，真实GU40/Wd152块，固定T64/W8、x/g/u64基准+S2、16/32、准确Attention。修复源0d1e85176fd52205669148296c585a06c47bc369，9文件远端内容与原字节blob核验（索引重读通过），51执行文件冻结。v1 GPU62256已撤回且原快照/日志保留，不采用其数值；只动本人新任务，旧x实验保留。

CPU62257二十六项PASS且COMPLETED/0:0，GPU62258在run_v2运行；先16组独立整数oracle/完整BF16/64位无操作及旧pilot字节验证，再64/32/24位同8窗PPL；宽32/24若≤1.01×64则自动完整WT2，1%仅资源触发。尚无已完成窄位宽PPL，不更改默认64位、RTL/TLM或PPA。RTL原g sigmoid与当前PPL P8重建g存在独立入口差异，本轮保持PPL入口以隔离缩位。分析experiments/t64_narrow_state_20261127/ASSESSMENT_ZH.md；恢复work/rayggxia/225/narrow_state_20261127/HANDOFF.md及v2/SUBMISSION，根check_narrow_20261127.py只读。无训练，不合并PR，Projects待同步。

## 2026-11-27｜Issue225／PR266：x加1bit的部分结果，完整评测仍运行

负责人rayggxia，同task/225-cim-bank32-20261124。新源fa079820冻结。CPU19PASS、GPU Gate62243已COMPLETED/0:0，完整BF16 PPL11.5364289819、关闭x标志与原共享logits逐位一致及任务回放通过。62244 PPL和62245任务仍健康运行，62246等待；无失败，不重复提交。

已完成4项同8窗PPL/9215目标：原逐元素四档11.512866，x原四档+g/uS2为11.357426，x纯64共享+g/uS2为12.090864，新x/g/u均64基准+S/S2为11.406840。已完整ARC-C1172题，新方案acc42.74744%、acc_norm44.453925%；原x纯共享对应41.29693%/43.856655%，提升1.4505/.5973pp。原逐元素四档ARC-C43.17406%/45.56314%，新方案仍略低。逐窗NLL/目标SHA/36层与ARC逐题/SHA/配对ledger复核通过。PIQA只8/15片、完整PPL原四档182/292窗且新候选尚未开始，不能报完整成绩。按当前约13秒/窗，完整PPL剩余约1～1.5小时，PIQA约15分钟，随吞吐变化。正式部分记录experiments/t64_x_onebit_20261127/progress_20261127/REPORT_ZH.md，私有PARTIAL_RESULTS_VERIFIED_20261127.json；不混入旧环境PPL，不训练/改RTL/TLM/PPA，不合并，Projects待同步。

## 2026-11-27｜Issue225／PR266：x也增加S/S2一位选档，16/32评测已提交

负责人rayggxia，同task/225-cim-bank32-20261124。推理源fa079820e849966c5d5f1ecbf2ea5eb825a28135已推送，7文件内容/原字节blob回读一致；42文件执行快照冻结。只给x增加组64基准+逐元素S/S2，g/u维持组64基准+S/S2、T64/W8、GU16/Wd32及准确Attention。CPU62242十九项PASS且COMPLETED/0:0；GPU Gate62243运行，PPL62244与单任务worker62245依赖门禁，CPU62246自动汇总，最多两GPU并行。PPL含4项同窗pilot和新候选/原逐元素四档各一份完整WT2；PIQA1838/ARC-C1172完整25分片/2组，seed101，全部题干答案36层FFN覆盖。尚无正式新结果；初估1～2小时，以实测为准。入口experiments/t64_x_onebit_20261127；私有恢复work/rayggxia/225/x_onebit_20261127/HANDOFF.md及SUBMISSION。无训练/PPA/RTL/TLM默认变化，旧健康结果不重跑/覆盖。PR未合并，Projects待维护者同步。

## 2026-11-27｜Issue225／PR266：S/S2完整任务8/8完成并独立复核

负责人rayggxia，同task/225-cim-bank32-20261124。S2的PIQA1838／ARC-C1172、100/100片与8/8组全部完成，无缺项/失败；GPU62237、62238_0/1及CPU62239均COMPLETED/0:0，队列为空。独立CPU62241重算S2 12040与S4 27090配置×题目计分、原文档SHA/输入ledger/36层/模型源码身份通过；只读复核不重跑GPU。正式汇总experiments/t64_onebit_half_tasks_20261126/results_20261127/REPORT_ZH.md，原字节evidence及SHA/CSV/复算脚本同目录。S2并非任务全面改善：x原四档16/32 acc为68.44%／42.41%，比S4 +.435／+.768个百分点；x动态64的16/32为67.57%／41.30%，PIQA降低1.523pp。64/128两x路径分别74.27%／48.46%、74.10%／48.38%，接近S4。准确Attention、T64/W8、seed101不变；没有S2完整WT2、新训练/PPA/RTL/TLM默认变更。原件小归档project_archives/scale_results225_20261126/S2_TASKS_AND_AUDIT_20261127.tar.gz；私有恢复work/rayggxia/225/onebit_half_tasks_20261126/HANDOFF.md。PR未合并，Projects待维护者同步。

## 2026-11-26｜Issue225／PR266：S/S2完整PIQA／ARC-C已提交

负责人rayggxia，同task/225-cim-bank32-20261124及原独立目录。数值源354bef257affa393d5677c04c9d71004e9d88286已推送，6个新源文件的远端内容与原始Git blob逐SHA一致；35文件执行快照沿用冻结S2编码和旧官方任务前向。CPU62236已COMPLETED/0:0、18项PASS，GPU Gate62237运行；两个worker62238_[0-1]依赖门禁，CPU62239依赖汇总。四配置为x原四档／动态64×GU16/Wd32及64/128，g/u64共享基准+逐元素S/S2；PIQA1838／ARC-C1172，100分片／8完整任务组，seed101。当前尚无S2正式准确率。新完整BF16、原S4逐答案分数/请求ledger、S2重复一致需门禁通过；不复跑旧S4全任务，不改训练/RTL/TLM。预计两卡约2～3小时，排队另算；PR266未合并、Projects待维护者同步。入口experiments/t64_onebit_half_tasks_20261126，私有恢复work/rayggxia/225/onebit_half_tasks_20261126/HANDOFF.md。

## 2026-11-26｜Issue225／PR266：三批尺度质量任务全部完成并复核

负责人rayggxia，同task/225-cim-bank32-20261124。5090 S4完整WT26项齐、S2/S4八窗8项齐；学院PIQA／ARC-C225/225分片、18/18完整配置全部completed，无失败／缺项。独立CPU62235重算27090配置×题目评分、原文档／请求ledger／模型与源码身份，全部一致。正式报告experiments/t64_scale_results_20261126/REPORT_ZH.md，CSV／原字节evidence／SHA与复算脚本同目录。S4完整三seed16/32为10.958236±.011138，64/128为8.989489±.005269；S2四种小测均优于S4，但尚无S2完整WT2或任务成绩。S4高预算共享1bit接近原四档，纯32共享低预算严重退化。所有本批GPU作业退出且队列为空，原件在共享存储及项目小归档。数值源7283f041／90b7742a／ea293cae均未修改；未训练／改RTL/TLM默认／合并，Projects待维护者同步。复核／发布恢复work/rayggxia/225/final_scale_results_20261126/HANDOFF_PUBLIC_ZH.md及私有记录。

## 2026-11-26｜Issue225／PR266：S/S2单5090 PPL小测已排队

负责人rayggxia，同task/225-cim-bank32-20261124。数值源90b7742ac88beeb95203ab600c5a78adac809bf4已发布且6文件原始Git blob逐SHA一致。CPU6379十四项PASS；6380资源探测数组等待其成功及原完整PPL内部6361（6355_5）结束，独占claim最多一个模型worker，仅一张5090跑数值。x原四档／动态64×16/32及64/128×S/S2与同轮S/S4，共8项8窗seed101，T64 W8／原non_ffn、准确SDPA、分层与AND直连Wd不变。尚无S2 PPL；不自动扩full／任务／训练。另记组内档间跨度和整数后端范围，档间最多少2bit不等于整链64→32。入口experiments/t64_onebit_half_20261126，公开／私有交接work/rayggxia/225/onebit_half_20261126。原lab／学院任务保持，PR未合并，Projects待维护者同步。

## 2026-11-26｜Issue225／PR266：共享尺度准确率门禁通过，四卡正式运行

负责人rayggxia，同task/225-cim-bank32-20261124，数值源ea293caea14b8ec5b271a937919ae21693ccae9c不变。独立CPU62231九项PASS；Gate62228 completed，新完整BF16 PPL11.5364289819、整数核／两预算四档包装器及采样重复逐位一致、官方HFLM一致和16个路径短任务通过。62229_0～3四个A6000 worker实际RUNNING，62230等待汇总。三候选×两预算×两任务12项，加lane／BF16参考共18完整组、225分片；seed101、准确SDPA、全题干／答案FFN。尚无完整准确率，初估3～5小时。验证experiments/t64_scale_task_accuracy_20261126/VALIDATION_AND_SUBMISSION.json；公开／私有HANDOFF及只读状态入口已更新。原lab PPL保持，不变更RTL/TLM默认、不合并，Projects待维护者同步。

## 2026-11-26｜Issue225／PR266：共享尺度PIQA／ARC-C准确率已提交

负责人rayggxia，同task/225-cim-bank32-20261124。源ea293caea14b8ec5b271a937919ae21693ccae9c已推送且5文件回读一致。Gate62228实际RUNNING、9单测PASS；62229_[0-3]四张A6000正式worker依赖Gate成功，62230 CPU汇总。候选dynamic32／gu_onebit64／all64_onebit×GU16/Wd32和GU64/Wd128，seed101；加同预算lane与原BF16，共18完整任务配置、225分片。PIQA1838、ARC-C1172官方全量、lm-eval0.4.8、题干和答案FFN全覆盖，准确SDPA，无模板／截断。尚无正式准确率，完整模型及计分Gate待封存。原lab PPL6355_5保持。方法experiments/t64_scale_task_accuracy_20261126/README_ZH.md；公开交接work/rayggxia/225/scale_tasks_20261126/HANDOFF_PUBLIC_ZH.md，私有回执另存。不训练、不改RTL/TLM或合并；Projects待维护者同步。

## 2026-11-26｜Issue225／PR266：64共享基准＋1bit PPL初筛完成，完整WT2运行中

负责人rayggxia，同task/225-cim-bank32-20261124。数值源7283f04157ff6cdb3d526271766ed64eb5db4461已发布；CPU6351九项PASS、GPU6355_5实际执行。新完整BF16为11.5371603731；两预算四档包装器逐位一致及8候选计分位置／36层覆盖／SHA核验通过。8窗单seed：原四档16/32=11.554504、64/128=9.600821；g/u动态64基准＋1bit=11.917554／9.662735；x也动态64共享=12.541277／9.616025。gu_onebit64_16_32与all64_onebit_64_128已接完整WT2三seed，尚未收齐。报告experiments/t64_group64_onebit_20261126/results/REPORT_ZH.md，公开交接work/rayggxia/225/onebit_20261126/HANDOFF_PUBLIC_ZH.md；私有原件／执行索引在原任务目录。旧无四档动态64／32／16无任务准确率；学院任务另一配置，不继承。只读原权重、不修改RTL/TLM默认、不重复健康任务、不合并PR。Projects待维护者同步。

2026-11-25：g/u机理诊断完成。6320唯一采集并通过观察器末logits逐位一致；median统计失败，6321 cuBLAS环境失败，6322复用同一6.23MB激活完成5层×16位置解析后级诊断，无重跑模型/PPL。极端幅度组只占少数；纯共享造成低事件概率更关键。简单截断伤害首/末层；共享基准＋1bit修正后局部NMSE接近原四档，尚无该新方案PPL/PPA。优先候选为组64基准＋1bit，而非再缩组或全层统一裁剪；这是建议，未修改默认。报告experiments/t64_dynamic_scale_20261125/diagnostic_results/REPORT_ZH.md，raw/source/失败记录均归档并校验。

2026-11-25：新增小型g/u尺度机理诊断6320，单窗口、五层各16位置，不是PPL；父算术9789339冻结，新增patch SHA在diagnostic_v1/EXECUTION_MANIFEST.json。解析moment对逐格枚举断言通过，模型加载/无操作观察器核对及分析待完成。不得重复提交，恢复读work/rayggxia/225/t64_dynamic_20261125/diagnostic_v1/HANDOFF.md。

2026-11-25最终：原GPU本人队列已空；原四档完整48/48分片和12/12配置/seed、6316补跑/6317汇总均sealed完成。逐元素GU16/Wd32完整PPL均值10.753594，GU64/Wd128 8.975547；旧组64四档分别22125.753736/28.551581。动态64/32/16的10项8窗初筛亦全完成。学院Issue263仍34/52逻辑分片，完整WT2七项齐，coarse32/fine128三seed均值9.446296/9.406494，任务仅coarse32 PIQA齐，主池62220保留运行、62221等待。总览experiments/t64_dynamic_scale_20261125/ALL_SUBMITTED_RESULTS_ZH.md。

2026-11-25：用户要求动态组32/16都跑；已核实Slurm6318缩组触发为真，并实际执行四项，复用健康作业而不重复提交。当前四项状态completed，未完成[]。同seed101/8窗/9215目标，T64/W8/准确Attention不变。结果与SHA见experiments/t64_dynamic_scale_20261125/GROUP32_16_SCREEN_ZH.md及work/rayggxia/225/t64_dynamic_20261125/GROUP32_16_REQUIREMENT.json。

# Issue225 最新：动态组64 PoT已在原GPU启动

2026-11-25 17:30北京时间，用户要求改在原GPU先测，已提交Slurm6318并实际RUNNING，分配GPU1/RTX5090，开始时32105MiB空闲。4项CPU测试通过；GPU整数核R6/12/15/29 oracle检查通过（在driver加载BF16之前执行）；同轮完整BF16已跑至292窗，尚待封存汇总，未宣称动态候选PPL完成。

实验：固定训练100M T64 W8及其原non_ffn，准确Attention。x/g/u各连续64项独立计算max(abs)，选覆盖它的最小二次幂。取消每组原四档候选表；最小指数−6，初始上限x512/g256/u512，超上限明确饱和并统计，不声称任意输入都不截断。g/u各自尺度独立；sigmoid仍用恢复真实幅度的S8Q3/P8 LUT；三流AND事件直接送Wd，最终整数归约/恢复。随机字共享仍64路。

GU16/Wd32与GU64/Wd128两档，前级16/64层各1次，后级4×2×4或8×2×8联合分层。单seed101，8个分散2048上下文WT2窗口，逐元素四档和组64四档同轮对照。若动态64任一档比同预算逐元素对照PPL高5%以上，按此前用户授权补组32/16；5%只是调度触发阈值，不是质量合格线。不是候选完整WT2或重新训练。

数值源码9789339555f8059dc02cf42d152db02d43a3cf81，manifest SHA e87991b403e4c72bc765ee5106e78cc16cf4a6c056e669cdae1fa7eb5953a89c。原GPU root=/home/Hongjie_Zeng/projects/zhj/t64-dynamic-scale-issue225-20261125/gpu_run_v1；outputs/PROGRESS.json为中间进度，outputs/RESULT.json及其SHA才是完成回执。source和outputs提交后不修改；权重、数据和runtime只读复用，未复制大文件。resource_launch.py是独立资源包装器，不在原数值manifest内，其SHA与精确命令见original_gpu_v1/SUBMISSION.json。

原组四档完整WT2作业6309及单片补跑6316/汇总6317保持；不重复其健康计算。EDA1871089环境导入已通过，但仍等待模型暂存；已核对未传输模型并取消重复作业，释放GPU，成功环境配置记录保留。原GPU任务提交后不依赖本机保持在线。

本轮无新训练、RTL/PT/PPA或TLM默认修改；Issue225 / PR266沿用、未合并。下一步读取6318封存门禁和candidate逐窗目标/模型/数据SHA，比较对应预算与缩组结果。失败则保留快照另开执行目录修复，不改已提交source。

---

最新2026-11-25 16:01：原GPU可登录；23/48分片封存SHA、逐窗目标SHA、36层覆盖核验；完整5/12配置。lane16/32 seed101/202 PPL10.758346/10.749732；group64原四档16/32三seed PPL22080.554872/21999.098386/22297.607950。lane303 shard2 CUDA超时，仅补该片6316 afterany6309；6317新汇总，旧6310取消；6309健康任务保留。64/128未完成。小结果392758B/416成员已本地保全，归档SHA89de5e55655050808c1e80b9a8310ca2351a4a77c8a3ae871857566c2d650d72。新动态PoT EDA1871089仍Priority排队、未跑PPL。下一步读single_retry_v2/collection/SUMMARY.json与全部sealed结果，不重跑健康片。详见FULL_WT2_PROGRESS_ZH.md和SINGLE_RETRY_SUBMISSION.json。

Latest launch verified: original shards6304/6306 completed (73 windows each); continuation6309 RUNNING on assigned GPUs0/6 only, each >32100MiB free at selection. Collector6310 pending. Numerical snapshot and prior completed reference unchanged. See resource_resume_v1/RESOURCE.json and RECEIPT_*.json; final collection/SUMMARY.json only after all46 retries complete.

## 2026-11-25 T64 group64 resource-aware continuation6309/6310

资源接续（最新优先）：BF166299完整完成PPL11.537160。原6300_0/1/3资源OOM；5/6确认被占满后取消；7…47仍未启动即取消；保留健康2/4（实际6304/6306），不重跑。原依赖父数组的6301取消。新6309（afterok:6304:6306，Slurm请求5卡，仅使用分配范围内空闲≥24GiB的卡，最多2worker）接续其余46片；6310 afterok:6309组合原健康片与新片并调用冻结runner汇总。RESUME_SUBMISSION.json含精确命令、resource_resume.py SHA和各类状态。新目录resource_resume_v1，collection索引与结果均留该目录；不要等待旧6301或将旧3次OOM写成算法失败。原数值source/manifest均不变；只新增资源包装器，不覆盖已提交快照。学院GPU也可连接，但Issue263已有健康任务，本轮不重复其部署或评测。

---

## 2026-11-25 T64 group64 GPU preflight completed; full WT2 running

更新：GPU6298已completed，311.289秒，两项原生无操作逐位检查通过；6299及6300首四片已运行。新两窗口初筛、消融和实际T64表范围见experiments/t64_group64_scale_20261125/results/SCREEN_ZH.md。3071目标的组64两档PPL20911.71/31.54，不是完整WT2；完整结果未出。封存RESULT及SCALE_TABLES的SHA已本地核验。下方提交时快照保留。

---

## 2026-11-25 T64组共享尺度PPL已Slurm提交（Issue225/PR266）

用户要求同一T64训练权重验证每64共享尺度，GU16/Wd32和GU64/Wd128，采用随预算细化的分层。正式代码experiments/t64_group64_scale_20261125/，源码提交b44974f9c44c22ea238d06b571de4d4d3245a6c0。未改其他owner冻结源码/原始PPL/TLM默认。

尺度：x/g/u分别每连续64项共用最小覆盖档；保留T64各组四档原表，不是全局同四个绝对值。逐元素选档为同预算配对。前级16/64层，每层1次；后级4×2×4或8×2×8，每联合格1次。三流AND直接作为Wd事件，没有重新统计再编码。sigmoid仍为原生true-scale P8 g恢复到S8Q3后查冻结P8 LUT；不使用浮点精确SiLU。准确Attention，T64原配套non_ffn保持，无重新训练/校准。

Slurm新任务：CPU6297（6项通过，0.046秒测试）；GPU门禁6298运行；BF16完整参考6299、12配置的四分片数组6300_0…47、汇总6301均afterok等待。48分片不是48独立配置；三seed12组完整WT2292窗/299077目标。数组并发上限4，另一个BF16独立参考；其他用户已有3张卡运行。只能从封存completed RESULT/SHA与逐窗位置/36层覆盖核验后认定完整。

服务器root=/home/Hongjie_Zeng/projects/zhj/t64-group64-issue225-20261125/run-v1；source=source-b44974f9c44c。全部新文件在zhj。模型/数据复用授权只读既有存储，INPUTS.json为原身份清单同字节副本。不需要本机保持在线。

SOURCE-b44974f9c44c.tar.gz为16290字节，SHA aba0a2f3dcbe14914558a9bca79b3a1e0fb2c99af7b8019f3b946e79db68b526；EXECUTION_MANIFEST SHA fc4305b1992d28a118786d91545c7b4cb0c4c1196362b33ad02972dad5dc0ca8。SUBMISSION.json含精确命令/全部ID，SETTINGS及其SHA保留。只读复用runtime SOURCE_MANIFEST SHA eb23a172efbd18e3e56060a6b10d2bfcde33fc7a014c5b10949038921ffb9076，逐文件在进程中核验。



---

## 2026-11-25追加：21bit与本地PRNG

rayggxia，同Issue225/PR266、task/225-cim-bank32-20261124，独立目录不变。TLM局部计数/结果槽21bit，默认GU16/Wd32；本地PRNG持续供数，无默认中央跳步/逐tile播种。10unit＋六回放＋六错误轨迹拒绝通过；新PPA待定，旧19bit价格仅参考，相关新预算合计为null。无新RTL/整机/PPL或远端作业。正式报告COUNTER21_LOCAL_RNG_ZH_20261125.md，交接work/rayggxia/225/cim_count21_localrng_20261125/HANDOFF.md；PR266交付、未合并，实际head由PR核实。尺度封装、描述符握手未在本轮完成。Projects待同步。

## 2026-11-25 Issue225：TLM／RTL对齐完善

负责人rayggxia；复用task/225-cim-bank32-20261124 / PR266（main206bf81f18ea），独立目录tmp/cim-bank32-tlm-issue225-20261124。正式实现仍在process_28nm/cim_bank32_20261124；新增ALIGNMENT_CONTRACT、RTL接口表、事件检查器与结果报告，不另开分叉TLM，不改冻结parent/旧结果。

本地完成：每核双结果槽与128列捕获、32项/拍四次传输、结果/状态分开释放、当前4ns时钟入口、缓存生命周期/16B动作、共享16KiB DMA及64描述符容量、逻辑tile随机状态接口。8项unit、父BeatSRAM、六组trace回放、五份错误轨迹拒绝、完整首层及封存SHA闭合。首层1.106372→1.106300ms，616KiB，面积6.776269mm²不变，片上0.342181→0.342178mJ；是解析外存首层，不是新36层/native/PPL或五核RTL等价验收。

已增量发布同一PR266，ready/open、未合并；source commit401d1db5715a1814d8e7e31aeceedd2c5f1e180b，完整25文件树匹配，8个关键文件blob回读通过。实际回执work/rayggxia/225/cim_alignment_20261125/PUBLICATION.json。原件归档project_archives/cim_alignment225_20261125/RAW_AND_EXECUTED_SOURCE.zip，SHA de69a693f7a88f32b22a1314289659bbe35f2b94d53e95202b6e2ec43479e5d3，86成员全部复核。无运行中/新增远端任务，无新电路台账run。

下一步：RTL对话实现相同五核接口；真实随机状态提供器/PPA及512B定制CIM外围仍待补。默认随机状态1拍/II1为条件宏；64描述符峰值30，超出需补生产端等待。PR待审不合并；Projects待维护者同步。完整交接：work/rayggxia/225/cim_alignment_20261125/HANDOFF.md。

## 2026-11-24 Issue225：32×128-bit CIM单权重区TLM

负责人rayggxia；分支task/225-cim-bank32-20261124，base main206bf81f18ea；独立目录tmp/cim-bank32-tlm-issue225-20261124。用户选定16bank/核、32字×128bit、K64/M128/W8不变，默认5核，删除32槽池。普通SRAM576KiB＋CIM40KiB＝616KiB，另有原16KiB DMA寄存器保持。

本地完成3合同测试、父BeatSRAM真实调度128ns装载测试、4/5/6核FFN完整事务及旧3核/新5核首层对照，封存SHA/队列/工作量与能量账本通过。FFN620.860/566.452/554.264us；首层1.094636→1.106372ms，覆盖面积6.480303→6.776269mm²，片上0.344964→0.342181mJ。定制512B宏面积/idle仍为明确代理；无新PPA/PPL或36层原生回放，不改旧封存结果。源码/结果：architecture_tlm/process_28nm/cim_bank32_20261124/；交接work/rayggxia/225/cim_bank32_20261124/HANDOFF.md。

已推送PR266，ready/open、待审未合并；核心提交db7c7ebd58adc5d0ce0945bf44db44f3bb81a701，12文件远端内容/blob回读一致。远端未运行，SSH依赖/代理环境待修复；Projects待维护者同步。下一步先做Slurm原生首层验证，其他模块/模型任务不接管。

# Issue95 九项预算整理

2026-11-02，rayggxia；task/95-nineway-power-20261102，main0320f486，工作区tmp/rng-nineway-issue95-20261102。

本地完成27行（九结构×K1/64/128）100MHz功率/J每输出bit条件表，81项算术与确定性重建通过。PR215已核实合并，本次不新增EDA/run，不改已有原件/其他任务。正式结果random_service/digital_pbit/nineway_20261102，中央summaries同字节镜像。共享q8价格仍代理，不称独立实测。精确版本/发布及下一步见work/rayggxia/95/nineway/HANDOFF.md、PUBLICATION.json；Projects待同步。

---

## 2026-11-02 Issue230：55 nm/100 MHz纯数字基线仿真清单

负责人rayggxia；分支task/230-digital-baseline-plan，目标main。独立稀疏目录tmp/digital-baseline-plan-issue230-20261102。正式文档digital_circuit_simulation_registry/41_纯数字基线仿真清单_55nm_100MHz.md；根a_P_BIT同名阅读副本按SHA核对。

本轮仅文档：盘点13份已读台账record，区分复用、补测、宏估计和TLM重放；新增建议包括FMA反馈/供数切片、完整数字SwiGLU、在线Softmax、归一化/转换及局部DMA/SRAM外围。既有A9W8/端点、FMA时序限制、P8与完整Softmax差别均保留；不把筛选后准确PV当完整数字Attention。

本地引用存在/JSON解析、UTF-8 LF及阅读镜像字节检查通过，SOURCE_INDEX.json绑定文档及13份record的SHA。没有新RTL/EDA/GPU/Slurm/PPA/PPL，未修改#198/#204/#210/#227代码和冻结任务。尚未执行清单中的补测，未知成本不填0。

发布前已读远端main@7d42c7d30fa9c729c899ba7f815332dd6ed5671a及规则。Git网络fetch失败，局部准备基于已存787489192ebfcdb61ad72edde406818f450aa3dc；通过API只把本任务4份文档增量接到核验后的main，不推送本地历史。主体已发布提交6d137fdbcb2d79db416e084558ccc24dd0c59feb，PR #231 ready/open、待审未合并；四个PR文件逐项blob SHA及零删除核对通过。具体本地回执见work/rayggxia/230/PUBLICATION.json；待审不等于合并。Projects看板未同步，待有接口的维护者处理。

下一步先决定并实现最小代表模块，再按功能→STA→三seed PT逐项推进；不要把本任务当作自动启动许可EDA的指令。

---

## 2026-10-29 Issue204：用户要求继续SRAM存内比较主架构

双随机结构继续SRAM驻留、本地SNG并行比较，阵列输出随机权重bit；不默认搬整组权重到DFF，不默认每采样走普通窄口完整读。两颗全局LFSR32（输入一颗/权重一颗）、T32/8×4与原共享尺度保持；P8输入/P7权重各需5位抖动。ICG DFF及普通宏预读保持仅作对照。已更新12方案页，新增13_SRAM存内比较估算口径与证据.md并同字节同步根阅读镜像。

历史框架可以延续：真实宏库/尺寸/面积/保持与装载＋SRAM邻近标准单元SNG/驱动表征＋存储节点带载接口增量。旧四32×144宏2.25KiB、576bit预读Q保持不是完整64×64存内比较；S0–S5保持/读写有原件但CE关闭动态缺表/hold/XZ边界限制保留。Issue146实际N64/M1/seed17/T32数字前端SS100MHz115.3µW、340ns/39.202pJ，含一颗LFSR/输入比较/固定W门控，不含物理SRAM，功耗表告警保留；不可直接当新W-SNG价格。真实定制存储位/位线比较尚未表征；新最小探针应是7幅值存储位+W7比较/必要隔离，旧模板只有bitcell/AND/BUF。不能将缺接口能量填0，或每拍重复收费全普通读；按真实本地模式收费。普通宏外围也不能任意扣除成裸cell成本。

只读核实Issue146与本机原件；旧source508bdaa4当前workspace GitHub ref404，未伪造远端可见、不重跑/接管其任务。源码/证据阅读SHA见SRAM_CIM_VALIDATION.json。rayggxia继续Issue204/PR209/task/204-bf16-baseline，源基线06b14a96fef58533c5af85851a2a6eae17d07aee；本轮仅合同/历史证据整理，无新RTL/EDA/SPICE/PPL，不新增run，完整根union保留。实际发布见SRAM_CIM_PUBLICATION.json，PR待审未合并、Projects待维护者同步。

## 2026-10-29 Issue204：用户指定输入/权重各一颗全局LFSR32

用户进一步明确：全部输入共用一颗LFSR32，全部权重共用另一颗LFSR32，分层计数器独立生成层号。主候选据此固定，连接独立只作数学精度对照，不按每连接完整PRNG计成本。P8输入/P7幅值权重且8×4时，仅各需5位格内抖动；两颗32位状态共64位、单5位格计数器合69位（不含概率/权重保持、累计和广播）。T64/128/256分别5+4、4+4、4+3位抖动。只广播所需低位与层号，不把32位全部拉给比较器；K64/M输出仍有64个X-SNG及64M个W-SNG。

先单乘法T32/64/128/256，再64对乘累加与M输出复用；当前只是用户方案记录，未启动实现/EDA/模型。两轴不同非零seed、实际抽头/反馈与短窗联合/时间相关性、帧间连续推进另验；普通LFSR5缺零/31周期不能直接替代32值均匀抖动。全局共享改变点积协方差，不能继承连接独立PPL；先精确归约、OR4单列，原尺度不改。已更新功耗面积目录12方案页并逐字同步根镜像，不新增run、旧台账不改。rayggxia，Issue204/PR209、task/204-bf16-baseline，源基线f5d22ac4470c9a423bbba238994957f1a4491cd0；本补充发布见TWO_LFSR_PUBLICATION.json，PR待审未合并、Projects待维护者同步。

## 2026-10-29 Issue204：双随机双轴分层架构分析（未启动EDA）

用户要求保持输入及权重各自共享尺度，思考两侧随机比特流、双分层（非DS-CIM互斥映射）及待评估模块。已只读核实PR207@05d7d986的尺度合同/dual_gu数值参考：x每64共享原四档PoT、W每64×64共享PoT LSB，码[-127,127]不变、pW=abs(q)/128；T32沿已有8×4联合格，非32²拍。原数值参考W按连接独立，硬件分组/列共享改变协方差，不能继承PPL。未修改Issue201/206源码、模型/尺度默认或运行其他任务。

方案入口digital_circuit_simulation_registry/12_双随机分层矩阵架构评估计划.md，论文与项目Git blob在references/dual_stochastic_20261029/SOURCES.json，根镜像两文件同字节。主候选一套signed popcount64+13位累计，OR4近似分支popdiff16+11位累计，均为每输出一个状态而非每权重位平面一套；9/10位饱和另验。双分层不会消除OR碰撞：4个相同pX=pW=.5共用二维点时，精确和1、OR4仅.25，手算/32格枚举一致，非新电路仿真。两侧SNG可拆高层判断/低5位边界比较；收益待测。必须计2D调度/真实抖动分发、X8/W7比较、驻留SRAM/ICG DFF、符号AND、归约/累计、组间PoT对齐舍入及M扩展广播，不能把旧69pJ除6当新功耗。

DS-CIM、DATE2017 Sobol、ICCAD2018 LD、uGEMM及Frontiers2023一手正文已读；原生方案与论文映射/条件推进不同。当前仅分析建议，不预设T32精度/能效，不新增run、无新RTL/PPA/模型/PPL，全部旧record字节不改。建议先同尺度/同事件数数值与共享拓扑消融、再功能和同PVT集成PPA；未自动启动这些后续实验。rayggxia，继续Issue204/PR209/task/204-bf16-baseline、复用原checkout；文稿科学源69f1503894becdddbb1440bd2d24ed2d43b237f5已推送PR209，10文件tree与3关键内容/blob读回一致；回执见DUAL_PLAN_PUBLICATION.json；PR待审未合并，Projects沿既有限制待维护者同步。

## 2026-10-29 Issue204：功耗面积文件夹补齐模块长期索引

用户要求把此前模块的功耗、面积、时钟及具体文件地址统一整理，避免遗忘。已在digital_circuit_simulation_registry新增11_矩阵与算术模块功耗面积时钟索引.md及summaries/20261029_matrix204/MODULE_INDEX.json、MODULE_MODES.csv，覆盖Issue204六批66配置/209运行模式：四档首轮8、单尺度16、参数模块33、BF16五核、四lane INT8两核、64路INT8两核。固定读取提交4175c5565fcd714b0648d97a15c1697b5fbcee05；6源汇总/源码逐字及66原始报告归档SHA核验，保留每项活动/idle、raw与×.81等效面积、100MHz/10ns、操作定义/平均周期/原生延迟和II（未知留空）、STA负值/告警、源码Git地址与本机绝对原件路径。旧04页保留原始表值并加新入口和面积口径说明，README补导航。

同3份新文件已逐字同步根阅读镜像；各自README/04原有内容保留，旧record字节不改、不用67条任务子集覆盖89条完整根union。无新EDA/模型/PPL、不新增run。复现build_power_index.py，核验POWER_INDEX_VALIDATION.json；未来新增模块需同时更新中央run与阅读索引。rayggxia，继续Issue204/PR209、task/204-bf16-baseline，复用tmp/matrix-t32-issue204-20261028；本补充科学源4207651c9cfd2cbabfc4c3572a83e21e07d25998已推送PR209，13文件tree及5关键内容/blob读回一致；回执见POWER_INDEX_PUBLICATION.json；PR待审未合并，Projects待维护者同步。

## 2026-10-29 Issue204：按用户要求完成同64路并行INT8对照

rayggxia，task/204-bf16-baseline / PR209（base main），复用tmp/matrix-t32-issue204-20261028；执行base158e489816bde1547d07cd3f9e377b809055f63f+明确未提交冻结快照。用户澄清重点为整体面积/功耗、要求同SC的64路物理输入并行度，主比较已改为64个动态signed8×8并行乘法+六级平衡树+32/22位结果寄存，不以四路复用替代。旧四路/BF16/SC原件完整保留。正式入口architecture_tlm/int8_parallel64_20261028/results/REPORT_ZH.md与FINAL_SUMMARY.json。

SS1.08V125℃100MHz，面积raw×.81一次。64路32位结果：raw34842.96µm²、等效0.028222798mm²；满速2.126333mW/21.2633pJ每完整N64点积，原生1拍结果、II1=10ns；每35拍接受一帧且100MHz时钟自由运行时0.1148mW/40.1800pJ。22位结果raw34756.92µm²、等效0.028153105mm²，满速2.118333mW/21.1833pJ，同35拍0.108933mW/38.1267pJ。固定N64无bias的22位精确，非任意K累加器，外部均32位；综合高符号位复制/合并，缩位面积差约0.247%。

同原SC54操作数匹配：从原ZIP恢复X/W并逐项SHA核验，每帧W行f%8、absW上限127、X原signed8。SC54原0.0055240704mm²、0.198466667mW、69.4633pJ/350ns。相同64并行度SC面积小5.109倍、各自满速功率低10.714倍，但数字原生吞吐高35倍、满速能量低3.267倍；同350ns完成工作率下SC能量/功率为数字1.729倍。可以支持同64路SC面积优势，不能宣称目前SC相同工作率能耗优势。SC OR4/T32/去LSB近似、数字精确，合成输入匹配不等于模型质量匹配；无新模型/PPL。

最终两top/三seed各164事务，984 RTL及984映射门级输出逐项oracle/四态valid通过，24PT窗口mapped端口/leaf活动100%。v1另24窗口已算出但hold−.061165ns，原件保留；v2核验源/配置/库绑定/原网表后，DC原生hold-only实际插buffer，每核面积仅+raw1.44µm²（等效1.1664）。不重编译算术/retime、不放宽约束；最终setup/hold：32位1.429668/.032151ns，22位1.881098/.027525ns，parser flags空。数据delay1/.02ns、slew.05、load20fF、uncertainty.5/.05，reset4.5..5.5ns释放，无false/multicycle。无CTS/SDF/SPEF/完整毛刺，不是物理签核。

两执行ZIP/8报告/24传输文件/全部成员SHA已核验；准确作业与命令RUN_LEDGER，v2manifest f39df885a073d53ac9c5a7584d78e97906122722b29664ba0155f8e6cd434c8d，原件project_archives/matrix204_parallel64_20261029，私有配置/SDC/库模型指纹单列EXECUTION_FINGERPRINTS。Slurm38447564/38447584/38447776/38447785及两只读DC命令帮助作业均COMPLETED/0:0，不重交。权重/概率存储、SRAM/RNG/比较器/格式/真实广播/ICG仍在核边界外，paced不称最佳数字门控能量。

中央run matrix-int8-par64-204-20261029，任务分支67、完整本地根镜像89，分别保留原66/88个record字节并check/render，不以小子集覆盖全union。新run原件/成员全可访问；历史不可达项见LOCAL_REGISTRY_CHECK.json。科学源48be94077e14a668be0633d44a8dbc7694e505e3已推送PR209，47文件tree及8关键内容/blob远端回读一致；实际回执见同目录PUBLICATION.json；PR待审未合并，Issue保持open，Projects连接器不支持写待维护者同步。

## 2026-10-28 Issue204：经典INT8本工艺结果及SC面积质疑复核

rayggxia，task/204-bf16-baseline / PR209接续，基线6435de8854d8ddb93375e03085ed1eea9c3f9002，复用tmp/matrix-t32-issue204-20261028。用户明确要求按成熟参考计算INT8，随后质疑“无论怎样SC面积肯定更小”；已核查源/映射库存，不根据期待反改结果。入口architecture_tlm/int8_classic_ppa_20261028/results/REPORT_ZH.md、AREA_EXPLANATION_ZH.md及完整SUMMARY。

经典四lane signed8×8→16位乘积寄存→17/18位平衡归约→输出驻留累加；INT32主参考和固定N64无bias精确INT22。一帧64项点积一个输出，不是64×64全矩阵。三seed216完整帧+6 reset中断功能与对应门级通过，18PT窗口全映射leaf/端口活动核验；matched48帧来自BF16原INT8派生数据，整数结果/128与BF16/FP32逐位同值。无新模型/PPL。

SS1.08V125℃100MHz：INT32 raw3825.36µm²、等效0.003098542mm²、0.2151mW、40.869pJ/帧；INT22 raw3621.96µm²、等效0.002933788mm²、0.207mW、39.330pJ。正常18拍valid/19拍帧间隔=180/190ns；位宽收缩省5.32%面积/3.77%能量，不截断有效结果。setup/hold分别3.082494/.082897ns与3.299786/.082897ns，parser未列警告。前布局无CTS/SDF/SPEF，不是物理签核。

面积复核：SC54寄存器77个/449.064µm²，组合1860个/5075.006µm²，总5524.070µm²；INT32寄存器109个/785.279µm²，组合793个/2313.263µm²，总3098.542µm²，全部已乘.81一次。SC寄存器更小但六平面并行符号/OR/计数/累加/恢复组合网络更大；整数只4个乘法器复用16拍。两核都未放整组权重/概率存储，未发现因漏权重DFF或双乘.81导致排序。旧64路全并行INT8约0.04621mm²确实比SC大，但20ns帧间隔不同；N64问题长度不等于物理并行度，不能宣布SC所有实现必然更小，也不把当前SC54称面积下界。

当前粗比SC54相对四路INT32面积1.78倍、能量1.70倍、帧间隔1.84倍，不能支持相对INT8已有巨大优势。对同批数值BF16556.2pJ参考，INT32能量低13.61倍、面积低14.50倍。SC输入/近似精度不同；SRAM、供数、随机源、格式与广播/时钟边界未闭合，不宣布整片胜负。未来可优化SC符号/计数路径，但需独立质量与PPA，不因用户直觉覆盖负结果。

v1/v2门级X失败保留，v2去重定时仍失败，故不能归因于重定时本身。波形定位同步reset时控制计数LSB停留X；v3真实异步控制reset、同步sum、valid保护无reset产品寄存，v4相同电路强化四态ready/valid拒收后完成门级/PPA。数据delay1/.02ns、slew.05、load20fF、uncertainty.5/.05；reset下降沿附近4.5..5.5ns释放与BF16补充契约相同，未加false/multicycle、未force初值、未改库模型。最终set_fix_hold core后compile_ultra，不重定时。

4执行ZIP/14报告/42传输文件和成员SHA核验，配置/SDC/库模型指纹单列EXECUTION_FINGERPRINTS；准确作业见RUN_LEDGER。v4 manifest6523fbde32b9d8cad460f09f1ccf9892466788071fc20aa37a931d86d507255f。实际执行为base6435de88+未提交冻结快照，不伪造执行提交。原件project_archives/matrix204_int8_classic_ppa_20261028，本轮无运行作业；私有控制器不发布。

中央run matrix-int8-classic-204-20261028，任务/完整根镜像各自增量union check/render，准确数见REGISTRY_CHECK。旧record字节保留，不用任务子集覆盖全镜像；本run所有产物可访问，旧94路径仍不可访问。科学源fe060b5a26bfa5281b8a61b353cb8b5bd33f47d9已推送PR209，49文件tree及8关键内容/blob远端回读一致；准确回执见同目录PUBLICATION.json；待审未合并、Issue保持open，Projects工具不支持写待维护者同步。

## 2026-10-28 Issue204：成熟BF16本工艺N64 PPA完成，INT8经典划分已核对

rayggxia，task/204-bf16-baseline / PR209接续，源起点99bf019c。用户明确要求按经典流水划分做本工艺PPA，再查INT8；这是新授权，已实际运行EDA，不沿用上轮“无EDA”的历史结论。复用tmp/matrix-t32-issue204-20261028，未接管Issue107。结果入口architecture_tlm/bf16_ppa_20261028/results/REPORT_ZH.md、FINAL_SUMMARY.json及INT8_CLASSIC_ZH.md。

CVFPU77811635/common_cells9afda9ab精确上游，BF16×BF16/FP32乘加及独立乘/加；四lane非融合DOT4树+四FP32交错上下文，N64正常29拍valid、帧间隔30拍=300ns。五top45个三seed窗口、27696标量+108整帧功能比较及对应门级回放已完成；48个INT8派生帧另用Fraction精确点积核验。合成数据，无模型/PPL；不称单轮舍入fusedDOT4或最佳生产矩阵引擎。

N64原始面积55454.76µm²，raw×0.81等效0.044918mm²，normal平均1.923333mW、577.000pJ/完整64项点积；INT8派生输入556.200pJ。相对SC54(0.005524mm²/69.4633pJ/350ns)约8.13倍面积、8.31倍能量，SC帧间隔长16.67%。这是异精度/不同合成激励的计算核对照，不能宣称整片或同质量优势；既有INT822.19/38.80pJ仍比SC省能。

原共享reset0.02..1ns约束导致async removal负余量。相同SHA网表补充STA明示下降沿附近4.5..5.5ns释放，数据约束不变、无false/multicycle，N64setup/hold 0.000027/0.143288ns；四独立标量en→valid仍−0.061165ns hold，未修复。功耗表范围、高扇出和极小setup余量保留；无CTS/SDF/SPEF或复位分配实装，不称物理签核。

v1..v7负结果/源包/原始报告保留，原字节、远端SHA和全部报告成员核验。v6标量完整，v6 N64仅TB time变量裁剪失败；v7只修波形裁剪并核验全部RTL/bench/fixture/库绑定/约束后复用相同网表，未重综合。补充STA独立冻结。执行是base99bf019c+uncommitted快照，后续源码提交需按ZIP逐字绑定，不伪造执行提交。准确批次见work/rayggxia/204/bf16_ppa/RUN_LEDGER.json；本轮作业已结束，不重交。

中央run matrix-bf16-204-20261028；分支与根镜像分别向各自最新record集合增量登记，旧record字节均保留，绝不用分支子集覆盖完整镜像。准确数量、check/render及原件校验见REGISTRY_CHECK.json。科学源5d21923c7dc7268e2cb19cf393bd858dc3dfb52b已推送PR209，70文件tree与8关键文件内容/blob回读一致；实际回执见同目录PUBLICATION.json。PR待审未合并、Issue不关闭，Projects沿既有限制待维护者同步。

INT8经典实现采用signed8×8→16位积，output-stationary INT32反馈累加，或DOT4/8平衡树后累加；固定N64无bias最坏范围可用22位精确，但可复用长K/带bias经典基线应保留32位，再把22位列独立消融。Gemmini/NVDLA一手源码/文档已核查；推荐100MHz先用乘法级+累加级，是否树内增级交STA决定，无新INT8 PPA冒称。

## 2026-10-28 Issue204：已找到完整28nm BF16数字阵列功耗证据

rayggxia，task/204-bf16-baseline / PR209接续，源起点d6aa128997072acd837508c7703844bf950603ec。用户要求确认是否没有28/55nm BF16数字矩阵依据、缺乏时再自建仿真。二轮已找到MFSA完整正文和FlexBlock作者PDF，纠正首轮检索不足；两原PDF及表II/V原图已下载、SHA绑定、渲染核对。当前入口architecture_tlm/bf16_baseline_20261028/README_ZH.md、LITERATURE_RECHECK_ZH.md及literature_recheck.py。

MFSA2026-10-14预印本：28nm SS0.72V/125℃/1GHz，16×16全格式数字阵列，BF16输入/FP32累加；后布线RC+LLM门级轨迹稳态估算1.85W/1.024TOPS，排除reset/预装/排空。两op/MAC由256PE×两项×1GHz核验，得3.61328pJ/MAC、231.25pJ/64MAC；对SC54核69.4633pJ为3.329倍，仅异工艺/异精度/异边界归一，非N64冷启动延迟或整片节能。原73pJ摘要换算保留低完整度版本，不作为唯一参考。

FlexBlock作者文件头为2203.06673v1：65nm BF16 SA128×128、333MHz、9.84W、1.77TFLOPS；P/T约711.59pJ/64MAC，但吞吐只占乘法器理论峰值16.22%，属含利用率/周期模型的负载归一，不能据此宣布10倍优势；SRAM另CACTI。外部65nm面积不套本项目0.81。55nm严格同PVT/数据/接口仍未找到已核验匹配项，不断言不存在。

有了可用28nm参考，用户“确认没有才自建”的条件未成立，本轮未启动新RTL/EDA/Slurm/GPU/PPL，中央台账84条不变。后续本工艺表征仍是独立工作，不冒称已测。实际追加提交/回读见work/rayggxia/204/bf16_baseline/LITERATURE_PUBLICATION.json；PR209待审不合并，Projects沿既有限制。

## 2026-10-28 Issue204：BF16数字基线调研与可复算预算
发布切换：原PR205已于2026-10-28T10:51:05Z合并；本BF16补充改用task/204-bf16-baseline，基于main@7874891，准确新PR查PUBLICATION.json。原成果不重跑。

rayggxia，同task/204-matrix-t32 / PR205，复用tmp/matrix-t32-issue204-20261028；本轮读取既有证据及一手论文，无新RTL/EDA/Slurm/GPU/PPL，中央台账84条不变。结果architecture_tlm/bf16_baseline_20261028/REPORT_ZH.md及ESTIMATE.json；estimate.py核验旧SS/TT两份summary SHA、三seed单位和负时序，绑定旧RTL，重算预算。

主比较合同BF16×BF16、FP32累加。28nm Li等TCAS-II论文作者机构摘要可核实1761.41GFLOPS/W；条件按2 FLOPs/MAC为1.13545pJ/MAC、64项72.6691pJ，非55nm已测事务，全文累加/舍入/FLOP计数/面积/N64延迟未核验，不按工艺或0.81换能量。与本SC54计算核69.4633pJ接近，不能据此宣称巨大节能。SC需数字>1.08536/5.42682/10.85365pJ/MAC才分别持平/5倍/10倍，均未计两侧缺失前后端成本。

旧本工艺BF16标量KIND2在SS100MHz setup−26.219376ns、TT−10.537953ns；原731输入/5变长帧不是N64。其通用转换和26次依赖规格化循环值得优化，但未做新网表关键路径归因，不能用旧失败实现代表成熟基线。建议补专用乘法、树LZC FP32加法、融合MAC、共享处理DOT2/4/8与真实N64反馈/归约封装，验证35拍/350ns附近预算；两个算术lane不自动保证32拍。旧原件保留，不接管Issue107；BF16与SC W8/T32/OR4精度不同，匹配量化数字控制仍需保留。

研究稿/脚本本地完成；实际推送状态查work/rayggxia/204/bf16_baseline/PUBLICATION.json和PR205，不宣称新BF16 PPA已完成。Projects沿既有限制待有权限维护者同步。

# Issue204：参数化模块能耗完整交接（2026-10-28）

rayggxia；task/204-matrix-t32，同PR205，base main@d83eeb1fc6b89a3dff51b5b62bf79acf665c7166。执行基线9f762ced3d25b47bf3963fbf38ff8d321850854b；复用tmp/matrix-t32-issue204-20261028。新目录architecture_tlm/module_energy_20261028，不改旧冻结PPA或模型/整机默认。

用户授权测试不同输入/输出精度popcount和不同位宽移位相加，补时间累计器与组合验证估算边界。33个固定top全部VCS功能PASS，99次RTL回放/162396逐周期比较；另完成对应门级回放和396个PT窗口（3seed×sparse/dense/replay/idle）。全部所报setup/hold非负，最小2.643270/0.007787ns，功耗表范围警告保留；无CTS/SDF/SPEF。

关键结果：pop8/16/32/64 full输出dense单次0.05251/0.09941/0.19720/0.39630pJ；pop64少一个输出LSB面积只降约0.54%、dense能量约1.20%。9位饱和累计4.8554pJ/33拍（清零+32次）；六平面9位固定恢复1.3190pJ/35拍驻留一次。77/54/50状态位组合分别84.6883/69.4633/67.9817pJ/35拍，55nm等效面积6647.90/5524.07/5447.09µm²；54→50只省2.13%能量，48点积相对OR基线额外NRMSE0.969%→1.538%，非模型质量。

未经校准的独立模块和对bank高估约23%、对单平面约26%–27%；统一独立端口20fF与内部连接负载不同，且有相关性/综合/控制差异。用bank54校准后预测bank50，三seed最大绝对误差0.637%，仅是N64/同输入的位宽配置留出验证，不能宣称跨规模/全芯片普适误差。popcount+恢复树两项不足；必须补mask/OR、累计器、时钟/控制、调用次数与组合校准。共享输入计数属于随机输入量化+数字后端的独立对照，不能冒充本OR4路线收益；匹配确定量化数字参考仍待独立开展。

V1 manifest f454a321，349归档成员：旧Python不支持Path.write_text(newline=...)，38441318共33任务在EDA前失败，全部日志保留。V2仅修复driver，manifest cb9fb058b35c723970752bde9fd4e6ee4496808b2a380ad626e899c68ef5b8da，350成员。成功Slurm38441385功能、38442559四类pilot、38442655其余29类（全量4并发）；无遗留任务，勿重交已完成33/396。Windows Icarus DLL错误623导致本地功能工具不可用，pyslang0错225警告，实际功能门禁来自服务器VCS。

67报告归档、2源包原字节、远端/本地大小SHA和全部成员SHA已核验，stable project_archives/matrix204_module_energy_20261028。报告/完整JSON：architecture_tlm/module_energy_20261028/results；执行索引EXECUTION_INDEX.json；传输TRANSFER_VERIFICATION.json；中央新run matrix-modules-204-20261028，84条union check/render、83旧record原字节保留。源码和结果已推送，科学源080729c314e2e0e62efada3e32d4c27c7eac4bb5，68文件完整tree及10关键回读核验，实际回执PUBLICATION.json；PR205待审未合并，Projects既有权限限制待维护者同步。

边界：组合top没有人为I/O寄存器；顺序top含真实计数/控制/结果寄存器，CE非ICG。bank为预解码7幅值位W和乘积符号，abs(W)显式限127；SRAM/概率保持、RNG/比较器、编码/符号预处理、物理广播、最终格式恢复在外。pop缩输出位是丢LSB、单位2^DROP；固定移位与可变对齐分开。非16 pop的replay为IIDp=.35，align replay为随机字，其余由旧M8合成回放派生，均不是模型数据。原PT samples字段0为占位元数据错误，派生表按stim en补32样本/帧，原始字节不改。

后续：先用这组数据估相同接口/频率/负载附近的算术配置，扩大输入规模时补signed-popcount/增量宽度（当前累计器D6只对应OR后16路），并做新组合校准；新存储/随机前端/真实ICG/物理连线独立补齐。报告不按状态位比例推功耗，不把纯算术表当整机PPA，无新PPL/GPU。

---

# Issue204：计数器缩位分析（2026-10-28）

负责人rayggxia，沿用task/204-matrix-t32和PR205，base main@d83eeb1f。分析基线a288901fa783277a134bf7052e49d4e09437308f；既有EDA科学源5dcef4fd99200418f804cbd51f3bf325d1cbea60。独立目录architecture_tlm/matrix_counter_precision_20261028，不修改单尺度或四档冻结执行输入。

用户要求统计32拍各权重位平面累计，研究饱和/截断和低位舍弃，查论文是否必须全按最大值位宽。本轮只做冻结合成数据的数值回放与一手论文核查，不新跑模型、RTL/DC/PT或改变台账83个硬件run。BF16复跑/模型语料字段不适用：未做模型推理/PPL比较；Issue206只读权重量化合同和已封存源码成员SHA，不继承其质量或PPA。

已完成：功耗432输出、功能432输出全部独立重构等于原OR oracle，60个原始输入SHA核验；主M8统计384输出、24条驻留W行，各32拍。B0–B6平均绝对累计53–58、99分位166–220；B7平均1.36、最大32。9位饱和额外NRMSE0.242%；B0–B6用9位、B7用7位为70位状态；删除B0后61位、额外NRMSE1.063%。均以原OR输出RMS归一，不是模型准确率。全8位饱和10.681%、回绕74.642%，负面结果与极值功能退化均保留。64位混合校准例在seed1009留出误差1.072%，尚非模型候选验收。

理论修正：严格signed [-512,512]需11位，但10位只在最后一拍+512缺1；每平面误差≤1、8平面加权原始误差≤255。固定权重支持Gp个OR4组时，精确计数范围±32Gp，可依位平面进一步收紧。逐拍饱和不等于帧末饱和；截计数LSB会丢失逐拍小增量，相关断言已通过。

论文：REX-SC §II-C明确6位饱和对照；SC-DCNN §4.1/Fig7近似并行计数（非直接缩时间计数）；DS-CIM §III-D四拍latch缓存后更新宽累加器。原文链接和适用范围在SOURCES.json/REPORT_ZH.md，不把论文PPA移植成我方收益。Issue206冻结aa43d00d的PoT量化clamp(-127,127)，7个幅值平面；仅在采用这一接口后B7可无损删，不改旧完整INT8边界。

成果REPORT_ZH.md、RESULTS.json、MANIFEST.json、WEIGHT_CONTRACT_REFERENCE.json；复现命令python architecture_tlm/matrix_counter_precision_20261028/analyze.py、report.py。分析已推送，科学源904068b9e70bab558f93c93ff2c230216164cf51；13文件完整tree与6关键回读核验，PR205待审未合并；回执PUBLICATION.json。无新服务器作业；Projects既有权限限制待同步。

后续建议：11位精确对照，10位保守端点饱和，9位/低位删除候选；先补真实权重/激活分布和独立模型质量，再按同条件RTL/DC/PT测饱和与门控成本，不按状态位数直接推功耗。不要重跑已完成96窗口或启动昂贵模型任务。

---

# Issue204 单尺度INT8完成回执（2026-10-28）

发布确认：单尺度科学源5dcef4fd99200418f804cbd51f3bf325d1cbea60已推送PR205，217文件完整tree与8关键逐字/blob回读通过；Issue204正文已同步，PR ready/open未合并，本任务无遗留作业。

负责人rayggxia，task/204-matrix-t32，PR205 open/ready/unmerged，base main@d83eeb1fc6b89a3dff51b5b62bf79acf665c7166，科学输入基线cc04dee9890ea6dcfbeee872b0cab914d3b1c2c6。本地目录tmp/matrix-t32-issue204-20261028。沿用原Issue/PR，不改旧四档冻结输入、其他任务或整机/模型默认。

用户决定：64路共用一个尺度、真正signed INT8[-128,127]、N64/T32；每幅值位平面和符号先OR4，64→16个事件，再做精确并行计数。实现3版：V1直接实现；V2把每组正负各6位改为一个signed7时间计数；V3使用专用无符号popcount并隔离末端恢复输入，保留signed7组计数。mode3每拍popcount16再时间累计；mode6每组独立累计后求和，二者同事件OR oracle全等。SC内部20位，数字22位，输出符号扩展32位。

全部完成：V1 672帧、V2 96帧、V3 288帧，共1056帧功能PASS；16个综合变体、96个active/idle PT窗口，SS1.08V125C100MHz。3原始执行包和22报告归档远端/本地SHA/大小及逐成员校验；Slurm全部COMPLETED/0:0，本任务无遗留作业。执行索引EXECUTION_INDEX.json，结果architecture_tlm/matrix_single_scale_20261028/results/FINAL_SUMMARY.json和REPORT_ZH.md；源包/报告在project_archives/matrix204_single_scale_20261028。不得重复昂贵测量或改写冻结输入。

M1：精确树179.906pJ、OR4-popcount16优化版101.932pJ（能量-43.34%、面积-16.51%），16路signed7独立时间累计优化版348.483pJ；数字位串行38.797pJ。M8优化OR4 790.767pJ/帧、数字位串行262.133pJ/帧，每帧8点积。还不能证明SC能效胜数字。共同尺度省去bin选择/移位，但新旧码域、刺激及位宽也改变，不能作纯尺度消融归因。

主PPA为16帧驻留权重、uniform signed INT8输入、公共R8，三seed均值；SC原始期望=数字点积/4。OR损失另报，时间计数硬件改动不改变OR结果；真实模型单尺度质量未验。面积raw×0.81保留双列，不缩放功耗/时间。外部权重存储/保持读口、RNG/比较器、输入量化/尺度选择、最终浮点恢复、物理广播线及CTS/SDF/SPEF在外，CE未冒称ICG。全部时序与功耗警告保留。

中央新run matrix-single-scale-204-20261028，增量union check/render并保留其他record；结果见REGISTRY_CHECK.json。源码/结果已推送，科学源5dcef4fd99200418f804cbd51f3bf325d1cbea60；发布回执见PUBLICATION.json和最新PR205。Projects既有权限限制仍待维护者同步。下一步审阅计数实现、hold/功耗表告警；真实ICG、SRAM驻留端口及真实后训练模型同质量验证独立开展，不自动启动昂贵模型实验。

---

# Issue204：T32矩阵改进验证

更新时间2026-10-28；负责人rayggxia。分支task/204-matrix-t32，PR base main@d83eeb1fc6b89a3dff51b5b62bf79acf665c7166；独立目录C:/Users/86134/Documents/a_P_BIT/tmp/matrix-t32-issue204-20261028。未修改Issue193/186源码或其执行快照。

本地首轮完成：六算法×M1/M8×三seed×15帧，v1/v2各540帧VCS功能通过；8个固定top完成综合、门级及48个SS1.08V125C100MHz PT窗口。恢复时队列已空，不重交EDA。27原始报告归档远端/本地SHA/大小与逐成员SHA均核验；9个执行包原字节保存。报告architecture_tlm/matrix_validation_20261028/results/REPORT_ZH.md及FINAL_SUMMARY.json，精确执行/终态见work/rayggxia/204/EXECUTION_INDEX.json。已推送PR205（ready/open、待审未合并），科学源f19b603578ba215433ae68809c7eed3f30c7bf55；144文件完整tree与本地一致、8关键文件逐字/blob回读通过，回执work/rayggxia/204/PUBLICATION.json与REMOTE_VERIFICATION.json。

M8共享输入计数相对S0：1331.137→479.067pJ/帧（−64.01%），174255.20→168423.79µm²（−3.35%），37→40周期（+8.11%）。M1位平面省能16.88%、面积多37.80%；M1先计数反而多耗能18.40%。普通OR4共享源同号同位权例低估75%。D1确定位串行34.467pJ/帧、11周期、22054.00µm²，低于M1 S0的165.994pJ/帧；尚未证明随机整体胜数字，M8数字同规模尚待扩展。

面积均已按用户要求raw×0.81并保留原始列。S0两尺寸hold−0.041792ns；S2 M8 setup仅0.000099ns，功耗表范围等警告保留。前布局，无CTS/SDF/SPEF、真实模型质量、存储/RNG/比较器/编码/最终浮点尺度及实际广播线成本。D0是未优化q9参考，不称成熟最佳INT8。SRAM/门控权重与内部位宽收紧属于后续，不伪称本轮全链路完成。

中央台账新增matrix-t32-204-20261028，82记录联合check/render、81旧record逐字保留；main缺全台账，本PR只交付增量record及校验回执，不复制别人记录。失败波形/别名/调试可见性版本保留；v3旧数字后处理实际已跑1分34秒后取消并由v9替代，如实记录。Projects既有权限限制待同步。下一步：审阅本轮PR，修hold/功耗表范围，M8数字控制、SC位宽/真实ICG及驻留权重端口验证；不自动启动新模型或昂贵作业。
