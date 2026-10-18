# A8 短流分层采样与精确随机矩阵 PE：RTL 仿真包

本目录是 Issue #22 的数字电路功能和功耗表征输入，基于 workspace TLM 分支 `3553996bf014a29dee7fdb2250a3965e8fd881a4`。它不包含工艺库、SRAM 宏或物理 p-bit 器件；RTL 通过不等于已测得面积/功耗，也不证明 Qwen 的完整 PPL 已保持。

## 1. 这次具体改变了什么

一个 PE 对 64 个输入计算一个点积。固定带符号 W8 权重、独立输入符号、A8 幅度概率 `p=q/256`，每拍产生一个被 64 路比较器共享的门限。

| 模式 | 拍数 T | 本拍门限 r | 每拍真正参与门限的随机位 |
| --- | ---: | --- | ---: |
| IID4096 | 4096 | `random[7:0]` | 8 |
| IID128 | 128 | `random[7:0]` | 8 |
| strat64 | 64 | `(sample_count << 2) \| random[1:0]` | 2 |
| strat128 | 128 | `(sample_count << 1) \| random[0]` | 1 |
| enum256 | 256 | `sample_count[7:0]` | 0 |

比较严格使用 `q>r`。`q=0` 永不命中，`q=255` 的完整枚举命中 255 次，不把 255 当作概率 1。所有模式只用已有的一个帧计数器，分层模式复用它的高位形成区间，不另外增加一个分层计数器。计数输出使用 `LOG_T+1` 位以容纳帧结束的 T，例如 128 拍需要显示 128，而非回绕成 0。

`strat128` 的平均是随机舍入：偶数 q 精确，奇数 q 在相邻偶数码之间随机选择。属于随机分层/一元编码，不是每拍独立同分布的 Bernoulli 流。`enum256` 完全确定，在本包固定权重、精确累加条件下准确恢复量化点积，不应再称为纯随机计算。

## 2. 算术与存储边界

每个权重位平面分别产生正/负事件，使用两棵平衡精确 popcount 树；计数作差、按位平面权重移位后，再用平衡树合并；最后每个有效拍更新主时间累加器。这与历史 `sc_grouped_or_core` 的 G1/B1 路径一致，没有 OR 碰撞近似，没有缓存多拍后才更新的第二种结构。

默认主累加器统一为 **27 位**，避免用不同宽度使模式比较混入额外优化。`sc_ss_exact` 的 `ACC_W` 可另行指定；N64、W8 的最坏情况可用 `15+LOG_T` 位，所以 T128 可另做 ACC22、T64 可另做 ACC21。先比较同宽 27 位，再单列缩位结果。

权重输入为普通二补码 signed W8。组合符号/幅度转换支持 `-128`，包括其幅度 128；本项目现行模型量化权重实际限制在 `[-127,127]`，RTL 的 `-128` 仅用于通用边界测试。若系统预先离线存储符号/幅度码，可以进一步去掉片上转换，但不能把该改动与当前这组面积结果混用。

**本模块不包含权重银行、概率银行或输入符号银行。** `weights/probability/input_sign` 是外部稳定的 packed bus，在从 start 被接受到 done 的整个帧内必须保持不变，可由 SRAM 输出保持接口或已有 tile 缓冲提供。这里不声称这些系统级存储免费：SRAM 读出、保持、布线和接口能耗应在 TLM/物理设计中另外计入。不能把旧 P_W12、概率/权重 DFF 银行的历史 PPA 当作这组外部总线版的实测 PPA。

最终输出是未归一化整数：

`raw_sum = Σ_t Σ_i weight_i × input_sign_factor_i × [q_i > r_t]`。

外部恢复连续值：`y = (Sx × Sw / T) × raw_sum`。本包不实现 BF16/定点缩放、SiLU、分支乘法或残差；这些是系统其他模块，仍需独立计费。对 enum256，`raw_sum = Σ_i weight_i × sign_i × q_i`。

## 3. 接口与随机源

