# S/S2完整任务评测交接

Issue225 / PR266，负责人rayggxia。数值源354bef257affa393d5677c04c9d71004e9d88286，同task/225-cim-bank32-20261124。6个新源文件的远端回读和Git原字节blob逐SHA一致；35个执行文件冻结，旧S4、S2和任务原件不改。

- 范围：T64 trained100M/W8、准确SDPA；g/u64共享动态PoT基准，逐元素一位选S或S/2；x原四档／动态64×GU16/Wd32及GU64/Wd128。PIQA1838、ARC-C1172全量，seed101，8组100分片，所有题干和答案36层FFN覆盖，无模板和截断。
- 编码直接复用90b7742a/half.py；官方计分复用ea293cae/runner.py。只加任务适配与收集封装。S4回放检查后复用旧全任务对照，不标为新的S2成绩。
- CPU62236 COMPLETED/0:0，18项PASS。GPU Gate62237运行；workers62238_[0-1]与CPU汇总62239已提交、依赖等待。只用两张A6000做正式评测，门禁先用一张，不额外并行。
- Gate重新完整BF16 WT2；核对模型/数据/harness、原S4逐位logits和任务前两题逐答案分数与请求ledger、S2重复一致、整数核oracle。未完成门禁不报告正式准确率。
- 原S4任务已完成；本轮仅S2，8组全部完成才宣称全部结果齐全。结果SHA、逐题重算、36层和请求ledger必须核对；CPU预检不是GPU验证。
- 同目录VALIDATION_AND_SUBMISSION.json为公开状态摘录。没有训练、PPA、RTL或TLM默认修改，PR保持未合并、Issue不关闭，Projects待维护者同步。预计约2～3小时，按实际吞吐调整。
