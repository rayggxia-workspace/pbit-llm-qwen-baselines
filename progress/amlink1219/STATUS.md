# Issue48远端交付核验

结果提交`c2811a61e94226cc79607d91dfeba0d0b9dac992`已在目标仓库任务分支核验，[PR49](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/49)待审未合并（draft=True）；[Issue48结果评论](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/48#issuecomment-6262037367)与阶段清单已同步。34/34后缀案例及全部成果SHA已回收，当前无本任务运行作业；联合完整WT2未执行，Projects缺scope待同步。下面保留本轮结果及历史快照；准确版本与文件索引见Issue48 PUBLICATION/DELIVERY_MANIFEST。

# Issue48：联合Attention采样曲线完成（2026-10-19）

Slurm2380 COMPLETED/0:0，34/34项、S32/64/128/256/512/1024各3seed；原FFN、全部24层decode、准确prefill，4096固定WT2后缀目标/seed。匹配SDPA=10.371557；筛选准确PV=10.895520。联合完整WT2确认尚未执行，不能混称。

CPU2362 38/38；GPU2365原BF16完整WT2锚点及同BF16 wrapper逐位接入通过，参数/输入/目标/结果SHA通过。本任务无运行作业。结果位于qwen/results/attention_joint_ising_20261019；执行源11f1d6eea2776e201f2021081f8b0fbae2cc455e，PR49 base task/35-attention-e01，待审未合并；准确上传回执见work/amlink1219/48/PUBLICATION.json。Projects缺scope待同步。以下旧段落均为历史快照，接续以Issue48 HANDOFF/VALIDATION为准。

# Issue48：Slurm2380正式联合PPL扫描运行中（2026-10-19）

PR49待审未合并，base task/35-attention-e01；执行源11f1d6eea2776e201f2021081f8b0fbae2cc455e。CPU2362完成38/38测试；GPU2365完成，原BF16完整WT2复现11.652735047455899，同BF16 SDPA wrapper和原模型逐位相同、参数前后SHA一致。

Slurm2380在本人gpu5090分配中运行34项2K初始上下文后缀PPL矩阵，每seed4096目标、24层decode、原FFN。尚未完整回收扫描结果，不是完整WT2联合结果。作业/源/输出见work/amlink1219/48/RUNNING_2380.json；中断先查询2380，不重复提交。Projects缺scope待同步。以下旧段落为历史快照，不代表当前作业。

# Issue48：联合筛选＋有限时间Ising模型PPL（实现完成，待Slurm门禁）

负责人amlink1219；分支task/48-attention-joint-ppl，目录workspace_projects/aj48，PR base task/35-attention-e01（复用其输入身份核验）。原FFN保持，24层decode联合路径，S32/64/128/256/512/1024三seed；34项后缀矩阵已注册，完整确认需独立cached计分。

35/35本机真实Torch CPU测试通过、无skip；包括CTMC有限时间/非IID/采样前缀、配额/GQA/因果/原参数保持、每计分目标24层调用及完整目标集合。服务器第二次SSH已恢复，当前已核本人队列空；尚未提交本任务作业或得到新模型PPL。代码与小型旧train校准来源见experiments/attention_joint_ising；接续work/amlink1219/48/HANDOFF.md。

以下保留此前发布进度快照：

# amlink1219 项目进度

更新时间：2026-10-19T03:58:53.771030+00:00；负责人amlink1219（GitHub id75301230）。
正式目标：rayggxia-workspace/pbit-llm-qwen-baselines（repository id1420564659）。2026-10-19实时核验push/admin均为true。
本轮补传基线：pbit-tlm-attention-details-20261016 @c1555ae6594c863011a70845d88c950a68de732b；阶段：五项任务分支均已推送，五个PR待审、未合并。
没有自动合并或关闭Issue；分支、PR待审与已合并分别记录。Projects同步状态见各任务PUBLICATION.json。

| Issue | 分支 / PR | 本轮结果与验证 |
|---|---|---|
| [#1](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/1) | [task/1-amlink1219-hardware-onboarding](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/tree/task/1-amlink1219-hardware-onboarding)；[PR#41](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/41)（待审、未合并） | 协作规范与本机交接；原manifest 9/9。 |
| [#33](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/33) | [task/33-attention-value-plan](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/tree/task/33-attention-value-plan)；[PR#42](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/42)（待审、未合并） | 文献与623行实验计划；原manifest 15/15，计划不等于已执行。 |
| [#35](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/35) | [task/35-attention-e01](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/tree/task/35-attention-e01)；[PR#43](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/43)（待审、未合并） | 原BF16完整WT2 PPL11.652735047455899；CPU39/39，pilot12/12、full465/465；原manifest74/74。 |
| [#36](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/36) | [task/36-digital-attention-reference](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/tree/task/36-digital-attention-reference)；[PR#44](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/44)（待审、未合并） | 在线Softmax+GQA数字参考，10/10解析测试及3上下文账本；原manifest16/16；完整PPA未闭合。 |
| [#37](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/37) | [task/37-attention-comparison](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/tree/task/37-attention-comparison)；[PR#45](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/45)（待审、未合并） | Slurm2164完成，9/9快照测试、32/32事务场景、40返回文件SHA；原manifest68/68；完整物理PPA和PPL尚未验证。 |

Issue37依赖Issue36：PR base为task/36-digital-attention-reference；其余PR base为上述集成分支。
各分支使用相同的AGENTS规则并集与个人进度总表，避免共享文档相互覆盖；正式代码和成果仍按任务分支隔离。
历史执行提交、配置、输入版本、Slurm终态和原始成果散列均保持；原manifest按PUBLICATION.json中的pre_publication_commit读取，不能用后续更新的STATUS/HANDOFF冒充原字节。

正式入口：Issue33 architecture_tlm/ATTENTION_PBIT_VALUE_AND_EXPERIMENT_PLAN_ZH_20261018.md；Issue35 experiments/attention_e01 与 qwen/results/attention_e01_20261019；Issue36 architecture_tlm/digital_attention_reference；Issue37 architecture_tlm/attention_comparison。
辅助/交接：work/amlink1219/<Issue>/。本地工作目录及原任务提交见各PUBLICATION.json；旧STATUS可从原提交恢复。
原始大trace/NPZ留服务器本人/home/Weican_Chen/projects/attention-e01-issue35；Issue37冻结源/原始结果留本人/home/Weican_Chen/projects/attention-compare-issue37。当前没有本轮在运行作业，不重交旧实验。
下一步：审阅上述PR；继续完整随机Attention PPL、有限字长数字实现、真实随机相关性与同工艺PPA验证，不能由代理成本或局部NMSE宣布优势。
