2026-10-28 普通数字Softmax调研完成：512输入公开FP16/DW/P8为199拍/45nm 0.283300mm²；fixed32/LUT/P1/2/4为1542/775/392拍、0.059/0.085/0.138mm²（NOREG，外部存储另计）。65nm小定点核与FP精度/边界不同；不据跨工艺文献宣称Ising胜出。正式SURVEY/SOURCES记录PDF SHA、页面/代码pin、失败与算术；私有原件已逐SHA归档。无新RTL/EDA/模型或registry run、无运行作业；上传状态见SOFTMAX_PUBLICATION.json。下一步同SHARK库实现明确精度/缓冲的数字及CDF采样对手，本轮未启动。Projects待维护者同步，PR199待审未合并。

发布确认（2026-10-28）：Attention服务器DC/VCS/PT已推送草稿PR199，源2c4e4bafb74d41779bbaff78e346d0800172bcc8，39文件完整tree及7关键文件逐字读回、本地同SHA通过。Issue198评论6460241999，未合并；8DC/116回放/66PT，hold违例与PWR-981保留。81联合台账，1662报告/72诊断成员SHA已核，原始大包仅服务器，本任务无运行作业。回执work/rayggxia/198/EDA_PUBLICATION.json。

2026-10-28服务器评估已完成：8DC/116VCS回放230400拍/66PT窗口及8top时序审计，所有hold违例，PWR-981保留；无签核/模型结论。主候选G16融合折算0.035969mm²、全1控制17.17pJ/输出。准确结果RESULTS_ZH.md，源/作业/原件EDA_*；原始私有大包仅服务器。本地报告包逐成员SHA与72诊断成员已核；上传见EDA_PUBLICATION.json，PR199待审。下一步IO/reset合同/hold/标注，无需重跑健康原任务。

## 2026-10-28 EDA服务器测试进行中

用户明确授权本任务EDA实测；延续PR199/task198，不接管pbit整片任务。已通过现有客户端验证登录、库SHA与本地一致；私有连接/库/模型位置仅在.eda_private。DC预检38437604因拒绝RTL先引用后声明coin_mask失败；仅调整声明顺序，新20项/90000拍独立oracle通过，旧快照保留。修正预检38437625完成，G16p2 setup约+0.44ns、hold约−0.02ns，不能称时序通过。其余DC矩阵38437668（7项，%2）及VCS/PT预检38437709/矩阵38437736已提交。SS1.08V125C/100MHz、输入slew0.1ns/输出0.02pF、setup uncertainty2ns/hold0.1ns；无SPEF/CTS/SDF。原始面积×0.81另报55nm折算，功耗时序不缩放。长任务均Slurm，已冻结v1/v2/v3且逐SHA校验；真实状态以后续收集回执为准。不得重复提交健康任务。

发布确认（2026-10-27）：完整Attention反馈/仲裁v2已推送草稿PR199，源7fe360390c01de5195e504094f36ee62735b02be；56文件完整tree与本地同SHA、7关键文件逐字读回通过。Issue198评论6445525003；待审未合并，STA/PT及后训练/全V链仍待后续，无运行中任务。准确回执work/rayggxia/198/CONTROL_PUBLICATION.json。

2026-10-27 控制v2本地完成，上传状态见CONTROL_PUBLICATION.json（尚未生成即未确认发布）。完整赢家/拒绝反馈仲裁RTL、8固定PPA top、独立oracle/数学检查、DC/PT脚本在control_v2。124RTL项422800拍及3个cap64零延迟门级1920拍通过，8个55nm SS映射0.018058–0.056112mm²；STA/功耗未跑，不把TB100MHz当时序通过。源码/原字节/公开包/台账/记忆同步见CONTROL_*。保留G16融合/两级及G32候选待STA；源供给/完整V链/后训练QKV/GQA/D1仍待补。无运行中GPU/Slurm/许可EDA作业；PR199草稿、未合并。

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

控制v2原始目录已逐SHA归档后回收，释放629349369字节；保留最终小汇总与PPA源bundle。重现report.py需从CONTROL_RAW_ARCHIVE.json所指ZIP恢复对应results成员；逐成员SHA必须一致。CONTROL_CLEANUP.json记录范围，未删除其他任务/共享库。
