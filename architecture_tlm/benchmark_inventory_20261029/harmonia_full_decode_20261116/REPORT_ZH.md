# Harmonia 公开参数的探索性估算（归档）

2026-11-16。以下是此前根据论文公开参数、Qwen3-4B 张量尺寸及自行设定的调度和计价假设所做的独立解析估算。项目没有执行 Harmonia 的实现，没有将其接入项目 TLM，也没有运行对应的 Qwen3-4B 推理任务。这些数字仅用于追溯此前的推导，正式 benchmark 使用论文原报数据。Harmonia 原文的 decode 分项采用 Llama-3.1-8B-Instruct。 [修订后的 benchmark 表](../LLM_HARDWARE_BENCHMARK_20261116.md) · [Harmonia 原文 §IV–V、Table I、Fig.21](https://arxiv.org/html/2602.04595v3#S5)

## 解析估算的历史数值

脚本代入项目封存的 Qwen3-4B 形状，假设 B1、2,048 个缓存位置和一个输出 token。它根据各阶段张量尺寸计算工作量，令 INT4/BFP8 线性数据通路适用于全词表头，并假设 KV 采用 M8 或 Mix。项目数字行来自既有项目 TLM 封存，Harmonia 行的结果取决于脚本里的容量、调度和代理计价。

| Qwen3-4B B1/2K | 时延（ms/token） | 片上能量（mJ/token） | 含外存能量（mJ/token） | 含外存平均功率（W） | 已计价面积（mm²） |
|---|---:|---:|---:|---:|---:|
| 假设 W4/BFP、M8 与 Mix，仅解析估算 | 约 40–50，双缓冲 | 约 8 | 约 80 | 约 2 | 约 4 |
| 本项目 BF16 Dense，原生 LPDDR TLM | 111 | 32 | 299 | 2.7 | 6.4 |
| 本项目 W8 Dense，原生 LPDDR TLM | 95 | 23 | 204 | 2.1 | 6.4 |
| 本项目 W8 + Key Selection，原生 LPDDR TLM | 85 | 20 | 193 | 2.3 | 6.4 |
| 本项目 P-bit，原生 LPDDR TLM，三种子均值 | 51 | 15 | 188 | 3.7 | 6.5 |

外存动态统一按 4 pJ/bit，用读写事务字节 × 32 pJ/B 计算。平均功率按中心情景逐行求每 token 能量与时间之比。片上面积边界为估算的片上子系统，外存裸片、PHY、封装和板卡在边界之外。Harmonia 行为形状级解析估算，项目行使用已封存的原生 LPDDR 时序。表内的约数和情景范围用于呈现估算量级，逐项复算使用原始 JSON。 [输入与来源散列](INPUTS.json) · [分阶段结果](RESULTS.json) · [项目原生封存](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/01a2fb1d13018d381e012630ea1be442e85bdd26/architecture_tlm/process_28nm/results_20261111/REPORT_ZH.md)

### 权重、KV 与整机比较口径

| 每输出 token 的外存事务（GB） | QKVO、FFN、词表头权重及量化元数据 | KV 和其余事务（含范数、查表） | 合计 |
|---|---:|---:|---:|
| Harmonia-M8，稠密 Attention | 约 2.14 | 约 0.18 | 约 2.31 |
| Harmonia-Mix，稠密 Attention | 约 2.14 | 约 0.10 | 约 2.24 |
| 本项目 P-bit，三种子均值 | 约 5.36 | 约 0.06 | 约 5.41 |

双方线性张量的形状相同。Harmonia 重放用 W4 方式存线性权重，项目端为 W8 FFN、BF16 QKVO 和词表头。仅权重搬运相差约 **3.2 GB/token**，在 4 pJ/bit 下相当于约 **100 mJ/token**。Harmonia 的压缩 KV 用于稠密 QK/PV，KV 及其他事务仍高于项目的 Key Selection 与 V 采样路径，抵消了少量权重收益。词表头本身的权重读取约为 0.21 对 0.78 GB/token。表中列的是单步跨接口搬运量。 [Harmonia v3 Table II/III](https://arxiv.org/html/2602.04595v3#S5.SS2) · [外部事务明细](RESULTS.json) · [项目原始汇总](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/01a2fb1d13018d381e012630ea1be442e85bdd26/architecture_tlm/process_28nm/results_20261111/SUMMARY.json)

- **未来的同条件整机比较**需要同一个 Instruct 权重来源及 revision、同一评测协议、同一 decode 窗口和硬件条件。双方需验证相同质量门槛。M-ANT 用混合精度对齐基线 PPL。 [M-ANT §VII-A](https://arxiv.org/html/2502.18755v1#S7.SS1)
- **用片上消融解释概率机制。** 项目 W8 + Key Selection 与 P-bit 的外存都约 5.4 GB/token，可配对观察概率 FFN 和 Attention 采样这套组合的贡献。需要外部架构消融时，只在双方有兼容数制时选共同存储格式、精确量化张量和 KV 协议，放入共同外存模型重跑。可单独试项目端的 W4 打包存储，在片上按各计算路径解包或反量化，计入 scale、zero point、缓冲和转换开销后再核对质量。

### 芯片、时钟和外存换算

| 项目 | Harmonia v3 原始条件 | 共同条件及处理 |
|---|---|---|
| 工艺 | TSMC 28 nm、0.9 V，DC 综合和门级 VCD，SRAM 来自 28 nm 编译器 | 同为 TSMC 28 nm、0.9 V，论文未披露具体库子型号和角。复用原生核心约 3.4 mm²，以项目 28HPC+ 的 DMA/FIFO 和非线性／输出代理估算约 0.8 mm²。 |
| 时钟／阵列 | 300 MHz，阵列 8×16，B1 GEMV 行利用 12.5%。整核约 300 mW，峰值约 2.5/1.2 TOPS（2 ops/MAC） | 250 MHz。按 512 MAC/周期的单行 M8W4 路径重算每个线性 tile，QK/PV 使用同组四条 Q 映射。M8M8 计算速率为 M8M4 的一半。每输出子块额外 8 拍是中心情景假设。 |
| 外存 | HBM2，256 GB/s，3.9 pJ/bit | LPDDR5 配置的共同目标 136.4606 GB/s、4 pJ/bit；64 B 事务、传输末端 30 ns 响应。同一链路序列化字节，预取和响应尾段重叠。解析后端用带宽和响应延迟代替具体 bank、读写转向与刷新。 |
| 片上能量 | Table I 给 PE、SRAM 和其他逻辑功耗约 115、181、5 mW | PE 以频率、活动拍和活动行计价。中心假设原点功耗 10% 为静态、PE 动态中 35% 随活跃周期支付。SRAM 动态用项目 16 B 宏的每次访问计价代理。DMA/向量/输出逻辑合计按约 40 mW。 |

由原文 8,176 GOPS/W × 0.30060 W 复算峰值 2.458 TOPS，约 4,096 MAC/cycle，B1 一行是 512 MAC/cycle。重放采用线性 INT4 每 128 个权重 4 B 块元数据，BFP 每 32 个数打包一个向上取整至字节的共享指数，独立记符号位。Mix 保留首 32 和末 64 个注意力位置的 8 位尾数。计算恰好使用 2,048 个注意力位置，另计新 KV 写回。QK Norm、RoPE、Softmax 等由 16 路公共向量代理排程。W4 头按流式 argmax 结算，嵌入查表使用 BF16。 [Harmonia §III/IV、§V](https://arxiv.org/html/2602.04595v3) · [本项目 28 nm 250 MHz 外存与 SRAM 配置](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/01a2fb1d13018d381e012630ea1be442e85bdd26/architecture_tlm/process_28nm/250MHz/WHOLE_CONFIG.json)

### 时延和能量敏感性

双缓冲且改变每片开销和链路效率的情景落在 **约 40–50 ms/token**。改成单缓冲，排程时延约 **60 ms/token**。PE 活动及静态功耗扫点给出 M8 片上 **约 6–11 mJ/token**、含外存 **约 80–85 mJ/token**。这些范围来自已算情景，尤其受缓冲和流水实现影响。原文报告灵活双端口缓冲和分片数据流，缺少可直接复核的 B1 缓冲容量、端口时序和绝对步延迟。中心重放用两份 32 KiB 权重缓冲，并安排 GQA 逐组计算以降低分数缓冲峰值。 [分阶段与敏感性数值](RESULTS.json) · [原文 §IV-A/D、§V-D](https://arxiv.org/html/2602.04595v3)

## 复算和证据

```powershell
python architecture_tlm/benchmark_inventory_20261029/harmonia_full_decode_20261116/replay.py --workspace .
```

Python 3.8，依赖标准库。可去掉 `--workspace` 在独立目录重放外部候选。带 `--workspace` 核验四个冻结文件的 SHA-256，逐项核对 Qwen 形状和平台计价，并载入项目封存对照。程序检查了 **4,626,251,776 MAC** 和全部输出头权重、36 层与 288 组 Attention QK/PV、突发对齐、PE/外存占用约束、位宽和带宽敏感性，两次执行的 JSON 逐字节一致。项目端额外的解析后端复跑在检查前五层后结束，主表采用完整原生 LPDDR 封存。数值模型权重与任务质量、同库 RTL 或 STA、新 SRAM 宏测量、详细 LPDDR 控制器、布局布线及芯片实测尚无新证据。 [脚本](replay.py) · [输入](INPUTS.json) · [结果](RESULTS.json) · [完整原生 benchmark 表](BENCHMARKS_ZH.md)

权重事务复核使用项目封存 `project_archives/tlm28p250_full225_20261110/seed{17,503,1009}/RESULT.json` 中的 `memory.by_kind`，将 QKV、O、GU、Down、词表头、FFN scale 元数据相加。Harmonia 取 `RESULTS.json` 中两个模式各自八个线性投影的读取字节之和。每行以完整读写量减权重读取量得到 KV 与其余事务。
