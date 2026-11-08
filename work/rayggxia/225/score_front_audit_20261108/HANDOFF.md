# Attention分数前端成本审计交接

2026-11-08，Issue225 / PR249，rayggxia，task/225-tlm-unified250-20261107，base task/225-norm-stream-20261106；关联Issue198/PR199，只读owner源码/结果，不接管或修改其文件。

用户要求把S12先量化与FP32先差的功耗面积区别写一份文件给其他对话。正式入口architecture_tlm/module_handoff/attention_score_front_compare_20261108/HANDOFF_ZH.md；13来源SHA、机读事实与单位核验随同目录，根阅读镜像同字节。

结论：A第二步只是整数饱和，不是二次浮点转换。已有S12独立SS100前布局面积.015050059mm²、.166291667nJ/query/65拍；不含LUT/随机/输入SRAM。B是宏，并非已测FP32前端；FP32比较不能套ADD，FP32差→U8可做融合专用实现但需核数值等价。两者存储组织/流水/原准备资源/多份proxy价卡/采样轨迹还未公平拆清。当前同宽前端预算复用不能证明同成本。文档给出对方最小配对工作，无新硬件/模型仿真。

仅分析建议保留S12证据参考，用户未在本轮授权切换默认。本轮没有改当前100/250或28nm准备profile、38629485/38631668冻结快照/健康任务；没有新TLM/RTL/PT/GPU/PPL，不新增虚构电路run。未来若写新RTL/PT交由Attention任务，台账登记对应实测边界。

公开范围：正式四文件、本交接、构建/交付辅助和本人STATUS；私有源码/报告/PDK仅留SHA索引。发布/回读以PUBLICATION.json为准，PR249保持draft/open/unmerged，Issue225/PR199同步关联；Projects待维护者同步。本地Git HEAD可能落后连接器发布的远端头，先核PR249，禁止reset或覆盖其它staging。
