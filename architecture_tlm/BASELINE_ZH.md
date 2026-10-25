# 当前 TLM 基线与配置选择（PR183 / PR190）

正式交付主线为 `main`；统一命令 `python -m architecture_tlm`，实现仍在 `unified_v6/`。PR183补齐标准DRAM/片存及跨组预取，PR190建立数字与随机方案共用的有限tile调度、SG接口和对照证据。旧分支 `pbit-tlm-attention-details-20261016` 用于历史追溯，后续主线修改面向main。

这里的“基线”是可追溯的**条件时延与工作量对照**，不是已经验证质量、面积、能量的最优芯片。模型采用后训练Qwen3-4B的形状，默认36层、batch1、总上下文2048、一个decode token；不加载模型权重、不执行PPL、不包含上下文prefill。

## 三类配置分别使用

| 用途 | 配置/入口 | 当前地位 |
|---|---|---|
| 默认共同调度基线 | `--memory-profile mature_ddr4`；100MHz、8MiB/64bank/64GB/s SRAM、双通道双rank DDR4；普通矩阵512 MAC/拍、SC 8×64 | CLI默认存储配置；数字和SC共同有限DMA响应、双共享槽、单本地消费者，下一DMA重叠当前计算 |
| 高带宽外存对照 | `--memory-profile mature_hbm2_pipelined`；HBM2 8通道、16GiB、256B入口和流水响应 | 明确选择的对照；并非默认。HBM功率参数占位，禁止输出有效HBM能耗结论 |
| 架构/调度候选 | `ffn_locality.configure`、`resource_sweep.apply`及封存实验矩阵 | R8/128阵列、宽SRAM/大MAC及digital_shared_prefill均为可选实验；不自动提升成默认，不混称同面积优化 |

`config.load()`给出基础参数，CLI再施加memory profile；直接调用Python API时必须记录最终配置，不能仅用“用了PR190”描述实验。`--config`仍会受到CLI的模型模式、context、seed及memory-profile覆盖，使用时核对输出配置。

## 比较什么

先以相同Attention、外存、片存、上下文、调度和seed比较`--ffn bf16/w8/sc`，再单独比较Attention候选。默认CLI的Attention为`screen_rejection`；以下基准显式选择`exact`，避免把两个口径混在一起。

| Qwen3-4B / 2K / 准确Attention | 默认DDR4 ms/token | HBM流水 ms/token |
|---|---:|---:|
| BF16数字 | 599.340 | 402.629 |
| W8数字，K64块尺度恢复 | 426.364 | 333.664 |
| 原SC 8×64 | 509.471 | 本表不推定 |
| SC 8×64 / R8局部部分和 | 503.639 | 438.038 |

R8另使用有界随机检查点宏；不把它冒充原Issue95实际FFN端点。W8参考仍是配置的数字MAC吞吐，不代表最优INT8 ASIC。表中不是同质量/同面积结论；SC的GU定点编译/舍入与完整后训练模型质量仍待闭环。

资源扫描中的约107.639ms只对应数字BF16、8192 MAC/拍与1024GB/s SRAM等指定目标；不能代替上表基线，也不能直接拿它与未同步扩容的SC比较算法优劣。更多bank、局部供数和互连未通过RTL/STA/PPA。扩容和调度收益分别见[资源消融](unified_v6/RESOURCE_SCHEDULING_ABLATION_ZH.md)。

## 运行与证据

先按[桥接器构建说明](unified_v6/probes/dramsys_bridge/README_ZH.md)准备实际DRAMSys桥；缺失时应报错，不回退为Link估计。示例使用尚不存在的输出目录：

```sh
export PBIT_DRAMSYS_BRIDGE=/absolute/path/to/pbit_dram_bridge_sg_v6_audit
python -m architecture_tlm --memory-profile mature_ddr4 --model qwen3_4b --ffn bf16 --attention exact --output output/new-ddr-bf16
python -m architecture_tlm --memory-profile mature_ddr4 --model qwen3_4b --ffn w8 --attention exact --output output/new-ddr-w8
python -m architecture_tlm --memory-profile mature_ddr4 --model qwen3_4b --ffn sc --attention exact --output output/new-ddr-sc
python -m architecture_tlm --memory-profile mature_hbm2_pipelined --model qwen3_4b --ffn bf16 --attention exact --output output/new-hbm-bf16
```

这些命令展示入口，不要求重跑已完成实验。恢复先读原manifest、Issue和交接。R8及资源候选的准确配置以任务矩阵/最终结果的config为准，不用上述默认命令冒称复现全部候选。

- [共同调度及45项结果](unified_v6/MATURE_SCHEDULING_ZH.md)
- [标准DRAM与预取依赖](unified_v6/RESULTS_MEMORY_ZH.md)
- [局部部分和/128阵列](unified_v6/FFN_LOCALITY_ZH.md)
- [HBM对照](unified_v6/HBM_RESULTS_ZH.md)
- [LLMCompass独立交叉核对](unified_v6/LLMCOMPASS_COMPARISON_ZH.md)：名义资源与算子统计对照，不是同拓扑或完整周期精度证明
- [架构优化记录本](ARCHITECTURE_OPTIMIZATION_LOG_ZH.md)
- [本轮审核与验证边界](../work/jieruiz/55/round11/REVIEW_ZH.md)

完整物理能耗/面积保持null；DDR4负ACT分项原样保留且不反馈时序，priced subtotal不是整机能耗。旧结果保留执行SHA和旧标签，新配置不得继承旧PPL或改写原始结果。
