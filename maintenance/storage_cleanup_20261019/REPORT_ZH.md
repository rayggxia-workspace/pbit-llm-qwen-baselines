# 本地项目磁盘清理结果（2026-10-19）

负责人：GitHub `jieruiz`；[Issue #68](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/68)。正式目标 `rayggxia-workspace/pbit-llm-qwen-baselines`；任务分支 `task/68-local-storage-cleanup`；集成基线 `6197f24a9cc03ab0dc5e2e72297457f638e37292`。用户明确选择清理本地项目文件。

本次按被删除文件的逻辑字节统计回收 **3.133 GiB**。执行前C盘可用 36.45 GiB，执行后 39.70 GiB。磁盘差值还受NTFS分配与其他进程影响，不与逻辑字节强行等同。

| 清理项目 | 数量 | 逻辑空间 |
|---|---:|---:|
| 本人已完成Issue55的PR刷新临时工作目录 | 17 | 3.041 GiB |
| 已安装依赖的wheel下载缓存 | 28 | 61.082 MiB |
| 可再生成Python字节码 | 1187 | 29.280 MiB |
| 与final图片SHA完全相同的Word检查图片 | 16 | 3.741 MiB |

实际数量和字节以 `SUMMARY.json`、本地逐项回执为准。没有清理内存/RAM，没有删除远程服务器文件。

## 保护和恢复

- 唯一Qwen2.5本地权重仍在原位置，988,097,824 bytes；清理前后SHA-256均为 `88c142557820ccad55bb59756bfcfcf891de9cc6202816bd346445188a0ed342`。
- 最优模型、其他权重和特征文件、正式原始结果、SRAM校准、工艺库、已安装的 `zigzag385` 环境、运行中/其他成员工作目录均保留。
- 仅回收 `tmp/pr55-resolve-<PR>-20261019` 本人的Issue55临时工作副本。Issue55远端已关闭；17个HEAD均是集成基线的祖先。原17个本地分支和主Git对象库完整保留。
- 13个目录存在少量未提交 `sources.json` 或 `_resolution_inputs/*`；删除前全部压缩保存并逐文件核验SHA-256。恢复包合计 224,076 bytes，位于本地 `tmp/local_cleanup_20261019/recovery/`；这些包不上传GitHub。
- 其他含未提交资料、尚在进行的实验、长期备忘录目录和其他成员目录没有回收。
- 检查清理范围之外原盘点的 462 个10 MiB以上文件：路径均存在、大小未变；这项不是每个大文件的内容散列验证。另对Qwen权重及16张保留图片执行了实际SHA-256复核。

恢复任意已回收目录：先根据 `RECOVERY_INDEX.json` 选择目录、原分支和HEAD。在主仓库执行 `git worktree add <原目录绝对路径> <原分支>`；必要时用 `Expand-Archive -LiteralPath <恢复zip> -DestinationPath <原目录> -Force` 恢复那13组未提交辅助文件。恢复包哈希见索引；不要覆盖已重新使用的同名目录。

## 实际命令和边界

实际依次执行 `inventory.py`、`audit_worktrees.py`、`cleanup_local.ps1 -Mode Prepare`、`cleanup_local.ps1 -Mode Execute`，完成后核验分支、恢复包、模型及保留图片。删除前检查绝对路径位于授权工作区且没有reparse point；Git工作目录使用Git自身的worktree remove。含辅助文件的13个目录只有在备份与状态重新核验通过后才使用force；没有丢弃唯一辅助资料。

源码脚本随本报告归档；其中的计划和回执为一次性、不可重复执行。完整清理前盘点、删除计划和逐文件回执仍在本机 `tmp/local_cleanup_20261019/`，大小和SHA索引见 `work/jieruiz/68/LOCAL_ARTIFACT_INDEX.json`。

本任务没有新模型质量测试、RTL/PT、TLM或GPU结果。模型/数据版本、种子、计分协议不适用于磁盘清理；保留模型散列及Git代码版本已经记录。Projects看板此前缺read:project，待同步，未宣称已更新。

交付状态：本地清理已执行；[PR #69](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/69)已创建并推送，待审未合并。
