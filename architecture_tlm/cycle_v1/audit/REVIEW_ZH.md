# Issue 116 独立正确性审查

审查代理不负责 kernel、FFN、Attention 或 layer 的实现。检查依据为用户提供的周期深化方案、`audit/ACCEPTANCE_ZH.md`、已有 v6/native RNG 协议和原始 W8 位平面 RTL。自有 `cycle`/`event` 两种循环共享执行核，因此它们的相等只作为回归检查，不能代替独立 oracle 或 RTL 验证。

本稿状态：**所列实现范围内的独立验收已完成，未发现尚未修复的 P0 反例**。这不表示整份深化方案、完整模型或物理硬件已经完成。固定范围为 core `d4f08a1`/`5a6078f`、native operators `a751442`/`9b69c64`、FFN `da24266`/`93c26d9`、Attention `0597d06`/`e2695e2`、layer `cd27d98`/`c5f9a20`。以结果文件中的源码 SHA-256 为准；各工作树 cherry-pick 后 Git 提交 ID 可以不同。

## 当前结论与实测范围

- 已独立通过 **54 个测试方法**：core 20、FFN 13、Attention 14、native 2、layer 5；其中包含 32 个随机跨域 DAG、32 个随机重叠字节内存案例、4 组 B/T/K 数值配置、2,043 个 Q256 查表中心/半边界/饱和点。
- 核心时序由手工推导的接受沿、完成沿、II、完成端口和保守释放约束检查；内存值由独立字节数组按程序序核验。单纯“两个循环输出相同”不计作独立时序 oracle。
- FFN 标量 oracle 不导入生产 encoder、PRNG、sample accumulator、restore 或 reference 函数；从冻结门限统计每输入 lane 的命中数，再按约定 FP32 边界还原，核对 gate/up/z/projected/output。
- 真实 Qwen fixture 的 layer 0、12、23 各执行 **4,725 个** native FFN 操作，上述五个数组均与独立 oracle **逐位相等**。这些是完整 896 输入维、裁剪 70 intermediate / 16 output 的 FFN，不能称完整 Qwen 层、完整模型质量或 PPL 结果。native 门限来自实际服务返回，再冻结给独立数学 oracle。
- native 混合 LFSR/Bivium、响应保持、长空闲、锁定下到期重播种、SAVE/RESTORE/RELEASE，与未加速的原始 `RandomNetwork` 逐沿重放核对输出、全部端口计数、seed transcript、内部 state/age/epoch。另检查 257 hidden 的 FFN 超过 8 引擎后重放同一组门限：112 个实际源帧对应 240 个 SC tile 帧，而非错误地把每个 tile 当作一个新随机字。
- reduced layer 采用 2 维 identity QKVO、单当前 token、position 0，前半段有闭式答案，后半段接独立 FFN oracle。只改实际 SRAM 输入而保留原 fixture 时，全链数值随真实字节改变；改变内存延迟只改完成时间。所有额度归还，动态初始化遵守 producer 到 memory 的 3 目的沿 CDC。
- 17 项 EXP 在 16 lane / 1 lane 下分别服务 9 / 24 个配置周期；数字 Softmax 只有一个 reciprocal，阶段依赖隔沿生效。PV 的 2 项 CDF 构造占 2 周期、4 样本扫描占 6 周期。21 个逻辑 source lane 使用 40 个 native lane 时，生成/使用/padding 计数单独守恒。layer 单 bank、window=1 仍保留相同结果并增大完成时间。

对应保存结果为 `results/restoration_da24266/RESULT.json` 和 `results/real_layer{0,12,23}_native_da24266.json`。测试源码后续新增时必须重跑，不能把这份回执的通过数自动推广到新增代码。三个真实片段回执包含 native 随机服务报告、实际门限 hash 和完整本地运行依赖的源码 hash。

后续固定 `e2695e2` / `93c26d9` 的完整 **54 项**回执为 `results/prefetch_profile_08f3c48/RESULT.json`。新增检查不是沿用原 50 项结论：实际重跑全部独立测试，包括 V 预取死锁和两个恢复 profile。逐 bin oracle 改用 `Fraction` 精确有理数及整数 ties-to-even FP32 舍入，260 组正负/normal/subnormal 输入逐位符合两种公开舍入契约；另对正常和 tiny 输入、两个 profile 的多 bin / 跨 tile 完整 FFN，核对两模式和五个数值边界。

