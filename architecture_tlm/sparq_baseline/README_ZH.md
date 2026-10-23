# SparQ 算法、双 K 布局与条件资源账本

Issue157；本目录只做可复算的动作、字节、存储和资源速率分析。没有执行模型、GPU、RTL、DC/PT/STA；面积、功率、能量保持 `null`。旧 max4、小网络、Bernoulli 筛选和固定八块修复不在此方案中，也不继续叠加它们的费用。原 FFN 未改变。

## 固定算法与输入

目标 `Qwen/Qwen3-4B` 后训练版本 `1cfa9a7208912126459214e8b04321603b3df60c`，32Q/8KV、d128；此工具不加载权重。主方案 `paper-v6-gqa-probability-sum`：r32、k_total128、local_total32（含当前 token）、reallocation=False，BF16 缓存与 FP32 计算。

1. 同一 KV 组将四头的 abs(Q) 相加，选共同 r 个通道。各头保留自己的评分和尺度。
2. 扫描 N 行的 r 个 K 通道，各头做近似 QK 和 N 长度 softmax。
3. 将组内概率相加，强制最近 local_total 个有效 token，在剩余位置选足 k_total。local 占总 k 预算，不再额外加一次。
4. 读取共享候选的完整 K/V；各头准确 QK、候选 softmax 和 PV。关闭 meanV 补偿意味着直接输出候选结果，公式上相当于 alpha=1。

N<=k 的组直接 dense。数值核对任一头的 selected-channel L1 为零也整组 dense；调用者通过 `dense_fallback_kv_heads` 显式提供这些组，并传其全部 token ID。后者仍计选通道/检测，随后跳过近似扫描。r=d 只使路由点积完整，不取消 k<N 的候选筛选。

数值行为由本任务 `qwen3/sparq/core.py` 单独验证。本账本不产生候选，只验证外部 indices 的形状、范围、唯一性、local 完整性和 fallback 容量，不能证明这些 indices 是真实 top-k。官方 tag `2024-05-sparq` 的 raw-score-sum、k+1/local+1 不与本配置混用。

