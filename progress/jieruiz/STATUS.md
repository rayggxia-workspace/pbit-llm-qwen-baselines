# jieruiz 项目进度

更新时间：2026-10-17（Asia/Shanghai）；已核验GitHub实际登录 jieruiz。

| 项目 | 当前状态 |
|---|---|
| 当前任务 | [Issue #12](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/12)，LLaMA-1 7B 当前标准 TLM |
| 负责人 / 正式仓库 | @jieruiz；rayggxia-workspace/pbit-llm-qwen-baselines |
| 分支 / PR base | task/12-llama7b-tlm → pbit-tlm-attention-details-20261016 |
| Base | 9608c0d06cf8b421cbbd348aca4fc84c5990aae7 |
| 独立目录 | a_P_BIT/tmp/llama7b-tlm-issue12-20261017/ |
| 当前阶段 | 已推送；[PR #13](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/13) 草稿；Slurm完整DRAMSys运行中，尚未作为全部完成发布 |
| 执行源码 | 84c131951b9ce69a52778e8725d62a21ab9cc40f；不可变tlm_84c131951b9c快照 |
| 已完成 | 真实BF16捕获1877，3上下文原样/捕获逐位一致；Link数组1878全部60项完成；SRAM容量/MHA实际地址/9项Attention＋3项架构＋6项DRAM检查通过 |
| 运行中 | DRAMSys1879：18项Staggered；1896：4项NoPowerDown；只用Slurm CPU，不使用额外GPU |
| 成果位置 | architecture_tlm/llama7b/；服务器 /home/Hongjie_Zeng/projects/pbit-llama7b-tlm-20261017-issue12/ |
| 数值边界 | 单公开WT2窗口真实BF16 QK作为地址oracle；随机FFN/比例PV/新max4/Ising宏没有新PPL |
| 待同步 | 等完整DRAMSys后汇总、manifest、PR及Issue验收；Projects缺read:project，看板待权限补齐 |
| 下一步 | 读work/jieruiz/12/HANDOFF.md，保留执行快照；检查1879/1896并汇总现有输出，不重复提交 |

此前治理#1/PR#2、架构审计#3/PR#4、DRAM#5/PR#6、FFN#7/PR#8及#11、筛选K流量#9/PR#10仍为各自独立待审分支。本任务没有覆盖其工作树。
