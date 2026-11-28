# Prefill到连续Decode：统一TLM的会话控制扩展

2026-11-28，Issue225 / PR266。入口`run_session.py`。本扩展把软件模板、有限引擎执行和存储事务连接成完整会话；原decode封存结果与默认配置不改。

## 实际执行范围

```text
软件：Model配置 → 层模板 → 行分组/缓冲与任务计划
设备：命令发出 → 独立引擎及本地循环 → 完成事件/回压

prompt token IDs → Embedding → 全部Decoder层与KV写入
  → 最后prompt位置的final RMSNorm/LM head/流式argmax
  → 首个生成token → G−1次单token Decode → 完成
```

支持当前SwiGLU稠密Decoder模板，Q/K Norm可配置；尺寸、层数、Q/KV头数和词表由Model参数提供。`llama_template`只是关闭Q/K Norm的同宽合成适配测试，不是Llama checkpoint评测。未知激活类型在编译时拒绝。Qwen3默认形状来自已固定revision的配置：36层、H2560、F9728、32Q/8KV、D128、V151936。

第一轮运行固定W8 FFN、GU16/Wd32、SparQ r32/K256和PV64，短因果前缀自动限制候选数为合法KV长度。不同生成阶段使用相同硬件，不把prefill按decode时间简单相乘。K/V从空状态按真实位置写入；decode继续读这些地址。G个输出只执行G−1次decode前向。完整激活采用有限DRAM后备，当前行分组、概率码和部分和留在片上。

## 代码与分工

|文件|作用|
|---|---|
|session_program.py|软件侧模型/层模板和容量规划；不让硬件解析HF配置|
|session_control.py|会话、层、局部矩阵循环、KV生命周期、head与采样/gather管线|
|session_services.py|有限资源池、DMA、SRAM适配器和引擎完成事件|
|session_profile.json|初始硬件和宏参数；保留来源与未标定项|
|session_memory_reference.py|既有Issue227 shared_memory.py的同字节依赖快照；复用其事件队列、Signal、delay、run及可选BeatSRAM/DMA，无工艺库|
|test_session.py|12项控制/存储/工作量回归|
|verify_session.py|独立复算会话结果的形状、帧、MAC、KV与封存SHA|

默认5核，每核8KiB单权重区；576KiB普通SRAM、16KiB独立DMA返回寄存器；12个FP24状态槽，每槽128项384B，两状态worker。DMA返回寄存器没有重复计入SRAM。数字池256 FMA、16路向量；8个KV工作区、单采样服务和32头PV资源。

计划生成器约束GU记录、x码/指数、Wd输出、状态和工作区容量。Qwen3请求32行时，目前自动收敛至4行，前端活跃预算约254KiB；12状态槽只允许3个输出组同时执行。该结果显示prefill的状态约束，不是声称五核已经充分利用。增加行分组或并行组需重新分配真实空间并重跑，不能隐藏增加状态槽。

## 数值和生命周期

- 公共中间结果/跨K状态为FP24 E8/M15，局部计数23bit。这里统计相应恢复、FP24转换/加法、编码及访存；**不执行完整4B数值前向**。RNE/FTZ等算法行为仍由module_contracts/FP24_ZH.md及独立数值/RTL参考验证。
- x为组64共享；g/u为组64动态基准＋逐元素S/S2，sigmoid沿P8重建→S8/F3→LUT。GU输出保存完整288B/64对记录（含尺度及填充），直接供Wd事件生成，不插入一次z数值落地。
- BF16权重数字计算采用BF16乘、FP32局部累加，显式计算输入/输出格式转换。LM head流式FP32 logits直接做argmax，不写全词表logits，也不强行压成FP24。
- Norm按整行完成平方和归约后再归一化，使用有界行缓存；Q/K Norm按每个head处理，不能把V一并归一化。
- 每CIM核双结果槽；四拍捕获完成才释放结果槽。局部结果捕获后可释放权重区，跨K状态提交/输出后再重用状态槽。同一输出的下一K块等待提交。
- Attention采样与V gather通过有限8地址FIFO重叠，FIFO满会阻塞采样消费；共享V缓存64向量，包含pending/引用状态，读完之前不可覆盖。8个工作区不足的KV头使用分批映射。

## 两种访存粒度

**快速控制集成模式**：`--sram-backend burst --dma-backend burst`。SRAM按bank日历/连续范围服务，DMA按最多8KiB范围占用有限16KiB credit并计带宽、首响应及落地。规则传输被合并，结果属于宏时序；将未来整个范围预留bank可能改变竞争，因此不称逐拍精确。

**交叉检查模式**：`--sram-backend beat --dma-backend beat_analytic`。直接使用既有BeatSRAM逐拍bank授权和SharedMemory的64B请求、256个全局credit、返回保持、写源读取与目标落地。物理普通bank每拍1RW；CIM bank仍限定32行128bit。原内核用于均匀容量上界的辅助配置不是新增物理容量；外部报告只计实际576+8×核数KiB。

两种模式的**DRAM目前都是解析带宽/延迟代理**，不是新Ramulator执行。默认136.4606GB/s和30ns来自原接口情景；宏模式用较粗credit会影响利用率，不能据此替换既有LPDDR整机性能。要给论文TTFT/TPOT，下一步需要绑定原生LPDDR后端并做更长前缀的回放。

Attention地址使用确定seed的合成候选/均匀抽样，不是从真实QK得出的地址：它只用于验证因果访问、缓存、合并与回压。Coarse K在token-major布局下按实际64B sector并集读，记录SG段数，不把稀疏维度直接当成理想连续小字节。真实SparQ/赢家保持轨迹接入后需重算，不能继承PPL或实际命中率。

## 运行

在仓库根目录：

```powershell
python -B architecture_tlm/unified_v6/test_session.py
python -B architecture_tlm/unified_v6/run_session.py --prompt 4 --generated 2 --out results/session_qwen_short
python -B architecture_tlm/unified_v6/run_session.py --model small --prompt 3 --generated 2 --sram-backend beat --dma-backend beat_analytic --out results/session_small_beat
python -B architecture_tlm/unified_v6/verify_session.py results/session_qwen_short
```

`--memory-kernel`可改用外部已签SHA的既有内核。默认同字节快照使本目录可独立运行；不需要GPU、EDA工具或工艺库。实际长跑使用work中不可变执行快照；不修改快照来补跑。

## 输出与下一步

RESULT/PLAN/HARDWARE/SEAL包含TTFT、各输出时间、每token间隔、包含/去除final Norm+head的组件时间、GU/Wd帧数、数字MAC、KV追加区间、资源峰值、读写与64B物理流量、逐层/行分组用时、源文件SHA。first_token包括最终head；去除head的数字只作组件拆分，不叫可直接产生token的TTFT。

能量目前只给S0 SRAM动作（CIM含一次读等价代理）及4pJ/bit外存传输两项；整机能量、功率和面积返回null。新23bit核、FP24服务、控制/接口及完整等待成本尚未绑定，不能套旧64bit价格。没有新增数字电路仿真run或PPL。

后续按顺序：真实Attention轨迹/现有模块服务绑定 → 原生LPDDR回放 → 2K prefill与连续decode → 状态容量/行数/核数扫描 → 补齐整机能量账本。现有功能提供可运行的控制与事务起点，不改已封存的论文结果。
