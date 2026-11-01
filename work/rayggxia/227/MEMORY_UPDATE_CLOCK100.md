## 2026-11-01 Issue227：用户要求片上统一100MHz

沿PR228/task/227-shared-memory，默认chip100，旧legacy_mixed显式复现。QKV/O/lm_head/QK/PV/FFN/SRAM/DMA前端均100MHz；DDR4独立。修正原500MHz跨K/量化/出口/argmax合同的ns，并按片上边沿观察SRAM/DRAM完成，不只是频率标签。GU/NL66拍不变；数字2048MAC/拍×100MHz=0.4096TOPS，旧500MHz=2.048TOPS。20检查通过，FMA2/完整阵列及宏物理限制保留，不宣称全芯片STA。

实际执行3651/3652单层同源同数据配对，完整3653依赖3651成功；原健康混合版3650不改不重交。正式clock100/REPORT_ZH.md、RESULTS.json与本HANDOFF_CLOCK100，原件仍归project_archives/shared_memory227_20261101，源码/配置/输入/结果SHA逐项记录。无新EDA/PPL/电路run。验收前不继承旧220–240ms为100MHz完整结果，不把时间或动态能量机械乘5。实际发布看CLOCK100_PUBLICATION.json，PR未合并。