- `start && !busy && !seed_load`：接受一个新帧，清零累加器与计数。启动拍本身不计为一个样本。
- `busy && sample_valid`：接受一个样本。valid 为 0 时，计数、主累加器、内部 PRNG 全部保持。
- busy 期间的 start、seed_load 被忽略，正常 valid 样本仍接受。空闲时 start 与 seed_load 同拍，执行 seed_load，阻止 start，避免模糊的第一个随机数。
- `done`：最后一个有效样本被接受后脉冲一拍；raw_sum 和 sample_count 保持到下一个帧。
- `seed_load && !busy`：载入种子；0 规范化为 1，避免 xorshift32 全零锁死。先载入同一个种子，再启动同一帧，可复现相同门限；空闲时保存 `rng_state`、随后重新载入，可恢复下一帧的序列。start 本身不会自动回卷随机种子。本包只支持**帧边界**恢复，没有 frame_count 装载接口，不能恢复任意半帧。
- `INTERNAL_RNG=1`：内置一个 xorshift32，输出其低 8 位。每个被接受的样本更新一次。分层 128/64 虽仅使用 1/2 个随机位，**这个保守版本仍更新完整 32 位状态**，不能因此把 PRNG 电路功耗直接除以 8/4。
- `INTERNAL_RNG=0`：使用 `ext_random[7:0]`，输出 `rng_step` 通知外部源何时消耗一个数。外部应在 stall 时保持其状态；如果希望停顿时门限也完全稳定，应同时保持 ext_random。外部随机源能耗未计入这个综合 top。
- enum256 不实例化 PRNG，也不会发出 rng_step；rng_state 为 0。seed 对 enum256 无效。`MODE=1,LOG_T=8` 的 strat256 控制也等同于无随机抖动的完整枚举，同样不实例化/推进 PRNG；它不属于五种主模式的独立随机方案。

xorshift32 是可综合、可复现的面积/功耗代理。它的序列相关性、低位品质、跨组/跨层种子分配均须另外评估；**功能 RTL 不等价于 Llama/Qwen PPL 数值参考中的理想 IID/理想独立分层采样器**，更不证明它与模拟 tanh p-bit 的行为相同。

内部 PRNG 只保留正在运行的 32-bit state。`seed_in/rng_state` 是上游写入/读出接口，保存帧起始 seed 或 checkpoint 的 32-bit 上游保持状态不在 standalone top 内；整机需要按实际随机源组计入，不能为每个输出列重复计数。对多个输出波次重播同一组输入流，应在各帧边界装载相同初始 seed 并通过 start 重置帧计数。

64 路输入共享一个门限。本包的单列 `integrated *_rng` top 是独立 PE 表征，不表示 64 个输出列各要复制一个 PRNG。真实 64×64 tile 可对相同输入在多个输出列之间广播同一组二值比较结果，前端每个输入组计一次，后端每列计一次。应分别测共享前端和算术 body，再加入广播布线与负载，避免把单列 standalone 源成本重复乘 64。

## 4. 综合 top 与文件

`rtl/sc_ss_fixed_tops.sv` 给出五种模式各两种随机源方式：

- `sc_ss_iid4096_rng/ext`、`sc_ss_iid128_rng/ext`；
- `sc_ss_strat64_rng/ext`、`sc_ss_strat128_rng/ext`；
- `sc_ss_enum256_rng/ext`，两者都不含 PRNG；
- `sc_ss_sampler_<模式>_rng/ext`：只含采样前端、64 路比较器和帧控制，不含位平面/时间累加。
- `sc_ss_threshold_<模式>_rng/ext`：只含门限生成、帧控制和可选 PRNG；N1 恒零概率比较器输出未使用，综合时应被删除。
- `sc_ss_body_n64_acc27`：只含一列的固定权重符号/幅度转换、精确空间 popcount 和时间累加，输入已有的 bits，不含 PRNG、概率比较器或帧计数器。与 integrated 中的 `u_body` 是同一个 `sc_ss_exact_body` 模块。

`*_rng` 表示内置 PRNG，`*_ext` 表示外部随机数接口。所有 integrated top 均固定 N64、W8、A8、ACC27。

主文件：`rtl/sc_ss_sampler.sv`、`rtl/sc_ss_exact.sv`、`rtl/sc_ss_fixed_tops.sv`。功能 bench 为 `sim/tb_function.sv`，单 DUT 功耗激励为 `sim/tb_power.sv`，运行入口为 `sim/run_sim.py`。

## 5. 如何重跑

需要 Python 3 与 Icarus Verilog；工具二进制不进入 Git。Linux 如已安装 Icarus：

```sh
python3 sim/run_sim.py
python3 sim/run_sim.py --power --rng 1 --out results/power_local
python3 sim/run_sim.py --power --rng 1 --sampler-only --out results/power_sampler_local
python3 sim/prepare_active_vcd.py results/power_local
python3 sim/prepare_active_vcd.py results/power_sampler_local
```

