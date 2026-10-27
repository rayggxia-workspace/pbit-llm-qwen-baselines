# jieruiz当前进度

更新2026-10-27；负责人jieruiz；Issue193，关联107/133/186；分支task/193-calibration-v2，PR发布状态见work/jieruiz/193/PUBLICATION.json；base main d83eeb1f；独立目录tmp/calibration-v2-issue193-20261027。

本地已完成新精确计数器、可配置实库ICG接口、真正流水的BF16/FP32数字代表核及DC/VCS/PT脚本。16计数配置128帧、24数字配置22245事务、31flow测试和ICG功能门禁通过。完整结果与SHA见architecture_tlm/calibration_v2_20261027和work/jieruiz/193/DELIVERY.json。没有新综合/STA/PT、500MHz达标或PPL；未改TLM默认，未合并。

待用户工艺仿真：g0可先跑，g2需要实际库单元映射；缺失PPA和ICG信息不是零成本。下一步按RUN_FIRST_ZH.md跑代表性100MHz并回传，检查关键路径后再250/500MHz与门控。exp/recip/rsqrt、完整向量链、CIM/时钟树、真实模型数值闭环仍在原待办。Projects待维护者同步。可执行交接见work/jieruiz/193/HANDOFF.md。
