建立BF16存储/FP32累加、64分块在线Softmax与GQA复用的完整数字Attention参考，列出QKV/RoPE/KV追加/core/Wo、算存边界和可引用的局部SRAM证据。2K为132120576 MAC、24MiB KV和84MiB投影权重；完整PPA保持null。

验证：10/10解析测试、512/2048/8192三上下文账本及原manifest 16/16通过。14.155776ms仅为指定16GB/s SRAM资源下界，宏面积0.53161955mm²和0.16995849mJ仅为已表征的局部项；没有新模型/PPL/RTL/DC/PT。文献去重新增1、复用3，PDF保存在Zotero。

Refs #36；PR base `pbit-tlm-attention-details-20261016`。补传前已重新核实amlink1219身份、目标仓库Admin/push权限、唯一push URL和最新集成提交，并保留其他成员FFN成果。所有历史执行源、模型/数据和成果SHA保留；旧无权限回执是历史记录，当前状态见PUBLICATION.json。

共享AGENTS/本人STATUS采用本对话五任务规则并集与进度总表，避免旧状态覆盖新状态。无模型权重、数据集、论文PDF、工艺库或凭据；不自动关闭Issue或合并PR。

发布验证：182项历史manifest文件及历史blob审计通过；合入最新集成后本任务10/10解析测试通过。详见work/amlink1219/36/PUBLICATION_VALIDATION.json。Projects接口实际仍缺read:project，看板待同步。
