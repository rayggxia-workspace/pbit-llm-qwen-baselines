# Issue225 / PR249：250面积机会与实现证据审查

负责人rayggxia，task/225-tlm-unified250-20261107，独立目录tmp/tlm-unified250-issue225-20261107；远端基线18c6e912a51c7ea7e780a48d537116a7c770160b。资源和容量维持当前3核/256FMA/PV64/r16/16KiB入口/1216KiB，不运行新TLM/EDA/GPU作业，不改204/198源码或健康/封存任务。

交付250MHz/AREA_AUDIT_ZH.md及JSON：真实遗漏是投影32KiB最大tile仍用2×80KiB槽，另列历史DMA SRAM32KiB、Attention48KiB/组和2核候选。缩容量数字只作预算；实际删bank会改前端176→144等端口/冲突，不把它说成无损新默认。2核和192FMA的利弊、格式旧代理及已接入改动分开说明。

更正过期证据：204最新profile为SS100_READY_TT250_TIMING_FAIL，381成员验收由上游完成，本轮整TT250归档SHA复验通过。setup−0.421007ns，失败映射面积1.498438mm²仅诊断。共用FFN_PROFILE更新版本250的provisional证据，bindings有效core仍null，注入失败core的负向测试拒绝；100价仍有效。250 model/pricing输出物理250实现未闭合，不强行应用失败面积/能耗、不降频或改周期。旧DMA16/REFRESH原件及SHA保留，不重写历史pending字段。

检查：默认构造仍1216KiB/304bank/16KiB，3核假设不变；新元数据为timing_failed；对旧完成RESULT重新计价保持22.5947725参考、有效短T能量null；源码/原件及新报告在SOURCE_MANIFEST/EVIDENCE/VALIDATION。没有新数字电路台账run。

下一步若用户选择容量方案，先做两投影槽32KiB＋回收32KiB历史预留的真实地址布局/时间配对，再做Attention48KiB；204负责FFN门限加载侧修复。不得把area-only的20.87作为可运行250MHz芯片面积。公开状态见PUBLICATION.json，PR待审不合并，Projects待维护者同步。
