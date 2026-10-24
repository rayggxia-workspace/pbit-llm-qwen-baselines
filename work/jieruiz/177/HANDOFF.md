# Issue177 实现交接

负责人 jieruiz；2026-10-24。目标repo rayggxia-workspace/pbit-llm-qwen-baselines，分支task/177-trainable-and-ffn，PR base task/173-and-direct-wd，准确依赖b41ee00835b1ae385b2a7c3654df67df26eff3e3。独立sparse目录 C:/Users/86134/Documents/a_P_BIT/tmp/trainable-and-issue177-20261024。

用户要求写实际FFN权重训练代码，非线性改为随机采样并写给远程agent的说明。用户回复昨天训练结果未全出；没有提供checkpoint路径或代码交接。本次不重复/取消昨天训练，不向其他线程发送消息。

已实现 qwen3/training/stochastic_nonlinear/：W4/6/8（默认8），x固定四档共享64 T=K64，g/u固定四档P8，signed8真实尺度sigmoid驱动与冻结P8 LUT，joint32有限三流AND直连固定Wd，整数最终累计/RNE。硬前向与有偏STE反向分开。只训练FFN108个权重张量，attention及其他模型参数冻结。Wg/Wu恢复明确仍FP32参考，不宣称整链bittrue。

入口AGENT_HANDOFF_ZH.md有checkpoint导出格式、TRAIN两遍校准、完整manifest结构、训练/恢复命令、T128→T64/W6/W4的顺序、评估门禁和未验证边界。train.py是CE最小入口；既有KD/FSDP训练器需要集成，不能假称已支持。实际4B/H200训练未启动。

验证：CPU13项（12过1跳过），Slurm2906的34项全部通过；tiny HF Qwen3 CUDA5步和3seed合成训练完成。validation/results-2906/COMPLETED.json的documents已验证；执行a3f5a4ac及归档SHA见VALIDATION_ZH.md。完整源包/结果保留本人远端 pbit-trainable-and-20261024-issue177，不改冻结快照。DDP2907/2908是本任务附加小模型通信诊断，状态另见验证记录，不是4B实验。

发布PR178：https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/178 ，待审未合并。Projects缺read:project权限，待维护者同步。PRE_PUBLICATION_CHECK.json记录身份及依赖。DDP2907超时；2908在长初始化后已封存完成，2909在socket隔离环境也完成3步，跨rank参数一致、冻结参数不变；封存documents SHA已核验，失败原件保留。所有本任务作业已结束，无新的定时任务。最终准确发布SHA和核验以PUBLICATION.json为准。

下一步：先读本PR最终回执和验证记录。待昨天checkpoint完成后由原agent提供SHA/导出，按交接重新校准，在H200上先2步确认，再200步pilot；同轮原始BF16/旧精确非线性/未再训练随机前向对照，最后三seed完整PPL，不能复用旧后缀PPL作为完整模型结果。
