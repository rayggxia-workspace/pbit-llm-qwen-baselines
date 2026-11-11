## 2026-11-08 用户决定：小前端成本缺口先沿用，不阻塞现有任务

当前FP32→S12/握手尚未独立拆净的增量PPA可以先用宏预算；已完成结果保留，健康任务继续，不因本项重跑PPL/训练/全TLM。以整个实测A作偏大的额外情景（非严格物理上界），100/250MHz面积.131731/.076112mm²，占当前覆盖.396%/.345%；全程工作逻辑压力计入输入读约占整机能量.061%/.115%。全部服务额外串行.7488/.308736ms，按现8/4实例均摊.0936/.077184ms，非集成延时保证。当前已经有前端非零预留，不再叠加整块A。

正式local_integration_A/PROVISIONAL_USE_ZH.md和PROVISIONAL_BUDGET.json，数值路径A仍S12/F4→整数max-gap→U8/P8；冻结较宽前端时序/成本＋S12地址轨迹的组合标签保留。ready=false只表示未整链PPA，不再作为禁止宏级评估的门槛；不宣称B继承A的PPL。没有改默认/冻结源码或重跑健康任务。另有245残差地址执行bug独立修复，不混为成本近似。发布见PROVISIONAL_PUBLICATION，PR249未合并，Projects待同步。

---

## 本地A适配器消费（2026-11-08）

补充源来自根local_integration_A，已25输入SHA核验并在adapter_review_runtime隔离复跑，VALIDATION与提供方字节一致。正式原4文件及复核REVIEW/INTAKE已收录，父交接保留侧对话新增入口。数值ready，全链PPA仍false；不改默认/冻结任务，不重复GPU/EDA。发布看LOCAL_ADAPTER_PUBLICATION；新CPU日志及ADAPTER_REVIEW保留，本机root/任务目录更新同字节。

## 新PPA消费补充（2026-11-08）

当前PPL明确对应A=s12_max_gap，后续主线应显式传A；提供方forward/card默认B不是PPL配置。新版四张独立前端价卡已核，旧“B仅宏价”历史结论已更新；完整采样器去重尚未ready，不改冻结运行。正式HANDOFF/AUDIT_FACTS/SOURCE_INDEX/VALIDATION同步；不重复producer测试或原始归档全审计。

# Attention分数前端成本审计交接

2026-11-08，Issue225 / PR249，rayggxia，task/225-tlm-unified250-20261107，base task/225-norm-stream-20261106；关联Issue198/PR199，只读owner源码/结果，不接管或修改其文件。

用户要求把S12先量化与FP32先差的功耗面积区别写一份文件给其他对话。正式入口architecture_tlm/module_handoff/attention_score_front_compare_20261108/HANDOFF_ZH.md；13来源SHA、机读事实与单位核验随同目录，根阅读镜像同字节。

结论：A第二步只是整数饱和，不是二次浮点转换。已有S12独立SS100前布局面积.015050059mm²、.166291667nJ/query/65拍；不含LUT/随机/输入SRAM。B是宏，并非已测FP32前端；FP32比较不能套ADD，FP32差→U8可做融合专用实现但需核数值等价。两者存储组织/流水/原准备资源/多份proxy价卡/采样轨迹还未公平拆清。当前同宽前端预算复用不能证明同成本。文档给出对方最小配对工作，无新硬件/模型仿真。

仅分析建议保留S12证据参考，用户未在本轮授权切换默认。本轮没有改当前100/250或28nm准备profile、38629485/38631668冻结快照/健康任务；没有新TLM/RTL/PT/GPU/PPL，不新增虚构电路run。未来若写新RTL/PT交由Attention任务，台账登记对应实测边界。

公开范围：正式四文件、本交接、构建/交付辅助和本人STATUS；私有源码/报告/PDK仅留SHA索引。发布/回读以PUBLICATION.json为准，PR249保持draft/open/unmerged，Issue225/PR199同步关联；Projects待维护者同步。本地Git HEAD可能落后连接器发布的远端头，先核PR249，禁止reset或覆盖其它staging。