`integer=3, activation_scale=2^-145, T=32, weight_scale=1.5` 明确产生 host `0x00000002`、`rtl_fused0_order` `0x00000003`。该逐 bin 反例不等于当前 encoder 会生成该 scale；encoder 的低档最小 normal clamp 仍是独立契约。profile 只改变恢复舍入顺序，不构成整套 encoder/SiLU/异常处理/FFN RTL bit-true 声明。

## 审查发现及修复闭环

| 问题 | 反例 / 影响 | 已核验状态 |
|---|---|---|
| FFN 数据最初绕过内存 | 输入/权重由 fixture 直接提供，partial write 无实际 payload | 已改成严格实际字节链；破坏权重 payload 必须影响数值或显式报错 |
| 流水缺少有限完成带宽 | 长堵塞解除后 3 个结果在同沿瞬间清空 | 加完成端口/输出 II；独立断言每沿最多一个默认结果 |
| 默认流水允许越过旧操作 | 后来的短 latency 或另一输出队列可越过旧堵塞项 | 默认 per-instance in-order；显式 OOO 才允许越过 |
| 事件模式漏 stall 变化 | CDC 可见性到期或第一个 bank 解锁时，被更晚的另一个 bank 可用时间遮住 | 两个最小反例及 32 随机内存案例通过，完整解释轨迹一致 |
| 位平面映射与原 RTL 不符 | abs(W) + sign(xW) 数学相同，却改变原 input-sign rail 与 W8 二补码位权 | 已改；x=-1,W=-1 的 negative input rail 八个位均计数 2048，而非只计 magnitude bit0 |
| Attention 动态控制部分免费 | winner 的 active rank 选择、提议决定未经过显式阶段 | 已加 rank-select 与 decision 阶段，fair 越界重试无 modulo fallback |
| 量化 adaptive rejection 错称 IID | Q256 阈值量化与 shift 自适应没有对应独立性证明 | provenance 已改，不继承精确 softmax 或模型 PPL |
| 工作集保留少计 | g/u/z/residual、Q/probability/drive/history 等状态没有完整字节边界 | 增加本地状态明细；全局 backing memory 仍明确未分配 |
| layer 动态初始化绕过 CDC | callback 创建的 memory write 没有 producer dependency，默认 cdc=0 | 已加 producer deps + 3 目的沿，独立最早受理时间断言通过 |
| PV 在随机回调内免费扫描 | CDF 构造和全部样本位置在 RNG delivery 回调一次性计算 | 加独立 CDF build/scan 及有限 index scratch，手推周期通过 |
| tiny FP32 的倒数中间溢出 | `[1e-38,-1e-39,0]` 本应有有限 A8 编码，却因 FP32(256/scale) 溢出 | 改用 PoT 指数缩放；最小 subnormal、正常 tiny、最大允许 scale 测试通过；显式拒绝 group max > 2^127 |
| encoder 原始输入驻留少计 | 64 lane 的 FP32 输入为 256B，只保留 196B 编码状态额度 | 原地复用取 raw/encoded 最大值；196B 容量不能接受 256B 输入 |
| restore 作为一个定长宏操作 | 不同位平面/行数的还原缺少有限算术 lane 和中间态 | 已拆 rail subtract、三级 plane tree、每 bin 有序 FP32 restore、跨 tile add；有限 scratch 先预留，最后阶段才释放 counters；16/1 lane 时延和数值通过 |
| V 额度与顺序消费形成死锁 | sparse ID 1/2/10 按字符串读仲裁，使后面的 V 占满额度，物理数字顺序中前面的 accumulator 无 V 可消费 | 改为消费前沿的有限窗口；3 种 candidate 顺序 × exact/PV × 两模式、仅 1 slot 全通过；2 slots 加真实乱序返回也通过，未退化为强制顺序返回 |
| 默认 host 恢复被误当原 RTL 顺序 | 次正规边界先除 T 再 FP32 与先 FP32 再乘权重/除 T 可相差 1 ulp | 显式 host_order / rtl_fused0_order；独立精确有理数 oracle 及已知十六进制反例通过 |

上述修复均在固定版本上重新运行独立反例。完整生产矩阵、最终运行器和外部工具回执由主代理另附；本报告不把未列出的检查继承为已通过。

## 不能由这些结果推出的结论

