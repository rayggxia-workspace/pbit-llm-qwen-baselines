# Llama 2 7B 当前结果入口

任务 [Issue #14](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/14)，[PR #15](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/15)。模型与LLaMA-1、Qwen分别保存。

| 部分 | 当前实际状态 | 查看位置 |
|---|---|---|
| BF16完整WT2基线 | Slurm1961完成；2K PPL4.979503，4K4.895831，均335686个target | [基线中文结果](../../baselines/llama2_7b/results/bf16_wt2_20261017/RESULTS_ZH.md) |
| 模型身份与差异 | 11文件官方SHA/Git blob匹配；Llama2 7B仍MHA，原生4K、epsilon1e-5 | [实际模型对照](MODEL_COMPARISON_ZH.md)、[身份清单](configs/model_identity.json) |
| 真实BF16轨迹 | 512/1K/2K/4K捕获逐bit一致，前2K IDs与Llama1匹配 | [捕获验证清单](../../work/jieruiz/14/capture_validation/manifest.json) |
| Link结构对照 | 全部72项完成；外存能量未标定 | 服务器outputs/link_Staggered；不当作完整DRAM能耗 |
| 完整DRAMSys主对照 | 36项Staggered＋8项NoPowerDown运行中 | 完成后汇总到results/current，原始输出留服务器 |

[设计与复现](README_ZH.md)及[执行57输入清单](EXECUTION_MANIFEST.json)保留提交时的不可变字节；本索引独立更新实际结果，不修改已提交作业的快照。报告后处理源与捕获/TLM源分别记录。

注意：完整PPL只验证原BF16模型；单次真实QK轨迹用于TLM地址对照，不代表随机FFN/稀疏Attention/Ising联合模型的PPL或芯片实测能效。
