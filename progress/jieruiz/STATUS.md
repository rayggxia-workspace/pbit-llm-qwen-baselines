# jieruiz 项目进度

更新时间：2026-10-16（Asia/Shanghai）。本人身份已通过本机 Git 凭据调用 GitHub `/user` 核实；仓库有写权限。

| 项目 | 状态 |
|---|---|
| 当前任务 | [Issue #1：workspace 协作规则](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/1)，负责人 @jieruiz |
| 目标仓库 | `rayggxia-workspace/pbit-llm-qwen-baselines`；旧个人 origin 不作为本任务发布目标 |
| 分支 / PR | `collab/issue-1-governance`；PR 将在推送后回填 |
| 基线 | workspace/main `8068bfbb71d892ef8b0850dea391aa612739aa4f` |
| 独立目录 | 本机 `a_P_BIT/tmp/collab-issue-1-20261016/`；不修改现有实验 worktree |
| 当前阶段 | 本地协作规则和模板已编写，待文档检查、推送及 PR；未合并 |
| 正式规则 | [AGENTS.md](../../AGENTS.md)；保留历史英文复现规则 |
| 验证与交接 | [HANDOFF.md](../../work/jieruiz/1/HANDOFF.md)、[manifest.json](../../work/jieruiz/1/manifest.json) |
| 阻塞 / 待同步 | Projects v2 缺少 `read:project` 权限，无法读取/更新看板；Issue/PR 可同步 |

## 项目状态边界与后续

- 已核实的最新已发布 TLM 快照：`pbit-tlm-attention-details-20261016`，提交 `9608c0d06cf8b421cbbd348aca4fc84c5990aae7`；读取其 `architecture_tlm/WORKSPACE_LATEST_ZH.md` 与发布验证。它尚未合入 main。
- 已查看成员 amlink1219 的 `codex/tlm-attention-alignment-20261014` 评审和 `codex/ten-layer-calibration` 规则；前者针对历史 TLM 基线，不能将其中“尚未实现 attention”直接套给后续 v3/v4。
- 本地工作区另有 PV stream v6 和能耗审计资料，不属于本次协作规则 PR，不能因为本 PR 已上传而视为这些代码/结果已发布。后续如需发布，先建独立任务 Issue，核对版本、依赖和证据后交付。
- 下一步：检查本任务文档与清单，推送到 workspace 任务分支并创建 PR，更新此状态和 Issue；有 Projects 权限后补看板同步。待 PR 审阅/合入后再按验收结果关闭 Issue。
