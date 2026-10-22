# 给用户的数字功耗仿真交付说明

本包不给出未经测量的功耗/面积数字。先验证功能，再在用户自己的工艺库中综合与时序检查，最后用匹配活动做门级功耗。行为VCD仅验证接口和活动场景，不能直接当成包含门级毛刺/CTS/布线的功耗结果。

## 建议优先仿真的核心

| top | 配置 | 测什么 |
|---|---|---|
| `rng_seeded_top` | KIND=0 | 基础LFSR、1字输出寄存器、比较、seed入口/控制 |
| `rng_seeded_top` | KIND=1 | 原GF扩展64字输出及64比较器的实际共享成本 |
| `rng_seeded_top` | KIND=2 | 160bit展开Bivium、5拍预热、20比较器 |
| `rng_ffn_shared64` | 无KIND参数 | 单字广播64阈值、阈值保持和回压；与GF64字区分 |

可另综合`rng_lfsr32_map`、`rng_shared64_map`、`rng_bivium_map`做组合路径/面积拆分，但组合块没有内部时钟；其功耗必须由实际输入活动驱动，不能套虚构更新率。`rng_seed_ingress`可以单独测启动/重播种活动。

所有可综合文件在rtl/；`rng_shared64_map`是现有优化XOR DAG的提取，独立封装后寄存器/握手由endpoint负责。使用SystemVerilog（VCS `-sverilog`、Xcelium `-sv`、DC `analyze -format sverilog`），不是模拟Verilog-A。

## 流程

1. 在包根执行Python单测和verification；若工具不在PATH，显式给`--iverilog`及`--vvp`。无工具时会生成向量并标VECTORS_ONLY，不宣称通过RTL。
2. 选择top和KIND，提供实际corner库、目标时钟、输入延迟/输出负载。`scripts/synth_dc.tcl`是参数化起点，要求环境变量，不绑定/上传工艺库。
3. 检查时序，特别是Bivium展开网络、GF输出网络及比较路径。未过目标频率时降低时钟或加流水线；加流水线后必须同步更新Python协议并重验，不能只改报告中的频率。
4. 对门级网表用相同输入向量生成VCD/SAIF，保存精确top、参数、库/PVT、约束、综合版本与文件SHA。门级内部名称不同，不应继续用RTL内部状态断言；向量中的接口数据/握手仍可作为外部scoreboard。
5. 在PT-PX或你现有流程读取网表/库/SDC及活动；报告annotation coverage、未标注网、未知X比例、时序和功耗分项。布局前后、是否含CTS/RC单独标记。

## 活动场景

下例产生新目录，`--seeds 17`只是可复现活动，不是部署固定种子：

```bash
python -m architecture_tlm.random_service.verification --output power_stream --scenario stream --reseed-cycles 0 --cycles 10000 --seeds 17 --vcd
python -m architecture_tlm.random_service.verification --output power_idle --scenario idle --reseed-cycles 0 --cycles 10000 --seeds 17 --vcd
python -m architecture_tlm.random_service.verification --output power_burst --scenario burst32 --reseed-cycles 0 --cycles 10000 --seeds 17 --vcd
python -m architecture_tlm.random_service.verification --output power_stall --scenario stall --reseed-cycles 0 --cycles 10000 --seeds 17 --vcd
python -m architecture_tlm.random_service.verification --output power_reseed --scenario stream --reseed-cycles 300 --cycles 10000 --seeds 17 --vcd
```

- `stream`：持续请求，阈值每32拍变化；测满吞吐活动。
- `idle`：完成播种后不请求，测保持/时钟与泄漏。RTL使用数据enable，没有自动插入ICG；综合插门控与否必须记录。
- `burst32`：每128拍有32拍请求，用于短流开关活动；不是实际LLM trace。
- `stall`：消费者阶段性反压，确认寄存器保持与无免费生成。
- `power_reseed`：人为加速换种便于测每次事件。不能把此平均功率冒充每秒换种时的平均功率；应分离启动/正常活动/每次重播种能量。

实际慢换种无需为1秒在RTL中运行1亿拍才能估算：分别测各阶段事件与空闲，再用系统统计次数/时长组合，但相互重叠的活动必须避免重复计账。

验证TB时钟10ns，只是目标约束起点。波形时间戳以TB为准；operations.json建议窗口从1000ns起，用户应确认该配置已完成启动/预热。短于该窗口的自定义运行不得使用该窗口。

## 边界和回填模板

FFN前端与GF64输出的位数、保持寄存器和相关性不同，应同时报告每帧成本、可用输出数和质量要求，不只比较每个bit。未使用的端口会被综合裁剪；明确是raw+bits全部保留还是mask-only，与Python动作口径对应。

本轮不含真实物理源、健康/调理、CDC、片外PHY、共享总线仲裁器、完整sigmoid LUT/配置存储、长线分发和全芯片CTS。不要将这些视为零成本。已有模拟结果应单列加入，不能重复统计其比较器。

回填`configs/characterization_template.json`：按top/KIND/corner/时钟/场景提供面积、时序、平均功率或积分能量、成功帧数、种子装载数、门级活动覆盖与证据路径。模板数值默认null；核心总能量与每操作能量任选明确模型，不能同时相加。

