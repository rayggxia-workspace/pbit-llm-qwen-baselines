# Issue 28 交接

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
