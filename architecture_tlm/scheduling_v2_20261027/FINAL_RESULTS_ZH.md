# 随机版调度更改：最终汇总

本轮完成11项完整模型TLM。组合三seed平均 **64.4113 → 57.4454 ms/token**，时间减少 **10.81%**，约 **1.121倍**。

比较对象：Qwen3-4B后训练模型形状、36层、batch1、2K decode、包含lm_head。固定500MHz、32个64×64随机阵列、2048MAC/拍、GU64/NL128、8MiB/512bank/512GB/s SRAM和同一标准HBM；Attention为QK筛选＋准确Softmax＋PV采样。各情景不开门控，先隔离调度。

| 调度变化（同seed0） | 整机ms/token | FFN ms | 普通投影及lm_head ms |
|---|---:|---:|---:|
| 原调度 | 64.3779 | 25.4916 | 29.8444 |
| 仅普通矩阵预填充 | 64.3779 | 25.4916 | 29.8444 |
| 仅资源就绪日历 | 64.3779 | 25.4916 | 29.8444 |
| 仅SC跨窗口装载 | 64.3004 | 25.4095 | 29.8433 |
| 上述三项组合 | 64.3004 | 25.4095 | 29.8433 |
| 仅提前下一DMA请求 | 57.5095 | 25.2949 | 23.1734 |
| 三项组合＋提前DMA | 57.4212 | 25.2070 | 23.1709 |

各组合seed都与旧同seed基线配对；三seed波动见两份COMPARISON文件。seed0旧基线64.3779ms逐数复现。

## 做了什么，为什么

首轮去掉SC跨窗口装载限制、使用资源空隙、启用既有普通矩阵prefill，但合计收益只有约0.14%。42541次普通prefill中，下一权重能在前一计算结束前就绪的次数为0：请求仍在当前本地装载/计算开始后才发出。就绪日历无法提前尚未发出的请求。

第二轮把请求发起改到已有响应缓冲释放的边界。普通BF16矩阵在当前权重写入shared槽后，即发下一tile DMA，与当前shared→local读出重叠；SC在当前program消耗响应后、准备随机context前发下一DMA。此时原来的单响应槽已经空闲，不需要新数据bank或第二套计算资源。

普通矩阵提前请求次数42541，SC提前请求次数25272。组合seed0的FFN为25.4916→25.2070ms，普通投影/lm_head为29.8444→23.1709ms。

## 保持不变与成本解释

所有同seed方案的算术动作、采样需求、FFN逻辑帧/恢复顺序、DRAM/SRAM物理字节和数据容量已核对。沿用一个DMA响应槽、两shared槽、两个本地权重/系数bank；没有扩大阵列或SRAM容量。控制器的具体面积和能量后续回填。

访问量和有效算术不变，节省主要来自等待被覆盖以及总时长缩短；不能把时间减少比例直接当成动态能耗减少比例。本轮不报完整芯片PPA或模型PPL。

## 仍未展开的调度

外存仍用原DRAMSys单macro actor，跨描述符仍排空；SRAM仍按整描述符锁资源；SC计算/计数与恢复仍串行。本轮不是全局最优调度，也没有改变普通数字L/II。下一步若继续优化，应分别测跨描述符有限在途、按beat供数与SC恢复流水，避免再次只开prefill标志而没有改变请求时机。

## 证据和复现

首轮执行410fa5af95fd454f551fb340891d16ea8c7bcc56、Slurm3156七项；第二轮执行5ba7947767d40be6f694e8c1a1346aec1eb07f72、Slurm3163四项，全部completed并核原始RESULT/EXECUTION/SUMMARY SHA。134项本地软件测试及第二轮每项12条冻结包测试通过。完整原件留个人服务器，只收小摘要入Git。

首轮RESULTS_ZH.md/COMPARISON.json，第二轮RESULTS_EARLY_DMA_ZH.md/COMPARISON_EARLY_DMA.json，最终FINAL_COMPARISON.json。重建顺序：collect_schedule_v2.py、analyze_schedule_v2.py、collect_schedule_early.py、analyze_schedule_early.py、report_schedule_final.py。所有脚本位于work/jieruiz/186。
