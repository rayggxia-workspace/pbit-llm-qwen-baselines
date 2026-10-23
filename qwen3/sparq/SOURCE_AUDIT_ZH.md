# Issue 157：SparQ GQA 数值合同与官方来源审计

本实现用于 **Qwen/Qwen3-4B 后训练版**的单 token 解码数值评估。默认算法命名为 `paper_v6_gqa`，配置 `r=32, k_total=128, local_total=32, reallocation=False, selection="probability_sum"`。它是按论文 v6 GQA 描述实现的独立 PyTorch 参考；原论文没有验证 Qwen3，当前单元测试也不证明全模型 PPL、任务准确率、稀疏内存加速或物理 PPA。

## 1. 固定来源与版本差异

- Luka Ribar, Ivan Chelombiev, Luke Hudlass-Galley, Charlie Blake, Carlo Luschi, Douglas Orr，*SparQ Attention: Bandwidth-Efficient LLM Inference*，[arXiv:2312.04985v6](https://arxiv.org/html/2312.04985v6)，2024-09-04。主要依据：§3 式 (7)–(10)、§4 Algorithm 1 / Grouped query attention、Appendix B、Appendix G Table G1。
- Graphcore 官方仓库：[llm-inference-research](https://github.com/graphcore-research/llm-inference-research/tree/554ea6db219405becbdc0a126984a19f181bdc69)，tag `2024-05-sparq`，固定提交 `554ea6db219405becbdc0a126984a19f181bdc69`。
- [`ann_attention.py`](https://github.com/graphcore-research/llm-inference-research/blob/554ea6db219405becbdc0a126984a19f181bdc69/llminference/methods/ann_attention.py#L69)：`SparseQ.forward` 选择组内绝对值和最大的通道，各 Q 头分别算 L1 温度；`AnnAttention.forward` 约 L234–245 却在组内相加**近似 logits**，而不是先 softmax 再相加概率。tag 的 `k` 与 `local_k` 都在调用时另加当前 token，即实际预算为 `k+1` 与 `local_k+1`。
- [`sparse_attention.py`](https://github.com/graphcore-research/llm-inference-research/blob/554ea6db219405becbdc0a126984a19f181bdc69/llminference/methods/sparse_attention.py#L62)：原始 `causal_index` 按可见位置倒数，因此本实现 local window 也按可见 token 数计数，而非按填充后的数组距离。

`SOURCES.json` 内嵌上述两份未修改 UTF-8 源码及原 MIT LICENSE，并记录原始长度、SHA-256、Git blob SHA-1、固定提交 URL 和获取时间。生产 `core.py` 不导入这份源码；测试核对散列后，直接编译、执行原源码的算法 AST 节点，仅避开旧 Transformers 模型适配器及其导入依赖。没有把重写的近似函数冒称官方 oracle。

| 项目 | 本任务默认 paper_v6_gqa | 官方 2024-05 tag 比较模式 |
|---|---|---|
| 通道 | `top_r(sum_h abs(q_h))` | 相同 |
| 温度 | 每 Q 头独立 L1 覆盖温度 | 相同 |
| 共享 token 分数 | `sum_h softmax(approx_logits_h)` | `sum_h approx_logits_h` |
| 候选预算 | `k_total`，已包含当前 | tag `k+1` |
| local 预算 | `local_total`，已包含当前 | tag `local_k+1` |
| mean V | 默认关闭 | 由设置决定；源码即使关闭仍计算 mean |
| 算术精度 | BF16/FP16 输入提升 FP32 | 主要矩阵运算沿输入 dtype；softmax FP32 |

`selection="raw_score_sum"` 是明确标注的 tag 路由比较模式：测试使用 `k_total=tag.k+1`、`local_total=tag.local_k+1`。只在已测试的 FP32、有效输入范围声明它与官方算法输出近似一致；不声称 BF16 算术路径、所有 ties 或零 L1 异常也逐位等同。

## 2. 可实现合同

`q[B,Hq,1,D]`，`k/v[B,Hkv,N,D]`；`Hq=G*Hkv`，同 KV 组的 Q 头在 head 轴连续。传入的是 QK norm 与 RoPE 之后的张量，缓存已含当前 token。核心不做投影、RoPE、缓存追加或驱逐。可选 `valid_mask[B,N]` 为 bool，True 表示可见；所有头共享此 mask，不支持每头不同 mask 或一般加性 attention bias。

对每个 KV 组：

1. 按 `sum_h |q_hj|` 选共享的 `r` 个通道 C。
2. 每头算 `tau_h = sqrt(D * sum_{j in C}|q_hj| / sum_j|q_hj|)`，再算 `p_h = softmax(q_h[C] K[C]^T / tau_h)`；masked token 在 softmax 前置负无穷。
3. 按 `sum_h p_h` 选共享的总计 `k_total` 个候选，强制纳入末尾 `local_total` 个有效 token。实现把 local 分数置正无穷；这等价于保留 local 后在外部选剩余预算。**不能在组内概率和后只加 1**：组和上界为 G，这样未必保住 local。
4. 收集候选完整 K/V，各 Q 头用完整 D 通道、`sqrt(D)` 缩放重新计算 exact softmax 和 PV。输出 shape 与 q 相同。
5. 默认关闭 reallocation，直接输出上述候选注意力。可选实验模式按每头 `alpha=sum_selected p_h` 与可见 V 均值做式 (10) 混合；本参考显式全 V 求均值，未实现增量 mean 缓存。论文 §4 对 Llama 3 / Mistral GQA 关闭此项，但这不是 Qwen3 最优性的证据。

这里的 exact 指候选集上、相应浮点运算精度中的完整通道注意力，不表示精确实数或全缓存 attention。`r=D` 使路由 logits 完整，`k_total<N_valid` 时仍是稀疏候选；不会自动当成全预算。

## 3. 边界、回退与精度

- `N_valid<=k_total` 时返回全可见 KV 的 dense 数值结果（reason 1），跳过逻辑路由计费。物理缓存长度也不超过预算时，执行静态短缓存分支。
- 若某组任意 Q 头全零或所选通道 L1=0，则整组 dense 回退（reason 2）。原公式在这些点未定义；这是明确的数值边界策略，不能称为原论文已规定的行为。使用非零总 L1 原值，避免把可表示的 subnormal 无端钳制到最小正规数。
- 无可见 token、非单 token query、不合法形状/预算/dtype、可见 Q/K/V 的 NaN 或 Inf 默认报错。masked K/V 的非有限值先归零，不影响可见计算。默认检查算术输出，浮点溢出也报错；不静默输出 NaN。
- FP16/BF16/FP32 用 FP32 计算后转回输入 dtype，FP64 用 FP64；这与原生 BF16 SDPA 的舍入轨迹不同。dense 控制与 adapter 身份门禁应另用原生官方 SDPA，不能把本核心 full-budget 结果声明为 native BF16 bitwise identity。
- 通道或非 local 分数并列时沿用 `torch.topk` 的 tie 行为；不承诺跨硬件/精度候选顺序一致。候选集合内排序不改变数学 softmax/PV，浮点归约顺序仍可能带来差异。
- 本实现只支持 decode；prefill 应走模型原生完整 attention。PPL/任务 teacher forcing 必须逐个 scored target 经单 token 路径，并记录实际 sparse/full-budget/zero-coverage 数量。不能用一次多 token 前向、自动走 dense，冒充 SparQ 质量评测。

## 4. 诊断与成本边界

`return_diagnostics=True` 返回 `(output, diagnostics)`。`group_fallback_reason[B,Hkv]` 中 0/1/2 分别为 sparse/full-budget/zero-coverage；`valid_counts` 和 `selected_counts` 为同形整数张量；`all_groups_full_budget` 是设备上的标量布尔值。候选/通道 ID 按组共享，dense 回退组的 ID 为 -1，含义是读取全可见 KV，而非没有候选。`temperature/alpha` 为 `[B,Hkv,G,1]`。

`logical_counts` 全部是 device 上 int64 标量，可以累计后一次转到 CPU。对于每个 sparse KV 组，路由 K 元素 `N_valid*r`，候选 K/V 元素各 `k_total*D`；QK 路由 MAC 为 `N_valid*G*r`，候选 QK/PV MAC 各 `k_total*G*D`。dense 组 K/V 元素各 `N_valid*D`，QK/PV MAC 各 `N_valid*G*D`。因此共享物理候选不等于少算 G 头输出。计数未包含 top-r/top-k 比较、指数/除法/开方的具体实现、cache append、地址/索引、布局重排或总线粒度；这些需由硬件账本另计。

**计数是理想算法元素账，不是本 PyTorch 引用实现的实际 HBM 流量。** 该实现会提升完整 KV 精度、建立 masked 副本，默认扫描全部可见 KV 的有限性（另报 `validation_kv_elements`），并使用 Python/device 条件判定；混合 dense/sparse batch 还可能执行临时完整算子后按组选择输出。开启 mean 时也显式读取全 V。不能由它的 GPU 时间反推已优化 SparQ kernel 的速度、能耗或面积。真正物理节省需要通道/候选 gather 与存储布局；论文双 K 布局增加约 50% KV 存储容量的边界也应另算。

## 5. 已执行的离线 CPU 验证

2026-10-23，已有 Windows Python 3.13 / PyTorch `2.7.0+cu118`，仅 CPU，`CUDA_VISIBLE_DEVICES` 为空，单线程；未安装新环境，未启动 GPU 或远端作业。

命令：`python -m unittest qwen3.sparq.test_core -v`。

15 项测试全部通过。其中：

- 16 组原始官方 tag 算法比较：4 seeds × MHA/GQA × mean 开/关，含 left padding，核对输出和候选集合。
- 6 seeds 的论文路由：实际官方 `SparseQ` 提供投影结果；按论文做 probability sum/local，然后用独立 PyTorch SDPA 验证候选输出。
- 手工 logits 反例区分 probability sum 与 raw-score sum；4 头聚合概率大于 1 的例子核验 local 强制保留。
- 校验有效位置窗口、masked NaN/Inf、混合预算回退、零查询/零选中 L1、`r=D`、full-budget 与独立 SDPA、BF16 dtype/重复性、输入错误、subnormal 温度、溢出报错和分组逻辑计数。

这是核心数值与来源复核结果。Qwen3 原生 adapter、完整模型与数据集版本、全 PPL/任务分数和实际运行范围由上层评测另行记录，不能从本文件推断已经完成。