1. `cycle_v1` 是有明确有限资源契约的周期模型。配置 latency/II 不是 STA 结果；`energy.status=unknown` 保留未知，总功率/面积/能耗没有由动作数臆造。旧 PPA 只能在其原映射和边界下引用。`memory.*` 与前端语义动作有重叠，不能直接求和收费；free-credit buffer 的 token 高水位不是已用容量峰值，应同拍聚合 trace 后计算 `capacity-min_free`。
2. MemoryPort 按地址、line、bank、端口和有限 window 建模并返回真实字节；它不是已校准 DDR/HBM controller。全局 SRAM/DRAM 地址空间没有总容量 allocator，不能声称整层/整模型 SRAM 闭合。
   FFN 的 32KiB weight credits 表示 DMA admission 到 restore 的单份逻辑所有权。有限 SRAM `weight_local_read` 已按 line/bank/port/II 服务，此后 T 次 SC 采样假设整 tile 静态驻留、并行可见；Python resident list 并不能证明已实现阵列侧宽读口。若物理方案采用独立 SRAM staging 和阵列保持，应分别实现容量、装载端口和生存期；当前额度不能同时证明两份物理存储均已计入。
3. NativeRandomService 使用已有 native 协议和确定性 seed fixture；不代表物理熵。layer 中 Attention 与 FFN 各自创建 source network / seed bus，当前未验证全层统一随机网络共享与竞争。
4. `clock_process` 是隔离 FSM 的扩展接口；本轮 adapter 仅从提交后 operation callback 接收请求。任意第三方 callback 直接读写其他进程的可变状态，不自动获得双阶段 old-state 语义保证。
5. Attention 查询从已投影、已 RoPE 的 Q/K 开始；显式候选列表不等于已实现真实 selector。reduced layer 为单头、全候选、合成尺寸。后续独立 GQA group 已实现共享一个 KV head，见下节；它尚未接入 reduced layer 或完整 Qwen/Llama decoder，不包括 24/32 层质量验证。
6. 数学契约包含 double fsum/softmax 或连续 SiLU 配合已声明 FP32 边界；它不是全算子固定点或流水 RTL 的 bit-true 数学声明。
7. 外部框架构建/小例、合成握手 RTL 和已有局部算术 RTL 各有独立覆盖范围。主代理将另附回执；它们不能自动证明完整 SC 数据通路、真实 CDC 电路、物理时序或 DRAM 闭环。

旧 v6 与 random_service 源码相对本任务基线未改。主代理另行运行三个旧 v6 测试模块共 43 项通过；其日志需由主代理附入最终证据，不并入本审查代理的独立测试数量。

## 外部 ONNXim 回执复核

固定提交 `e3972ac` 已在独立审查工作树读取 C++ 探针与全部四个逐请求 JSON，并运行离线 `external/onnxim/verify_results.py`。12 个服务器原始文件的 SHA-256、实际编译探针源码 hash、Slurm 2772 首次终态 `COMPLETED / 0:0` 和官方两例/自定义一例通过日志一致。拒收时 ID 4 / 地址 0x1020 保持 10 拍，随后受理并返回；乱序例实际返回 0x1020 再 0x1000。COMP 处理 64 bytes 时，64/32 bit 数据宽度分别占 8/16 active cycles，完成时间由 17 增至 25 cycles。

这确认了真实 native Operation / Tile / Core 指令路径、有效性依赖、外部窗口和请求 ID 控制。探针内存返回不携带数值，因此不验证随机门限、矩阵/FFN 数学；它也未执行原生 DRAM 命令后端、完整 ONNX graph 自定义节点、全模型，或与 cycle_v1 做逐周期等价比较。ONNXim 允许同沿返回后再受理，在 bounded trace 的 cycle 12 可以直接看到；不能把这组总周期与严格 old-state 的 cycle_v1 直接相减解释为速度差异。

## 独立 RTL 协议回执复核

审查了 `2d3ad89` / `9dcc6ac` 的四个 SV 文件、比较器和逐例 stdout。SV 使用倒计数、环形指针和两级 toggle 同步寄存器独立计算握手，testbench 读取实际 pre-edge ready/valid，未从 Python 预期事件驱动 SV ready 或输出。流水测试覆盖固定参数组合下的有限 in-flight、有限 FIFO、输出 II 和回压；mailbox 测试覆盖四种 100/80 MHz 相位关系，payload 为 token ID。

`verify_rtl_evidence.py` 在审查工作树重新解析原始 stdout、重新运行当前 kernel 期望，核对 **9 例 / 252 个握手**；原始 archive 及其 **93 个制品**和 **8 个执行源文件**散列均一致。回执为 `results/rtl_offline_review.json`。这是对 Slurm 2764 / Icarus 12.0 原始执行证据的独立离线复核，没有声称本机重新执行 RTL。

