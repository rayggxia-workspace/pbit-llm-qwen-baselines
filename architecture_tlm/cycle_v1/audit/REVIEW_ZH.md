# Issue 116 独立正确性审查

审查代理不负责 kernel、FFN、Attention 或 layer 的实现。检查依据为用户提供的周期深化方案、`audit/ACCEPTANCE_ZH.md`、已有 v6/native RNG 协议和原始 W8 位平面 RTL。自有 `cycle`/`event` 两种循环共享执行核，因此它们的相等只作为回归检查，不能代替独立 oracle 或 RTL 验证。

本稿状态：**所列实现范围内的独立验收已完成，未发现尚未修复的 P0 反例**。这不表示整份深化方案、完整模型或物理硬件已经完成。最终固定范围为 core `d4f08a1`/`5a6078f`、native operators `a751442`/`9b69c64`、FFN `da24266`、Attention `0597d06`、layer `cd27d98`/`c5f9a20`。以结果文件中的源码 SHA-256 为准；各工作树 cherry-pick 后 Git 提交 ID 可以不同。

## 当前结论与实测范围

- 已独立通过 **50 个测试方法**：core 20、FFN 11、Attention 12、native 2、layer 5；其中包含 32 个随机跨域 DAG、32 个随机重叠字节内存案例、4 组 B/T/K 数值配置、2,043 个 Q256 查表中心/半边界/饱和点。
- 核心时序由手工推导的接受沿、完成沿、II、完成端口和保守释放约束检查；内存值由独立字节数组按程序序核验。单纯“两个循环输出相同”不计作独立时序 oracle。
- FFN 标量 oracle 不导入生产 encoder、PRNG、sample accumulator、restore 或 reference 函数；从冻结门限统计每输入 lane 的命中数，再按约定 FP32 边界还原，核对 gate/up/z/projected/output。
- 真实 Qwen fixture 的 layer 0、12、23 各执行 **4,725 个** native FFN 操作，上述五个数组均与独立 oracle **逐位相等**。这些是完整 896 输入维、裁剪 70 intermediate / 16 output 的 FFN，不能称完整 Qwen 层、完整模型质量或 PPL 结果。native 门限来自实际服务返回，再冻结给独立数学 oracle。
- native 混合 LFSR/Bivium、响应保持、长空闲、锁定下到期重播种、SAVE/RESTORE/RELEASE，与未加速的原始 `RandomNetwork` 逐沿重放核对输出、全部端口计数、seed transcript、内部 state/age/epoch。另检查 257 hidden 的 FFN 超过 8 引擎后重放同一组门限：112 个实际源帧对应 240 个 SC tile 帧，而非错误地把每个 tile 当作一个新随机字。
- reduced layer 采用 2 维 identity QKVO、单当前 token、position 0，前半段有闭式答案，后半段接独立 FFN oracle。只改实际 SRAM 输入而保留原 fixture 时，全链数值随真实字节改变；改变内存延迟只改完成时间。所有额度归还，动态初始化遵守 producer 到 memory 的 3 目的沿 CDC。
- 17 项 EXP 在 16 lane / 1 lane 下分别服务 9 / 24 个配置周期；数字 Softmax 只有一个 reciprocal，阶段依赖隔沿生效。PV 的 2 项 CDF 构造占 2 周期、4 样本扫描占 6 周期。21 个逻辑 source lane 使用 40 个 native lane 时，生成/使用/padding 计数单独守恒。layer 单 bank、window=1 仍保留相同结果并增大完成时间。

对应保存结果为 `results/restoration_da24266/RESULT.json` 和 `results/real_layer{0,12,23}_native_da24266.json`。测试源码后续新增时必须重跑，不能把这份回执的通过数自动推广到新增代码。三个真实片段回执包含 native 随机服务报告、实际门限 hash 和完整本地运行依赖的源码 hash。

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

