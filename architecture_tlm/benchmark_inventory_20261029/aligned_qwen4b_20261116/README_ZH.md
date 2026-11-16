# 外部架构运行 Qwen3-4B 的对齐协议

本表的比较对象是各架构在共同配置下执行同一份完整 Qwen3-4B 解码事务。目标参数见 [TARGET.json](TARGET.json)，结果见 [BENCHMARK_ZH.md](BENCHMARK_ZH.md)。快速阶段级估算见 [BitMoD / Tender 快速 benchmark](QUICK_BENCHMARK_ZH.md) 与 [EVA / M-ANT 快速估算](EVA_MANT_ESTIMATE_ZH.md)。

Fig.11 一篇一行汇总见 [benchmark 表](FIG11_LLM_BENCHMARK_ZH.md) 和 [可编辑工作簿](FIG11_LLM_BENCHMARK.xlsx)。

## 对齐顺序

| 项目 | 目标 | 实施方式 |
|---|---|---|
| 模型和测量窗口 | `Qwen/Qwen3-4B` 冻结 revision，B1，2,048 个缓存位置，1 个输出 token。36 层，151,936 词表。 | 接同一套算子和事务范围。覆盖 embedding、Q/K Norm、RoPE、QK/Softmax/PV、KV 更新、FFN、残差、final Norm、全词表 head 与输出选择。按项目边界计时，已有 KV 为初始状态。完整 TLM 使用形状级工作量，真实权重和量化任务质量另验。 [封存的项目原生结果](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/01a2fb1d13018d381e012630ea1be442e85bdd26/architecture_tlm/process_28nm/results_20261111/REPORT_ZH.md) |
| 工艺和计价 | 28HPC+，TT，0.9 V / 25°C。 | 保留各架构的模块划分和阵列配置。用同一套标准单元及 SRAM/PVT 证据，重新给逻辑、控制、片上互连、SRAM/CIM 及 DMA 计价。面积用实际配置下的模块数量。片上能量用事件或真实活动窗口计价，面积边界按项目排除片外 DRAM、PHY、pad、CPU 与封装。CIM、ReRAM 或 NAND 原语需要对应 28 nm 宏模型及接口范围。 |
| 时钟 | 250 MHz，周期 4 ns。 | 先检验被映射的关键路径和存储宏服务。如果需要增加流水级，更新各模块发射间隔、完成延迟和 FIFO，再运行这一版排程，保留时序证据和改动。 |
| 外存系统 | 同一个原生 Ramulator LPDDR5-derived8533、8 个 x16 通道，项目标称 136.46 GB/s。 | 复用 `derived8533.yaml` 和桥版本，保留通道映射、行策略、队列、刷新及回压。让各架构发出自身按时序生成的物理地址流和读写事务，使用相同控制器配置。外存能量按相同 4 pJ/bit 价格乘实际传输字节，得出含外存能量。平均功率可按每 token 能量除以同一窗口的时延求得。 |
| 数制与任务质量 | 固定模型来源、任务和质量门槛，各方案使用可验证的原生数制。 | 按原生权重、元数据、KV 数据和转换的物理流量计价。同数制消融可另列。完成硬件事务结果以后，再在相同 checkpoint 和测试协议上对齐 PPL 和应用分数。 |

先在作者给出的原始配置下校验其工具及每类操作的边界，然后把 Qwen workload 接到同一原生外存；用一层与词表尾块做门禁，核对张量布局、KV 组数、事务字节、队列排空及算子发射条件。完整 36 层与全词表结果通过后，再引用整步时延、能量、面积。原作者 PPA 若仅覆盖单个宏，明确保留该范围并补齐其余部件。Harmonia、EdgeCIM、Zhou 等原报参数仍在 [原生文献表](../LLM_HARDWARE_BENCHMARK_20261116.md)。

