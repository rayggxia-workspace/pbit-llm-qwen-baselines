# 最新任务：完整概率版已提交

门禁38644763、全量数组38644764；恢复[本次交接](full250_20261109/HANDOFF.md)。先查STATUS，不重复提交。

## 2026-11-09 28nm250 TLM最新更新已发布

PR249源b64cbb3241dc2f0e6d6bdb5b3ce5269e3cb06d02，31文件远端完整回读一致，Issue225评论6743216455。新零余量FFN/FMA、PV参考与平台宏已接，条件面积6.480303mm²；六CPU回放及六检查通过，250时间/访存未变、500 BUDGET不变。完整46.01856ms/核心15.016133mJ仍为明确外推，不是完整36层实跑；扣head阶段39.408936ms。S12主线、832KiB、55/500默认保持，宏/PV hold限制保留。原件zip/SHA与恢复在本work，PR待审未合并，Projects待维护者同步。

---

# 最新：28nm250 TLM价卡/账本更新

[本次可执行交接](update250_20261109/HANDOFF.md)。832KiB混合宏保持；当前250面积6.4803mm²，500不变。发布实际状态见本次PUBLICATION。

# Issue225最新恢复入口

当前阶段：28nm832KiB混合宏默认，PR249待审；详见[mixed34交接](mixed34_20261109/HANDOFF.md)。持续任务此前的55nm250、统一时钟、DMA16KiB、SRAM表征与832容量回放交接保留在各有日期子目录；不要只依据早期默认恢复。正式配置以architecture_tlm/process_28nm/{250,500}MHz/WHOLE_CONFIG.json为准，55nm不变。开始或发布前核实最新Issue225/PR249、本人STATUS和本次PUBLICATION回执。
