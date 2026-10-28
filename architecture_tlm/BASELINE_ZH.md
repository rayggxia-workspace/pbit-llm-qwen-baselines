# 当前 TLM 基线与配置选择（PR183 / PR190，2026-10-28更新）

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

## 2026-10-28新增实现与证据

PR190仍是共同调度基线。下列模块和候选随本轮审核接入main，默认配置不变；各阶段应分别引用，不能把功能测试、局部PPA与模型精度拼成同一已验证系统。

| 入口 | 已完成 | 仍需完成 |
|---|---|---|
| [FFN第一阶段](ffn_calibration_stage1/README_ZH.md)、[校准v2](calibration_v2_20261027/README_ZH.md) | 精确整数计数/恢复、合并计数、BF16/FP32数字核及握手功能；PR194/196 | 真实模型数制闭环、目标频率完整集成；v2私有EDA执行包比公开功能包有后续流程修订，应按PPA源manifest复现 |
| [8位前端](random_service/pbit8_char/README_ZH.md)、[228窗口PPA](../digital_circuit_simulation_registry/summaries/20261027/PPA_SUMMARY.json) | 比较器/LUT及部分计数/门控/数字核的局部DC、gate、PT结果；PR195/197 | 非后布局；100MHz表征不能证明500MHz；X4负例与工具告警保留 |
| [固定资源调度](scheduling_v2_20261027/FINAL_RESULTS_ZH.md) | 完整36层条件TLM三seed 64.4113→57.4454ms；PR192，大部分收益来自普通投影供数 | 500MHz STA、同质量/同面积验证；没有新PPL |
| [本地端口](local_ports_20261027/RESULTS_ZH.md) | 单层＋完整词表SC 8.3223→6.8168ms，数字8.9369→7.1730ms；原件/负例保留 | 不是36层TPOT；16KiB FIFO、端口/mux/driver/CDC/CTS成本未闭环；新后端拒绝尚未适配的Ising sink |
| [T32单尺度矩阵](matrix_single_scale_20261028/README_ZH.md) | 真INT8、精确/先计数/OR4/数字对照；16设计96个局部PPA窗口；PR205 | OR4不是精确算术：约42–44%相对事件参考NRMSE；本批仍未胜过数字位串行能量；未测真实模型质量 |
| [参数化模块能耗库](module_energy_20261028/results/REPORT_ZH.md) | PR205增量：33个固定top、396窗口；组合逻辑、累计器与bank分开表征 | bank为预解码7幅值位，abs(W)≤127，不同于旧完整INT8；未经校准的模块相加偏差约23%–27%，0.637%仅为相邻位宽配置留出验证 |
| [文献与指标审计](simulator_survey_20261025/README_ZH.md) | 调研、计算边界和数值探针；PR189 | 不是论文复现实验；历史“待跑T32”等计划由PR205的新证据接续，不能用旧估算覆盖实测 |

原始面积及原件SHA不改。本项目后续面积汇总按用户口径单次乘0.81，保留原始面积、系数与等效面积；本轮[面积派生表](../work/jieruiz/55/round12/evidence/AUDIT197.json)给出对应值。旧PPA/TLM表中的原始面积不能当作已折算值。功率、能量、频率、时延与PVT标签不随面积折算。

[本轮审核、复验与待办](../work/jieruiz/55/round12/REVIEW_ZH.md)；[统一数字电路台账](../digital_circuit_simulation_registry/README_ZH.md)。保留已计算功耗但时序违例、准备中和历史负结果的独立阶段；台账收录不代表所有设计验收通过。
