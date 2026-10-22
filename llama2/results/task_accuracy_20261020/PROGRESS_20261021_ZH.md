# Llama 2 7B任务评测进度：19/26已封存核验

2026-10-21 10:25:54 UTC（北京时间18:25）；Issue73/PR83；负责人jieruiz。

**19项completed、2项running、5项pending，无缺失或无效结果。新增ARC-E FFN-only seed2完成，两套任务的仅FFN三seed均齐；26项尚未全部完成。** Qwen此前39项任务在服务器均显示completed：PIQA13、ARC-E13、HellaSwag固定1000题子集13。

## 已完成组的阶段指标

PIQA1838题、ARC-E2376题；概率组为三seed均值。指标已从封存逐题记录重聚合；最终收齐后仍须独立官方process_results复算。未齐组不报均值。

| 任务 | 配置 | 完成数 | acc | acc_norm | 相对BF16，百分点 acc / acc_norm |
|---|---|---:|---:|---:|---:|
| piqa | 原BF16 | 1/1 | 77.8564% | 78.9989% | 0 / 0 |
| piqa | 仅FFN B4/T32/K32 | 3/3 | 77.8020% | 78.9989% | -0.0544 / +0.0000 |
| piqa | 仅Attention S128 | 3/3 | 77.1853% | 77.4392% | -0.6710 / -1.5597 |
| piqa | 联合S128 | 3/3 | 77.2942% | 77.8745% | -0.5622 / -1.1244 |
| piqa | 联合S512 | 2/3 | 待齐 | 待齐 | 不计算 |
| arc_easy | 原BF16 | 1/1 | 76.3047% | 74.6633% | 0 / 0 |
| arc_easy | 仅FFN B4/T32/K32 | 3/3 | 76.2767% | 74.3266% | -0.0281 / -0.3367 |
| arc_easy | 仅Attention S128 | 3/3 | 75.4068% | 73.8356% | -0.8979 / -0.8277 |
| arc_easy | 联合S128 | 0/3 | 待齐 | 待齐 | 不计算 |
| arc_easy | 联合S512 | 0/3 | 待齐 | 待齐 | 不计算 |

仅FFN的变化较小：PIQA acc约−0.0544个百分点、acc_norm约0；ARC-E acc约−0.0281个百分点、acc_norm约−0.3367个百分点。尚不能据此判断未齐的联合S512或ARC-E联合结果。

## 剩余任务与预计时间

- 2585_12：PIQA联合S512 seed2运行；2585_20：ARC-E联合S128 seed0运行。
- 2585_21～25：ARC-E联合S128 seed1/2和联合S512三seed排队。
- 五项排队任务约6.71GPU小时；加上两项运行尾部及争用余量，保持现有两卡预计仍需约4～6小时，单卡情景8～11小时；不是排程保证。
- 原2572八项＋2585十八项不动；此次仅CPU Slurm2634封存核验，无新GPU推理或冻结源码变化。

## Apple基线独立列出

| 原始FP32模型 | PIQA acc / acc_norm | ARC-E acc / acc_norm |
|---|---:|---:|
| Apple Softmax7B | 75.5713% / 77.0403% | 72.1801% / 68.7710% |
| Apple Sigmoid7B | 76.4962% / 77.4211% | 73.2323% / 69.6970% |

以上复用APPLE_BASELINE.json及PR67，非Llama同权重替换或新推理。

## 核验边界与原件

- completed须通过逐题SHA/bytes/LF、完整唯一docid、全部候选token、32层prefill/decode和active/dummy审计、配置及源/请求/数据身份绑定；不以progress或队列消失认定完成。
- 已存逐题二值指标与summary均值一致；官方process_results独立oracle尚待26项收齐。模型identity绑定保留，没有再次散列14GB权重。
- 当前Attention是unscreened有限CTMC，32层计分decode替换，multi-token前缀准确SDPA；短题all-K。FFN在prefill/decode替换。不是刚讨论的8位p-bit输入量化测试，亦非PPA。
- 最新封存目录checkpoints/20261021T102541Z/，CHECKPOINT.json的SHA256为c3e1ac52858d6f3cb3006e1e36c032c0c20eb0bf4df93858e7dc708a42da4871；命令见work/jieruiz/73/STATUS_CHECK_SUBMISSION_20261021.json。
- 原18/26检查点checkpoints/20261021T101123Z保持原字节，7合同测试不变，本次复用已验证核验器而未重复测试。
- PR75为已合并的代码/提交/恢复阶段；后续PR83仍草稿未合并，26项最终结果及官方oracle交付后再停用回查。
