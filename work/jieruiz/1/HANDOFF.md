# Issue #1 交接与核实记录

负责人：@jieruiz。任务：[Issue #1](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/1)。本次仅协作规则、模板与状态资料，不包含实验实现变更。

## 身份、工作目录及远端

- 当前外层工作区 `a_P_BIT/` 的 `.git` 为空目录，不是有效 Git 仓库；没有将混合实验/工艺资料根目录初始化成仓库。
- 有效主 checkout：`a_P_BIT/pbit-llm-qwen-baselines/`，原分支 `pbit-attention-qk-blockscale`，开工时工作树干净；`origin` 是 `jieruiz/pbit-llm-qwen-baselines`，`workspace` 是正式目标 `rayggxia-workspace/pbit-llm-qwen-baselines`。
- 本任务独立 worktree：`a_P_BIT/tmp/collab-issue-1-20261016/`，分支 `collab/issue-1-governance`，PR base 为 workspace/main `8068bfbb71d892ef8b0850dea391aa612739aa4f`。
- GitHub `/user` 实际登录 `jieruiz`（id 169070146），仓库 API 返回 push/triage/maintain/admin 权限。没有使用另外两个 connector 账号代替本人。
- 外层本地 `a_P_BIT/AGENTS.md` 安装同一规则，并加上适用范围说明，方便本工作区后续任务读取；它不属于仓库提交，不把本地安装称为已在 main 生效。

## 已读取的最新状态和既有规则

读取日期：2026-10-16；先 `git fetch workspace` 再读取远端 refs。开工检查 Issue 和 PR（含关闭）均为空；本任务创建 Issue #1 后继续沿用它。

| 来源 | 版本/核实结果 |
|---|---|
| workspace/main README、目录树 | `8068bfbb71d892ef8b0850dea391aa612739aa4f`；无 AGENTS.md、CONTRIBUTING.md、个人 STATUS 或 .github 协作模板 |
| 最新 TLM README、WORKSPACE_LATEST_ZH、PUBLICATION_VALIDATION | `9608c0d06cf8b421cbbd348aca4fc84c5990aae7`；v3/v4、随机源、SRAM校准与发布限制；未合入 main |
| 历史 AGENTS.md | workspace/codex/ten-layer-calibration `595c3ab44be27799878353395d30645df0441983`，五条英文复现要求逐字保留 |
| 成员评审与实际验证 | workspace/codex/tlm-attention-alignment-20261014 `cd3b471a4e33234ed60bc07bcff0b86b22cd1695` 的 `reviews/tlm_attention_alignment_20261014/ATTENTION_TLM_ALIGNMENT_ZH.md`；不重复执行其已完成的历史审计 |
| 组织公共协作仓库 | `rayggxia-workspace/.github` API返回404；仅表明该接口未能读取，不据此推断有/无私有组织规则 |
| Projects v2 | GraphQL 返回 INSUFFICIENT_SCOPES，缺 `read:project`；未读到项目列表，未改看板 |

## 验证及成果

- 文档差异检查、相对链接、Issue模板结构、原规则逐字保留和文件 SHA-256 由同目录 `verify_delivery.py` 核验，实际结果写入 `validation.json`。
- `manifest.json` 记录代码基线、来源提交、文档任务配置/数据不适用原因、文件位置/大小/SHA-256。manifest 本身不自散列；Git commit 和 PR 标识承载整份 manifest 的版本。
- 未运行 GPU、PPL、RTL/DC/PT、DRAMSys 或实验回归：本任务未改运行代码或历史结果。历史验证只记录为已阅读，不宣称本次重跑。
- 未上传权重、语料、远程凭据、工艺库、大型 trace 或未提交的 v6 实验。没有运行中的本任务远程作业。

## 可执行接续

```powershell
cd C:/Users/86134/Documents/a_P_BIT/tmp/collab-issue-1-20261016
git remote -v
git fetch workspace
git status --short
git log -1 --oneline
python work/jieruiz/1/verify_delivery.py
git diff --check workspace/main...HEAD
```

1. 先读 Issue #1、关联 PR 最新讨论、其他成员 STATUS 和本交接，核对远端 head 及本地未提交改动。
2. 若 PR 尚未创建，验证后只推送 `collab/issue-1-governance` 到 workspace，创建面向 main 的 PR；若已创建则接续原 PR。不得重推历史实验分支。
3. 将实际 PR 链接、验证结果与当前阶段同步到 `progress/jieruiz/STATUS.md` 和 Issue；PR 待审不等于已合并。
4. 看板权限不足仍为待同步：需要具备 Projects 读取及写入权限后，先核实正确看板与字段，再将本 Issue 加入/更新状态；本次不擅自新建看板。
5. 后续正式发布 PV v6 或其他实验须另建 Issue、独立分支和成果 manifest；本次治理 PR 不承担实验发布。

交付阶段与 PR 链接以个人 STATUS 和 Issue 最新评论为准；这些内容可能随后续接续更新。任何未同步项需保留，不把本地安装、分支上传或 PR 创建混写成 main 已完成。
