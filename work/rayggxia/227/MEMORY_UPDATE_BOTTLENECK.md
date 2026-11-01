## 2026-11-01 Issue227完整回放与瓶颈审计（待PR228审核）

rayggxia，task/227-shared-memory / PR228，main7d42c7d3，复用tmp/shared-memory-issue227-20261101。完整3673已验收：100MHz、8chDDR4-1866、8MiB、B1/2K/r32/k128/S64，66.991850ms/6,699,185拍；36层57.012840ms，lm_head9.978310ms。旧同100MHz3653为222.636130ms；同模型/输入/动作/核帧，DMA与物理排布改变。不是数值推理/PPL或全芯片PPA。

11项CPU审计3688全部封存、28机制检查通过；观测器不改变原单层结果。数字MAC2048→4096单层仍1.591150ms；NL256→160降到1.498110ms（Wd332.89→239.85µs），有限返回直达省FIFO写读为1.394060ms；在途256→1024只降到1.573780ms，扩总fabric/向量bank没有整层收益。工作量/外存地址守恒；bypass有意减少SRAM写读，控制/路由PPA未标定，各收益不可相加或当完整token。

仍有普通投影操作数端口不足、Wd突发/尾批与g/u码重复读、GU供数与采样混合、GU→Wd屏障、粗QK/筛选宏开销。shared后端只用随机核/事件合同，没有实际调用完整RNG服务，500MHz仍未实现统一周期迁移。报告architecture_tlm/shared_memory_20261101/bottleneck_audit/REPORT_ZH.md含36层表、等待/资源结果与SHA。恢复先读HANDOFF_BOTTLENECK.md及BOTTLENECK_PUBLICATION.json，不重交已完成作业。PR仍待审未合并；Projects待维护者同步。正式根记忆由Issue28接收此窄增量；保留其当前内容与并发他人更新。
