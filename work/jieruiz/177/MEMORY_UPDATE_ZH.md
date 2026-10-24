## Issue177：可训练随机非线性FFN已交付PR178（2026-10-24）

用户要求给远程agent实际训练代码，接续昨天FFN权重，把精确非线性换为随机三流AND。用户确认昨天结果未全出，checkpoint/训练交接未提供；没有重复启动或取消昨天训练。新实现 qwen3/training/stochastic_nonlinear/，默认W8、x固定四档共享64 T=K64、g/u固定四档[S/2,S/8,S/32,S/128] P8＋符号、signed8真实g尺度驱动与P8 LUT、32联合分层AND T128（另有T64）、事件直接固定Wd整数累计/BF16RNE；支持W4/6，需分别校准。只训练gate/up/down共108张量，其余冻结；不采用失败FSM。Wg/Wu恢复仍FP32参考，不宣称整链bittrue。

硬前向保持真实有限随机分布，反向明确有偏STE：Wd梯度用采样z，上游用量化条件均值代理；不会在前向用FP32 SiLU回退或z重新编码。包含TRAIN固定尺度校准、旧权重精确键名导出/接续、严格SHA断点恢复、CE最小入口、随机键与checkpoint重算、远程agent完整说明。昨日checkpoint可作warm start，但要重校准且重新做同轮对照，不继承原PPL。代码不是4B训练已完成，也未证明新PPL。

验证：CPU13项（12过1CUDA跳过），Slurm2906的34项全部通过；tiny两层HF Qwen3 CUDA五步、三seed合成训练完成。DDP2907默认NCCL超时；2908禁P2P在长初始化后已封存完成（中途停止请求不覆盖最终完成证据），2909以本机socket隔离配置也三步通过，权重跨rank一致、冻结参数不变，失败日志保留。不将诊断配置/小模型时间当H200性能。所有作业结束，无新增定时。封存validation/results-2906及ddp-results-2909的documents SHA核验；远端本人projects/pbit-trainable-and-20261024-issue177；a3f5a4ac为单卡执行、4ab8350e为DDP成功执行。无RTL/PPA/full WT2。

本人jieruiz，task/177-trainable-and-ffn，独立sparse tmp/trainable-and-issue177-20261024；Issue177/PR178待审未合并，PR base为依赖PR174的task/173-and-direct-wd。入口AGENT_HANDOFF_ZH.md、VALIDATION_ZH.md、work/jieruiz/177/HANDOFF.md及PUBLICATION.json。Projects缺read:project待维护者同步。下一步由原agent待昨日结果齐全后核对checkpoint/数据SHA，先2步再200步pilot，T128→T64，然后W6/W4，最后同轮BF16与三seed完整PPL。不要把已推送代码写成已完成4B训练。
