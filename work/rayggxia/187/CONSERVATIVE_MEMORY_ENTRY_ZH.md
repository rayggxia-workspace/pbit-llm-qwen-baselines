## 2026-10-27 Issue187：保守调度审计已发布

用户要求将当前保守调度整理为文件并确认论文惯例。沿用PR189，源提交2a7352b767fb6966b800a04522d0650bae3864eb；6文件逐字远端回读/tree核验通过，仍待审未合并。报告architecture_tlm/simulator_survey_20261025/CONSERVATIVE_SCHEDULING_AUDIT_ZH.md；目录tmp/simulator-survey-issue187-20261025。只读PR192@556462dc，实际调度实现继续Issue186，不重复开工。

确认FIFO预约空隙不回填、宏DMA批间排空、SRAM整描述符占用、SC跨窗口编程限制；12配置数字shared_prefill均未设/有效False，而SC启用局部overlap与weight_bypass。两任务Scheduler实际120ns与合法110ns安排仅证明软件限制，没有整机收益数字。桶归约/恢复边界和功耗上界待对齐；保守与乐观假设并存，不能称整体上界。不概括“大部分模拟器不保守”，代表工具常表达/搜索合法流水，但仍有资源限制与近似。

8份源码SHA/Git blob、12结果/派生配置SHA与微例在work/rayggxia/187/CONSERVATIVE_CHECK.json。未改运行源码/默认/历史结果，无新完整TLM/GPU/PPL/RTL/EDA或服务器任务。Issue187评论6435467483，Projects仍待权限。发布回执CONSERVATIVE_PUBLICATION.json；完整记忆在Issue28唯一维护副本与根镜像同步，保留既有原字节。

---
