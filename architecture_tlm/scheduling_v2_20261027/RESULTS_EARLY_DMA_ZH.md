# 随机版固定资源调度优化结果

Issue186/PR192；Qwen3-4B后训练形状，36层/B1/2K，含lm_head。执行5ba7947767d40be6f694e8c1a1346aec1eb07f72，4项均completed并封存SHA核验。

本轮保持500MHz、32个64×64随机阵列、GU64/NL128、8MiB/512bank/512GB/s片上SRAM与同一标准HBM时序。Attention仍为筛选＋准确Softmax＋PV采样；主比较均不开门控。

| 方案 | 整机ms/token | FFN ms | 普通投影/lm_head ms | 较原调度时间减少 |
|---|---:|---:|---:|---:|
| 只提前DMA seed0 | 57.5095 | 25.2949 | 23.1734 | 10.67% |
| 组合＋提前DMA seed0 | 57.4212 | 25.2070 | 23.1709 | 10.81% |
| 组合＋提前DMA seed1 | 57.4758 | 25.2161 | 23.1712 | 10.84% |
| 组合＋提前DMA seed2 | 57.4392 | 25.2059 | 23.1749 | 10.80% |

组合三seed平均57.4454ms/token，标准差0.0278ms。seed0原调度与旧封存同seed情景差0ms，复现通过。

同seed算术、随机抽样需求、FFN逻辑帧/恢复顺序、SRAM/DRAM物理字节相同；各情景计算资源、SRAM容量/接口和本地数据状态相同。没有新增数据bank、计数器或第二套SC计算资源；就绪仲裁控制的具体PPA仍待后续校准。

资源日历只对已有有限tile前瞻利用空隙，外存仍是原单macro actor/批间排空；本轮没有声称完成跨描述符并发、SRAM逐beat仲裁或SC计算/恢复解耦。

本轮负面结果：首轮三个策略合计仅约0.14%收益，因DMA请求仍在当前本地装载后才发出。第二轮在当前shared fill释放响应缓冲时就发出下一BF16矩阵请求，覆盖本地读出；SC在当前program释放响应缓冲后、随机context准备前发下一请求。二者仍只有一个待接收响应及原有两槽/两bank，没有新增DMA通道或数据存储。

动态动作不变时，调度提速本身不会同比减少计算和访存动态能量；总时长缩短可减少开钟空闲/背景/泄漏。当前priced_subtotal不含完整HBM/CIM/控制/时钟树，不能当整机功耗或能效比。后续PPA回填保留同动作边界。

本轮是事务时序/动作模型，没有新模型PPL、GPU性能或RTL/PT。数字算子L/II仍沿原参数来隔离调度影响；后续按文献/实库校准另做参数情景。

复现：先collect_schedule_early.py核远端completed和原件SHA，再analyze_schedule_early.py重新生成本报告。具体各动作变化、资源日历命中数和原件SHA见COMPARISON_EARLY_DMA.json与results_early_dma/。
