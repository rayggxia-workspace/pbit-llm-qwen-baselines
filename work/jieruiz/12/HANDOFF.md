# Issue #12：LLaMA-1 7B TLM 交接

负责人 @jieruiz，正式目标 rayggxia-workspace/pbit-llm-qwen-baselines。独立目录 `C:/Users/86134/Documents/a_P_BIT/tmp/llama7b-tlm-issue12-20261017`，分支 `task/12-llama7b-tlm`，PR base为已发布TLM分支9608c0d。开始前已读取最新README/协作AGENTS/TLM索引/Issue/PR/本人状态，未发现重复LLaMA任务，建立Issue12并assignee jieruiz。当前已推送，PR #13为草稿，待完整DRAMSys结果；未合并。

## 已完成与版本

- `architecture_tlm/llama7b/runtime/` 是最新本地v5/v6与来源核查DRAM profile的独立快照，来源表在SOURCE_SNAPSHOT.json；后续必要差异有Git历史和EXECUTION_MANIFEST。
- 模型32层/32Q32KV/4096/11008，独立embedding和完整norm参数，原生512/1024/2048单decode；没有8K外推。
- 当次TLM代码提交 **84c131951b9ce69a52778e8725d62a21ab9cc40f**，服务器不可变快照 `tlm_84c131951b9c/`。不得为修测试而编辑这个目录。
- Capture源码e09b5e0c1319dee3ad3f212c51ff0495687b1043，独立不可变capture_e09b5e0/；Slurm1877完成。模型/语料散列已验证，三个上下文原样BF16和捕获输出逐bit一致。记录见capture_validation/；大trace留服务器。
- 小测试：Attention 9项、模型结构3项、DRAM配置6项；真实桥跨rank/channel/SG微事务通过，见dram/。CPU微型模型捕获集成通过，实际7B由1877验证。

## 运行中与待办

服务器项目：`/home/Hongjie_Zeng/projects/pbit-llama7b-tlm-20261017-issue12/`，代码与output分开；本地SSH配置继续按既有指南，不上传凭据。

- 1878 Link数组0-59：60项全部完成，真实轨迹、3个上下文、随机地址3种子、16/32/64阵列敏感性。
- **1879 DRAMSys Staggered 0-17**：18项完整模型，已把并发从8提升至18，实际调度由Slurm资源控制。
- **1896 DRAMSys NoPowerDown 0,2,9,15**：4项配对低功耗对照。
- 不要因等待而重复提交。DRAMSys约需数十分钟，每个任务4小时上限，CPU1核4GiB。
- 捕获已完成；GPU不再占用。模拟芯片ms/token与CPU仿真墙钟分钟完全不同。

预览汇总是服务器 `reports/preview_1/`，只有60条Link；不是最终DRAM能耗。正式report.py是后处理代码，可以在新输出目录运行，不得覆盖原始结果或执行快照。

## 可继续执行的步骤

1. 重读Issue12最新讨论及相关PR，核验身份/远端，不默认推到个人origin。
2. 用完整路径Slurm命令检查1879/1896；服务器PATH不默认含Slurm。
3. 全部完成后在新目录执行report.py；应得到60 Link＋18 Staggered＋4 NoPD＝82条，未齐须列实际缺项。
4. 保存源代码提交、每配置及原始结果SHA、真实trace SHA和结果位置。大轨迹/requests gzip留已授权服务器，Git只提交摘要及索引。
5. 生成中文总表并清楚分开Link估计、DRAMSys core电流情景、接口代理、未标定数字/随机核PPA和无新PPL边界。
6. 更新个人STATUS、Issue验收；明确文件范围提交、逐blob核验SHA，通过本任务分支/PR交付，PR待审不自动合并。Projects缺read:project，保留待同步。

## 解释边界

新筛选是未校准的max4固定bias/temp，旧LLaMA26%及PPL来自另一套mean筛选，不能混用。真实BF16地址oracle不证明随机FFN联合质量。没有把旧Qwen PPL写入新结果。Ising使用足额capacity=L宏，内部随机/状态/读出已打包，不再重复计外部leaf；零预算跳过前元数据/直方图扫描收费。

模拟的权重resident接口和随机核复制成本仍是现有宏代理，未宣称定制CIM已实现。SRAM时序/面积/能耗采用现有55nm SS校准；DRAM采用已溯源Micron电流场景，IO/PHY和多rank板级时序未认证。
