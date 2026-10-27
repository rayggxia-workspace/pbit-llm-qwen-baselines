**完整对照已核验8/8，见[RESULTS_ZH.md](RESULTS_ZH.md)。SC/BF16的accept方案较旧集中模型慢约1.13%/1.20%；这是一个decoder层＋全词表、seed0，不是36层TPOT。**

# 分簇共享SRAM端口/链路TLM

Issue186 / PR192，2026-10-27，沿用unified_v6，新增可选memory_factory，不改默认SRAM与历史封存结果。

## 为什么需要改

当前共享SRAM每个描述符一次锁住所有涉及的bank和唯一sram_fabric，直到访问、串行发送及CDC全部完成。FFN本地驻留权重和寄存器部分和已经绕过该fabric，不能说所有片上数据都走同一条总线。仅删除fabric也不够：长请求通常触及所有bank，仍会整批互相阻塞。

本版将共享SRAM分成4个slice，每slice128个单端口bank；原8MiB、512bank、80MHz、16B/word、512GB/s总链路预算保持。每slice共用一条128GB/s读写链路，DMA/矩阵/向量各有具体端点端口；同bank、同link、同端点才仲裁，读写不免费全双工。没有更换数制、采样数或计算资源。

| 情景 | bank占用粒度 | 链路 | 新增payload暂存 |
|---|---|---|---|
| legacy | 原完整描述符 | 一个全局fabric | 无 |
| descriptor | 每slice完整描述符（只去全局锁的控制） | 4×128GB/s | 无 |
| beats | 每bank一个16B访问/80MHz周期 | 4×128GB/s，共享读写 | 每slice两槽、每槽最多2KiB，共16KiB |

beats中SRAM访问延迟和发起间隔分开。读：bank发起→数据就绪→链路/端点→消费；写：链路/端点→bank接收。CDC20ns分成入口/出口各10ns，每描述符一次，不持有bank或wire等CDC。有限payload credit从生产到消费全程预订，不能将请求排进无限FIFO。一个描述符可拆多个有上限的bank批；同一stripe每bank最多一个字，数据量按原物理word计。

数据地址保持原有交织，不做免费重排。总带宽没有变成4×512GB/s。16KiB是新增链路FIFO的显式硬件成本，不从原8MiB中暗扣，也未假装其PPA已测；后续可综合代表性flit FIFO/仲裁/链路驱动。实际动态路由、跨簇组播、全片布线/CTS未由此证明，当前是静态合法事件预约模型。

## 参考机制

- [Gemmini官方Architecture](https://github.com/ucb-bar/gemmini#architecture)：banked scratchpad、独立accumulator与DMA启发本地层次；没有照搬其默认容量/吞吐。
- [Eyeriss v2原文](https://eems.mit.edu/wp-content/uploads/2019/04/2019_jetcas_eyerissv2.pdf)：分簇与分层互连启发局部连接；本版不是实现其hierarchical mesh。
- [ONNXim官方配置](https://github.com/PSAL-POSTECH/ONNXim#hardware-configuration)：scratchpad、accumulator、注入端口/网络频率分开；本版未运行ONNXim/BookSim。

访问日期2026-10-27。用户给出的旧MIT PDF地址返回404，已从作者实验室镜像读取同篇论文。

## 验证与比较范围

首版42项测试通过；当前45项通过，其中新模块13项覆盖独立slice并行、同bank单端口冲突、读写共享link、有限credit/历史空隙、物理字节与SRAM能量相等、完整小模型事件无资源重叠、算术/DRAM/SRAM/FFN状态守恒；原调度/局部流水/能耗测试保持。

run_case计划6项代表性实际DRAMSys对照：SC/BF16各legacy/descriptor/beats；Qwen3-4B原隐藏/FFN/注意力/完整词表形状，只执行一个decoder层。不是完整36层TPOT，最终结果必须从completed MANIFEST和原RESULT SHA确认，不用玩具例子或理想链路代替整机结果。全部使用相同供数和有限缓冲政策。

新构造只接受exact/pv/screen_exact/screen_pv；并行Ising sink的旧整段SRAM占用尚需单独拆成输出beat，明确拒绝而不悄悄混用。报告会列slice/端点链路字节、每bank访问数、额外FIFO容量及等待。执行回执/交接见work/jieruiz/186/SRAM_SLICE_*，不重交旧健康作业；源快照不可变。

运行测试：`python -m unittest architecture_tlm.sliced_sram_20261027.test_memory`。默认FullDecode不传memory_factory时仍为原SRAM。新增电路实验为0，不把TLM功能测试当作门级PPA。

## 写入capture与credit（后续独立对照）

原18dd259a执行把FIFO槽保留到bank周期结束，作为cycle_end策略保留。新accept策略在SRAM接受写入沿后归还payload credit，但bank端口仍占完整12.5ns发起周期；FIFO数据必须满足写入端setup/hold的接口合同，未由本次TLM代替STA。SC/BF16各新增一个beat对照，不重跑健康legacy/descriptor/cycle_end。45测试通过，含写入接受与端口占用分离；FastCalendar仅软件append优化，500个随机预约与原调度逐事件完全相同。
