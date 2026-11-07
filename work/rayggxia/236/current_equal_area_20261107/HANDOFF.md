# Issue236 / PR244：当前两频率数字基线准备

负责人rayggxia，2026-11-07；本地复用task/236-fair-digital-20261105 / tmp/digital-fair-issue236-20261105；公开PR244实际head为task/236-time-ledger-recovery-20261105，base main。远端起点98a781294bdf747ec0e0d30ec03011df32f835bc；本地原82fd18ed仅是历史checkout状态，采用限定文件Git tree发布，不推本地私有历史。旧原件/运行快照不改。本人STATUS采用最新远端作为旧段，再加本轮进度；旧本地已提交状态可从Git恢复。

完成：equal_area_100_250_20261107的TARGETS/WORKLOAD_AUDIT/PLAN、面积配额器与4项测试；唯一模块需求文件module_handoff/DIGITAL_BASELINES_100_250_NEXT_ZH_20261107.md。三数字方案×两频率均pending，未算新数字延迟/能量。当前两版概率默认不改。来源SHA在TARGETS及SOURCE_MANIFEST；没有新电路/PPL/整机TLM作业，旧任务不重交。

恢复先查Issue236/PR244及198/204最新交接。将模块需求文件交给现有模块对话，等待实际profile/adapter；不要伪造旧2.5MiB配置已适配1088/960KiB。模块可先用宏合同补接口，已有PPA尽量复用；250条件面积随合格概率核价重算。

本地验证：python -B architecture_tlm/equal_area_100_250_20261107/test_planner.py -v；planner.py --out <新JSON>。4测试及实际CLI六pending case生成通过。给--modules时先核实账本角色、共享资源ID、合法大小、时钟/容量和真实执行入口；allocate只是配额，不能把allocated_not_executed当完成回放。

下一步由宿主合并bundle、逐个实例核对计费/存储、解析单层后原生Slurm完整36层。是否补BF16/W8码域质量对照另列，不在本轮启动训练。上传状态见PUBLICATION.json；PR未合并、Issue仍open，Projects待维护者同步。
