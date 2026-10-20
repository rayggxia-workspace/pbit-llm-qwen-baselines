# 第二轮本地工作副本清理与防止重复占用（2026-10-19）

负责人jieruiz；接续[Issue68](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/68)和[PR69](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/69)。用户明确要求继续清除已完成任务副本，并要求以后不长期保留。

本轮实际移除 **42个工作目录，逻辑文件量7.377 GiB**。两轮共移除59个工作目录，加上第一轮缓存/重复图片，累计逻辑回收 **10.510 GiB**。第二轮保留的恢复材料共26个文件、3,042,843.0 bytes（约2.90 MiB）；实际磁盘净变化还受NTFS分配、当前任务新增资料及其他程序影响。

## 为什么原来会有这么多副本

并行任务需要各自的Git工作目录以避免覆盖；但此前对每个实验helper/审阅/冲突处理都全量检出，历史事务轨迹和结果包随之复制，交付后没有及时回收。Git对象库本来可以共享，重复占用主要在各工作目录的已检出文件。后续已改为按任务需要检出，并在交付阶段回收完成使命的临时目录。

## 实际保护与恢复

- 逐项核对远端Issue为closed且owner为jieruiz，保护仍在进行的Issue7/19/22/28/50/59及本任务；未直接清理其他负责人状态或归属未确认的历史目录。
- 全部42个HEAD都新增了本地archive/cleanup-20261019恢复ref；原分支保留。部分helper的HEAD并非集成祖先，这些额外创建并验证增量Git bundle，未将它们误报成已合并。
- 440.0个未提交/未跟踪/ignored独有文件在本地压缩归档并逐SHA核验，包括Issue30真实runs、源码差异和审核记录。没有将这些原始材料上传GitHub。
- 本地恢复材料位于 `project_archives/cleanup_20261019_round2/`。本报告的ROUND2_RECOVERY_INDEX.json记录每项原HEAD、分支、恢复ref、zip/bundle文件名和SHA。完整逐文件清单保留在本地round2_delete_plan.json及各zip的_cleanup_git_state/manifest.json。
- 恢复方法：主仓库执行git worktree add <空的目标路径> <原分支或索引中的recovery_ref>，然后仅恢复zip中manifest列出的原文件。working_vs_HEAD.patch和staged.patch也已保留，用于恢复原工作状态；增量bundle需要现有基础对象，原主Git库已保留。
- `pr47-review-main-20261019`含rayggxia的唯一交接状态，本轮保留。长期备忘录canonical目录和进行中任务保留。其余旧发布/未知用途目录没有按日期盲删。
- 唯一Qwen权重再次通过SHA-256核验；其他模型、最佳checkpoint、工艺库和正式唯一结果保留。没有修改Windows页面文件或系统设置，没有新Slurm/GPU/RTL/PT/TLM测试。

## 防止再次堆积

根工作区AGENTS.md及本PR仓库AGENTS.md已追加用户要求：同任务恢复复用已有目录；并行才建必要独立目录；新worktree先不检出，按需要使用稀疏检出；只读审阅优先git show；不默认在每个helper检出历史大结果；交付时核验并回收自己的review/resolve/helper，保留Git版本和独有资料的校验归档。

本任务自身已执行 `git sparse-checkout set --cone --no-sparse-index maintenance progress work`，当前工作副本约1.86 MiB，仍保留根README/AGENTS/备忘录及任务所需目录；其他worktree稀疏设置未改变。Git官方文档指出set采用worktree专属配置，适合按任务精简检出：https://git-scm.com/docs/git-sparse-checkout 。

本轮独立分支仍为task/68-local-storage-cleanup，基线6197f24a9cc03ab0dc5e2e72297457f638e37292；交付通过原PR69追加，待审未合并。原第一轮报告/回执保留，不重写原始统计。Projects read:project仍待同步。
