# 本地bank端口改进：取消无物理依据的全局512GB/s封顶

本目录是已有`unified_v6`的可选存储后端/配置，复用同一个完整decode图、DRAMSys、FFN和随机服务。Issue186/PR192；没有另写一套整机、没有增加MAC/SC阵列、没有修改采样算法。原入口与封存结果保留。

## 改什么

借鉴[Gemmini](https://github.com/ucb-bar/gemmini#architecture)的banked scratchpad＋DMA，以及[ONNXim](https://github.com/PSAL-POSTECH/ONNXim#hardware-configuration)的端口级限制。没有直接运行这两个模拟器，也不继承其工艺、面积和带宽数值。

```text
标准HBM2 → 原有有界DMA/响应缓冲 → 四个SRAM slice的DMA写通路
                                      ↓ 同一bank端口仲裁
                         4 × (128bank × 16B/word)
                              ↓                 ↓
                         矩阵本地读通路       向量读/写通路
                              ↓                 ↓
                       原2048MAC/拍矩阵算子   原64lane向量算子
```

四个slice是四组相邻供数接口，不是四个可独立执行程序的计算核。继续使用原`mac`/`vector`调度资源；没有免费增加四倍算力。矩阵入口由四个512MAC等份接口供数，输入广播、归约仍属于原矩阵宏合同，未声称完成实际布线。SC的权重已由DMA写到局部驻留CIM，不会每采样一拍重新经过本共享SRAM；这一机制不变。

## 容量、频率与带宽依据

| 项目 | 旧分slice对照 | 新候选 | 依据/边界 |
|---|---:|---:|---|
| SRAM有效/物理容量 | 8MiB | 8MiB | 不复制存储位 |
| 宏数量 | 2048 | 2048 | E宏256×128bit，每个4KiB |
| bank数量 | 512 | 512 | 每bank4宏选一，单读写端口 |
| 宏时钟 | 80MHz | 250MHz；另测200 | SS E宏read最小周期3.468ns；250MHz周期4ns，周期筛查通过，尚非wrapper STA |
| bank端口合计峰值 | 655.36GB/s | 2048GB/s | 512×16B×宏时钟；R/W共用，不是双倍全双工 |
| 公共fabric总封顶 | 512GB/s | 删除 | 原值无实际互连RTL/布线依据 |
| 有限payload FIFO | 16KiB | 16KiB | 每slice两个2KiB credit；沿用额外缓冲，不藏进8MiB |

首轮本地通路分别定宽，500MHz core固定。以下为**每slice**；它们是消融候选，后续等宽候选见下方：

| 通路 | 宽度/核周期 | 峰值 | 选择依据 |
|---|---:|---:|---|
| 矩阵本地读/结果通路 | 1024B | 512GB/s | 2048MAC分四份，每MAC一份2B BF16权重/拍 |
| 向量读/写 | 64B | 32GB/s | 64lane分四份，每lane一个4B值/拍；多操作数仍逐请求计 |
| DMA输入/输出 | 128B | 64GB/s | 四份合计256GB/s，匹配既有标准HBM2引脚峰值；实际完成由DRAMSys决定 |

每类、每方向是明确的独立通路，**同bank读写仍不能同时发生**；同端口请求按宽度排队、有限credit回压仍在。所有通路的标称带宽不可相加成可持续SRAM带宽；最终还受bank单端口限制。250MHz到500MHz使用原20ns描述符CDC预算，FIFO和gearbox实现未新综合。512GB/s局部矩阵通路虽宽，但来自短距离并行bank总线，不能理解为需要一条贯穿全片的8192bit mesh链路。

**等宽候选（`widen_burst_ports`，索引10～13）**：DMA/矩阵/向量各本地通路均按1024B/corecycle/slice，即512GB/s设置。原有64KiB响应缓冲可以在HBM读完后以短突发排入本地SRAM；不能把外存平均峰值256GB/s再当作片内搬运的必然上限。bank单端口、同端口排队和16KiB有限payload credit保持，未增加HBM带宽。响应缓冲的banking/宽读出和gearbox是本方案明确的宏合同，仍需外围PPA校准。等宽共享vs独立、512逻辑bankvs2048独立宏作匹配对照，不拿不同端口宽度的结果证明拓扑优劣。

这不是“给每个SRAM加几个免费读端口”。使用现有独立bank的并行性，增加的是wrapper/mux、读写通路、驱动和布线，不是1R1W/多读口bitcell。宏cell容量/面积基线保持；外围增量尚未测，不能声称整片面积/功耗完全不变。

## 消融与结果

`run_case.py`索引0～5为：SC只升250MHz、SC升频并拓宽共享通路、SC独立本地通路、SC独立通路200MHz、BF16独立通路250MHz、BF16拓宽共享通路250MHz。用旧已完成80MHz accept两项作基线，不重跑。索引6/7可执行完整36层SC/BF16；未实际执行封存前不能报36层结果。

每项使用真实Qwen3-4B后训练版结构、单层＋完整151936词表，seed0；SC固定四档T64、NL128、原32阵列，Attention筛选＋准确Softmax＋PV采样。不是模型权重推理或PPL，不把单层＋词表乘36。完整度、版本、配置、SHA及结果以`RESULTS_ZH.md`和`work/jieruiz/186/LOCAL_PORTS_*`为准。

### 进一步暴露宏端口：索引8/9

`configure_exposed`/`PartitionedSRAM`将原2048个E宏分别作为独立单端口bank，去掉原来每4宏合一bank的外部选择关系；**宏数量、存储位和库cell面积均不增加**。四个slice各512宏，分别保留128个ping宏、128个pong宏、256个workspace宏。当前权重读取、下一权重预取和工作区访问因此可以落在不同物理宏上；它们不再无故争用同一个逻辑bank。每类本地通路仍按上表定宽，FIFO仍16KiB。

代价是按带宽分配容量：ping、pong各占2MiB物理宏容量，但目前每个live tile只用64KiB；workspace占4MiB。未使用的ping/pong行**不再当作另一份免费workspace**。映射器对virtual live region、实际宏row、workspace上限和跨slot请求逐项检查，返回实际物理bank/row。全2048宏的端口总峰值是8192GB/s，但单个权重slot只占512宏，其峰值仍2048GB/s，不能拿总峰值宣称矩阵获得四倍供数。

这是通过现有宏端口与布局换并行，不是增加存储位或多端口bitcell。wrapper/mux可能简化，局部选择/布线/时钟使能会变化，净外围PPA仍需校准，当前不填写虚构的面积增量。端口宽度越大必然越好、完全免费均不是本模型的假设。

本轮不改变：单DMA actor/有界窗口、一个响应缓冲、完整tile到齐再填充、矩阵本地装载后才计算、直方图RMW依赖。它们仍可能限制速度；删除一个任意带宽数不会使这些限制自动消失。Ising输出sink尚未拆成beat，新后端明确拒绝该模式，不能把此结果称作Ising整机结果。

运行：`python -B -m unittest architecture_tlm.local_ports_20261027.test_ports`。正式DRAMSys运行必须使用提交后冻结manifest，通过Slurm调用`run_case.py`；不要覆盖已有快照。库内部SRAM动作能量/单元面积可按同宏复用，整片能量/宽互连增量不由本轮速度结果自动确定。
