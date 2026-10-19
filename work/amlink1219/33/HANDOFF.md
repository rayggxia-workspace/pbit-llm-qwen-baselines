# 分层FFN参考采用已上传（当前状态）

已核验目标任务分支结果提交`e8eec4c8deb296db4c4ed937c5c46192a782c6f4`，[PR58](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/58)开放待审、未合并，接续Issue33。B4/T32/K32主参考及三个对照、源码SHA、13项CPU核心测试和4profile接口均已交付。此前“本地待提交”等段落保留为历史准备快照，准确回执见STRATIFIED_REFERENCE_PUBLICATION.json。

本次没有新模型PPL/GPU作业、未改TLM/PPA默认；PR52完整联合仍未收齐，恢复重新核状态。看板scope不足待同步。稳定manifest不含易变进度/交接/发布回执，后续元数据提交不改变已核验的方法和配置。

# 当前接续：分层FFN采用（2026-10-19）

Issue33本人负责；分支task/33-stratified-ffn-reference；目录workspace_projects/fa33；base=ed0c7a4e8e9546ec89895135efff36aa8a00d568。新增architecture_tlm/ffn_stratified_reference的版本锁定配置、原StratifiedFFN工厂和方法说明，追加本用户的AGENTS规则，未改他人FFN源码、进度或运行任务。本次采用变更本地CPU验证已通过，尚待提交/推送及PR。

FFN核心发布5518a0a2、原执行db27fa3d，PR47已经合并bef83e54；B4/T32/K32为主，B2/T32/K32、B4/T16/K16、B4/T64/K64保留。三seed完整FFN-only已有PPL；本次不重新声称复现。使用原实现的共享相关性与符号/尺度/端点语义，版本校验对Python代码仅允许CRLF/LF差异，历史实验原件SHA不作归一化。

运行本地CPU接口：隐藏GPU后 python -B -X utf8 architecture_tlm/ffn_stratified_reference/reference.py --smoke；原核心测试 experiments/qwen_multiscale_stratified_20261019/test_stratified_core.py。不需Transformers或模型权重即可做这两项。真实PPL另需本人Slurm分配、精确模型/数据SHA和匹配BF16门禁。

PR52公开head=e3c5e957c3769b5fc6867b42a52facace647a83b，后缀结果与完整pending边界见reference.json及README。记录中2430/2461由jieruiz继续，不访问其Hongjie_Zeng目录，不重交；新联合用PR52的Guard/ExecutionAudit，新case用fresh模型。不得放宽Issue48 original-FFN guard然后把绕过当完成。

发布时核amlink1219、目标repo权限、实际push URLs、文件范围；本任务交付为新PR接续Issue33，不合并旧PR或修改Issue50。Projects若仍缺scope则记录待同步。之后的元数据/验证回执会在此顶端追加当前状态；以下保留旧已合并计划的交接，不能用旧状态判断今天任务。

# 2026-10-19 Attention质量证据核查接续

本次恢复已核最新Issue/PR/成员状态：其他成员Issue46/PR47属FFN，不接管。先读根architecture_tlm/ATTENTION_QUALITY_EVIDENCE_AUDIT_ZH_20261019.md及本目录QUALITY_AUDIT_20261019.json。此前“没有完整模型PPL”的宽泛表述应改为：历史已有24层模型级后缀PPL，但没有查到当前max4筛选→真实Ising同一路的联合/完整WT2质量验收。

已完成历史代码分支与数值核查；没有新job_id/模型运行。接续按报告第“接续实验只补缺口”节建立具体实现/执行Issue，在独立工作树做原FFN、当前预算的联合模型。不要重新跑140项旧矩阵，也不把精确Softmax后IID叫Ising。当前核查通过PR42补交，不关闭Issue。

下面保留原交接历史时点：

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
