## 2026-11-01 Issue227：统一共享调度与存储能耗审计

rayggxia，task/227-shared-memory，独立tmp/shared-memory-issue227-20261101，目标main@7d42c7d3，接续Issue186成熟调度/Issue198局部Attention和Issue225预算，不覆盖原任务。正式代码unified_v6/shared_memory.py、shared_decode.py，既有入口--shared-memory显式选项；默认保留。全局64在途/8KiB返回FIFO，512个128bit1RW bank逐拍释放、物理每bank容量、双缓冲/直接填充、跨阶段预取、写回源与尺度metadata均显式执行。GU16/NL256为已测100MHz，普通2048MAC/500MHz仍宏合同，RNG/外围未知不填0。

16机制检查PASS；Slurm3647/3648/3649新版同地址/同算术采样工作量配对：异步直接5.459883ms、0.431708mJ SRAM、49.802673mJ DDR core；串行8.834193ms、.485296mJ、69.530172mJ；额外staging6.444903ms、.638161mJ、57.642898mJ。一层含embedding无lm_head、B1/2K、K128/S64、seed17；不能当整机或质量验收。纯RR1小探针反而慢约9%，保留负结果；返回FIFO原16bank导致12.8GB/s上限，改128个既有bank，没有增容量/双端口。

旧21.304mJ片上存储由原访问/库单价复算PASS（读/写.62829375/.87249375pJ/B）；约8.055mJ来自旧整块响应缓冲，重复搬运是优化方向，不任调单价。**DDR确有参数来源问题**：同名Micron memspec被覆盖电流，旧ACT负项；官方本地原件SHA3fcfb7f3与公开表核对。只改电流同时间/同SRAM事件实际54.758627→49.957182mJ（−8.77%），ACT转正，不能把此变化当调度收益。64GiB/128颗背景远非50mW；官方NoPowerDown预充5.184W、激活6.0672W，背景整机只计一次。PHY/VDDQ与低功耗状态未校准；单rank32GiB为未来容量敏感性，未运行不宣称能量减半。

健康Slurm3650为36层+lm_head同一全局DDR时间线，root /home/Hongjie_Zeng/projects/pbit-shared-memory-20261101-issue227/wholeofficial_v3_15da73345c7a；预计2–3h，6h上限；无GPU。不得改冻结source或重复提交。完成后按HANDOFF核对36层、lm_head、排空、配置/输入/结果SHA再更新。私有3场景代表流量循环，不是36层新数值推理；无PPL/新EDA/run。原件project_archives/shared_memory227_20261101，正式报告architecture_tlm/shared_memory_20261101/REPORT_ZH.md，任务索引work/rayggxia/227/EXECUTION_INDEX.json。PR/发布实际状态看PUBLICATION.json；未自动合并。根正式备忘录合并此增量待Issue28协调，不上传本地混合union或两个受限module_handoff原包。