文献/实现来源：[SparQ 官方实现](https://github.com/graphcore-research/llm-inference-research/tree/2024-05-sparq)、本任务固定算法合同。对照范围以同任务算法核/测试的版本及 SHA 为准，不以当前网页分支代替冻结来源。

## 运行与 API

在仓库根目录：

```bash
python -B -m unittest architecture_tlm.sparq_baseline.test_ledger -v
python -B -m architecture_tlm.sparq_baseline.run --out /new/path/ledger.json
python -B -m architecture_tlm.sparq_baseline.run --tokens 2048 --layouts dual_k token_major --capacity-tokens 32768 --illustrative-rates --out /new/path/conditional.json
```

默认生成 N=128/512/2048/8192/32768 × 两种布局 × contiguous/spread 两种合成通道，共20项。合成 token 为前缀加必要最近窗口；这是地址布局夹具，不是模型稀疏分布。输出包括源码 SHA、配置、indices SHA 和来源。已有输出拒绝覆盖。

已生成 [20项账本](results/analytic_20261023/LEDGER.json)、[4项显式资源率示例](results/analytic_20261023/CONDITIONAL.json) 和 [验证回执](results/analytic_20261023/VALIDATION.json)：15项CPU测试通过，24项JSON逐项重放一致，4个Python源码SHA逐一核验。下表是64B burst、spread合成通道、capacity=N时的**64B事务模型读取量比值**，分母为相同N的dense K/V读取；没有纳入prefill构建，也不是延迟比值。

| N | dual K核心读/dense | 单布局核心读/dense | dual K核心读＋追加 / dense读＋追加 |
|---:|---:|---:|---:|
| 128 | 1.000000 | 1.000000 | 1.124031 |
| 512 | 0.375000 | 0.750000 | 0.407407 |
| 2048 | 0.187500 | 0.562500 | 0.195705 |
| 8192 | 0.140625 | 0.515625 | 0.142683 |
| 32768 | 0.128906 | 0.503906 | 0.129421 |

短缓存N128走dense，双K仍有额外写入，因此该配置没有读流量收益；较长缓存的收益仍依赖真实通道分布、缓存/事务实现和选择器开销。这里没有推导ASIC或GPU加速倍数。

```python
from architecture_tlm.sparq_baseline import Config, Rates, build_ledger
result = build_ledger(
    Config(2048), channel_ids=channels_by_kv, token_ids=tokens_by_kv,
    rates=Rates(), provenance={"capture_sha256": "...", "kind": "model_selection_trace"},
    dense_fallback_kv_heads=[],
)
```

channels_by_kv 长度8，每个 sparse 组32个唯一通道；tokens_by_kv 每组128个唯一位置（包含最后32个）。fallback组须传全部 N 个位置，其不再用于读取的通道列表可为空。数值核将 fallback 的候选/通道掩成 -1，转换时依据明确的 fallback 标签填全部有效 token、通道留空，不编造实际选中通道。`--indices-json` 读取上述字段和可选 provenance/fallback 字段，要求只传一个 N。真实 trace 可能有 batch/padding，需要先按每层、每样本的有效 token 压缩映射分别调用；不能把 padding 当作已读取有效行。

## 计数和选择器

无 fallback 时，每层近似/精确 QK MAC 分别为 `32*N*r`、`32*k*d`，PV 为 `32*k*d`。每 KV 组共享读，但不能把四头算术也除四。FP32 概率乘 BF16 V 按 FP32 算术边界单列，不能套旧2pJ BF16 MAC单价。

账本包含 abs/跨头和、尺度归约/倒数/开方、近似 softmax、概率汇总、通道/token选择、local控制、准确 softmax 和格式转换。MAC 是乘加动作单位；不再额外计其内部加法。与数值核一致，先缩放 Q，再点积：近似缩放 H_sparse*r、准确缩放 H*d，不按 logits 数重复收费。尺度的 sqrt(d) 可作固定常数，动态 tau 不能免费。

选择器采用**明确的保守数字参考**：完整 bitonic 排序，补齐到2的幂，长度 L 的比较交换数为 `2^ceil(log2 L)*m*(m+1)/4`。通道排序长d；token参考先隔离已知local，再排序 N-local，取 k-local。因此这是可复算的候选硬件算法，**不是 torch.topk 的实测比较次数、最优 top-k 或已综合电路**。local已占满k时不排序；r=d时不排序通道。改变选择器实现应建立新费用配置，不能偷偷沿用旧32/128个block的预算修复单价。

## 地址布局与写放大

定义每个 KV head 各自独立、burst对齐的数组：

- token_major：`K[capacity,d]`、`V[capacity,d]`；同一行连续。
- dual_k：上述两份，加 `K_channels[d,capacity]`；同一通道的时间维连续。

容量在调用前固定；默认 capacity=N 仅用于单步快照。持续生成应预留容量或分页，超过容量明确拒绝，不能因为 N 变化无偿重排整个转置缓存。

读取按给定索引触及的 burst 并集精确计数，阶段内重叠只记一次，阶段之间默认 cold、不复用。K/V及其副本是不同地址空间，不能跨副本去重。默认64B；它是传输假设，不声称与某GPU或DRAM控制器的真实事务完全一致。支持不整齐行宽/容量，已有逐字节独立 oracle 测试。

无fallback的核心逻辑读为 `8*2*(N*r+2*k*d)` B，dense为 `8*2*(2*N*d)` B，比值 `r/(2*d)+k/N`。本式只含payload。token_major的32个散布通道可触及每行全部4个64B burst，不能假设始终只读64B。双K使缓存持久容量增加50%，另有对齐padding；**读取变少不是容量减少**。

逐token追加单列：K、V各写一行；dual_k还对每个通道写一个BF16值。默认立即 masked full-burst write，没有隐含跨token write-combining。d128/64B时转置副本可能每KV组写128个burst，8组额外65536B物理写，而逻辑额外K只有2048B。若采用缓冲/合并写，必须另报实际保持、填满/排空、读写冲突和延迟。若硬件不支持masked write而需read-modify-write，额外读取尚未计入。

初次构建转置K的额外完整K读取、转置写入分别报告，未混入每token结果；转置缓存和构建调度尚未实现，不能省略后直接宣称端到端收益。相同输入的prefill/dense cache构建基础费不在增量项里。

## 条件周期、局部状态和未知项

不传 `Rates` 时周期为null。传入的是整层共享资源吞吐，不是每头各有一套。工具输出各资源的 `ceil(work/rate)`、其最大值（容量下界）和总和（无重叠服务工作量）。非整数时钟使用整数周期与有理数换算。

**这两个数均不是完整执行延迟，后者也不是可实现调度的上界。** 它们未解决排序/归约依赖深度、流水启动、有限队列、bank冲突、CDC、DRAM命令/行状态、片内存储传输、互连和主机开销。`latency_ns` 始终null。示例100MHz/资源率只是敏感性参数，不是STA达标。已有 v6 的旧2pJ/1pJ/10pJ系数没有导入；功率/面积/能量无占位值。

`materialized_reference_scratch_bytes` 列出Q/output、近似logits/概率、组概率、精确logits/概率和索引；是命名张量总量，**不是片上SRAM最小值、峰值或完整硬件状态**。排序workspace、响应FIFO、读出保持、transpose/write-combine buffers、物理bank padding待定义。融合/流式方案应另列，不能强迫dense基线物化全概率矩阵后声称省面积。

参考Python核 `validate_finite=True` 会额外扫描完整KV；账本在 `reference_implementation_extra` 明列其元素/字节，不包含在算法core totals。PyTorch还可能完整FP32转换、混合fallback下同时计算后where；这些不是已实现稀疏硬件。GPU计时必须测真实调用，并报告这些开关，不能把本账本读量当实测GPU流量。

meanV/alpha当前拒绝开启，防止主线不收费却使用补偿。独立补偿配置至少需：prefill每KV的V归约；FP32 sumV/count持久状态；每新增token d次加法、任意长度倒数/归一化及读写；每头alpha对选中近似概率归约、1-alpha、两个d维缩放和一次向量加。现有KIND8只做2^mean_log2归一化，不能直接充任意N meanV。

## 可复用RTL/EDA，与待表征范围

| 范围 | 复用入口 | 尚缺什么 |
|---|---|---|
| 加乘、MAC、格式 | `digital_ppa_v1/rtl/nr_fp32_mul.sv`、`nr_array_probes.sv`、`format_conversion_rtl_20261016` | 匹配dtype/数组/真实II/供数，标量功能一拍不证明10ns |
| 比较/选择 | `nr_vector_math.sv:nr_compare_exchange`、`nr_attention_control.sv` | 通道及N-token完整top-k、local控制、容量、索引和广播；KIND14/15不是整选择器 |
| softmax | `nr_unary_lut.sv`及FP32加乘 | 现exp/reciprocal是近似PWL，需匹配质量；两轮softmax与在线PV、重标定和保持尚未形成完整SparQ核 |
| 存储/流水 | `nr_memory_control.sv`、cycle_v1/gqa与MemoryPort | 双K/按通道读取、真实burst/bank/CDC、动态候选，有限缓冲完整消费 |
| 工艺流程 | Issue107 `digital_ppa_v1/ppa8`、Issue123 `encoding_restore_contract/ppa` | 固定SparQ顶层/端口/参数/活动/单位后再使用；旧五项编码恢复不属于Attention |

截至本任务读取的2026-10-23交接，107的16工艺配置仍not_run，123只有功能RTL与EDA交接；已有RNG/Q10/SRAM库结果只可在匹配边界复用。Issue146/PR148的SRAM邻近SNG/W8门阵列由jieruiz维护，**不复制或接管该任务，也不把它当SparQ选择器**。工艺库不上传。

建议由jieruiz新增SparQ对应配置，而非重跑健康旧任务：先组合选择/算术/存储接口的功能oracle，再SS1.08V125C与TT1.2V25C分别DC→门级活动→STA/PT；保留库单位、源/网表/约束/活动SHA、WNS/TNS、II/latency、internal/switching/leakage、有效输出窗口和X/Z覆盖。active、idle、stall、append/transpose分列；先布局前，未知CTS/SPEF/SDF不称物理实现。DC/PT运行后新增中央数字仿真台账，不覆盖历史记录。

GPU测量合同见 [GPU_MEASUREMENT_CONTRACT_ZH.md](GPU_MEASUREMENT_CONTRACT_ZH.md)。
