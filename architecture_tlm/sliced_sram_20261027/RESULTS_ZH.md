# 分簇共享SRAM调度：实际对照

one real-shaped Qwen3-4B decoder layer plus full151936 vocabulary; not36layer TPOT, no PPL/PPA

**总容量/带宽、算术和物理访存不变；beat方案额外16KiB FIFO明确计为未校准硬件成本。**

| 存储调度 | SC非词表部分 ms | SC含完整词表 ms | BF16非词表部分 ms | BF16含完整词表 ms |
|---|---:|---:|---:|---:|
| 旧全局fabric/描述符锁 | 1.413238 | 8.229026 | 2.015330 | 8.831064 |
| 分slice，bank仍整描述符 | 1.413270 | 8.280314 | 2.031322 | 8.897864 |
| 逐beat，写FIFO保留至周期末 | 1.440596 | 8.481780 | 2.084412 | 9.125730 |
| 逐beat，写入接受即返credit | 待完成 | 待完成 | 待完成 | 待完成 |

已封存6/8项；未收齐时不能声明最终结果。主验证逐配置保持算术、SRAM/DRAM物理字节、FFN/Attention工作与实际RNG输出SHA相同。正号是变慢。没有把单层＋词表乘36当作整机时间。

## 如何解释

仅拆全局锁仍可能无收益：同一长流仍会访问大部分bank，且阶段依赖、唯一DMA actor和既有算子供数顺序未改变。细化模型还显式计入包、bank时钟对齐和有限buffer；旧模型不是统一的悲观上界。

cycle_end策略让写入payload等待整个bank周期才返credit；accept在SRAM接收沿后返credit，bank端口仍独占完整12.5ns。二者作为硬件协议对照保留，而非改掉旧结果。具体收益以完整表为准。

新模型限定带宽在每个bank、端点与slice共享读写链路上，保持4×128GB/s总预算512GB/s，不能把每簇都当512GB/s。16KiB FIFO/互连/CDC功耗尚未校准，不能将旧2.52W直接套为新结构能耗。

参考/结构/限制见README_ZH.md；COMPARISON.json含执行提交、配置/原结果SHA与机器检查。原执行3169的BF16三项配置前失败，3175仅补这三项；旧SC健康项未重跑。accept执行3178是新协议比较。无新GPU质量/RTL/PT，全模型时序仍旧入口。
