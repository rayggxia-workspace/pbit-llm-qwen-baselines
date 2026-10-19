# Llama 2 7B 当前结果入口

任务 [Issue #14](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/14)，[PR #15](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/15)。模型与LLaMA-1、Qwen分别保存。

**完整中文总表：[原始模型基线与当前标准 TLM](results/current/RESULTS_ZH.md)。116/116项全部完成。**

| 部分 | 当前实际状态 | 查看位置 |
|---|---|---|
| BF16完整WT2基线 | Slurm1961完成；2K PPL4.979503，4K4.895831，均335686个target | [基线中文结果](../../baselines/llama2_7b/results/bf16_wt2_20261017/RESULTS_ZH.md) |
| 模型身份与差异 | 11文件官方SHA/Git blob匹配；Llama2 7B仍MHA，原生4K、epsilon1e-5 | [实际模型对照](MODEL_COMPARISON_ZH.md)、[身份清单](configs/model_identity.json) |
| 真实BF16轨迹 | 512/1K/2K/4K捕获逐bit一致，前2K IDs与Llama1匹配 | [捕获验证清单](../../work/jieruiz/14/capture_validation/manifest.json) |
| Link结构对照 | Slurm1964全部72项完成；外存能量未标定 | [逐项表](results/current/cases.csv)；不当作完整DRAM能耗 |
| 完整DRAMSys对照 | Slurm1965 Staggered36项、1966 NoPowerDown8项全部完成 | [分组汇总](results/current/summary.json)、[完整表](results/current/RESULTS_ZH.md) |
| 后处理与原始成果 | Slurm2069完成；116唯一项、时间/能量闭合和来源校验通过 | [原始结果索引](results/current/ARTIFACT_INDEX.json)、[88份DRAM事务/日志及运行库SHA](results/current/DRAM_ARTIFACT_INDEX.json) |
| 交付验证 | 27项本地协议/契约检查、4K容量复核、冻结输入与发布Git字节校验 | [验证记录](../../work/jieruiz/14/VALIDATION.md)、[交接](../../work/jieruiz/14/HANDOFF.md) |

2K/4K筛选PV物理K读取为37.16%/33.52%，V为1.41%/1.15%；摘要另外收费。同随机FFN准确Attention相比，整机能量降低2.16%/4.38%。当前T4096随机FFN仍使整机比BF16 ASIC情景更慢、更耗能，完整对照见总表，不据此宣称GPU能效优势。

[设计与复现](README_ZH.md)及[执行57输入清单](EXECUTION_MANIFEST.json)保留提交时的不可变字节；本索引独立更新实际结果，不修改已提交作业的快照。BF16执行源9ee1ab47d0317430212364e75adb78abec9797fb，捕获/TLM源b5964b165dfead06676580029235bf5e952b5dad，后处理源358d8b8f943f60986f86362f7bc7aacfca531adc。

完整PPL只验证原BF16模型；每个上下文单次真实QK用于TLM地址对照，不代表随机FFN/稀疏Attention/Ising联合模型质量。时间、能量和面积为ASIC情景估计，非GPU或芯片实测；Ising物理混合及部分算子PPA未标定。大权重、语料和长轨迹保留已授权服务器，不进入Git。
