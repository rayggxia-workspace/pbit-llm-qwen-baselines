## 2026-10-26 Issue186 / PR192：500MHz扩资源与门控完整12项

负责人jieruiz；task/186-local-pipeline，base main d83eeb1f；本地tmp/ffn-local-pipeline-issue186-20261025。CPU Slurm3124全部12项completed，执行64e0cf8a、后处理4ca97270；110统一回归＋32机制/PPA测试、36层、原件SHA、动作流量/门控寿命守恒通过。没有新PPL/RTL/PT/500MHz STA；不自动合并PR。
500MHz只提频157.595ms；再单独扩计算143.956、单独扩SRAM76.750、两者并扩NL64=63.134ms。GU64/NL128三seed：不门控64.411ms，门控64.526ms(+0.178%)；同存储普通BF16准确110.012→110.157ms。主候选32×64×64 SC、2048MAC/拍、桶256/恢复64/累加128、8MiB E宏512bank/512GBs，SRAM仍80MHz/HBM固定时序；注意力本轮仍screen_pv，未重跑Ising。
门控保留状态、idle8拍关闭/请求1拍唤醒，存储/随机/配置总线除外。新Issue193计数M1=一个输出，32阵列2048输出；B7/M8面积复制后counter209.803mm²，已知单元+宏小计279.637mm²，不是全片面积。100MHz动态/泄漏拆分，500MHz外推，默认关钟时段80%idle动态可消除：已计价27.34→8.41W，1.761→0.543J/token；ICG/CTS/HBM/数字阵列idle及面积/本地CIM等未知。旧100MHz/NL64未门控约0.476J/1.55W/93mm²仅工程预算；提速不自动减少能量，且新旧采样数不同。完整PPA null。
成果architecture_tlm/clock500_resource_20261026/RESULTS_ZH.md、COMPARISON.json、PPA_ANCHORS.json；记录本O15；回执work/jieruiz/186/CLOCK500_{SUBMISSION,COLLECTION,VALIDATION}.json。功耗原件POWER_RESULT SHA7e554296…10d59已关联统一台账power-recovery，现73条schema通过，无重复run。
发布状态以CLOCK500_PUBLICATION.json为准；该文件生成并远端回读前只算本地完成。Projects缺read:project待维护者同步。恢复先核Issue/PR/HANDOFF，不重跑健康/完成任务，未价成本不能当零；下一步实现并测500MHz流水线/ICG，优化巨大计数结构与HBM供数。

## 可执行恢复
1. 核最新Issue186/PR192、身份jieruiz、workspace org remote。
2. 新执行源码冻结64e0cf8a；旧3074和新3124均已完成，不能修改其source或重提交健康任务。后处理代码4ca97270及自身SHA和输入SHA在PPA_ESTIMATE里。
3. 运行 python -m architecture_tlm.clock500_resource_20261026.analyze 验证/复算已有12项；不需要GPU或DRAMSys重跑。collector仅在需要重新核远端原件SHA时使用。
4. 12份结果原件/DRAM轨迹在CLOCK500_SUBMISSION指定个人远端。Git仅提交各CASE summary/execution/manifest和派生PPA；本地包可在发布核验后按sha删除，保留source清单和回执。
5. 原Power报告属于Issue193，中央台账已有同次记录。本PR提供脱敏参数索引，不能覆盖其他分支registry或声称已把未发布record合入main。
6. 500MHz、ICG、B7功耗、CIM全并行读出、MAC局部TB/s端口仍待物理验证。门控面积/CTS和HBM功率不为0。不能用BF16代理小计和实测counter价格声称公平整机能效优越。
