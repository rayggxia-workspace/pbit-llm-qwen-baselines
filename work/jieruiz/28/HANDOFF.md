# Issue 28 交接

## 2026-10-19：Issue59/PR62记忆同步，本地待统一发布

- 实际认证`jieruiz`，目标`rayggxia-workspace/pbit-llm-qwen-baselines`；canonical为本目录对应checkout `tmp/project-memory-issue28-20261018`、分支`task/28-project-memory`。开始clean，HEAD为`b2527f12924a53da7334afbe78c752c101814193`。已只读核实Issue28open、PR29merged、PR62open/draft且base `task/50-joint-ffn-attention`、head348c8286。
- 两次git fetch因连接reset/不可连接失败；GitHub API独立核实当前集成仍为同一b2527f1，与本地HEAD及workspace ref相等；`git merge --ff-only`返回Already up to date。未reset、未改其他成员文件或主Issue59 checkout。
- 保留最新Issue55集成和历史规则。本次只改正式memo第5.8节/第12.1节、本人STATUS、本HANDOFF；根`a_P_BIT/PROJECT_MEMORY_ZH.md`仅从正式memo复制同字节。PR29已经合并，本次新提交尚未推送或创建PR，主任务统一处理发布；不要把本地更新写成已远端完成。
- 同步的Issue59范围：PIQA1838/ARC-E2376全量；HellaSwag固定seed20261019的1000题子集；官方Harness0.4.8 acc/候选字符长度acc_norm；新BF16、B4T32-only三seed、joint Ising64/128/512各三seed，共39项。新cached首答案token与全24层审计、候选KV/RNG/summary恢复、短prompt保留allK的限制均记录。执行源`348c8286bc8bc8e6ee00ec9876b3224b751f4800`。
- 记录时点状态：13scorer＋2plan CPU通过，2473准备完成；2474 BF16完整WT2 11.652735，但向量化/cached某两token候选sumLL差0.1168触发原0.05/token门禁，未绕过。新源`075574ec94307202f3187845d6d7417f1e98ba48`增加独立naive cached（每choice重算prefix、无clone/首query共享），2475/2476全部READY：sumLL1e-5和greedy严格通过、新BF16完整WT2仍11.652735、9pilot完成。pilot少量题目不作正式任务准确率结论。
- 正式39项已于2026-10-19T09:13:52Z提交：baseline2477（indices0/13/26）；ARC-E2478（14～25）、PIQA2479（1～12）、Hella1000 2480（27～38）各12项、各最多2GPU、afterok2477；CPU collector2481 afterany全部worker。回执`a_P_BIT/tmp/task59_workers_submission.json`；collector-only源`0d4be877714ace3f1b360c4d74b62e563850e9bc`，15collector本地modern Python测试通过，不修改075574数值源。正式分数待完成，恢复看Issue59 HANDOFF，不能重复提交。
- 2471package调用失败、2472取消均无模型运行，失败快照保留。仅取消本人pending 2430_19/20/21（B4T16）；保留最优完整评测及原件。任务实际运行由Issue59负责人继续，本次文档任务不提交/取消任何Slurm任务。
- 验证：`git diff --check`、UTF-8/LF、严格三文件差异和根副本字节/Git blob核验；本次文档维护无新PPL/训练/RTL/PT/PPA/TLM。下一步由主任务先查2477～2481最新状态，再新PR发布并同步Issue28/59及根副本；看板缺read:project历史待同步，不宣称已更新。

## 以下为历史交接，保留原日期和当时状态

日期：2026-10-18；负责人：@jieruiz。正式仓库rayggxia-workspace/pbit-llm-qwen-baselines。

- 独立分支：task/28-project-memory；base pbit-tlm-attention-details-20261016 @3553996bf014a29dee7fdb2250a3965e8fd881a4。
- 独立目录：C:/Users/86134/Documents/a_P_BIT/tmp/project-memory-issue28-20261018。
- 当前阶段：备忘录内容提交bcda21d905a327eeb41c353808bdcc7185472fc5已推送；PR29已实际创建并附当前任务，open、未合并。当前补充发布回执提交，最终head以远端PR为准。
- 正式文件：PROJECT_MEMORY_ZH.md；AGENTS.md增加恢复必读要求，原有全部复现/协作规则保留；README增加入口；.gitattributes限定新文档LF。
- 本地入口：a_P_BIT根PROJECT_MEMORY_ZH.md同字节副本；a_P_BIT根AGENTS.md已增加稳定路径和恢复要求，不是另建Git仓库。
- 验证：资料逐项核对、内部Markdown链接、UTF-8/LF、原规则文本保留、用户阅读副本字节一致、源报告SHA；提交后还需核对Git blob。FFN/TLM复核提出的OR独立性、P-DNN替换边界及DeltaNet状态补充已采纳。
- 验证命令：本地Python执行tmp/project-memory-20261018/prepare_delivery.py；随后git diff --check、Git blob对照。VALIDATION.json记录实际结果。
- 辅助材料：FFN_EVIDENCE_NOTES.md、TLM_EVIDENCE_NOTES.md、EXPERIMENTS_EVIDENCE_NOTES.md及来源hash；REMOTE_SNAPSHOT.json记录核验身份/Issue/PR，不含凭据。
- 文档任务不适用新模型/数据运行字段：引用历史模型、协议和SHA，不声称本次重hash远端权重或重跑PPL。没有修改/重交Issue19作业、训练、RTL/PT或TLM。
- 重要恢复点：双侧随机全量PPL已有，但权重Gaussian近似；精确二项只做过短片段。原精确后端完整WT2粗估20～30 GPU小时/配置，不宜重复盲开全矩阵。旧本地test raw哈希不符合正式语料，补测必须核远端完整数据。
- 后续实际任务：备忘录交付后已单独建立Issue30/PR31并完成Slurm2111的47项核查（完整BF16+短BF16+45随机短测）；新结论已同步备忘录第5.1节。模型测试属于Issue30，未混入文档Issue28的验证。原始校准公开推送被自动审批拒绝后，安全分支从3553996重建，只公开代码/汇总/索引，未推原私有执行历史；没有待用户批准的公开原始校准动作。
- 权限/阻塞：仓库admin/push已核实。Projects此前缺read:project，本次未重新核验看板权限，待同步；备忘录不因这一项延迟其它交付。远程队列本次未实时检查，旧2084状态仅是此前记录。
- PR：https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/29。
- 下一步：审阅PR29/31；合并前保持对应Issue open。精确短测不需重跑，完整精确随机WT2仍未做；后续先依据已确认短T退化决定是否优化编码/内核，不盲目开长评测。

