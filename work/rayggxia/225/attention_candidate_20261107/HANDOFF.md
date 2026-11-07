# 新Attention资源候选接入交接

2026-11-07，负责人rayggxia，Issue225/PR248，同task/225-norm-stream-20261106与工作目录。用户要求核对最新Attention修改能否接入TLM及面积减少。来源198/PR199本地resource_compaction与resource_rtl交接只读，不接管其PV X/许可证/TT250任务。

正式architecture_tlm/attention_candidate_20261107/README_ZH.md、integrate.py、estimate.py、INPUTS/RESULTS。宏级候选combined32：PV512→128、末端归约128→32、QK阶段借用普通池512/640，1216KiB/100MHz/T8-T32 FFN保持。当前普通共享池只计一份；全局52.621712→41.463021mm²（−11.158691／21.2055%），不是模块局部19.126924mm²。PV净省2.432451、归约.890392、独立QK7.835847。

已核真实宿主接口兼容，并修正继承executed_resources仍报告旧512QK/512PV/128reduce的账本错误。9项本地检查通过，原模块10个原生报告逐SHA核验。没有新GPU/EDA/PPL/RTL/PT或完整候选整机运行。新适配是显式opt-in，不改原宿主/其他对象/冻结源。

重要边界：PV4仅RTL通过，门级首帧X未解决，其0.085667mm²/头DC面积未用于估算；使用旧已标定组件拆减与2KiB暂存代理。QK共享FMA16门级通过，但实际SRAM K布局→接口供数未接通；新route/mux/PV状态选择门控增量PPA未测。因此41.46只作条件候选，不把默认52.62和旧时序直接替换成新芯片验收结果。

原模块首层至O605.30→640.21us（+5.77%）、冷lm_head7075.62→7419.06us（+4.85%），非整token。接法在首次事务前`integrate.install(model, owner_install,'combined32')`；owner原件不复制进Git，INPUTS绑定确切源SHA，外部需取得相同本地交接源码/runtime。

本轮还收齐昨日本人38617087两项完整宿主：T64/64含头51.43301、head7.07502、扣头44.35799ms；T8/32为51.40648、7.07546、44.33102ms。RESULT/SEAL和冻结源核验，8个原始prefix/full文件已归档project_archives/sampling_latency225_20261106/native。原Attention不变，不含本次资源候选。生成COMPLETED_CURRENT_PROFILE后快估T8=51.38117ms，单点误差−.02531ms／−.0492%，不作通用准确率保证。该完成态覆盖旧交接的RUNNING/两层外推，未重跑健康作业。

恢复先重读Issue225/PR248、本人STATUS及本交接；检查源SHA后可重跑check_integration.py和estimate.py。接下来应先由198闭合PV门级与单KV组真实QK供数，再做新整机时序/PPA；不能把已有宏级0us共享开销当免费布线。TT250若普通池320路需重分区，不套本映射。当前不提交新任务/自动化，原204/198任务不干预。

本地正式目录同字节镜像。源码公开/PR状态以PUBLICATION.json实际回执为准；不合并PR或关闭Issue，Projects无写接口待维护者同步。旧历史manifest保留，新增输入/验证和摘要独立记录。
