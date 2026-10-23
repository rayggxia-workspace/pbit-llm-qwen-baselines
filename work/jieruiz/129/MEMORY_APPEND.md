## 2026-10-23 Issue129 SRAM与DRAM节省报告

新增architecture_tlm/memory_savings_20261023/REPORT_ZH.md及7页Word，8个已封存v6情景复算、20源SHA、64文档/数字检查。W8减半权重不是随机独有收益；Qwen已记账2K/8K外存读写少31.95/35.52%，SRAM读写少29.82/33.49%，未闭合局部保持/计数未包含；条件存储能量不是整机PPA。采样不自动缩小完整KV缓存。PR120的48→5KiB是逻辑状态，PR127加宽读口不减少字节；新周期/完整FFN暂停保持。本轮无新实验，成果通过PR130已推送待审、未合并；Word及来源JSON原字节已核验。来源/回执见Issue129与work/jieruiz/129/PUBLICATION.json，Projects缺read:project待同步。