双同步触发器加按旧状态读取的同步消费者确实对应第三目的沿可见；反向信用也保持三个源沿的使用约束。该结果只验证数字协议，不覆盖真实 SC 位流、算术流水、内存乱序 controller RTL、亚稳态/MTBF、综合、STA 或电路功耗。协议 RTL 与源代码 checker 的相等不能扩大为整算子硬件验证。

## Reduced layer 运行器与制品复核

只读检查 `run_layer.py` 和 `results/reduced_layer_20261023` 的 7 个成功场景、2 个容量拒绝场景。运行器明确将内部复用 primitive 的计算称为功能回归，独立闭式/标量证明另见上述测试。exact / PV / winner / rejection 各自比较完整 cycle/event payload；单 bank/window、慢内存、刚好 768B layer state 的 exact 输出 hash 与默认相等。767B working state 和 9 候选容量分别因预期的工作存储/10 候选越界拒绝。

`verify_layer_artifacts.py` 重新解压全部 7 份原始 trace，核对唯一操作 ID、全部接受/完成集合与时间、实际 memory 字节/请求数、逐拍汇总后的额度范围/归还/已用峰值、BF16 输出 hash 和压缩 trace hash。全数通过，回执为 `results/reduced_layer_artifact_review.json`。当前 exact 为 728 操作 / 24,850 ns，单 bank/window 为 28,110 ns，慢内存为 27,510 ns；这些只反映已配置的缩小合成架构，不是完整模型性能或硬件预测精度。

## 最终真实矩阵的独立离线核验

Slurm **2776** 的固定 v5 结果包含 **68 个真实片段配置和 8 个 synthetic smoke**，本审查独立枚举 B/T/K、seed、layer、mode、N128/N512 和 S32/S512 的期望组合，核对全部 case 身份及有效配置。解包后的 **302 项制品**逐字节数量/SHA-256 通过；实际 source archive 的 **64 个源文件**逐项对照 execution manifest，再绑定各结果运行时记录的源码闭包。源 archive SHA 为 `f6c596f3d772dee19bea1d85badb25fe0088aefaaae70ab959555b68daf96cbf`，结果 archive SHA 为 `82319f0d95054149e7d3dbeba5248648d461fe91539107aaa85e83fd44429ee5`。

有完整 trace 的 **34 个配置 / 403,583 个事件 / 98,340 个操作**由独立程序重放：核对唯一 accept/complete、时钟沿、每拍旧态容量和信用、有限资源完成端、memory window/bank issue port、每项语义及物理 memory action、resource held/execution/blocked 汇总与容量使用峰值。另直接从私有 fixture 重建初始 FP32 Q/K/V/x/residual 与 signed W8/FP32 scale bytes，核对 **4,597 项实际 read hash**；不借用生产模拟器的 pack/matrix/算术 helper。

全部 76 配置的输出存储 hash、sample multiplicity/unique V/真实地址/字节、native seed/端口/事务报告、credits 与 `unknown` PPA 边界通过。未保存 trace 的 42 配置只有 summary/manifest/配置/数值门限回执层复核，不伪装为完整 trace 重放。矩阵数值 `pass` 和容差被核作**运行器回执**；本次离线核验没有重新计算全部 76 配置的数学答案。独立数学证据仍是三个真实裁剪 FFN 标量 oracle 和上述 54 项测试。

完整新回执与可重现程序为 `results/matrix_v5_offline_review_final.json` 和 `verify_matrix_artifacts.py`。旧 Slurm 2775 的 62 pass / 6 deadlock 应保留为修复来源；不能与本轮 68/68 结果混算。

## v6 可执行桥复核

固定执行版本 `d0ccc5e`、五例回执提交 `b741427` 的 FFN/exact/PV/winner/rejection 经过独立离线复核：**47 个制品、38 个源依赖**散列匹配，五份完整周期 trace 的 actions、旧态容量、资源和 bank/completion 端口守恒通过。源码按执行 Git SHA 核验；仅当 LF/CRLF checkout 变体的 SHA 与原记录精确相同时接受，未把后续 package_snapshot 变更误当旧执行版本。

