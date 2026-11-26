# S/S2小测已提交，等待5090资源

2026-11-26，Issue225／PR266，负责人rayggxia。数值源90b7742ac88beeb95203ab600c5a78adac809bf4的6文件已发布且逐字回读。

固定T64 trained100M W8／原non_ffn和准确SDPA。g/u各64项动态基准，逐元素一位选S或S/2，对照同条件S/S4。x原四档／动态64，两预算GU16/Wd32／64/Wd128，seed101，同8个WT2窗口9215目标，共8配对配置。其他编码、sigmoid、分层和AND直连Wd不变；不加完整WT2、任务或训练。

CPU6379已completed，14测试PASS。GPU资源探测数组6380等待CPU成功及原完整PPL6355_5结束；每个子任务只检查获配GPU，忙卡立即退出，独占MODEL_CLAIM至多启动一个模型worker，因此数值评测只使用一张5090。原PPL与学院任务不改、不重交健康任务。当前尚无S2 GPU PPL，不能称已测完。

正式方法见experiments/t64_onebit_half_20261126/README_ZH.md／PLAN.json。冻结新框架以S4包装器逐位一致、原S4逐窗SHA一致和新完整BF16校验后再报告S2。位宽诊断包含组内乘积跨度、实际整数输出范围及保守界；S2档间修正最多比S4少2bit，组间基准和权重指数另计，不直接据此改变RTL累加器或推断PPA。

GPU开始后预计10～20分钟，排队等待另算。完成后核验sealed RESULT、8组逐窗目标及36层覆盖，更新同PR／Issue、STATUS、长期备忘录和架构记录本。私有路径／完整命令／资源回执见本地任务交接，不上传模型、数据、连接或库。PR未合并，Projects待维护者同步。
