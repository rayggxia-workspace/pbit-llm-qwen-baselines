# cycle_v1 FFN 契约

实现入口为 `ffn.py`，本文核对 `da24266` 的阶段实现及后续显式 restore_rounding 扩展。默认保持 da24266 数值顺序。这是配置驱动的周期模型；延迟、II、算术共享方式和并行数组是假设，尚未做完整算术 RTL、STA、工艺 PPA 或完整 Qwen PPL 验证。已有裁剪 fixture 的通过不代表完整层通过。

## 数值与输入边界

`build_ffn(kernel, fixture, config)` 返回随执行更新的状态；`make_kernel(config)` 创建对应资源和容量。fixture 包含 `x`、`wg`、`wu`、`wd` 和可选 `residual`。矩阵为原始二维数据，或 `{"codes": [...], "scales": [...]}`；后者每个原始 64×64 tile 一项 FP32 scale，codes 允许 −128..127。裁剪真实权重时先量化原完整 tile，再保留其 scale，不能对裁剪行重新量化。所有矩阵输入维必须完整相接，不做隐式截断。

默认 W8/B4/T32/K32；B2、T16/K16、T64/K64 为显式配置。A8 门限编码按 64 个值分组，较低幅度档的 scale 以 1/4 递减，并保留 minimum-normal 下限。输入先转 FP32；组最大值必须 ≤2^127，因为更大的 ceil-PoT scale 不能存为 FP32。指数缩放支持 tiny/subnormal 输入，避免 `256/scale` 中间溢出。`q` 为 0..255；独立 full-one 标志使概率 1 不退化成 255/256。NaN、Inf、不可表示的输入或中间运算不构成有效输出。

默认 counter 对应原 RTL 的 **B 档 × 2 个输入符号 rail × 8 个 W8 二补码位平面 × 输出行**。bit7 权重为 −128；输入符号单独决定 rail。不是 `abs(W)` 的符号幅度重编码。T32 的 64 输入最大单计数为 2048，需要 12 bit；最大还原整数为 +262144。`signed_bin` 是独立替代布局，不继承原布局 PPA。

每个采样步由实际位平面门控更新整数计数。恢复按档完成 `FP32(count × activation_scale)`，再对 `× weight_scale / T` 表达式舍入为 FP32；按档顺序和跨输入 tile 顺序分别进行 FP32 加法。所有 gate/up 输入 tile 完成后才执行 `FP32(FP32(g × FP32(sigmoid(g))) × u)`，继而独立编码 z、计算 down。默认先把 down 转 BF16，与 FP32 residual 相加后再次转 BF16。此处 sigmoid、第二级缩放表达式是功能数学模型；不能据此声称具体 FP32 RTL 除法器或 SiLU 电路已实现。

**本数值顺序不等于 `digital_ppa_v1/rtl/nr_bin_restore.sv` 的 FUSED=0 位精确契约。** 当前 cycle_v1 使用 `FP32(FP32(integer*scale)*weight_scale/T)`；该 RTL 先做 `FP32(integer*scale/T)`，再乘 weight_scale 并舍入。可复现反例为 integer=3、scale=2^-145、T=32、weight_scale=1.5：本模型得到 FP32 bits `0x00000002`，RTL 的分步数学得到 `0x00000003`。normal-range 真实 fixture 与本模型 oracle 逐 bit 一致，只证明当前契约内部一致；不能覆盖次正规边界或声称与该 RTL 全域等价。正在运行的矩阵继续沿用固定契约，不静默更改舍入顺序。

`FFNConfig.restore_rounding="host_order"` 为上述默认顺序。显式 `"rtl_fused0_order"` 改为先 `FP32(integer*scale/T)`、再 `FP32(*weight_scale)`，并保留有序档累加；该 profile 要求 T 为 2 的幂。两者均记录 provenance，`reference_ffn_tiled` 使用对应独立分支。此 profile **只匹配恢复顺序**：编码器 lower-bin minimum-normal clamp、功能 SiLU、异常/溢出处理、全 FFN 与具体 RTL 的等价性均不在该名称的保证范围内。已有 v3 主矩阵不被替换，新的 profile 配对必须另列结果。所有恢复中间值必须在支持的有限 FP32 域内。

## 资源、延迟与动作

以下 `R` 为当前输出行数，`C` 为当前输入数，`B` 为档数，`L=vector_lanes` 默认 16。普通计算主时钟 100 MHz，DRAM/SRAM 端口 80 MHz；跨域依赖默认完成后的第 3 个目的沿可接受，对应两级同步器加读旧状态的消费者。内存地址、bank、请求窗口和返回依赖由统一内核处理。