上述修复均在固定版本上重新运行独立反例。完整生产矩阵、最终运行器和外部工具回执由主代理另附；本报告不把未列出的检查继承为已通过。

## 不能由这些结果推出的结论

1. `cycle_v1` 是有明确有限资源契约的周期模型。配置 latency/II 不是 STA 结果；`energy.status=unknown` 保留未知，总功率/面积/能耗没有由动作数臆造。旧 PPA 只能在其原映射和边界下引用。`memory.*` 与前端语义动作有重叠，不能直接求和收费；free-credit buffer 的 token 高水位不是已用容量峰值，应同拍聚合 trace 后计算 `capacity-min_free`。
2. MemoryPort 按地址、line、bank、端口和有限 window 建模并返回真实字节；它不是已校准 DDR/HBM controller。全局 SRAM/DRAM 地址空间没有总容量 allocator，不能声称整层/整模型 SRAM 闭合。
3. NativeRandomService 使用已有 native 协议和确定性 seed fixture；不代表物理熵。layer 中 Attention 与 FFN 各自创建 source network / seed bus，当前未验证全层统一随机网络共享与竞争。
4. `clock_process` 是隔离 FSM 的扩展接口；本轮 adapter 仅从提交后 operation callback 接收请求。任意第三方 callback 直接读写其他进程的可变状态，不自动获得双阶段 old-state 语义保证。
5. Attention 查询从已投影、已 RoPE 的 Q/K 开始；显式候选列表不等于已实现真实 selector。reduced layer 为单头、全候选、合成尺寸，不包括完整 Qwen/Llama 多头/GQA、24/32 层质量验证。
6. 数学契约包含 double fsum/softmax 或连续 SiLU 配合已声明 FP32 边界；它不是全算子固定点或流水 RTL 的 bit-true 数学声明。
7. 外部框架构建/小例、合成握手 RTL 和已有局部算术 RTL 各有独立覆盖范围。主代理将另附回执；它们不能自动证明完整 SC 数据通路、真实 CDC 电路、物理时序或 DRAM 闭环。

旧 v6 与 random_service 源码相对本任务基线未改。主代理另行运行三个旧 v6 测试模块共 43 项通过；其日志需由主代理附入最终证据，不并入本审查代理的独立测试数量。

## 外部 ONNXim 回执复核

固定提交 `e3972ac` 已在独立审查工作树读取 C++ 探针与全部四个逐请求 JSON，并运行离线 `external/onnxim/verify_results.py`。12 个服务器原始文件的 SHA-256、实际编译探针源码 hash、Slurm 2772 首次终态 `COMPLETED / 0:0` 和官方两例/自定义一例通过日志一致。拒收时 ID 4 / 地址 0x1020 保持 10 拍，随后受理并返回；乱序例实际返回 0x1020 再 0x1000。COMP 处理 64 bytes 时，64/32 bit 数据宽度分别占 8/16 active cycles，完成时间由 17 增至 25 cycles。

这确认了真实 native Operation / Tile / Core 指令路径、有效性依赖、外部窗口和请求 ID 控制。探针内存返回不携带数值，因此不验证随机门限、矩阵/FFN 数学；它也未执行原生 DRAM 命令后端、完整 ONNX graph 自定义节点、全模型，或与 cycle_v1 做逐周期等价比较。ONNXim 允许同沿返回后再受理，在 bounded trace 的 cycle 12 可以直接看到；不能把这组总周期与严格 old-state 的 cycle_v1 直接相减解释为速度差异。

## 重现

```powershell
python -X utf8 -m architecture_tlm.cycle_v1.audit.run_audit --output <新的结果目录>
python -X utf8 -m architecture_tlm.cycle_v1.audit.verify_real_fixture --backend native --fixture <私有fixture.json> --output <新的数值报告.json>
```

报告与 runner 都拒绝覆盖已有回执。共享制品只需测试、SHA-256、配置、数值比较和来源索引；不要把模型权重或私有 tensor fixture 加入 Git。