桥只调用旧 FullDecode 的算子方法，旧 FFN 没有权重数值输出；screen 模式已给候选后才进入桥。已明确旧桥 QK 逐乘/逐加 FP32 与 cycle 的 double fsum 后 FP32 可以产生不同 logits，加上不同 source 端点/请求时刻，不构成样本、数值、周期或加速比等价。`speedup=null` 正确保留；桥拒绝 cropped FFN、GQA、多时钟/native 不兼容和无法忠实映射的 II，不声称完整 decoder 已迁移。回执为 `results/v6_bridge_offline_review_final.json`。

## 后续 GQA group 独立验收

固定生产 `0cd8a26` / `de6123d` / `f94c9db` 新增同一 Kernel 中多个 query 共享一个 KV head。独立测试增加 **16 项**，全部 **70 项**在审查工作树 `a47fd64` 对应源码上重新通过，回执为 `results/gqa_a47fd64/RESULT.json`。历史 54 项回执和 Slurm 2776 的 68 real / 8 smoke 矩阵保持原样，没有用新增功能的通过数改写历史执行。

小 fixture 的两组稀疏候选为 `[1,2,10]`、`[10,3,2]`；手工确定 K union 为四行，PV 每 head 六次保留样本时各候选重复两次。exact、PV、winner hold、rejection 失败重试由独立 scalar/冻结轨迹计算每 head 答案，逐项 FP32 乘加采用物理 token 升序。除已知相等 logits 外，还核对不同非零 Q 的非均匀 softmax。K/V 各一个行槽、memory window/bank 为 1，以及一个 operand slot 均完成，所有信用归还；两槽实际乱序回复不导致先消费数据饥饿。每条共享读的实际地址、字节、全部 consumer、最后释放依赖及输出 SRAM bytes 均被检查，破坏实际 K/V payload 必须显式失败。

本轮审查发现并推动修复两个新 P1：运行时 V union 原先只在 Python set/sort 中完成，没有有限吞吐；cache read 完成后到 MAC 消费前没有有限 operand holding。现有独立手算验收为：两 head、四 union 项需要 **136B** metadata，136B 接受 / 135B 拒绝；六候选 scan 和四项 compact 在 1 lane 时分别为 6 / 4 周期，在 16 lanes 时分别为 1 / 1 周期。V 读不得提前于 compact 完成，metadata 保留至所有输出写回与行释放。一个 operand slot 从 cache read 受理至对应 MAC 完成持续占用，不能同沿复用。共享资源的 lane 数和物理 latency 不一致时明确拒绝。

12 head 的动态地址布局保持 Q/histogram/output 互不重叠；不同 head 的 source network/seed bus 明确为独立实例，而非同一全局随机网络。原始 K 候选 union 是给定输入的预编译计划，V 是有限 scanner 上的运行时 union。source 内部 state 与 cache/SRAM 宏仍没有物理 PPA/STA 证据，模型没有接入 QKV 投影、RoPE、selector、Wo、动态 KV append 或完整 decoder。

默认 Attention 路径的回归另用原始 v5 冻结结果检查：真实 layer23 的 exact seed0、PV/winner/rejection seed2，共 **4 case / 8 次 cycle/event 执行**的完整 payload SHA、输出、采样历史和信用均与原结果一致；包括原先发生死锁的 PV seed2。第一版及最终 operand hook 修改分别保存 `results/gqa_default_attention_1122365.json` 和 `results/gqa_default_attention_a47fd64.json`。这是代表 case 的完整执行回归，不宣称重新执行了全部 68 real 配置。

`verify_gqa_fixture.py` 为服务器内私有真实激活验收入口，已经用公开合成小 fixture 跑通 6 case × 两模式整入口。脚本独立核算 QK 与 FP32 weighted-V、实际共享字节、union/consumer 生存期及完整 trace 的动作/旧态容量；sampled 数值核验条件于实际 native 保留索引，不把这项检查冒称独立分布/IID 证明。公共回执仅含配置、hash、误差、计数和时间；张量、输出数组、直方图、索引、native transcript 和完整 trace 留在服务器私有目录。真实 7-head fixture 的执行状态以随后固定的服务器回执为准，本段不预告通过。

## 重现

```powershell
python -X utf8 -m architecture_tlm.cycle_v1.audit.run_audit --output <新的结果目录>
python -X utf8 -m architecture_tlm.cycle_v1.audit.verify_real_fixture --backend native --fixture <私有fixture.json> --output <新的数值报告.json>
```

报告与 runner 都拒绝覆盖已有回执。共享制品只需测试、SHA-256、配置、数值比较和来源索引；不要把模型权重或私有 tensor fixture 加入 Git。
