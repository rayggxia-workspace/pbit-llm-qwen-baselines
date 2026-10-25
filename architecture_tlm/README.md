# 完整 LLM TLM：统一入口

本目录的默认执行入口是 **`python -m architecture_tlm`**，实现继续维护在 `unified_v6/`，不另建 v7。Issue179 将原集成分支的必要运行代码整理到 main，并接入固定四档、三路 AND 直连 Wd 的 FFN。

推荐存储配置已更新为标准DDR4＋64bank SRAM＋共同tile生命周期＋有界SG/权重预取；说明见[存储层次与批次分析](unified_v6/MEMORY_HIERARCHY_ZH.md)。需要现有DRAMSys bridge，缺失时明确报错，不回退简化模型。

```sh
export PBIT_DRAMSYS_BRIDGE=/absolute/path/to/pbit_dram_bridge_sg_v6_audit
python -m architecture_tlm --model qwen3_4b --ffn sc --attention screen_rejection --nonlinear-samples 64 --output output/run01
python -m architecture_tlm --model qwen3_4b --ffn bf16 --attention exact --output output/reference01
python -m architecture_tlm --memory-profile legacy --model qwen --ffn-profile legacy --ffn-samples 32 --strata 32 --output output/legacy01
```

Python 3.10+，标准库即可。正式运行前提交执行源码；输出目录必须不存在。`--config`可提供完整配置，`--rng-backend`默认为已接入的实际随机服务。实际端点逐事件执行的大型场景可能需数十分钟或更久的CPU时间；这与输出中的硬件时间不是同一指标。

- [成熟调度探索、完整对照与复现入口](unified_v6/MATURE_SCHEDULING_ZH.md)
- [最新 FFN 的完整流程、宏周期与证据边界](unified_v6/FFN_CURRENT_ZH.md)
- [执行结果与验证](unified_v6/RESULTS_CURRENT_ZH.md)
- [配置及默认宏参数](unified_v6/ffn_latest.py)
- [实现来源、整理范围](../work/jieruiz/179/IMPORT_MANIFEST.json)

当前输出是 **batch1 decode 的架构级条件估计**；不含已有上下文的 prefill，不是逐门或全芯片周期精确仿真，也不计算PPL。完整能耗/面积仍为 `null`，已有价格的合计不是整机能耗。默认存储profile为`mature_ddr4`，调用真实DRAMSys/DRAMPower并使用冻结的Micron DDR4-1866双通道双rank配置。历史Issue179结果仍是Link估计；可用`--memory-profile legacy`重现该边界。DRAMPower仅core电流限值部分有依据，I/O/PHY仍未知；新旧DRAM能耗口径不能直接混用。

Qwen3-4B使用后训练版形状；旧Qwen2.5、Llama1/2配置保留历史标注，只用于形状/调度研究，不宣称这些新FFN已完成模型质量验收。Attention实现与原集成版本保持一致，新增的Qwen3显式head_dim及QK归一化是形状适配。

历史实验及完整证据继续在[冻结集成版本](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/tree/d6d33995754fcdcea99286e4ce43f91647aa231a/architecture_tlm)，无需复制历史大结果目录。
