## 2026-11-09 SRAM缩减分工明确，832KiB两频小配对已由宿主确认

Issue225/PR249，rayggxia。用户无需先找其他对话；激活128→96KiB、八Attention48→36KiB均由宿主实现并实减bank240→208，前端144→136/Attention96→72。Qwen3-4B/B1/2K/K128/S64/GU16/Wd32，250三核两层+384head、500两核一层+384head，四case同冻源7a3335833c8f、单进程顺序完成。250原2.205336→2.208844ms(+0.1591%)，500原.996176→0.997122ms(+0.0950%)；不是完整token时间。

四SEAL/SHA、实际容量/端口/边界/排空、核帧/转换/尺度/采样/算术及外存字节/地址摘要配对通过；SRAM读量和bank冲突按实际调度保留。宏面积少.380164mm²；无15%面积口径下的28nm250/500容量预算6.758447/6.784987mm²，未把小流程周期变化外推为完整token。现默认960KiB不自动切换；55nm/其它模型/长上下文/原生LPDDR/完整36层未在本轮验证，无新RTL/PT/PPL。

正式process_28nm/SRAM832_VALIDATION_20261109_ZH.md/json、可选candidate_sram.py；对接清单module_handoff/SRAM_REDUCTION_COORDINATION_ZH_20261109.md。后续CIM驻留32→16槽/内外存归属向FFN确认；Attention只在推广其他配置时补最大活跃数据约定；S0已有数据，不需重跑SRAM PT。发布看本work/PUBLICATION，PR待审未合并，Projects待同步。

恢复：读PLAN与四SEAL，不重跑健康或已封存case。下一步如采用832，另做完整token/原生及55频率回放；当前无需将任务转给其他对话。
