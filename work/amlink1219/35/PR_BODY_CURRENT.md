新增常规数字数值参考、online PV、数字IID/systematic与有限串行Ising对照，附可核验的真实QK/V输入、Slurm驱动和小型结果。完整原BF16 WT2复现PPL 11.652735047455899（299077计分token）；CPU39/39、无扰捕获、12/12 pilot和465/465 full通过。原执行源879050031ac1cc7757e3b7f54e19c25dc40faf72，早期2159漏fixture失败与修正记录保留。

原manifest 74/74通过。原始NPZ/长轨迹留本人服务器，Git只放代码、配置、指标和SHA索引。软件微基准不构成ASIC PPA或完整随机Attention PPL验证。

Refs #35；PR base `pbit-tlm-attention-details-20261016`。补传前已重新核实amlink1219身份、目标仓库Admin/push权限、唯一push URL和最新集成提交，并保留其他成员FFN成果。所有历史执行源、模型/数据和成果SHA保留；旧无权限回执是历史记录，当前状态见PUBLICATION.json。

共享AGENTS/本人STATUS采用本对话五任务规则并集与进度总表，避免旧状态覆盖新状态。无模型权重、数据集、论文PDF、工艺库或凭据；不自动关闭Issue或合并PR。

发布验证：182项历史manifest文件及历史blob审计通过；合入最新集成后本任务48项测试：47通过、1因Windows符号链接权限跳过，0失败。详见work/amlink1219/35/PUBLICATION_VALIDATION.json。Projects接口实际仍缺read:project，看板待同步。
