已发布：草稿PR199（https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/199），科学提交5fad0fc32f5284560c38c03f4fe28657f936f553；7关键文件远端逐字回读、完整Git tree和本地相同SHA导入通过。Issue198评论6443236705；待审未合并，广泛验收仍开放。PUBLICATION.json为准确回执。

# rayggxia 当前Attention任务

更新时间：2026-10-27；负责人rayggxia（GitHub连接器已认证）。

- Issue：[198](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/198)；分支task/198-attention-compare；PR base main@d83eeb1fc6b89a3dff51b5b62bf79acf665c7166。工作目录C:/Users/86134/Documents/a_P_BIT/tmp/attention-compare-issue198-20261027。
- 第一阶段本地完成：六方案单query数值/有限tile宏调度、完整外供bit拒绝控制RTL。正式入口architecture_tlm/attention_compare_20261027/README_ZH.md。
- 实际验证：6项机制检查；108三seed合成案例；72项合成质量预算探索；N16/64/512三seed9案例22500拍逐周期oracle全等。没有模型/PPL、GPU/Slurm、综合/STA/PT。
- 质量探索：2K/d128以完整IID128解析MSE为阈值，P3/P4观察须S512；条件117264/22181拍，D033586。合成输入、三seed均值、宏参数，不是实际芯片或模型验收；拒绝较慢保留。完整能耗面积null。
- 原始结果/事件/bit轨迹及旧失败共399成员，5.31MB ZIP在project_archives/attention_compare_issue198_20261027；路径/逐成员SHA见work/rayggxia/198/RAW_ARCHIVE.json。Git只放小索引/汇总。中央台账新增一run，79联合check/render通过；根镜像增量同步见READING_SYNC.json。
- 上传与PR状态以本任务PUBLICATION.json和最新远端为准；待审不自动合并/关闭。Projects权限未核实，待维护者同步。
- 尚未完成：RTL时序绑定PR88源/配置合同；D1成熟整数/ITA移植、赢家RTL及完整V链、GQA调度、后训练真实QKV/BF16匹配、代表STA/PT与同质量PPA。首轮不会接管186/95/193或恢复暂停116/123。
- 下一步：按HANDOFF的可执行入口继续；复用本目录，不重复历史GPU或健康作业。此分支main无既有rayggxia STATUS，其他任务状态留原分支只读，未覆盖其他成员。