Windows 可显式指定 `--iverilog <path> --vvp <path> --ivl-base <lib/ivl>`。脚本也能自动发现本地历史仿真工具目录，但不复制工具或工艺文件。

默认功能验证包括三种固定种子 `0x13579bdf/0x2468ace1/0xdeadbeef`、N1/N8/N64、内/外随机源和五个模式。每种配置测试 7 帧：逐拍门限、比较器位、signed W8 加权总和、样本计数、停顿、busy/start、seed_load/start 冲突、相同种子重播、下一帧 checkpoint 重播、0 种子规范化、256 枚举恒等。输入包含 q0/q1/q2/q26/q128/q255，权重含 -128/127/-1/0 与混合符号。

功耗激励的 `--cases 0 1 2 3 4` 分别是 q0、q1/2、小概率 q26、q128、边界混合。可用 `--presets`、`--rng`、`--seeds` 选择子集；种子支持 `0x` 前缀。相同 case 与 seed 在各模式下使用相同固定权重/概率/符号。

```sh
python3 sim/run_sim.py --power --presets strat128 enum256 --rng 1 --cases 1 --seeds 0x13579bdf
```

## 6. 送 PT 时看什么

时钟固定 100 MHz（周期 10 ns），不预设 DC/PT 一定能收敛。VCD 在 reset 与 seed_load 完成后才开始 dump；每个 VCD 只有一个 DUT、一个工作帧，窗口为 **1 个启动拍 + T 个有效拍**，没有夹入配置/seed 载入周期。对应 `*_window.json` 给出精确 `start_ns/end_ns/duration_ns`，帧耗时为 `(T+1)×10 ns`。不要拿不同帧长的平均功率直接当作任务能量比；任务能量为该窗口的能量积分或 `Pavg × duration`。

默认 integrated 活动层级为 `tb_power.integrated.dut`；sampler-only 为 `tb_power.sampler.dut`。只测算术 body 时可用 integrated 波形中的 `tb_power.integrated.dut.u_body`，源共享的前端则单独测一次。匹配不同综合层级时按实际 netlist 设置 strip path。测试平台中外部 PRNG 模型和时钟激励不属于 DUT，VCD 也只 dump DUT 层级，不能把整个 testbench 的切换数当作芯片功耗。

注意综合包装层的一级差别：若 PT design 是定型 `sc_ss_strat128_rng` 之类的 wrapper（内部实例名 dut），使用 `tb_power.integrated` 作为 strip path，保留相对的 dut；sampler 定型 wrapper 对应 `tb_power.sampler`。如果直接综合参数化的 `sc_ss_exact` / `sc_ss_sampler` 模块，则分别 strip 到 `tb_power.integrated.dut` / `tb_power.sampler.dut`。只测 body 的最直接做法是以默认 N64/ACC27 的 `sc_ss_exact_body` 为 top，strip 到 `tb_power.integrated.dut.u_body`。不要拿一种包装层的 strip path 套到另一种层次上后忽略 annotation coverage。

送活动窗口前先运行 `prepare_active_vcd.py`。它保留原始 VCD，生成 `*_active.vcd`，把第一个时间戳平移到 0，最后一个时间戳等于 `(T+1)×10 ns`；删除仅在最后截止点由 `$dumpoff` 自动产生的 X 块，并拒绝任何窗口内部 X/Z。`active_vcd_manifest.json` 同时记录原始/平移后 SHA-256、时间平移量和实际窗口。PT 使用 active VCD，按该窗口截止；门级仿真波形也应作相同裁剪、归零和检查。RTL VCD 不证明门级全网表注释覆盖率，缺少门级内部网切换时 PT 的 propagation/vectorless 补充必须单列说明。

建议同一工艺角/电压/温度、相同输入输出负载、相同面积/时序约束，报告：cell area、seq/comb area、critical path/是否满足 10 ns、internal/switching/leakage power、clock pin/clock tree 是否计入、VCD annotation coverage、sample/frame energy。分别跑内置源与外部源、集成体与采样前端；缩位版本独立成表。没有真实 SRAM 时不将 SRAM 面积/漏电填 0 后声称整机结果。

本包生成的 VCD 只是合成输入活动，不是 PT 功耗结果；大 VCD/VVP 不进 Git。`results/` 的已归档 JSON 仅证明本次实际功能仿真与波形生成。
