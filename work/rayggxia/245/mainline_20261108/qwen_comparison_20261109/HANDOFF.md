## 2026-11-09：Qwen12项完成后的近等面积数字对照已总结

Issue245/PR247，沿同一冻结胶合源12完整Qwen/8配置，三SC seed及三个数字单seed；不混225独立三seed。250MHz SC/BF16dense/W8dense/W8screen面积22.086/21.712/21.827/21.920mm²，含head时间50.428/103.839/95.515/85.732ms、总4pJ能量198.714/330.952/223.480/209.938mJ，平均总功率3.941/3.187/2.340/2.449W。SC相对W8screen快1.700×、片上节30.15%、总节5.35%。100MHz完整表已给，SC54.216ms/194.493mJ。

此前50.419包含head。直接消费finalnorm时刻动作/存储快照重计价：250SC去head43.005ms/片上20.058mJ/总168.331mJ；数字三项去head95.406/89.279/79.496ms及300.584/193.121/179.579mJ。保留embedding/finalnorm和此前重叠head预取，非删除head硬件重跑、面积不减。数字实际比SC小.75–2.48%，仅近似等面积；W8是FFN权重，QKVO/head仍BF16，W8screen不采样PV。

正式model_scaling_20261106/qwen_comparison_20261109/REPORT_ZH.md、SUMMARY/CSV、RATIOS及PHASE_TIME；12原件远端SEAL/SHA和本地11类计数/时间/能量/比率检查通过，无新TLM/GPU/PPL。数字250标量/转换代理、算法质量不对等已标，不宣称最优数字ASIC普遍优势或全36完成。PR247待审未合并，Projects待同步；发布以本work/PUBLICATION.json为准。

恢复不需重跑模型。可运行summarize/verify；DERIVED_INPUT和SOURCE_INDEX保留12远端原件SHA。补价但不改服务可重计，调度或资源更改须新冻结；新TT补测不自动覆盖旧封存。
