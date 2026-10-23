# 已结束任务工作副本清理回执（2026-10-23）

沿用 Issue68，负责人 jieruiz。本报告只记录“审核github”对话实际回收的10个工作副本，共1,182,605,540 B（1.183 GB / 1.101 GiB）逻辑文件量。保留的10份ZIP和3份增量bundle共418,758 B；报告、Git元数据、系统并发变化不包含在逻辑回收量中。

清理发生于北京时间2026-10-23 00:19，恢复复核于10:29完成。所有目标绝对路径均位于本工作区tmp下，操作前核对Issue为closed、负责人、HEAD、branch、全部文件SHA、未提交及ignored文件；归档校验通过后仅删除已归档独有文件，再使用不带force的git worktree remove移除干净副本。

## 实际回收与恢复

| 原目录（tmp/下） | Issue | 原HEAD | 逻辑字节 |
|---|---:|---|---:|
| collab-issue-1-20261016 | 1 | `8fb45388f51dcc4b6dcff2b25584da767ffd0575` | 24,079,253 |
| qwen-joint-evaluator-dev-20261019 | 50 | `f9be0c1b6fadd6d0661a8fba6248eacaf886d37f` | 190,154,828 |
| qwen-joint-full-dev-20261019 | 50 | `d61b2861edc91e00495268d39a738edb3599f87f` | 190,057,267 |
| qwen-joint-issue50-20261019 | 50 | `e3c5e957c3769b5fc6867b42a52facace647a83b` | 192,156,850 |
| qwen-task-accuracy-issue59-20261019 | 59 | `1c38b11717cab8c60382bcc05c8bcf1c6b58c734` | 192,622,182 |
| qwen-task-collector-agent59-20261019 | 59 | `83af20c37597d5e9cba0c7608118f52c10033f98` | 192,348,075 |
| qwen-task-scorer-agent59-20261019 | 59 | `b4a7e02ada0553ec38175b0cdcaad7510e8e5ba1` | 192,248,526 |
| llama2-task-accuracy-issue73-20261020 | 73 | `3939b730053db7965bb488fee6f5a2818ed1e23d` | 4,218,594 |
| santapp-novelty-issue84-20261021 | 84 | `4168bdc65d1319a454f230f8f5f869d634918160` | 1,170,577 |
| parallel-sampler-issue87-20261021 | 87 | `e32a9252c863f34ebc1f6727748a67263fe44b00` | 3,549,388 |

全部原分支与archive/cleanup-20261023恢复ref保留。3个非集成祖先的历史helper另保存并验证增量bundle，没有将其误报为已合入集成。64个未跟踪/ignored独有文件均保留原字节SHA。模型、最优checkpoint、唯一仿真原件、共享Git对象库、其他成员和进行中任务不在删除范围。

恢复按 [RECOVERY_INDEX.json](RECOVERY_INDEX.json) 的逐项绝对路径、SHA和recovery_ref进行：在主仓库创建按需稀疏worktree，指向原branch或recovery_ref；若需要独有文件，仅从对应ZIP的files/成员恢复。三份bundle依赖已保留集成46804fb3对象，用git bundle verify核验后可导入；不要重建整个混合资料目录或重跑实验。

## 并发归档事件与最终地址

两个对话开始时选择相同归档目录；本对话写入了带_git_state/的ZIP，覆盖另一对话7份同名包。对方删除前SHA门禁正确阻止继续。源文件仍在，已按原顺序和原字节重建那7份ZIP，全部恢复到对方最初记录的SHA；本对话版本另存review_audit_collision_preimages。没有源文件丢失。最终恢复地址以本报告RECOVERY_INDEX及本地REVIEW_REMOVAL_RECEIPT.json为准，早期CLEANUP_PLAN/removal_plan不是实际回执，禁止重复执行旧删除计划。

两个删除清单不重叠：“LLM”对话先前仅移除Issue19回执目录188,406,323 B，并对10份历史文本网表透明压缩释放2,713,174,339 B，见其独立Issue68回执。上述两项均不计入本报告1.183 GB；其后续清理仍在继续，Issue68保持open。本PR只发布已完成范围，不关闭总体任务。

## 实际验证与限制

复核10个删除路径不存在、原分支与恢复ref准确、10份ZIP逐SHA、64个归档成员SHA及3份bundle验证均通过。清理后registry.py check --local --members：35记录、516行、157文件、26归档成员，PASS且无缺失。校验不是新RTL/DC/PT/PPL运行。

本机恢复制品留project_archives/cleanup_20261023，不上传GitHub原始资料。此PR仅提交小型报告/索引、本人STATUS/HANDOFF和长期记忆；恢复索引不保证其他机器能访问本地路径。当前C盘空间为时点观测，不能把其他对话/系统变化归因于本报告。
