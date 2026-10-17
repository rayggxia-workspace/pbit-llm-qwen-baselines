# Issue #12：LLaMA-1 7B TLM 交接

负责人 @jieruiz，正式目标 rayggxia-workspace/pbit-llm-qwen-baselines。独立目录 `C:/Users/86134/Documents/a_P_BIT/tmp/llama7b-tlm-issue12-20261017`，分支 `task/12-llama7b-tlm`，PR base为已发布TLM分支9608c0d。开始前已读取最新README/协作AGENTS/TLM索引/Issue/PR/本人状态，未发现重复LLaMA任务，建立Issue12并assignee jieruiz。代码与Link已推送，PR #13仍为草稿；完整82项已汇总，准备上传最终成果；未合并。

## 已完成与版本

- 子任务均使用独立工作树：`tmp/llama7b-trace-issue12-20261017`（task/12-trace-capture）、`tmp/llama7b-dram-issue12-20261017`（task/12-dram-config）、`tmp/llama7b-attention-issue12-20261017`（task/12-attention-adapter）；代码通过cherry-pick集成，没有共用未提交状态。父任务复核后补上纯Ising面积去重、零预算扫描及完整LLaMA参数分配检查。

- `architecture_tlm/llama7b/runtime/` 是最新本地v5/v6与来源核查DRAM profile的独立快照，来源表在SOURCE_SNAPSHOT.json；后续必要差异有Git历史和EXECUTION_MANIFEST。
- 模型32层/32Q32KV/4096/11008，独立embedding和完整norm参数，原生512/1024/2048单decode；没有8K外推。
- 当次TLM代码提交 **84c131951b9ce69a52778e8725d62a21ab9cc40f**，服务器不可变快照 `tlm_84c131951b9c/`。不得为修测试而编辑这个目录。
- Capture源码e09b5e0c1319dee3ad3f212c51ff0495687b1043，独立不可变capture_e09b5e0/；Slurm1877完成。模型/语料散列已验证，三个上下文原样BF16和捕获输出逐bit一致。记录见capture_validation/；大trace留服务器。
- 小测试：Attention 9项、模型结构3项、DRAM配置6项；真实桥跨rank/channel/SG微事务通过，见dram/。CPU微型模型捕获集成通过，实际7B由1877验证。

## 已完成任务与成果

服务器项目：`/home/Hongjie_Zeng/projects/pbit-llama7b-tlm-20261017-issue12/`，代码与output分开；本地SSH配置继续按既有指南，不上传凭据。

- 1878 Link数组0-59：60项全部完成，真实轨迹、3个上下文、随机地址3种子、16/32/64阵列敏感性。
- **1879 DRAMSys Staggered 0-17**：18项完整模型全部完成，期间将并发从8提升至18，实际调度由Slurm资源控制。
- **1896 DRAMSys NoPowerDown 0,2,9,15**：4项配对低功耗对照全部完成。
- 本任务无运行中作业，不重复提交。服务器未启用sacct accounting，完成依据完整结果及squeue，而不是虚构的accounting日志。
- GPU与CPU资源均已释放。模拟芯片ms/token与CPU仿真墙钟分钟完全不同。

最终汇总是服务器 `reports/final_v1/`，包含全部82项，计划集合与实际集合相等，无缺项和重复；发布摘要为 `architecture_tlm/llama7b/results/current/`。`results/link_20261017/` 保留较早的60项Link摘要，不能替代主能耗表。正式report.py为独立后处理，源码提交7c29927，不能覆盖原始结果或执行快照。

## 可继续执行的步骤

1. 重读Issue12最新讨论及相关PR，核验身份/远端，不默认推到个人origin。
2. 执行 `python work/jieruiz/12/verify_delivery.py` 复核输入与发布成果；修改后重新生成manifest并核对暂存blob。
3. 如需重做后处理，使用新输出目录调用report.py，保持服务器原始结果字节不变。大trace与requests gzip按ARTIFACT_INDEX访问。
4. 评审本任务PR；若有新架构/数值实验需求，建立独立Issue/分支/执行快照，不重新提交旧数组。
5. PR待审不自动合并或关闭Issue。Projects缺read:project，保留看板待同步。

## 解释边界

新筛选是未校准的max4固定bias/temp，旧LLaMA26%及PPL来自另一套mean筛选，不能混用。真实BF16地址oracle不证明随机FFN联合质量。没有把旧Qwen PPL写入新结果。Ising使用足额capacity=L宏，内部随机/状态/读出已打包，不再重复计外部leaf；零预算跳过前元数据/直方图扫描收费。

模拟的权重resident接口和随机核复制成本仍是现有宏代理，未宣称定制CIM已实现。SRAM时序/面积/能耗采用现有55nm SS校准；DRAM采用已溯源Micron电流场景，IO/PHY和多rank板级时序未认证。
