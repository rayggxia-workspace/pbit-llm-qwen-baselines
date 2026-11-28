# x也增加一位尺度：GU16/Wd32交接

2026-11-27，负责人rayggxia，Issue225 / PR266，task/225-cim-bank32-20261124。源fa079820e849966c5d5f1ecbf2ea5eb825a28135已发布、7文件内容与原字节blob回读一致，42文件快照冻结。

- 唯一数值变化：x每64个取覆盖max的最小PoT基准，每元素一位选S/S2；g/u仍各64基准+S/S2，T64/W8、16/32采样、真实幅度sigmoid P8、输入分层共享64和4×2×4联合AND直连Wd保持；准确Attention，不训练。
- CPU62242 COMPLETED/0:0、19项PASS。GPU Gate62243运行；PPL62244、单任务worker62245依赖其成功，CPU汇总62246依赖两者结束。最多两GPU并行，门禁阶段一张。初估1～2小时，排队另算。
- Gate先重新完整BF16 WT2及模型/数据/harness身份校验，核对关闭x标志与旧动态共享模型logits逐位一致、新候选重复一致、旧S2任务前两题逐答案分数和请求ledger一致。CPU通过不等于门禁通过。
- PPL四个8窗对照：原四档、x原四档/g-u S2、x纯共享/g-u S2、新x/g/u均基准+S2；另原四档和新候选各一份完整WT2、292窗/299077目标，单seed101。完整与pilot分别比较。
- 两任务为PIQA validation1838、ARC-C test1172全量，25分片/2组，单seed101，全部题干/答案36层FFN覆盖。旧任务对照在门禁回放后只读复用，未重跑全矩阵。
- 全部结果以原sealed RESULT/SUMMARY/FINAL_RESULT及SHA为准，PPL或任务缺失写incomplete。尚无新正式PPL/准确率，不宣称已完成。代码入口experiments/t64_x_onebit_20261127。
- 不修改RTL/PPA/TLM默认或64bit状态，不合并PR，不关闭Issue225更广硬件工作。Projects待维护者同步。
