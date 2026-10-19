# FFN 调度与数字 CIM 仿真审计交接

- 负责人 jieruiz，Issue #7；task/7-ffn-cim-scheduling；base：pbit-tlm-attention-details-20261016 @9608c0d06cf8b421cbbd348aca4fc84c5990aae7。
- 工作目录：C:/Users/86134/Documents/a_P_BIT/tmp/ffn-cim-issue-7-20261017/。目标 rayggxia-workspace/pbit-llm-qwen-baselines；origin 是历史个人仓库，不能作为发布目标。
- 已核验真实登录、Git 根/分支/改动/remote，并 fetch workspace；已读最新 README、TLM 索引、治理规则及 Issue #1/#3/#5、关联 PR/状态和交接，未发现另一同范围负责人任务。
- 已完成：FFN 顶层及 v5 循环/存储/随机源核对，独立服务公式、源函数桩回放与历史计数交叉检查，中文仿真/优化报告与清单。
- 本地完整 v5/v6 尚未集成到该发布 base。本任务只发布报告、计数工具和函数摘录，完整原始文件 SHA、历史结果来源在 evidence.json；不将摘录冒充完整实现发布。
- 初轮源循环审计没有 RTL；本轮后续补充独立后处理候选的功能仿真，详见下节。仍没有新 PPL、DC/PT、DRAMSys 或版图结果；没有新提交的远端作业。历史能量有另一个 DRAM 审计任务，这里只引用历史 FFN 时间，不认证能量。
- 随机长度/模型权重/数据版本：形状和采样配置从历史结果归档；未运行数值推理，权重/语料/三随机种子的新评估不适用。若后续改变数值路径，要重新遵守 BF16 基线和语料 hash 规则。
- 精确产物 SHA 见 manifest.json（manifest 自身不递归哈希）。当前 Git 提交和 PR 状态以分支 HEAD / STATUS 为准；最终验证见 VALIDATION.md。
- 项目看板缺 read:project，待权限补齐；Issue/PR 不受此阻塞。

## 可执行接续

```powershell
cd C:/Users/86134/Documents/a_P_BIT/tmp/ffn-cim-issue-7-20261017
git remote -v
git status --short
python architecture_tlm/audit_ffn_schedule.py --evidence work/jieruiz/7/evidence.json --excerpt work/jieruiz/7/stochastic_matrix_excerpt.py.txt --output new-audit.json
git diff --check workspace/pbit-tlm-attention-details-20261016...HEAD
```

回放使用受信任的项目函数摘录，不执行未知代码。先重读 Issue #7/PR 的最新讨论。

下一步建议：冻结 fixed_sc_exact 64×64 权重载荷/展开/符号与保持接口；比较相同激励下的精确计数基线、压缩器缓存累加及真实 SRAM 接口。跨算子分组流水要收费于输入重访、局部部分和和引擎分配；不能直接把各阶段时间改成 max。

尚未完成/不属于本次交付：定制 CIM 电路、完整新调度器、PT 表征和新随机策略 PPL。后续新增的有限算术服务枚举不等于完整映射搜索。暂停/换人时沿用本记录，保留各旧任务工作树。

交付状态：已推送；[PR #8](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/8) 待审，未合并；Issue #7 保持 open，等待审查验收。

## 本轮接续：经典结构与后处理候选

- 新增经典 GPU/ASIC 对照报告、同矩阵引擎数量的阶段/分区流水服务比较；12 场景，仅算术服务，不是新完整 TLM 或 PPL。
- 新增 `architecture_tlm/rtl/ffn_epilogue_20261017/`。子工作树源提交 `e8bbc7f8e56a70ca5644fdc2eee15a950b107917` 经明确范围 cherry-pick 集成；当前主分支 Git 历史记录集成提交。子工作树和分工见 TEAM_COORDINATION.md。
- 后处理以 16 位 Q10 g/u、17 位 sigmoid LUT、50 位中间乘积、最终 RNE/饱和输出默认 24 位 Q10。是近似硬件表征候选，不是模型 BF16 的逐位等价实现；未启用到现有 TLM/推理。
- 两个工作目录分别实际运行 Icarus 10.1：三种子各 12295 周期，输出位宽24/16核对通过；active/burst/idle 每项4096拍，接受/输出数4096/1024/0。功能种子不是新的 PPL 三种子评估。
- 主工作树原始活动/编译日志保留在 `work/jieruiz/7/epilogue_validation_local/`（Git忽略），小型摘要/位置/散列见 rtl_integration_validation.json；子工作树旧波形保持原位置。未上传 VCD、工具或工艺库。
- 下一步把 RTL 包及中文 README 交工艺环境做 DC/布局/PT，返回每有效项能量、面积和时序；若把新近似单元接入模型，再做相同模型/语料哈希/BF16与PPL回归。现在没有工艺功耗数值。

本轮补充已完成主工作树审查和再次Icarus验证，通过同一任务分支追加到PR #8；保留待审未合并状态。主集成提交为8689b56（内容源于子提交e8bbc7f），完整发布提交见分支HEAD。
