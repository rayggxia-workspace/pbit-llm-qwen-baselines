# 周期动作与数字仿真台账的计费边界

本轮只输出可核对的动作和时间；缺少匹配表征的系数保持 `null`。以下是后续校准的绑定入口，不是把旧模块功耗迁移为新整机能量。正式台账在仓库根 `digital_circuit_simulation_registry/records/`。

| 周期模型对象 / 动作单位 | 可查台账记录 | 当前可用性与缺口 |
|---|---|---|
| `memory.*` 接受一次请求、实际读/写 byte、line beat | `sram-38068650-states`、`sram-38071895-library`、`sram-cacti-v1` | 宏内部保持/读写与库表已有证据；本轮64B line、bank/端口和局部工作集尚未映射同配置宏阵列，不能直接收费。DRAM 命令/背景/刷新能量仍未知 |
| `weight_read_bytes`、`sram_read_bytes`、`partial_read_bytes` 等 | 同上 | 前端语义别名；已经由 `memory.*` 记录同一次物理事务时禁止再加一次能量 |
| native `lfsr` / `bivium` endpoint 实际时钟活动、idle、seed、SAVE/RESTORE | `rng-38322118-lfsr-100`、`rng-38322118-bivium-100` | 100MHz SS 的 provisional PT profile 可供条件估计；seed 增量和 shared64 frontend 尚未配齐。不可把 `rng-38322118-ffn-100` 整块功耗再加到 LFSR 上；本轮不输出伪精确总能量 |
| `sc_sample_frames` 一 tile 一 temporal sample；`weight_input_trials` 为输出行×输入列；`counter_clocked_slots` 为实际布局槽 | `sc-37962470`、`sc-37981139`、`short-stream-22-functional` | 原分组OR/CSA/短流 RTL 与本轮输入-sign rails、二补码位平面、B/T/K/驻留供给不是自动同映射。需要相同RTL及活动回填 |
| 编码 group abs/max/bin/量化；每完整 tile 的逐行 restore 和 `cross_tile_fp32_add` | `digital-107-functional`、`conversion-1587-functional` | 功能证据不等于目标工艺价格；`complete_tile_restore=1` 只是阶段完成计数，禁止再乘72代理op。新恢复各级算术动作已分开，不能与tile宏价同时计费 |
| `silu_values`、`gated_multiply` | `swiglu-38100634-ss`、`swiglu-38100634-tt` | 旧模块是 Q10 单通道；本轮连续SiLU/FP32边界不同，不能继承其单元能耗或16lane面积 |
| QK/数字投影 MAC、EXP、reciprocal、normalize、PV CDF、winner/rejection反馈、V加权累加 | `digital-107-functional` 等功能入口 | 本轮格式、共享宽度、流水与源码函数需要匹配的 RTL/STA/活动表征；旧 BF16 2pJ/MAC 等条件系数不能作为这些 FP32/double-fsum 数学边界的实测价格 |
| 有限资源、FIFO、CDC mailbox 握手 | `cycle-116-protocol-rtl` | 本轮9组252握手只提供 RTL_FUNCTIONAL，综合/STA/面积/功耗均未运行 |

输出中的 source `receipts` 是协议事件；`native_response_copy` 是桥接动作，不是一次新的 p-bit 源帧。一个 shared64 随机字广播给多个 tile 时，随机字只在 native ledger 计一次，sink/比较/广播成本另列。20-lane Bivium 的物理生成、逻辑使用及padding分别记录，不能用逻辑64lane价格覆盖实际80lane实例。

资源 `execution_ps` / `held_ps` 为可能重叠的逐操作时间总和。面积必须先定义同时存在的物理实例、SRAM宏、数组局部保持和互连，不能把动作次数相加成面积；能量也不能把所有流水在途区间相加当作全芯片活动时间。`energy.status=unknown` 不表示能量为0。

相同 seed、相同语义算法不必产生同一源时序；改变等待、端点池或重播种时刻后，需要核验实际trajectory。新v6桥明确将双方存储/采样契约分开，因此没有从耗时差导出能效或性能优势。完整校准/同质量同资源优化对应原方案G，尚未完成。
