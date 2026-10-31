## 2026-10-31 Issue220：CR有界执行说明与可转发检验

用户要求明确修改CR并附检验给训练方。当前采用严格纯CR执行策略，不改概率律/P8/m/S或13组矩阵：每query/head总提议S×64，当前S128为8192；最后一轮恰好收齐算成功，否则归档并退出当前CR case、协调全部worker，其他case独立继续。不返回部分结果、不丢训练行、不隐式回退。上限保证成功或失败返回，不保证所有输入成功；不声称分布偏差已修复。

CASES仅增加执行/门禁状态字段，原11组、2控制、model/common/screening及采样数学参数逐对象保持。真实Qwen检验110592事件MC0超限/约214–222轮、P8归零约7%/2.95%、CR期望TV约10.4%/4.9%随报告附在CR_AGENT_REPLY_ZH.md。仅完成率/行级诊断，实际两更新及原10M阶段后再看训练质量。作为备选不阻塞赢家/数字对照。未新增GPU/训练/EDA或PPL，不重跑已完成3571/3572/3573。

正式入口qwen3/training/attention_ten_case_20261031/CR_AGENT_REPLY_ZH.md；同目录主方案/数值/复核/清单和校验器同步，父远端da2bbd276aeebe826d64deb59219c9bcae703ffb，复用Issue220/PR221/task/220-attention-ten-case-plan及本人原工作树。实际验证/发布见work/rayggxia/220/CR_GUIDANCE_VALIDATION.json和CR_GUIDANCE_PUBLICATION.json，PR待审未合并，Projects待维护者同步。

---

发布回执：V2科学提交33c7e6886623e453b338a611d1eb64763636dbfb已推送原PR221，13份修改逐内容读回一致；Issue220/PR221标题和当前矩阵已更新。PR仍open未合并。旧版本验证记录保留，不代表本次训练已执行，详细PUBLICATION_V2.json。

## 2026-10-31用户确认V2，覆盖下方历史十组口径

当前正式矩阵为11概率＋2数字控制：原10概率组的采样器/S/五对筛选对照全部保留，全部SparQ概率组和C_SPARQ候选改256，r32/local32不变；仅增加K_WH32（赢家保持S32，无N_WH32）。保留原S256，不采用此前6概率组精简/部署扫描替代训练的建议。

正式入口仍qwen3/training/attention_ten_case_20261031/REMOTE_AGENT_PLAN_ZH.md，详见REVISION_V2_ZH.md和CASES.json v2。模型/参数范围/教师/损失/预算/seed/数制/采样器规则未改。更新validate_plan.py及FILE_INDEX，验证结果见VALIDATION_V2.json，配置差异证据见REVISION_DIFF.json。历史VALIDATION/PUBLICATION/P8_REVIEW记录保留，不能称为本轮训练或256节点PPA。

目标仓库和rayggxia身份已核实，复用task/220-attention-ten-case-plan / PR221及本人独立目录；前远端head2b6dadb0、本地9dd73cff不同历史，API按真实远端父提交更新，不force。未启动新训练/评测/EDA；P8拒绝门禁仍保留。发布以PUBLICATION_V2.json为准；PR待审未合并，Projects缺写接口待维护者同步。

---

# Issue220交接

负责人rayggxia，2026-10-31。目标rayggxia-workspace/pbit-llm-qwen-baselines；远端task/220-attention-ten-case-plan基于main@7d42c7d30fa9c729c899ba7f815332dd6ed5671a。本地隔离稀疏目录tmp/attention-ten-case-plan-issue220-20261031，从可用本地787489192ebfcdb61ad72edde406818f450aa3dc建立；API发布时必须以真实远端main为父、仅加入本任务文件，不覆盖其他变更，不force-push。

用户确定10种概率方案、P8/8位sigmoid入口、传统稠密逐节点Gibbs。训练范围由用户委托判断，本方案建议只训练36层QKV/O（943718400权重）、其余冻结；新增两条同范围数字控制。内部12位分数、非正U8/F4地址、kappa24、固定burn/spacing、100M上限和准确前缀/概率后缀为本方案建议，已明确区分用户确认与设计选择。

成果入口qwen3/training/attention_ten_case_20261031/REMOTE_AGENT_PLAN_ZH.md；机器CASES.json、NUMERIC_TABLES.json、NUMERICS_ZH.md、validate_plan.py和SOURCES.json。只验证清单与数值合同；没有新增训练器、传统Gibbs实际实现、模型PPL、RTL或PPA，未提交Slurm。

恢复先核Issue220/PR、现有138/159/198及个人STATUS。执行Agent需继承上一轮实际optimizer/LR/data配方并展开SHA锁定；当前报告没有这些源配置，不伪造。需实现共同有限位前向、Gibbs离散oracle/代理梯度、suffix训练、参数审计/导出；CPU及GPU门禁通过后才能长训。不要接管或重跑其他任务。

发布状态和PR链接见PUBLICATION.json。本任务PR不自动合并，不关闭Issue；项目看板若工具不支持写入则待维护者同步。大权重和数据不在本目录，未改变服务器任务或节点交接状态。

发布回执：科学提交a9474b62a622ed3c24d3763740cf2215cca70ce0；PR221已创建、open未合并；14个科学交付文件内容已逐一从GitHub读回一致。后续回执提交不代表新实验。Projects待维护者同步。

2026-10-31进一步审阅：新增QUANTIZATION_HARDWARE_REVIEW_ZH.md、P8_REVIEW.json和p8_rejection_audit.py。P8在相对差值6.25后为0；N2048均匀行的校正拒绝期望55473.5提议/128地址，参考占比42.3155%，8192 cap几乎不完成。64事件MC交叉核对。N_CR128数值门禁未就绪，不改用户P8、十组或偷偷加cap。现有128硬件还需12位score、饱和差值、argmax/burn32和S256计数状态匹配。仅本地解析/接口审阅，无新LLM/GPU/RTL/PPA。
