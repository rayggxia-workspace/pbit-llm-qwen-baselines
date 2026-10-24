# 完整 LLM TLM：统一入口

本目录的默认执行入口是 **`python -m architecture_tlm`**，实现继续维护在 `unified_v6/`，不另建 v7。Issue179 将原集成分支的必要运行代码整理到 main，并接入固定四档、三路 AND 直连 Wd 的 FFN。

```sh
python -m architecture_tlm --model qwen3_4b --ffn sc --attention screen_rejection --nonlinear-samples 64 --output output/run01
python -m architecture_tlm --model qwen3_4b --ffn bf16 --attention exact --output output/reference01
python -m architecture_tlm --model qwen --ffn-profile legacy --ffn-samples 32 --strata 32 --output output/legacy01
```

Python 3.10+，标准库即可。正式运行前提交执行源码；输出目录必须不存在。`--config`可提供完整配置，`--rng-backend`默认为已接入的实际随机服务。大型场景可能需数分钟CPU时间。

- [最新 FFN 的完整流程、宏周期与证据边界](unified_v6/FFN_CURRENT_ZH.md)
- [执行结果与验证](unified_v6/RESULTS_CURRENT_ZH.md)
- [配置及默认宏参数](unified_v6/ffn_latest.py)
- [实现来源、整理范围](../work/jieruiz/179/IMPORT_MANIFEST.json)

当前输出是 **batch1 decode 的架构级条件估计**；不含已有上下文的 prefill，不是逐门或全芯片周期精确仿真，也不计算PPL。完整能耗/面积仍为 `null`，已有价格的合计不是整机能耗。默认DRAM为有限并发带宽/延迟链路模型，**本次结果不是DRAMSys/DRAMPower重跑**；`dram.backend=dramsys`继续保留已有外部bridge接口。

Qwen3-4B使用后训练版形状；旧Qwen2.5、Llama1/2配置保留历史标注，只用于形状/调度研究，不宣称这些新FFN已完成模型质量验收。Attention实现与原集成版本保持一致，新增的Qwen3显式head_dim及QK归一化是形状适配。

历史实验及完整证据继续在[冻结集成版本](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/tree/d6d33995754fcdcea99286e4ce43f91647aa231a/architecture_tlm)，无需复制历史大结果目录。
