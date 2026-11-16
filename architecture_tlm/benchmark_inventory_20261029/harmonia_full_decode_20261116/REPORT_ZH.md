# Harmonia 在共同条件下重放 Qwen3-4B 完整解码

2026-11-16。选 Harmonia v3 作第一个外部整机基准。其数字阵列原生执行线性层和 Attention 的 QK、PV，原文披露了各组件面积及功耗，以及 B1 线性 GEMV 只占 8 行中的 1 行。作者在 Llama-3.1-8B-Instruct 上给出 B1 单 token 线性和 2K–16K Attention 的归一化图。本文用公开参数重建独立的 Harmonia 整条路径，并给缺失的非线性和 DMA 补项目已用的公共估算。 [Harmonia v3 §IV、Table I、§V-A/D、Fig.21](https://arxiv.org/html/2602.04595v3)

## 完整解码结果

共同工作量采用项目封存的 Qwen3-4B 形状，B1、固定 2,048 个参加注意力的缓存位置、1 个输出 token。覆盖 token 查表、36 层的 QKVO、Q/K Norm、RoPE、KV 更新、QK、Softmax、PV、SwiGLU、残差，以及 final RMSNorm、全部 151,936 个 logits 和贪心输出选择。Prefill 已完成。时间和能量对应此单步窗口。Harmonia 的线性层和词表头用原生 INT4/BFP8 路径，KV 采用原文的 M8 或 Mix。P-bit／项目数字行以原封存精度录入。

| Qwen3-4B B1/2K | ms/output token | GB/output token | 片上 mJ/output token | 含外存 mJ/output token | 平均功率片上 / 含外存（W） | 已计价面积（mm²） |
|---|---:|---:|---:|---:|---:|---:|
| Harmonia-M8，整机重放 | 42.74 | 2.312 | 7.98 | 81.96 | 0.187 / 1.918 | 4.21 |
| Harmonia-Mix，整机重放 | 41.71 | 2.240 | 7.76 | 79.44 | 0.186 / 1.905 | 4.21 |
| 本项目 BF16 Dense，原生 LPDDR TLM | 111.12 | 8.347 | 32.09 | 299.20 | 0.289 / 2.693 | 6.45 |
| 本项目 W8 Dense，原生 LPDDR TLM | 95.00 | 5.658 | 22.91 | 203.97 | 0.241 / 2.147 | 6.37 |
| 本项目 W8 + Key Selection，原生 LPDDR TLM | 85.45 | 5.417 | 19.81 | 193.17 | 0.232 / 2.261 | 6.40 |
| 本项目 P-bit，原生 LPDDR TLM，三种子均值 | 51.13 | 5.411 | 15.27 | 188.43 | 0.299 / 3.685 | 6.48 |

外存动态统一按 4 pJ/bit，用读写事务字节 × 32 pJ/B 计算。表中平均功率等于对应每 token 能量除以对应时间。面积统计计价片上子系统，外存裸片、PHY、封装和板卡在边界之外。Harmonia 用和项目解析后端相同的峰值传输和响应模型，项目原生行使用已封存的 LPDDR 时序。 [输入与来源散列](INPUTS.json) · [分阶段结果](RESULTS.json) · [项目原生封存](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/01a2fb1d13018d381e012630ea1be442e85bdd26/architecture_tlm/process_28nm/results_20261111/REPORT_ZH.md)

### 为什么能量拉开

M8 重放的全部 W4 线性权重含元数据约 2.137 GB，其中 INT4 词表头 0.207 GB、约 3.38 ms。P-bit 原配置的词表头为 BF16，约 0.778 GB。Harmonia-M8 的 K 与 V 分别读约 0.087 GB，QK 与 PV 都执行稠密计算。Harmonia-M8 与 P-bit 的整机估算能量相差约 106.5 mJ，其中约 **99.2 mJ 来自外存字节差**。Qwen3-4B 全 INT4 线性与压缩 KV 的 PPL、任务准确率尚未做对齐，这组数字检验各架构及其数制组合的系统成本。 [Harmonia v3 Table II/III](https://arxiv.org/html/2602.04595v3#S5.SS2) · [项目原始汇总](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/01a2fb1d13018d381e012630ea1be442e85bdd26/architecture_tlm/process_28nm/results_20261111/SUMMARY.json)

### 芯片、时钟和外存换算

| 项目 | Harmonia v3 原始条件 | 共同条件及处理 |
|---|---|---|
| 工艺 | TSMC 28 nm、0.9 V，DC 综合和门级 VCD，SRAM 来自 28 nm 编译器 | 同为 TSMC 28 nm、0.9 V，论文未披露具体库子型号和角。复用原生核心 3.3812 mm²，含论文 SRAM 的 1.8567 mm²。使用项目 28HPC+ 的 DMA/FIFO 和非线性／输出代理，加 0.826 mm²。面积是输出。 |
| 时钟／阵列 | 300 MHz，阵列 8×16，B1 GEMV 行利用 12.5%。整核原点 300.60 mW，峰值约 2.46/1.23 TOPS（2 ops/MAC） | 250 MHz。按 512 MAC/周期的单行 M8W4 路径重算每个线性 tile，QK/PV 使用同组四条 Q 映射。M8M8 计算速率为 M8M4 的一半。每输出子块额外 8 拍属于重放参数。 |
| 外存 | HBM2，256 GB/s，3.9 pJ/bit | LPDDR5 配置的共同目标 136.4606 GB/s、4 pJ/bit；64 B 事务、传输末端 30 ns 响应。同一链路序列化字节，预取和响应尾段重叠。解析后端用带宽和响应延迟代替具体 bank、读写转向与刷新。 |
| 片上能量 | Table I 给 PE、SRAM 和其他逻辑功耗 114.761、180.873、约 4.966 mW | PE 以频率、活动拍和活动行计价。中心假设原点功耗 10% 为静态、PE 动态中 35% 随活跃周期支付。SRAM 动态用项目 16 B 宏的每次访问计价代理。DMA/向量/输出逻辑合计计 40 mW。 |

由原文 8,176 GOPS/W × 0.30060 W 复算峰值 2.458 TOPS，约 4,096 MAC/cycle，B1 一行是 512 MAC/cycle。重放采用线性 INT4 每 128 个权重 4 B 块元数据，BFP 每 32 个数打包一个向上取整至字节的共享指数，独立记符号位。Mix 保留首 32 和末 64 个注意力位置的 8 位尾数。计算恰好使用 2,048 个注意力位置，另计新 KV 写回。QK Norm、RoPE、Softmax 等由 16 路公共向量代理排程。W4 头按流式 argmax 结算，嵌入查表使用 BF16。 [Harmonia §III/IV、§V](https://arxiv.org/html/2602.04595v3) · [本项目 28 nm 250 MHz 外存与 SRAM 配置](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/01a2fb1d13018d381e012630ea1be442e85bdd26/architecture_tlm/process_28nm/250MHz/WHOLE_CONFIG.json)

### 时延和能量敏感性

| Harmonia-M8 改动 | ms/output token | 片上 mJ/output token | 含外存 mJ/output token |
|---|---:|---:|---:|
| 双缓冲、8 拍，主比较 | 42.74 | 7.98 | 81.96 |
| 有效带宽取峰值的 85% | 43.22 | 8.02 | 82.00 |
| 每输出子块额外 0 拍，带宽取峰值 | 37.87 | 7.39 | 81.37 |
| 每输出子块额外 16 拍、70% 带宽 | 48.82 | 8.66 | 82.64 |
| 每次仅 1 个缓冲槽，无法双缓冲预取 | 61.49 | 9.37 | 83.35 |
| 线性／Attention 中间值以 FP16 写回再读入 | 42.96 | 8.01 | 82.74 |
| 外存峰值减半至 68.23 GB/s | 45.62 | 8.20 | 82.18 |
| 同工作量，装回 300 MHz／256 GB/s／3.9 pJ/bit | 35.13 | 7.45 | 79.58 |

PE 活动及静态功耗假设扫点使 M8 片上能量在 **6.05–10.68 mJ/token** 间，总能量 **80.04–84.66 mJ/token**。双缓冲是速度结论的主要变数，取消后 Harmonia 中心模型用时从 42.74 增至 61.49 ms。论文支持灵活双端口缓冲与分片数据流，未提供可直接核查的 B1 tile 容量、端口时序和绝对步延迟。本模型要求两份 32 KiB 权重缓冲，并安排 GQA 逐组计算以降低分数缓冲峰值。 [分阶段与敏感性数值](RESULTS.json) · [原文 §IV-A/D、§V-D](https://arxiv.org/html/2602.04595v3)

## 复算和证据

```powershell
python architecture_tlm/benchmark_inventory_20261029/harmonia_full_decode_20261116/replay.py --workspace .
```

Python 3.8，依赖标准库。可去掉 `--workspace` 在独立目录重放外部候选。带 `--workspace` 核验四个冻结文件的 SHA-256，逐项核对 Qwen 形状和平台计价，并载入项目封存对照。程序检查了 **4,626,251,776 MAC** 和全部输出头权重、36 层与 288 组 Attention QK/PV、突发对齐、PE/外存占用约束、位宽和带宽敏感性，两次执行的 JSON 逐字节一致。项目端额外的解析后端复跑在检查前五层后结束，主表采用完整原生 LPDDR 封存。数值模型权重与任务质量、同库 RTL 或 STA、新 SRAM 宏测量、详细 LPDDR 控制器、布局布线及芯片实测尚无新证据。 [脚本](replay.py) · [输入](INPUTS.json) · [结果](RESULTS.json) · [完整原生 benchmark 表](BENCHMARKS_ZH.md)
