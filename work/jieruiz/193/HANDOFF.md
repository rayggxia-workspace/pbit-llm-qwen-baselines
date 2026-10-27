# Issue193校准v2交接

负责人jieruiz，task/193-calibration-v2，基线main d83eeb1f；关联Issue107/133/186。目录tmp/calibration-v2-issue193-20261027。新计数器/数字/门控与通用flow已本地完成；上传状态见PUBLICATION.json，无回执时不能称已上传。不要合并PR。

入口architecture_tlm/calibration_v2_20261027/RUN_FIRST_ZH.md；DELIVERY.json记录源码提交、交付ZIP和原字节SHA。计数16配置128帧等价，数字24配置22245事务，ICG功能/拒绝映射、31flow测试通过；功耗bench具体条数和原始摘要见包内results。全部仅功能，无新EDA/500MHz/PT/PPL，没有修改TLM默认。

用户暂不知道ICG单元，先使用可配置映射接口；g0可先校准，g2必须填写实库，g1仅仿真。当前计数立即按valid门控，不等同旧TLM idle8/wake1。单M数据组ICG扇出/缓冲/CTS未标定。数字CE不等同ICG。

计数先按固定2幂档位对齐再合并树，精确输出已对齐sum；旧多桶restore不能直接接、不能重复移位。B4输出26位、B7输出33位；六/三级流水支持事件II1，但整帧需要64/128样本与排空，不是帧II1。数字单状态反馈II15，16独立context轮转II1、最终跨context归约未含。MAC非融合，DAZ/RNE后FTZ，不能称GPU FMA完全相同。

下一步：用户填写工艺私有library JSON，先B4/M1/g0/100MHz连续+idle与BF16 MAC连续+idle，回传面积/时序/功耗/覆盖/告警/源SHA。再B7/M8和三级流水，最后实ICG与250/500MHz。缺ICG不阻塞g0，不擅自跑许可EDA或重复旧任务。将实测登记同一台账后再改TLM计价和周期。

主仓库尚无完整台账，当前PR仅新增本run；根聚合记录保留。根长期记忆还有其他更晚/未公开任务，本轮只同步新增段，不覆盖历史、不把整个根文件抄进公开分支。Projects沿既有权限缺口待维护者同步。raw helper证据在project_archives/calibration_v2_issue193_20261027，清理见HELPER_RECOVERY.json。
