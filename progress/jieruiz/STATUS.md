已合并：PR180 → main，2026-10-24T14:41:06Z，提交5273e5d9fdae811a714f1a278fee6e776c5675af。全部验证与远端blob核验完成，无本任务运行中作业；Projects待权限。准确回执见work/jieruiz/179/MERGE_VERIFIED.json。

# 当前统一TLM交付：Issue179 / PR180（2026-10-24）

负责人：jieruiz；仓库rayggxia-workspace/pbit-llm-qwen-baselines。
分支task/179-latest-ffn-tlm-main，base main；本地tmp/latest-ffn-tlm-issue179-20261024。
完整入口architecture_tlm/README.md，最新FFN和已保留的Attention/随机/存储接口在unified_v6。执行提交3a9ddfb1，原件results/current_ffn_20261024_v2；同目录报告及work/jieruiz/179/HANDOFF.md给出复现和边界。
已完成74项检查、7组完整36层、8组单FFN敏感性及15组三seed夹具，12份封存SHA核验通过；全部本地执行结束，无运行中任务。本任务通过PR180交付；合并状态以PR和Issue179最终回执为准。用户已授权验证通过后合并main。没有修改训练作业；没有新GPU、Slurm、RTL/PT、PPL或DRAMSys结果。完整结果见RESULTS_CURRENT_ZH.md，完整PPA未知。Projects缺read:project，待维护者同步。
后续：GU整数恢复数值对齐、新NL独立随机端口实际接合、权重保持及4/7桶宏STA/PPA；保留统一入口，不另建整机版本。

---
以下为此前main中的历史状态，不能替代最新Issue/PR：

# Issue138：可训练采样器接入 main（2026-10-23）

负责人jieruiz；review/138-main-port-20261023；main base35db820；tmp/pr142-main-review-20261023。PR142源bac0e04已审核，main独立移入模块与历史NumPy测试依赖，保留源码/原结果字节。22单测及两方法三seed合成训练复核；无LLM/PPL/硬件实验。成果experiments/trainable_pbit_attention，交接work/jieruiz/138/MAIN_HANDOFF_ZH.md。当前本地审核完成，推送/合并以关联PR回执为准。后续CUDA/模型训练/内存与梯度方差未验收；Projects待权限。无运行任务，合并后回收本目录。

以下保留历史状态：

# jieruiz 项目进度

更新时间：2026-10-16（Asia/Shanghai）。本人身份已通过本机 Git 凭据调用 GitHub `/user` 核实；仓库有写权限。

| 项目 | 状态 |
|---|---|
| 当前任务 | [Issue #1：workspace 协作规则](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/1)，负责人 @jieruiz |
| 目标仓库 | `rayggxia-workspace/pbit-llm-qwen-baselines`；旧个人 origin 不作为本任务发布目标 |
| 分支 / PR | `collab/issue-1-governance`；[PR #2](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/2) → main |
| 基线 | workspace/main `8068bfbb71d892ef8b0850dea391aa612739aa4f` |
| 独立目录 | 本机 `a_P_BIT/tmp/collab-issue-1-20261016/`；不修改现有实验 worktree |
| 当前阶段 | 协作规则/模板已验证并推送，PR #2 已创建待审；未合并 |
| 正式规则 | [AGENTS.md](../../AGENTS.md)；保留历史英文复现规则 |
| 实际验证 | 9个文件范围检查、26个相对链接、历史规则逐字保留、README 原字节保留、git diff --check、8项文件SHA-256核验通过；未运行模型/硬件实验 |
| 验证与交接 | [HANDOFF.md](../../work/jieruiz/1/HANDOFF.md)、[manifest.json](../../work/jieruiz/1/manifest.json) |
| 阻塞 / 待同步 | Projects v2 缺少 `read:project` 权限，无法读取/更新看板；Issue/PR 可同步 |

## 项目状态边界与后续

- 已核实的最新已发布 TLM 快照：`pbit-tlm-attention-details-20261016`，提交 `9608c0d06cf8b421cbbd348aca4fc84c5990aae7`；读取其 `architecture_tlm/WORKSPACE_LATEST_ZH.md` 与发布验证。它尚未合入 main。
- 已查看成员 amlink1219 的 `codex/tlm-attention-alignment-20261014` 评审和 `codex/ten-layer-calibration` 规则；前者针对历史 TLM 基线，不能将其中“尚未实现 attention”直接套给后续 v3/v4。
- 本地工作区另有 PV stream v6 和能耗审计资料，不属于本次协作规则 PR，不能因为本 PR 已上传而视为这些代码/结果已发布。后续如需发布，先建独立任务 Issue，核对版本、依赖和证据后交付。
- 下一步：接续 PR #2 的审阅意见；有 Projects 权限后补看板同步。待 PR 合入并确认验收后再关闭 Issue #1。本次未合并 PR。
