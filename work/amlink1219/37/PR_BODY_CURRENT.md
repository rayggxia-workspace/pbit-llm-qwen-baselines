补齐QKV/RoPE/KV追加/core/Wo相同边界的事务对比，核算权重流、GQA并集、有限DMA、SRAM峰值、随机宏服务和功率/能量分账。Slurm2164 CPU作业COMPLETED/0:0，23源SHA、9/9快照测试、32/32全24层场景和40返回文件SHA通过，三份后处理汇总逐字节复现。

2K、100ns宏周期下，D0为29.480ms/条件10.057mJ；S32为27.963ms/8.961mJ，S128为33.038ms/9.495mJ，S512为49.921ms/11.080mJ。均为配置条件下的代理成本，物理完整PPA和PPL为null。原manifest 68/68通过；执行源7f1cc0d5c3e967f4983727c726b7e1d6e36e7873，未修改旧执行快照。没有GPU/PPL/RTL/DC/PT，8K只保留6.25%候选，质量未验收。

Refs #37；PR base `task/36-digital-attention-reference`。补传前已重新核实amlink1219身份、目标仓库Admin/push权限、唯一push URL和最新集成提交，并保留其他成员FFN成果。所有历史执行源、模型/数据和成果SHA保留；旧无权限回执是历史记录，当前状态见PUBLICATION.json。

共享AGENTS/本人STATUS采用本对话五任务规则并集与进度总表，避免旧状态覆盖新状态。无模型权重、数据集、论文PDF、工艺库或凭据；不自动关闭Issue或合并PR。

发布验证：182项历史manifest文件及历史blob审计通过；合入最新集成后本任务9/9事务模型测试通过。详见work/amlink1219/37/PUBLICATION_VALIDATION.json。Projects接口实际仍缺read:project，看板待同步。
