# FFN 调度与数字 CIM 仿真审计交接

- 负责人 jieruiz，Issue #7；task/7-ffn-cim-scheduling；base：pbit-tlm-attention-details-20261016 @9608c0d06cf8b421cbbd348aca4fc84c5990aae7。
- 工作目录：C:/Users/86134/Documents/a_P_BIT/tmp/ffn-cim-issue-7-20261017/。目标 rayggxia-workspace/pbit-llm-qwen-baselines；origin 是历史个人仓库，不能作为发布目标。
- 已核验真实登录、Git 根/分支/改动/remote，并 fetch workspace；已读最新 README、TLM 索引、治理规则及 Issue #1/#3/#5、关联 PR/状态和交接，未发现另一同范围负责人任务。
- 已完成：FFN 顶层及 v5 循环/存储/随机源核对，独立服务公式、源函数桩回放与历史计数交叉检查，中文仿真/优化报告与清单。
- 本地完整 v5/v6 尚未集成到该发布 base。本任务只发布报告、计数工具和函数摘录，完整原始文件 SHA、历史结果来源在 evidence.json；不将摘录冒充完整实现发布。
- 本任务没有新 PPL、RTL/DC/PT、DRAMSys 或版图结果；没有新提交的远端作业。历史能量有另一个 DRAM 审计任务，这里只引用历史 FFN 时间，不认证能量。
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

尚未完成/不属于本次交付：定制 CIM 电路、完整新调度器、PT 表征、映射搜索和新随机策略 PPL。暂停/换人时沿用本记录，保留各旧任务工作树。

交付状态：已推送；[PR #8](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/8) 待审，未合并；Issue #7 保持 open，等待审查验收。