| 阶段 | 实际动作与共享假设 | 默认时序 |
|---|---|---|
| 编码 | 一组最多 64 lane 并行绝对值、max tree、B 档选择、指数网格转换 | 配置 `encode_latency=7`，一组前端，不是 16 lane 串行编码器 |
| 随机源 | 现有 LFSR32 原生 seed、warmup、ready/valid、hold、SAVE/RESTORE/RELEASE；同组各 tile/wave 重放同轨迹 | 实际 source clock process，另计 1 拍 submit、1 拍 delivery 及无同沿直通依赖 |
| 门限前端 | 每步 low bits 提取、stratum 选择、C 个激活比较、向当前 wave 分发 | `rng_latency=1`，与原生 PRNG 动作分账 |
| SC 阵列 | 每 engine 64×64 W8 并行门控、按档/符号/位平面的 popcount 与计数更新 | `sc_latency=1` 为未表征的并行数组契约；每 tile 每步记录 RC trials、16RB 个 clocked counter slots |
| rail 恢复 | 16RB 个 counter reads，8RB 个 rail subtraction 和位置移位 | `batches=ceil(8RB/L)` |
| 位平面归约 | 三个严格相依的整数树级，分别 4RB、2RB、RB 个加法 | 每级独立 `batches=ceil(work/L)`，不能把树免费折入回调 |
| 档恢复 | 每档 R 个整数/scaling、weight_scale/T 功能归一化及 FP32 subtotal 更新 | B 个严格相依阶段，各 `batches=ceil(R/L)` |
| 跨 tile 恢复 | R 个 FP32 加法，与该输出 tile 上一次真实 partial read 相依 | `batches=ceil(R/L)` |
| SiLU 与乘积 | 共享 L lane 的功能算术流水线 | `nonlinear_latency + ceil(F/L) − 1`，II=`ceil(F/L)` |
| BF16/residual | L lane 转换与相加；BF16 开启时两次转换各计 O 次 | `2 + ceil(O/L) − 1`，II=`ceil(O/L)` |

所有 restore 阶段共享一个资源。每阶段 `latency=restore_latency+batches−1`、`II=batches`，默认 restore pipeline 为 4 拍；资源默认只能持有 2 项、每拍完成 1 项。whole-batch 提交是保守的块级流水抽象，不能据此宣称已验证细粒度逐 lane forwarding。计数清零是并行清零控制动作，不是假设逐字 SRAM 写循环。

## 有限存储与真实字节依赖

| 默认本地容量 | 字节 | 含义 |
|---|---:|---|
| W8 payload | 32768 | 8×4096B slot，scale 不混入其中 |
| scale metadata | 32 | 8 个 FP32 tile scale |
| counters | 49152 | B4/T32 的 8 个 6144B tile；T64 自动降低同 wave 并行 tile 数 |
| raw/encoded group | 256 | `max(4C,3C+4)`；编码后原地覆盖原 FP32 输入 |
| g/u/z/down/residual | 65536 | 保守同时分配 `(3F+2O)*4`，没有隐式借用 g/u 存 z |
| restore scratch | 8192 | 每 tile 3R 个 FP32 值及小 T 的额外整数位增长；partial read 接受前预留，最终跨 tile add 后释放 |

counter banks 逐阶段原地覆盖为 signed positional terms，再覆盖为归约整数。可用 bit 容量不足时，超出的位增长计入 restore scratch。输出转换持有原 down/residual reservation，直到实际输出写完成；源码中为审计保留的历史数组、thresholds、receipts 与 trace 不作为额外硬件副本收费。

W8 与 scale 来自实际 DRAM read；fill 和本地 read 按真实地址执行并逐字节校验，解析出的数据供计算使用。输入、跨 tile partial 与 residual 真实回读；partial、z、最终 BF16/FP32 输出写出实际 bytes。损坏输入/权重会被校验捕获，partial 回读数据直接参与下一阶段算术。

这里封闭的是本地容量与端口/依赖约束；**全局 backing SRAM/DRAM 地址空间没有总容量分配器**，不能把上述表称为完整 SoC SRAM 容量。`RunResult.buffer_peak` 是 token 高水位；这些容量采用 free-credit buffer，因此其初值就是 capacity，不能把该字段直接称为实际已用峰值。实际已用峰值须从同拍输入/输出 credit 更新重放计算。

## 随机源与验证

默认 `random_backend="native"` 接 unchanged Issue95 原生协议的 LFSR32。确定性 fixture seed 是测试材料，不是物理熵，也不证明 IID。源在 request 间 idle 时仍按绝对时钟推进年龄、seed transport 与 reseed；原生账本单独给出实际动作。`behavioral` 才使用 Python Random，`replay` 必须有显式冻结轨迹。

原生输出的数值 oracle 应调用 `replay_fixture(fixture, state)` 冻结**实际已消费**的门限，再交给 `reference_ffn_tiled`。它使用独立 count-compressed 路径，在相同 FP32 边界逐 bit 对照。`reference_ffn` 使用较高精度全投影归约，仅作容差比较。周期与事件模式比较完整调度 payload；T16/32/64、尾 tile、原位负权重、true-one、跨 tile 非线性屏障、有限容量和阻塞均有测试。

完整 896→4864→896 的静态规模与局部实测详见 `work/amlink1219/116/FFN_SCALE_ASSESSMENT.md`；那些局部墙时不能冒充完整层性能结果。