Issue32/PR34范围修正已完成49输出并同步备忘录5.2及任务索引。执行源17c89c3；所有替换仍是128/2048token前缀，完整随机WT2未做；模型运行不混入本文件文档任务验证。PR34未合并。Issue33由amlink1219负责Attention计划，未修改其分支或个人STATUS。

2026-10-19，缩放PR31/34和分布补充PR38已按用户授权实际合入TLM，集成c1555ae，Issue30/32关闭；5.3和任务索引已同步。49旧输出不变，新8192token teacher分布与标量裁剪审计不是新随机/裁剪PPL。Projects再查仍缺read:project；只差看板同步，不影响代码/报告已合并事实。


2026-10-19追加Issue39/PR40：65项裁剪/固定PoT替换＋6基线共71输出齐，79产物SHA与源快照复核；512/T256动态13.9529、0.95范围13.7701（小改善、非显著结论）；2048动态10.6569、0.75裁剪14.1020、固定PoT A/W333.2295。完整随机WT2未做，无新PPA。第5.4节和Issue索引已更新；本任务仍是文档维护，实验属于Issue39。根阅读副本一致。PR40最终结果22文件blob核验通过，未合并；PR29仍待审未合并，Projects缺read:project。


2026-10-19补充Issue46/PR47：固定W8输入多尺度65项已完成，完整WT2四档T12812.309561、T25611.989865，原BF1611.652735；68原件SHA/30源blob复核。备忘录§5.5记录代码/数据/Slurm与硬件边界，PR47未合并，无新PPA；根阅读副本同字节。


2026-10-19 T64完整补测已发布：Issue46/PR47，结果提交a4a15018，执行a7bae630，Slurm2298/2299结束。4档T6413.038027±0.010666、8档13.038505±0.012030（3seed/299077目标），BF1611.652735；11项新增计分/14原件/31源blob核验。§5.5与§12已同步，新正式目录fixedw_multiscale_t64_20261019，旧65项不覆盖，无PPA，PR47/29未合并；Projects缺read:project。根阅读副本同字节。


2026-10-19新增§5.6运行状态：Issue46多档＋分层，执行db27fa3，Slurm2308通过、2309运行67完整配置；旧76项不覆盖。根阅读副本一致，新PPL未收齐，PR47未合并。


2026-10-19多档＋分层完成：§5.6与§12同步69新计分/72原件/37源blob，db27fa3，Slurm2308/2309结束，结果c8ea878已发布。B4细T16/32/64为11.900826/11.736131/11.693775，B2/T3211.769199；粗K16T64与fineK32T32相近。根副本一致，PR47/29未合并，无PPA。


2026-10-19 PR47合并同步：用户已明确授权且本机jieruiz实际合并；merge bef83e54b9da0081c51f393044d2156ce11a34b9，Issue46已closed/completed。PROJECT_MEMORY第0/5.5/5.6/12/15节同步实际远端状态，PR29保持待审，不替代新PPL或硬件验证。Projects新查询仍缺read:project。本次通过task/28-project-memory和既有PR29追加文档回执；最终发布head以远端分支为准，发布后将正式文件同字节复制至a_P_BIT根并核对Git blob。合并回执work/jieruiz/28/PR47_MERGE_RECEIPT_20261019.json；原任务源码/产物均未修改。

2026-10-19追加§5.7/Issue50：34后缀主项＋12诊断/64原件完成，B4T32联合Ising128/512 PPL11.197813/11.055307，对照10.371557；完整22项Slurm2430仍在运行（53dd0ff），不称全量完成。PR52草稿、依赖PR47；根阅读副本同字节，Projects待同步。

2026-10-19§5.7.1：Ising次数15新项已完成，B4T32 S32..1024后缀12.065755/11.514886/11.197813/11.066594/11.055307/11.006579，准确PV10.970368；sourcec0fd，21新原件/49源blob，Slurm2440/2441完成。完整S128的2430与新S256/512的2461仍运行，不称完整完成。保留刚合入的Issue51质量预算补充；根副本同字节，PR52草稿/Issue50open，Projects待同步。
