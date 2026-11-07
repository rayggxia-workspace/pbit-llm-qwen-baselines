## 2026-11-07 Issue225：Attention资源候选接入审计与面积

用户要求核对新Attention可否接入TLM及面积。已读取198最新resource_compaction/resource_rtl交接，combined32为PV128＋归约32＋普通640池借512做QK，100MHz/1216KiB。宏接口可接，新增attention_candidate_20261107/integrate.py显式适配，并修正继承executed_resources仍报512QK/512PV/128归约的旧资源账本。9项本地检查、原模块10个原生报告SHA复核通过；没有新任务/RTL/PT/PPL或候选完整整机运行，不改正式默认。

按旧已标定组件价，整机覆盖52.621712→41.463021mm²，省11.158691／21.2055%；独立QK省7.835847、PV净省2.432451、归约省.890392。PV16KiB状态保留、2KiB暂存计入，全部1216KiB SRAM保留；模块19.126924含普通池＋672KiB，不误当整个芯片，普通池不重复计价。

PV4新RTL通过但门级首帧X未解决，失败DC0.085667mm²/头未用于正式价；QK共享切片门级过，但真实K重排/供数尚未native集成，新mux/route/PV状态选路门控PPA未知。因此41.46是可用架构候选预算，不是新硬件验收；正式当前参考52.62仍保留。原模块首层至O+5.77%、冷head+4.85%，不能当整token百分比。TT250普通池320不能照搬借512映射。

同时收齐昨日本人38617087完整两项：旧Attention、1216KiB/640下T64/64为51.43301ms含头、7.07502头、44.35799扣头；T8/32为51.40648/7.07546/44.33102。RESULT/SEAL/冻结源核验，8个prefix/full原件逐字节归档project_archives/sampling_latency225_20261106/native。完成态覆盖旧RUNNING及外推；不重跑。新完整T64profile快估T8=51.38117ms，单点差−.02531ms/−.0492%，非通用精度承诺；不含本次新Attention候选。

正式architecture_tlm/attention_candidate_20261107/README_ZH.md及INPUTS/RESULTS；sampling_latency_20261106/COMPLETED_RESULTS_ZH.md/JSON和COMPLETED_CURRENT_PROFILE/CHECK登记完成结果。接续Issue225/PR248、同工作目录；交接work/rayggxia/225/attention_candidate_20261107/HANDOFF.md，源发布以PUBLICATION.json为准，Projects待维护者同步，PR不自动合并。198原件和运行任务只读，不接管PV X/许可证修复。

---

