# Qwen3 概率架构：先导运行中

2026-10-23 20:33 CST；Issue144/PR147。CPU2827完成；GPU2828（1.7B）/2829（4B）运行。两模型FFN-only的三个种子已完成并独立验证，联合Attention仍未完成。

## FFN-only 首轮已验证结果（4096目标后缀，不是完整WT2）

| 模型 | 配对BF16 PPL | B4/T32/K32三seed平均±样本标准差 | ΔPPL | 相对增量 |
|---|---:|---:|---:|---:|
| Qwen3-1.7B-Base | 7.59008810 | 7.66699268 ± 0.00865026 | +0.07690458 | +1.01322% |
| Qwen3-4B-Base | 6.33157462 | 6.36525314 ± 0.00299026 | +0.03367853 | +0.53191% |

FFN替换覆盖28/36层prefill与全部4096单token计分query；Attention仍原生SDPA，没有筛选或采样。三个种子分别：1.7B为7.674493459/7.668954618/7.657529959；4B为6.368627866/6.362933265/6.364198303。每配置实测约155.6–156.5秒及203.1–205.1秒；这是GPU数值参考耗时，不能作为硬件加速/能耗结果。

检查点checkpoints/ffn，包SHA53d085047ee27025f2ef42bf04c2ee7c863ae5cb09dcd4eab733c3557af8ab63，38小文件含服务器SHA清单；17已签JSON、6随机配置及2配对BF16全部覆盖/逐段NLL/源码/模型/数据/配置/校准SHA核验通过。后缀初步显示FFN迁移损失较小，但不能据此宣布完整WT2或FFN+Attention联合质量达标。

## 基线和门槛

| 对照（均未替换） | 1.7B | 4B |
|---|---:|---:|
| 完整WT2原始BF16重放，299077目标 | 8.3673395166 | 7.0386116013 |
| 本轮配对cached BF16后缀，4096目标 | 7.5900880974 | 6.3315746169 |
| 后缀执行秒数 | 36.47 | 47.62 |

后续所有后缀增量必须减第二行，不能混用完整WT2行。每模型13配置：BF16一次，FFN-only、FFN+screen-exact、FFN+拒绝128、FFN+赢家1024各3seed。W8固定64×64、B4/T32/K32共享64 A8；QK max4/64-token块/8块、TRAIN16拟合+16holdout温度1标量校准；QK-Norm/GQA/原生缓存保留。完整架构和实际作用域见[参数说明](../../stochastic/README_ZH.md)。两个采样数不等成本，理想数值响应不是物理RNG/RTL/PPA验证。

实际门槛：CPU tiny非等Q投影、全层计分、codes无损压缩、保存重载/异常恢复通过；GPU tiny和两个真实模型的SDPA包装逐logits hash一致；固定采样核独立轨迹/分布/均匀仲裁/拒绝cap测试通过。完整BF16使用原968046f源码精确重放NLL，未放宽阈值。迁移执行源8c35145冻结，校准/配对结果均绑定源/model/data/config SHA。

归档：checkpoints/start包含收取时点26小文件；包SHA12e1110bedfc8bc1e390d10bc085f8d188c59e6aafdf1f88e88a604345224427。SERVER_SHA256.json保存原件校验；11 sidecar、27源码blob、模型/数据/配置绑定、完整4096目标覆盖与NLL重算通过。VALIDATION.json明确PARTIAL；独立验证器8类篡改负例通过（PPL/目标/执行覆盖/token/revision/config/protocol/校准SHA）。日志为进行中快照，不是终态。大权重仅保留原服务器目录。

完整候选WT2尚未提交，将先根据实际联合概率配置速度评估预算。当前没有Attention联合方案的最终PPL均值、标准差或替换增量。

元数据注意：冻结8c35145复用旧scorer的args仍含legacy `burn=16/spacing=4`，它们只用于旧CTMC接口验证，并未传入本轮新kernel。实际执行由adapter→kernels.sample确认：winner burn=0、每更新保留一次（spacing=1），rejection无burn；结果sampling_stats.sampler_parameters为实际参数。保留原字节不改这些历史字段，不据其将本轮重命名成CTMC。
