# Issue220交接

负责人rayggxia，2026-10-31。目标rayggxia-workspace/pbit-llm-qwen-baselines；远端task/220-attention-ten-case-plan基于main@7d42c7d30fa9c729c899ba7f815332dd6ed5671a。本地隔离稀疏目录tmp/attention-ten-case-plan-issue220-20261031，从可用本地787489192ebfcdb61ad72edde406818f450aa3dc建立；API发布时必须以真实远端main为父、仅加入本任务文件，不覆盖其他变更，不force-push。

用户确定10种概率方案、P8/8位sigmoid入口、传统稠密逐节点Gibbs。训练范围由用户委托判断，本方案建议只训练36层QKV/O（943718400权重）、其余冻结；新增两条同范围数字控制。内部12位分数、非正U8/F4地址、kappa24、固定burn/spacing、100M上限和准确前缀/概率后缀为本方案建议，已明确区分用户确认与设计选择。

成果入口qwen3/training/attention_ten_case_20261031/REMOTE_AGENT_PLAN_ZH.md；机器CASES.json、NUMERIC_TABLES.json、NUMERICS_ZH.md、validate_plan.py和SOURCES.json。只验证清单与数值合同；没有新增训练器、传统Gibbs实际实现、模型PPL、RTL或PPA，未提交Slurm。

恢复先核Issue220/PR、现有138/159/198及个人STATUS。执行Agent需继承上一轮实际optimizer/LR/data配方并展开SHA锁定；当前报告没有这些源配置，不伪造。需实现共同有限位前向、Gibbs离散oracle/代理梯度、suffix训练、参数审计/导出；CPU及GPU门禁通过后才能长训。不要接管或重跑其他任务。

发布状态和PR链接见PUBLICATION.json。本任务PR不自动合并，不关闭Issue；项目看板若工具不支持写入则待维护者同步。大权重和数据不在本目录，未改变服务器任务或节点交接状态。

发布回执：科学提交a9474b62a622ed3c24d3763740cf2215cca70ce0；PR221已创建、open未合并；14个科学交付文件内容已逐一从GitHub读回一致。后续回执提交不代表新实验。Projects待维护者同步。
