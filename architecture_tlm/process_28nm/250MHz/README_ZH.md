# 28nm / 250MHz TLM当前入口

[最新结果、成本边界与验证](UPDATED_TLM_20261109_ZH.md)。配置权威为BINDINGS.json＋WHOLE_CONFIG.json，COMPONENTS用于展示。更新命令：`python -X utf8 -B architecture_tlm/process_28nm/refresh250.py --workspace <a_P_BIT绝对路径>`；验证：同目录test_refresh250.py。旧prepare_bindings.py不会覆盖已更新默认。

概率主线：3共享FFN核、GU16/Wd32、K128/S64、S12优先分数前端、832KiB/178宏；500MHz和55nm独立。run_whole.py仍支持完整36层/完整head命令，必须指定新的输出目录。当前完整token表是明确外推，不能当作已执行整机。预更新配置/价卡保留PRE_REFRESH，旧任务只按其封存SHA恢复。

[完整Qwen原生外存任务已提交](FULL_RUN_20261110_ZH.md)；[数字对照需确认的接口与分工](DIGITAL_BASELINE_COORDINATION_20261110_ZH.md)。
