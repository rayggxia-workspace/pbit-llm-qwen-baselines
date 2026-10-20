# Issue55 第二轮PR审核记录

用户要求继续审核，沿用正确且有增量价值则合并、未完成或有问题则保留的授权。原第一轮23项/21合并与报告PR60保留，本轮不重复计入；第二轮共5项，实际合并2项，3项仍draft。以下报告PR自身也不计入5项。

| PR | 审核head | 处置/实际merge | 依据 |
|---|---|---|---|
| [#49](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/49) | `8dd1b06aa465b3bdaaed60ae321c5362983ae169` | 保留draft | 与第一轮同head，仍为draft；联合完整WT2确认/作者ready未完成，不重复历史昂贵验证。 |
| [#52](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/52) | `e3c5e957c3769b5fc6867b42a52facace647a83b` | 保留draft | 与第一轮同head，仍为draft；公开完整确认未齐，保留cached与后缀边界，不重交原任务。 |
| [#62](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/62) | `ebc2d14a4f191a268227faf62b6085d58022bbdc` | 保留draft | 新draft仅11/39公开完整配置，28 pending；联合ARC-E仅S64单seed，短题activeK=1，依赖未合并PR52，尚不可作为完整三seed或长context筛选验收。 |
| [#63](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/63) | `743c3e8998349a6a6a40b412879030144b2e83cb` | `4f2d953395a7335e0f15b0546c91cdac73c81169` | 研究设计与历史证据有增量；方案均标待执行，数学自洽但不作为训练/PPL/PPA证明。 |
| [#64](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/64) | `6497bfdce739e1a2905b36fd7ead45bc240eadd3` | `679fd269ecaa4883bd79619d2f39d6ade2a7daca` | 只增量记忆与进度，已核11/39原件和评分边界，不把阶段结果当全量；修正PR发布正文旧SHA，源head不变。 |

PR63：56+80+38项数学/结构检查通过，独立有限链矩阵指数、非对称proposal与one-hot编码校验成立。锁定的PR52 CTMC在禁用Softmax后运行6000行CPU检查通过，证实该路径直接按score差采样；不证明学习能量的训练效果或物理收益。26项稳定制品、历史来源、官方源码及正文原文范围通过复核。报告明确activation-only与旧双支/AND不同，未把旧失败扩层路线重新写成未尝试方案。

PR64/62：67份原件、73个公开执行blob、12发布文件通过SHA/大小核验，严格collector的SUMMARY一致、Markdown逐字节复现。15项评分/计划夹具与15项collector负面测试通过；本次未安装Transformers或运行0.5B模型，评分CPU采用24层假模型及实际adapter夹具。两份私有校准仅检查manifest索引，不宣称读取原件。

截至所审核PR62 ebc2d14的公开记录为11/39，联合ARC-E S64/s0为1508/2376=63.4680%、字符归一1388/2376=58.4175%。不是三seed验收。三个任务最大计分上下文243/166/139、active K及GQA union均1.0，短题不能验证长上下文QK裁剪。时间估计只属于17:51快照，不是当前队列查询或完成承诺。

已修正PR64发布正文的旧SHA40a7为审核head6497的实际memo SHA8522b5f0a5173b414e4dc5a6eac3980c5beef9f4033afcaa24485fe288237826；source head和原始制品没变。旧STATUS/HANDOFF“待推送”句子保留历史时点，由本轮实际回执覆盖。合并后的联合memo还包含PR63增量，不能把6497源SHA冒称最终联合SHA。

Issue61按原研究设计范围验收关闭，实际训练另续；Issue28继续开放维护。49/52/62及Issue48/50/59继续草稿/开放，不抢占或重复实验。Projects read:project沿已知接口限制待同步，不影响已成功的仓库写入/合并。

原有科学源码、配置和结果Git blob保持一致，仅追加P-DNN设计文档与六个研究计划文档/JSON，见[TREE_PROOF.json](TREE_PROOF.json)。没有新GPU/服务器/训练/PPL/DRAMSys/DC/VCS/PT作业。更多逐项证据见[REVIEW.json](REVIEW.json)、[实际回执](receipts/PR63_RECEIPT.json)、[记忆核验](evidence/memory_PR64_REVIEW.json)和[Issue同步](ISSUE_SYNC.json)。
