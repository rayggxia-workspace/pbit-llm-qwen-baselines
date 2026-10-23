# SparQ / Qwen3-4B：部分结果已核验，完整任务尚未确认

模型：`Qwen/Qwen3-4B` 后训练版；revision `1cfa9a7208912126459214e8b04321603b3df60c`。原 FFN 保留。
执行提交：`8d60abe4e7c5c245c8f5f87b7f66e49e23ae0eea`。已逐 envelope 验证 30 个结果；下载清单字节散列核验 32 个文件。
源码实际字节复核：已完成；本次未重新散列模型权重。

全局 SUMMARY：尚未下载/生成。仅在 SUMMARY、全部部件及正式门禁均核验后标为 complete。
正式任务 document_batch=1；preflight passed=True。候选跨题 batching 诊断 present=True、passed=False；其负结果不等于正式串行任务失败。

候选诊断记录的失败项：[{"task": "piqa", "mode": "dense", "maximum": 0.043265106636681594, "threshold": 0.02}, {"task": "piqa", "mode": "sparq", "maximum": 0.032665827996371424, "threshold": 0.02}, {"task": "arc_easy", "mode": "dense", "maximum": 0.4130668640136719, "threshold": 0.02}, {"task": "arc_easy", "mode": "sparq", "maximum": 0.21209144592285156, "threshold": 0.02}, {"task": "hellaswag", "mode": "dense", "maximum": 0.04170358808955825, "threshold": 0.02}, {"task": "hellaswag", "mode": "sparq", "maximum": 0.02695267952402078, "threshold": 0.02}]。

## PPL（cached 配对；smoke 不计入）

实际源 token 数：299078；按 2048/1024 重建 292 个 window，完整目标数 N−1=299077。

| 模式 | 已验 window / 总数 | 连续前缀 | 已验目标 | 子集 PPL | 本项完整 |
|---|---:|---:|---:|---:|---|
| dense | 292 / 292 | 292 | 299077 | 11.5382 | True |
| sparq | 292 / 292 | 292 | 299077 | 10.7979 | True |

两模式共同核验 292 个 window；平均 NLL 差（SparQ−dense）=-0.0663052。未完整时不可称全 WT2 PPL。
向量化 BF16 anchor 单独统计：292 个 window，PPL=11.5372；执行形状不同。

## 官方任务逐行分数复核

以下准确率由保存的官方逐行 acc / acc_norm 重新聚合。制品没有 gold 标签与选项字符长度，不能声称独立重做官方判题；没有用 token 数冒充 acc_norm 分母。

| 任务 | dense 文档 | SparQ 文档 | 两者共同 | Δacc pp | Δacc_norm pp |
|---|---:|---:|---:|---:|---:|
| piqa | 512/1838 | 512/1838 | 512 | -0.195312 | 0.195312 |
| arc_easy | 0/2376 | 0/2376 | 0 | 待定 | 待定 |
| hellaswag | 0/10042 | 0/10042 | 0 | 待定 | 待定 |

piqa acc：dense对→SparQ错 1；dense错→SparQ对 0。dense=0.755859，SparQ=0.753906（各自已验子集）。

piqa acc_norm：dense对→SparQ错 1；dense错→SparQ对 2。dense=0.75，SparQ=0.751953（各自已验子集）。

arc_easy acc：dense对→SparQ错 0；dense错→SparQ对 0。dense=待定，SparQ=待定（各自已验子集）。

arc_easy acc_norm：dense对→SparQ错 0；dense错→SparQ对 0。dense=待定，SparQ=待定（各自已验子集）。

hellaswag acc：dense对→SparQ错 0；dense错→SparQ对 0。dense=待定，SparQ=待定（各自已验子集）。

hellaswag acc_norm：dense对→SparQ错 0；dense错→SparQ对 0。dense=待定，SparQ=待定（各自已验子集）。

## 稀疏路径覆盖

以下按各层 KV group 的实际逻辑计数汇总；逐层数值见 JSON。短任务上下文落在完整预算内时会 dense fallback，不能把这些分数当成稀疏路径质量证据。

PPL：sparse/query group 比例=0.999572；计数={"query_groups": 86134176, "sparse_groups": 86097312, "dense_groups": 36864, "full_budget_groups": 36864, "zero_coverage_groups": 0}。

piqa：sparse/query group 比例=0.0219555；计数={"query_groups": 6598080, "sparse_groups": 144864, "dense_groups": 6453216, "full_budget_groups": 6453216, "zero_coverage_groups": 0}。

arc_easy：sparse/query group 比例=待定；计数={}。

hellaswag：sparse/query group 比例=待定；计数={}。

## GPU 实测与硬件边界

GPU：NVIDIA GeForce RTX 5090，UUID `995ef4d3-b07f-33d6-db47-34313b3727bc`。完整模型、原 FFN、Python 数值参考的实际计时；不代表优化稀疏 kernel。

功率采样状态：本次已核源码调用方传入裸 UUID，而采样器要求 GPU- 前缀，导致采样未启用；不是另一块 GPU 或 NVML 缺失的证据。

| 上下文 | decode步数 | 模式 | prefill秒 | decode秒 | decode token/s | 板级估计J（decode） |
|---|---:|---|---:|---:|---:|---:|
| 128 | 64 | native | 0.0224392 | 1.33694 | 47.8703 | 待定 |
| 128 | 64 | dense | 0.0225614 | 1.34131 | 47.7145 | 待定 |
| 128 | 64 | sparq | 0.0224951 | 4.43679 | 14.4248 | 待定 |
| 128 | 128 | native | 0.0223583 | 2.68548 | 47.6638 | 待定 |
| 128 | 128 | dense | 0.0225836 | 2.68281 | 47.7112 | 待定 |
| 128 | 128 | sparq | 0.02259 | 8.90337 | 14.3766 | 待定 |
| 512 | 64 | native | 0.0318655 | 1.33686 | 47.8734 | 待定 |
| 512 | 64 | dense | 0.0318771 | 1.33046 | 48.1038 | 待定 |
| 512 | 64 | sparq | 0.031853 | 4.45898 | 14.3531 | 待定 |
| 512 | 128 | native | 0.0318948 | 2.65949 | 48.1294 | 待定 |
| 512 | 128 | dense | 0.0318705 | 2.66233 | 48.0782 | 待定 |
| 512 | 128 | sparq | 0.031854 | 8.90671 | 14.3712 | 待定 |
| 2048 | 64 | native | 0.102435 | 1.33793 | 47.835 | 待定 |
| 2048 | 64 | dense | 0.102526 | 1.33221 | 48.0403 | 待定 |
| 2048 | 64 | sparq | 0.102559 | 4.45997 | 14.3499 | 待定 |
| 2048 | 128 | native | 0.102503 | 2.67548 | 47.8418 | 待定 |
| 2048 | 128 | dense | 0.102606 | 2.67534 | 47.8444 | 待定 |
| 2048 | 128 | sparq | 0.10262 | 8.93258 | 14.3296 | 待定 |

功率为 GPU 板级采样估计，较新 GPU 的 NVML 值有 1 秒平均；短窗口/缺采样返回 null。没有验证隔离的阶段能量归因，不能称 ASIC 动态能耗。

物理 ASIC 面积、功率与速度均为 null；不得与 GPU 结果或逻辑访问账本混称。
