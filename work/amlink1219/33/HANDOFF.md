# 本轮补传状态（2026-10-19）

分支已推送，[PR #42](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/42)待审、未合并；Issue保持open。amlink1219当前Admin/push权限已核实。看板GraphQL仍缺read:project，待同步。最新个人汇总见progress/amlink1219/STATUS.md；PUBLICATION.json记录原交付提交，DELIVERY_MANIFEST.json记录补传后文件SHA。

以下交接保留原执行时点，其中无push权限/未发布描述属于历史状态；原manifest按原提交验证。

# Issue33 可继续执行的交接

负责人amlink1219，时间2026-10-18T23:30:29+08:00。目标rayggxia-workspace/pbit-llm-qwen-baselines；Issue https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/33；本地任务目录 `E:/BaiduSyncdisk/p-bit/DAC_2026_Draft_Proceedings/DAC_2026_Draft_Proceedings/workspace_projects/pbit-attention-issue33`，分支`task/33-attention-value-plan`，base `3553996bf014a29dee7fdb2250a3965e8fd881a4`。本次仅调研和实验安排，没有执行任何新模型/RTL/PT/TLM/Slurm任务。

1. 先读本目录TASK_CONTEXT、个人STATUS、根AGENTS、正式计划以及最新Issue3/9/19/22/28/30/32/33和相关PR。主要集成分支仍需实时核对；待审备忘录从明确分支读，不拿旧运行快照重交任务。
2. 原文证据和实际阅读范围见REFERENCES.json与两份调研笔记；LED直接相关论文只有摘要/元数据，不使用其宣传倍率。Zotero回执见ZOTERO_RECEIPT.json。PDF在D:/ZoteroData/storage托管，不把论文原件进Git。
3. 正式计划列出D0-D3数字和P0-P2原生接口，先E0任务契约与真实RNG回放、E1小状态验证和12个pilot，再E2路由/E3完整PPL。全部配置CSV/JSON目前只是计划规格，没有可执行新模拟器，不能直接当运行命令。
4. 需要实现的RNG后端、数字位明确模型、原生事件模型和sample_trace出口在计划第8节；恢复时把实际实现范围和验收列为对应Issue。现有输出跟踪不能证明硬件源质量。保留FFN per-tile重放，根与runtime两副本按实际加载关系固定。
5. 新计算先核Slurm身份、home、个人根、allocation、模型/数据SHA及权限。没有本次job_id；不得推断或取消Issue19/32的作业。先一个安全preflight，估时后仅提交有质量根据的少量GPU正式运行。
6. 质量以同上下文当次BF16、完整目标token NLL为准；首轮主门槛建议ΔNLL≤0.01，随机至少3seed；只把通过质量的点送PPA/TLM。显式概率向量、类别索引和最终V输出三种契约分别比较。
7. 本次分支尚未推送、无PR、无合并；push=false，不能使用其他账号或旧库替代。只提交正式计划、配置、本人STATUS及本任务work文件；PDF、审查缓存、模型/数据/PDK/凭据不在发布范围。提交SHA由Git日志和外部delivery_receipt标识，避免自引用。
8. 有写权限后先fetch/核差异与最新Issue，显式push本任务分支并PR到确认的集成base；更新本人的Issue正文/验收与有权限看板。Issue33的计划交付不等于实际E0-E5实验完成；本地完成不冒充远端已交付。

原始审查、来源缓存和状态回执目录：`E:/BaiduSyncdisk/p-bit/DAC_2026_Draft_Proceedings/DAC_2026_Draft_Proceedings/outputs/pbit_attention_research_20261018`。首份数字与p-bit调研是并行独立只读核查，正式结论由本计划整合；未修改现有硬件默认实现。
