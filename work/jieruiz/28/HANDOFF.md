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
- 后续任务：备忘录交付后，按用户授权单独Issue，复用SharedFFN准确二项后端进行短片段多seed风险检查和估时，再择代表配置补完整PPL；先无训练、准确Attention、自然IID，不挑序列。不将新实验混入Issue28。
- 权限/阻塞：仓库admin/push已核实。Projects此前缺read:project，本次未重新核验看板权限，待同步；备忘录不因这一项延迟其它交付。远程队列本次未实时检查，旧2084状态仅是此前记录。
- PR：https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/29。
- 下一步：审阅PR29；审查/合并前保持Issue open。用户已授权后续双流精确性能评估，使用独立任务而非改动本次历史证据。
