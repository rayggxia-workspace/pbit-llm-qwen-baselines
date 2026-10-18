# amlink1219 硬件设计接入交接

时间：2026-10-18T22:39:51+08:00；本地落地负责人amlink1219；关联既有Issue1，不改变其原assignee。正式目标 `https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines`。

## 已完成和未完成

本地规则、进度和最新项目核查已完成，详见ONBOARDING_ZH.md、REMOTE_SNAPSHOT.json和SOURCE_MANIFEST.json。原AGENTS字节保留，原上游checkout、其他成员STATUS/分支及远程作业未改。无本次实验运行、无本次Slurm job；模型/数据/种子字段不适用文档任务。

任务目录 `E:/BaiduSyncdisk/p-bit/DAC_2026_Draft_Proceedings/DAC_2026_Draft_Proceedings/workspace_projects/pbit-llm-qwen-baselines`，分支 `task/1-amlink1219-hardware-onboarding`，基线 `3553996bf014a29dee7fdb2250a3965e8fd881a4`，拟PR base `pbit-tlm-attention-details-20261016`。本地提交号由Git日志及外部delivery_receipt.json标识，不在本提交内制造自引用哈希。未推送、无本任务PR、未合并、未更新Issue验收/标签和Projects；本地完成不能当作远端交付。

## 恢复步骤

1. 读取AGENTS、本人STATUS和本交接。用本机GCM重新核实 `/user` 必须为amlink1219/75301230，重新查询目标repository权限。不得把Git作者配置当认证，也不得输出凭据。
2. 在此独立checkout执行 `git status --short --branch`、`git remote -v`、`git remote get-url --push --all origin`，检查pushurl和URL重写。先保存本地修改，再fetch；不要reset、clean或覆盖其他任务。
3. 重读最新Issue1/PR2、Issue19/22/28/30及关联PR/交接。备忘录在PR29待审分支，用 `git show origin/task/28-project-memory:PROJECT_MEMORY_ZH.md`；合并后改用根文件，不能沿用过期队列快照。
4. 对比集成base是否变化，必要时在自己的任务分支处理冲突，保留双方规则。复核原AGENTS保留、UTF-8/LF、相对链接、manifest和Git blob SHA。查看 `git log -1 --format=fuller` 获取当前本地交付提交。
5. 检查本任务提交仅包含AGENTS.md、progress/amlink1219/STATUS.md和work/amlink1219/1/。DAC根AGENTS、outputs审核缓存、备份、凭据、其他项目及模型/数据不进入发布。
6. push权限可用后，向origin推送同名任务分支；创建/更新PR到当前确认的集成base，关联Issue1，明确这是amlink1219本机规范接入子项，不接管jieruiz治理PR。附VALIDATION、实际范围和限制。没有写权限则保持pending，不重试注定失败的push。
7. 回读远端commit/PR及逐文件散列，再更新Issue阶段/本人STATUS与有权限的看板。Issue标签/assignee更新需相应权限；不擅自关闭整体Issue1或合并PR。若只允许发表评论，也只能同步真实阶段，不能冒称分支已上传。

## 数据和环境

无模型/数据/新结果上传。API审查原件及AGENTS备份在 `E:/BaiduSyncdisk/p-bit/DAC_2026_Draft_Proceedings/DAC_2026_Draft_Proceedings/outputs/pbit_hardware_onboarding_20261018`；仓库内REMOTE_SNAPSHOT/SOURCE_MANIFEST提供安全的公共证据索引及SHA。Windows沙箱故障为 `.sandbox-bin` 访问拒绝，未修复ACL；正常exec恢复前可能仍需授权执行工作命令。Projects实际缺read:project，未更改token范围。

## 后续设计入口

先确定质量/性能验收、数制和随机源语义，再展开SRAM接口/映射、采样计数、非线性、Attention/KV、控制调度与PPA。Issue30精确双流、Issue22短流RTL及Issue19Llama2评测已有人负责，使用其证据而非重复启动。尚未完成芯片架构、工艺表征闭合或等精度整机能效验证。

## 已同步的远端进度

[Issue1评论](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/1#issuecomment-6251225780)已发布并回读核验，comment_id=6251225780；回执见ISSUE_COMMENT_RECEIPT.json。没有更改Issue正文、标签、验收、assignee或关闭任务。恢复时先检查原评论，避免重复留言；只在阶段有实质变化时追加状态。分支/PR/看板仍未同步。
