# 旧存储预算复算：单价与搬运次数分开（2026-11-01）

**本页保留旧配置原账，DDR电流表后来发现与官方同型号不一致。修正和实际配对见上级REPORT_ZH.md；本页DDR数值不是新推荐值。**

## 结论

**原约21.30mJ片上存储预算能由原始访问计数和工艺库事件价格复算，没有发现字节/字、pJ/nJ或频率重复换算错误。但其中相当部分来自多层搬运，应通过数据路径优化减少，而不是任意调低SRAM单价。**

本项目4KiB/128bit SS宏每16B读取10.0527pJ、写入13.9599pJ；即读0.6283pJ/B、写0.8725pJ/B。每GB额外完整写入再读出约1.5008mJ，5.4GB约8.104mJ。位宽、容量、PVT和外围不同，不能拿其他工艺的一个MAC或SRAM数字直接替换。

| 原预算物理存储 | 动态mJ/token | 漏电mJ/token | 合计mJ/token |
|---|---:|---:|---:|
| shared_SRAM | 4.278546 | 0.912291 | 5.190836 |
| local_CIM_SRAM_base | 2.346657 | 0.028509 | 2.375166 |
| digital_local_buffers | 5.675167 | 0.008018 | 5.683186 |
| DMA_response_buffers | 8.040579 | 0.014255 | 8.054833 |

## 多层搬运如何判断

原DMA响应槽在整块返回后、共享SRAM填充前保存数据；共享槽随后供本地operand/CIM装载。这些在旧生命周期下是不同存储，不是同一事件简单重复收费。改成有界返回FIFO逐beat写目标SRAM，才能删除对应整块staging事件。FIFO若仍落SRAM，读写仍应收；若流通旁路，弹性寄存器/路由是未定价项，不能说成本为0。

当前新模块严格禁止每采样重复读全部普通SRAM权重。GU/Wd采样中的时间部分和在核内寄存器，跨K状态/量化/输入保持需另记。SRAM端口从整描述符占用改为每拍bank仲裁，主要改变时间，不会自动减少同一组实际读写能量。

## DDR有一个比SRAM单价更大的口径问题

实际八通道DDR4配置是2rank/通道、8颗x8器件/rank、4Gb/颗，共128颗、64GiB。关闭PowerDown时，按VDD/VPP与IDD/IPP参数，预充电待机约7.7184W，激活待机约10.3296W；DRAMPower还加入刷新和访问状态。旧外存64pJ/B＋50mW是另一套代理，不能描述这套DDR设备。

DDR总背景应在整机同一时间线只计一次，不能把每个Attention组的整设备总能量相加，也不能把扣除matched-idle后的增量称完整DRAM能量。纯读64B、ACT/PRE、开行背景、刷新、低功耗和PHY必须区分。当前ACT组件含已知负项，保留原始报告，不能截成0来粉饰。

一个合理的后续容量对照是同通道/相同时序的单rank，容量32GiB仍足够，待机电流下界约3.8592W；这属于器件配置变化，需用完整地址范围/刷新/能量实际回放验证，不能直接宣布整机能量减半。

## 公开资料如何对照

- [Horowitz，ISSCC2014原文](https://gwern.net/doc/cs/hardware/2014-horowitz-2.pdf)：Fig1.1.9中8KiB/64bit缓存约10pJ、32KiB约20pJ、1MiB约100pJ，是不同条件的量级参照，不作为本55nm库校准。
- [AttAcc，ASPLOS2024 §7.1](https://scale.snu.ac.kr/papers/2024-04-Conference-ASPLOS-AttAcc.pdf)：用公开SRAM数据校准FinCACTI，另取HBM访问依据，说明动作计数、存储结构与单价来源要分别核对。
- [CACTI官方实现](https://github.com/HewlettPackard/cacti)：几何/端口/组织共同影响能量、时延和面积；应校准之后探索，不把容量简单乘每bit价格。
- [DRAMPower官方实现](https://github.com/tukl-msd/DRAMPower)：命令和状态轨迹与memory specification决定能量；并非任意DRAM统一pJ/B。
- [Accelergy官方实现](https://github.com/Accelergy-Project/accelergy)：用动作次数及动作能量表建立估算，支持本轮把单价校准和流量优化分开。

本轮没有新门级/PT仿真。原始三seed摘要、库参数索引及SHA在JSON，后续新事件调度结果另表，不改旧21.30mJ原件。