主表以共同工艺、时钟和外存作为约束，允许各架构选择其实际片上容量和资源。项目四组已采用 832 KiB SRAM。后续若要等面积，可以在完成原配置对齐以后，另限相同面积并重做映射。NVLLM、RS-LPU 的近存介质与计算机制绑在一起，若无法确认共同的外存/近存比较边界，将原生点留在原生文献表。

## 实跑过的作者代码

已获取 BitMoD 作者的 [固定提交 e445a5f3](https://github.com/abdelfattah-lab/BitMoD-HPCA-25/tree/e445a5f31100a5057b4c5c4373da223ce95f1c3b)。使用原始作者矩阵阵列周期计算，适配器只提供本项目冻结的张量维度。Qwen 的 (d_mathrm{head}=128) 及四个 query head 共享一组 KV 使用实际数值。覆盖 325 个矩阵计算和 4,626,251,776 个有用 MAC，含 36 层 QK、PV、FFN 和完整 head。未加载数值权重。6-bit/3-bit 的名称沿作者生成时采用的两种配置，KV 均为 8 bit，Qwen 的任务质量未在此验证。 [BitMoD 原文](https://arxiv.org/html/2411.11745v1#S5)

| BitMoD 作者矩阵配置 | QKVO 与 FFN 阵列周期 | QK 与 PV 阵列周期 | 完整词表阵列周期 | 合计 |
|---|---:|---:|---:|---:|
| 6-bit weight setting | 42,577,920 | 2,359,296 | 4,558,080 | 49,495,296 |
| 3-bit weight setting | 28,385,280 | 2,359,296 | 3,038,720 | 33,783,296 |

该次运行用了作者的 `Accelerator._calc_compute_cycle`。内存设为 `init_mem=False`，保留矩阵范围内的周期。原版聚合代码的外存时延根据每层字节、重复读取次数和带宽计算。要得到共同 LPDDR 结果，需要实际加入 BitMoD 的缓冲/排程地址流、并接入项目的原生桥，再给未覆盖的 Norm、RoPE、Softmax、输出选择和 KV 更新补运行。EDA 远程登录助手在此会话的只读连接预检返回 DNS 11001，此轮没有提交远程任务。本机现有 LPDDR 桥为 Linux 二进制。以上阵列周期列只出现在阵列记录里。

## 执行和结果文件

```powershell
python architecture_tlm/benchmark_inventory_20261029/aligned_qwen4b_20261116/run_bitmod_pilot.py --artifact <pinned-BitMoD-checkout> --out bitmod_matrix.json
python architecture_tlm/benchmark_inventory_20261029/aligned_qwen4b_20261116/build_benchmark.py --out aligned_results.md
```

- [作者阵列结果](BITMOD_MATRIX_PILOT.json) 保存每类算子的覆盖和周期。
- [结果表生成器](build_benchmark.py) 核对项目结果 SHA。后续可加 `--external-result <run.json>`，导入经验证的完整外部执行和 28 nm PPA。它核对配置、阶段、250 MHz 与原生 DRAM 证据，按实际读写字节计算含外存能量。
- 完成记录包含 `candidate`、`scope=complete_decode`、`run_status=completed`、`conditions`、`executed_stages`、`clock_validated`，和三份 `evidence` 文件 `runtime, dram, ppa`（每份 `path, sha256`）。`metrics` 为 `time_ms, core_mJ, area_mm2, dram_read_bytes, dram_write_bytes`。
- 当前外部各工程覆盖范围见 [对齐 benchmark](BENCHMARK_ZH.md)。真实权重路径及质量实验独立于形状工作量。此轮未生成外部整机估算值。

能量补充版为 [片上能量估算、DeepScaleTool 工艺折算及覆盖](ONCHIP_PRICE_METHOD_ZH.md)。[单行 benchmark 表](FIG11_LLM_BENCHMARK_ZH.md) 同行标明片上范围和原文解码覆盖；[数值](ONCHIP_PRICE_ESTIMATE.json) 可用 `python price_onchip.py ONCHIP_PRICE_ESTIMATE.json` 复算。
