# Issue210 数字MAC标定接入更新 2026-10-29

用户追加授权修改TLM标注与功耗。同task/210-tlm-component-audit、PR211；实际新发布见DIGITAL_POWER_PUBLICATION.json，未有回执前仅本地完成，旧回执不代表本增量。

已实现architecture_tlm/digital_energy_20261029及unified_v6四个挂接文件，默认nonfused_pair，FMA2/3可选，legacy_proxy保留。Ledger逐动作归账确保替换旧收费；真实FullDecode/CLI小形状验证，主110＋新9测试通过。新复算3原摘要SHA与14项账目闭合；MAC0.451426W/片上1.757236W/154.017521mm²，TPOT57.445385ms不变。无新EDA/GPU/PPL/完整时序；PR209数据只读，不发布其本地未批准预算。

成果、限制和复现见digital_energy_20261029/README_ZH.md及results/REPORT_ZH.md。500MHz、ICG、集成tile、模型活动、接口/CTS仍缺，DOT64拒绝直接套scalar。当前HEAD仍main基线，index含API已发布旧20文件及本增量；CLI HTTP1重试仍low-speed失败，API发布可用。不得reset其他工作。下一步发布本增量到同PR211、核对新tree/来源、同步Issue和本人STATUS；不自动合并，Projects无操作接口待维护者同步。

---

# Issue210交接

- 负责人：rayggxia。Issue210；分支task/210-tlm-component-audit；目标main；不自动合并。
- 工作目录：C:/Users/86134/Documents/a_P_BIT/tmp/tlm-breakdown-issue210-20261029；独立稀疏worktree，保留原jieruiz目录只读。
- 原main：787489192ebfcdb61ad72edde406818f450aa3dc；原PR192科学head：91f68416acad0e8306b920b1b8ac779f3d24ad98。
- 已本地完成：architecture_tlm/component_budget_audit_20261029，Word/中文Markdown/CSV/JSON/复算脚本/原输入与交付SHA。没有改算法、TLM时序、原封存、台账run或其他成员STATUS。
- 验证：6项闭合、4×3旧情景精确复算、原8会计单测、6页Word视觉QA；没有新GPU/EDA/TLM运行。
- 结论：57.445385ms；已价片上144.544740mJ/2.516212W；raw192.738839mm²，0.81后156.118460mm²。能量MAC48.10%、FFN计数恢复34.72%、片存14.74%。外存6.166W仅旧代理。
- 原screen_pv用准确Softmax未用Ising。PRNG与比较器合并；转换/CIM外围/CTS与HBM仍有未价项，详见ACCOUNTING_GAPS.csv。
- 已发布PR211，open/待审、未合并；科学提交346f5ca9761ed650a06313c91475474ca56e51fd，19个blob SHA与index一致，两JSON回读原文一致，详见PUBLICATION.json。DOCX连接器不支持独立二进制回读，未冒称下载核验。
- 下一步：按PR211审阅意见更新同一任务，不自动合并或重跑健康实验；Issue210已同步，等待验收。CLI fetch因Connection reset失败，本地HEAD仍main基线，index为已发布文件及本回执；远端交付未因此失败。网络恢复后先核对index与PR tree再对齐自己的分支，不直接reset或覆盖其他工作。
- Projects：当前GitHub连接器没有Projects操作接口，尚未同步看板；不声称缺少已核实权限或看板已更新。
- 无本任务运行中作业，不需要定时回查；PR待审保留此最小工作目录，合并后按生命周期规则归档索引再回收。
