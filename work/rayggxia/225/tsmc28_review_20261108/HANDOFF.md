# Issue225：28nm250MHz新结果消费端审阅

用户问44个功耗窗口收齐后TLM需调整什么。复用Issue225/PR249现有checkout与分支，负责人rayggxia；起始远端d8b6f1e2233c99ef70383c4ebe3dc25d1f7c5cb8，base依赖PR248不变，未接管Issue204源、结果或正在运行作业。

正式architecture_tlm/module_refresh_20261107/tsmc28_review_20261108包含REPORT_ZH.md、review.py及四份JSON。实际核3正式归档SHA、1715报告成员SHA；44窗口FFN8/BF1615/A921与原验证一致，A9 hold失败拒绝，28面积不乘.81。读POWER_RESULTS作当前数值源，不采用老profile全null占位。

独立候选仅注册FFN28（250MHz、18/34拍、72/136ns、0.373801302mm²，GU/Wd10.1625/9.254021pJ每DOT64、等待.6209mW）与BF16/FMA16/C4（.06245379mm²、3.304622pJ每FMA），default_enabled=false。未改变55nm100/250、模型/输入、seed/采样、健康冻结38629485、面积或能耗账本；没有新EDA/TLM/PPL任务。

固定既有55nm冷层工作量和窗口，FFN三核重计价47.339549→13.207242µJ，面积4.122186→1.121404mm²；这是组件对比，不是28nm整机。未知TIE功耗null、部分宏/wrapper边界保留，不能套低核价宣布全片降72%。500三项待收，A9只诊断。旧55v3与28不同电压/流水，差异不全归工艺。

恢复看正式SOURCE_INDEX/VALIDATION和本目录PUBLICATION，不需要重复1715成员审计。要建立28全片，再接其他模块28交接和存储成本，显式调18/34服务、重做数字同工艺/等面积预算，跑新单层门禁；不能改旧快照。当前用户仅要求审阅是否需调，不擅自覆盖55默认或发新整机任务。PR待审未合并，Projects待维护者同步。
