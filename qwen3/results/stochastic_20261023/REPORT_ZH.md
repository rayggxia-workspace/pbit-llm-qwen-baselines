# Qwen3 概率架构：先导运行中

2026-10-23 20:25 CST；Issue144/PR147。CPU2827完成；GPU2828（1.7B）/2829（4B）运行，未得到完整概率配置结果。不能据此报告替换后的最终PPL变化。

| 对照（均未替换） | 1.7B | 4B |
|---|---:|---:|
| 完整WT2原始BF16重放，299077目标 | 8.3673395166 | 7.0386116013 |
| 本轮配对cached BF16后缀，4096目标 | 7.5900880974 | 6.3315746169 |
| 后缀执行秒数 | 36.47 | 47.62 |

后续所有后缀增量必须减第二行，不能混用完整WT2行。每模型13配置：BF16一次，FFN-only、FFN+screen-exact、FFN+拒绝128、FFN+赢家1024各3seed。W8固定64×64、B4/T32/K32共享64 A8；QK max4/64-token块/8块、TRAIN16拟合+16holdout温度1标量校准；QK-Norm/GQA/原生缓存保留。完整架构和实际作用域见[参数说明](../../stochastic/README_ZH.md)。两个采样数不等成本，理想数值响应不是物理RNG/RTL/PPA验证。

实际门槛：CPU tiny非等Q投影、全层计分、codes无损压缩、保存重载/异常恢复通过；GPU tiny和两个真实模型的SDPA包装逐logits hash一致；固定采样核独立轨迹/分布/均匀仲裁/拒绝cap测试通过。完整BF16使用原968046f源码精确重放NLL，未放宽阈值。迁移执行源8c35145冻结，校准/配对结果均绑定源/model/data/config SHA。

归档：checkpoints/start包含收取时点26小文件；包SHA12e1110bedfc8bc1e390d10bc085f8d188c59e6aafdf1f88e88a604345224427。SERVER_SHA256.json保存原件校验；11 sidecar、27源码blob、模型/数据/配置绑定、完整4096目标覆盖与NLL重算通过。VALIDATION.json明确PARTIAL；独立验证器8类篡改负例通过（PPL/目标/执行覆盖/token/revision/config/protocol/校准SHA）。日志为进行中快照，不是终态。大权重仅保留原服务器目录。

完整候选WT2尚未提交，将先根据实际概率配置速度评估预算。当前没有最终PPL均值、标准差或替换增量。
