## 2026-11-01 Issue227：DMA扩展与通道入口瓶颈

沿PR228/task/227-shared-memory，片上100MHz、8chDDR4-1866、8MiB SRAM/计算/采样不变。旧单入口约28.5GB/s；8原生initiator＋24请求/拍＋256全局在途＋32KiB返回FIFO，连续流110.84GB/s（名义119.424的92.8%）。按计算tile离线重排权重，单层5.418380→1.591150ms，DDR核心49.454646→27.970639mJ，SRAM.431049→.370269mJ；访问命令反增、背景刷新下降，平均DDR功率9.13→17.58W。不是全芯片能量/实测或PPL。

公开实现unified_v6/shared_dma.py与shared_memory.py/shared_decode.py，bridge在shared_memory_20261101/dma_expand；25测试，实际Slurm3655–3668消融，额外seed3669–3672与完整3673按RESULTS/HANDOFF_DMA核验；旧3650/3653健康任务不重交。全局额度不复制，原FRFCFS/JEDEC/端口冲突保留，重排物理地址改变但算术/字节/SRAM事件一致。控制/互连/PHY未定价；不发布受限module_handoff或原fixture。结果/源/配置SHA见dma_expand/RESULTS.json，状态以DMA_PUBLICATION回执为准；未自动合并，根正式MEMORY由Issue28接收此窄增量。
