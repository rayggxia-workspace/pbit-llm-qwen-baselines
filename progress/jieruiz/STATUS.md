# jieruiz 项目进度

更新时间：2026-10-17（Asia/Shanghai）；已核验GitHub实际登录 jieruiz。

| 项目 | 当前状态 |
|---|---|
| 当前任务 | [Issue #12](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/12)，LLaMA-1 7B 当前标准 TLM |
| 负责人 / 正式仓库 | @jieruiz；rayggxia-workspace/pbit-llm-qwen-baselines |
| 分支 / PR base | task/12-llama7b-tlm → pbit-tlm-attention-details-20261016 |
| Base | 9608c0d06cf8b421cbbd348aca4fc84c5990aae7 |
| 独立目录 | a_P_BIT/tmp/llama7b-tlm-issue12-20261017/ |
| 当前阶段 | 全部82项结果及代码已推送；[PR #13](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/13) 待审，未合并 |
| 执行源码 | 84c131951b9ce69a52778e8725d62a21ab9cc40f；不可变tlm_84c131951b9c快照 |
| 已完成 | 真实BF16捕获1877逐位一致；1878全部60项Link、1879全部18项Staggered、1896全部4项NoPowerDown完成；18项本地检查及82项后处理闭合通过 |
| 运行中 | 无本任务运行中作业；服务器未启用sacct，依据完整结果和squeue核查 |
| 成果位置 | architecture_tlm/llama7b/；服务器 /home/Hongjie_Zeng/projects/pbit-llama7b-tlm-20261017-issue12/ |
| 数值边界 | 单公开WT2窗口真实BF16 QK作为地址oracle；随机FFN/比例PV/新max4/Ising宏没有新PPL |
| 待同步 | Issue验收清单与PR已同步；Projects缺read:project，看板待权限补齐 |
| 下一步 | 评审PR #13；后续新架构或PPL任务使用新Issue/分支/快照，不重复提交旧作业 |

此前治理#1/PR#2、架构审计#3/PR#4、DRAM#5/PR#6、FFN#7/PR#8及#11、筛选K流量#9/PR#10仍为各自独立待审分支。本任务没有覆盖其工作树。
