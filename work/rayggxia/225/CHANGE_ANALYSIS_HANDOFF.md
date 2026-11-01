# Issue225变化分项与下模块建议（2026-11-01）

同PR226/task/225-module-estimate/owner rayggxia。原初估RESULTS/INPUTS不变；新增NEXT_MODULE_ZH、analyze_changes、ANALYSIS_INPUTS及CHANGE_ANALYSIS。重核五组分项守恒，FFN计数/恢复49.97→34.20–37.07mJ，保留GU仍30.63–31.13mJ，是下一电路模块优先目标。共享MAC降低主要是背景随时长下降，存储21.30mJ基本未变。时延改善来自8KV组服务并行假设，FFN阶段25.21→25.21–26.63ms没有变快。

发现新Attention只有活动核价，既有GF64开钟idle可补，不是缺PPA：0.087–0.090mJ敏感性，不改74–78mJ量级。旧GU池仍保留而新Wd核另加，面积未公平；硬件k128/F4/burn0与训练k256差分P8也未统一。建议下一RTL为GU 64x8/T64集成核并核共享PoT/跨K/量化/ICG合同；时间结论需统一DDR/SRAM后端接入，未自动启动任何工作。

本轮只审计和建议，无新TLM/DRAMSys/EDA/PPL/run，不修改registry。实际上传状态见CHANGE_ANALYSIS_PUBLICATION.json。Projects待维护者同步，不自动合并。原宽历史与两个未发布模块包不重传。
