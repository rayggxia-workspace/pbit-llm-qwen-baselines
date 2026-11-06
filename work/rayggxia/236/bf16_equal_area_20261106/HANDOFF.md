# BF16近等面积对照交接

负责人rayggxia，接续Issue236/PR244。本地复用task/236-fair-digital-20261105与tmp/digital-fair-issue236-20261105；公开源码/配置提交f5b649edd85ca6db115e3280c58af9dbb19c84ce，九文件逐字回读通过，PR未合并。

原生预检38612072已COMPLETED/0:0，四项检查＋完整36层分配的首层/跨层预取/字节核验通过。完整38612073已RUNNING，未产出完整结果。运行配置与封存源SHA在architecture_tlm/bf16_equal_area_20261106/RUN_RECEIPT.json；1888路共享BF16 FMA、覆盖67.39315824mm²/目标67.54144608mm²，其他100MHz/2.5MiB/2K/B1/36层及外存不变。

恢复先读本人STATUS和本地work/rayggxia/236/bf16_equal_area_20261106/HANDOFF.md。使用同目录ops.py status，只读核验sacct、日志及封存；完成后ops.py collect，不重复prepare、不改提交快照或旧17项结果。完整依赖位于已有授权EDA个人存储，main没有所有私有旧运行时，本目录不是独立可运行安装包。

收齐后核验全部36层＋lm_head、181矩阵、4,022,272,000普通FMA和8,044,544,000矩阵权重字节，以及队列、DMA返回、能量/面积守恒，再与原W8稠密及C20/Ising并表。BF16字节更多须如实收费，4pJ/bit主情景/6.6与8敏感性不变。更新同PR/Issue/STATUS/备忘录；不自动合并。当前无新PPL/电路PPA，Projects待维护者同步。
