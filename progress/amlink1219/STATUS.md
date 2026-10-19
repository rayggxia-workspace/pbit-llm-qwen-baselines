## ReMix v1精读，Issue70（2026-10-19）

用户指定v1正文和附录核查完成，Zotero原条目/PDF保持，唯一机器note25FR4EFX；24例独立数学校核通过。入口architecture_tlm/research_readings/REMIX_V1_ZH_20261019.md，工作资料work/amlink1219/70/。没有模型复现、训练/PPL/PPA；研究原任务61已关闭，本任务独立交付待审。

本轮p-attention能量调研已上传`a0d08a4208fe505c81aa150abf807fd5e622a0f2`，PR63开放待审未合并；远端ref/PR head及17项稳定制品Git blob已核验，回执P_ATTENTION_PUBLICATION.json。无新模型/训练/PPL/PPA；同事Issue50/59不重交。

## 2026-10-19 可训练能量p-attention调研

接续Issue61/PR63，核查PR52 e3c5e957c3769b5fc6867b42a52facace647a83b仍开放未合并。现有screen_ising已经不显式计算Softmax，直接score差热浴CTMC；新路线是蒸馏筛选器＋低维/低位条件能量＋实际有限链训练，独立mask与binary/tree作为另一结构。报告architecture_tlm/p_attention_feasibility_20261019/README_ZH.md；计划未执行，没有新模型/PPL/GPU/PPA。现有原始/负面证据保持，Issue50/59作业不重交。数学核验与文献入库回执在work/amlink1219/61/p_attention/。Projects仍按既有scope待同步。

本轮activation-only研究已上传`de10df308c78d5983ad4e1461518e8c9dc8d514d`，PR63开放待审、未合并；远端ref/PR head及18项稳定制品Git blob已核，实际回执ACTIVATION_ONLY_PUBLICATION.json。没有新模型PPL、训练或PPA。

本轮用户限定三投影＋连续up＋仅激活p-bit；精确A/B/C未找到执行/PPL，A只在历史§27提案。旧双支/AND/SC不得按名称迁移结论。activation_only报告、结构化计划、21tip/506历史对象审计、StochA直接负面先例和Zotero本批核验已整理；未训练。

用户再次核实门控历史：双路gate/value及三投影K4 AND-bank均已做，不能把保留门控/多位编码当新主线。当前优先训练B4/T32/K32随机计算FFN；旧结构须明确新增条件和数字/原实现对照。报告§4.2与JSON已纠正，未启动训练。


用户纠正后的增量：旧两投影全路径降为高风险诊断，加入匹配20层连续入口与四层4bit原件、表示/采样/结构控制门禁；补充AGENTS防止按单层结果重复优先推荐失败扩层路线。没有新训练或质量结果。

# Issue61：硬件感知训练研究与待执行计划（当前状态）

日期2026-10-19；负责人amlink1219；task/61-hardware-aware-training，独立目录workspace_projects/ht61；base集成88764ec8f6f00ed05f4ab337902bd23ad08cc4a8。身份75301230、目标repo1420564659和push/admin=true已核实。Issue33已关闭、PR58已合并；下方旧“PR58待审”等文字是历史快照。

用户确认较充足H100。本次核Extropic Z1T及一手训练文献、旧P-DNN/AND/variance负结果，提出当前B4/T32/K32到T16的真实短流微调、QK筛选器/有限Ising蒸馏、原生sigmoid/tanh激活及从头训练、DyT独立对照。正式报告与JSON在architecture_tlm/，来源和可执行交接见work/amlink1219/61。

本地56个精确条件Binomial均值/方差案例、SiLU/tanh恒等式、非线性顺序反例、同参数宽度、相对链接与4个既有源码SHA校核通过；仅CPU标准库检查，不是PPL、训练或PPA。独立只读评审后补DyT的embedding/alpha初始化。没有新训练、H100申请、Slurm任务、checkpoint或数据下载。

Issue50/PR52完整联合及Issue59代表任务属于jieruiz，只读公开结果，本任务不重交、不改变其状态。训练数据版本、H100实际调度/配额和本人存储尚需在执行Issue冻结。文献仅公开本批状态，不上传全库书目/PDF。

研究交付已推送777b3e51aec48c5c689c78e2257e18243c18c4b8，PR#63开放待审、未合并（https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/63）；远端ref、PR head、13项文件范围和稳定manifest的Git blob已核验。真实回执见work/amlink1219/61/PUBLICATION.json。看板按实际GraphQL响应记录，权限不足不影响报告交付。不自动合并或关闭Issue61。

以下为继承历史记录，最新协作状态需重新查询远端：

# 分层FFN参考采用已上传（当前状态）

已核验目标任务分支结果提交`e8eec4c8deb296db4c4ed937c5c46192a782c6f4`，[PR58](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/58)开放待审、未合并，接续Issue33。B4/T32/K32主参考及三个对照、源码SHA、13项CPU核心测试和4profile接口均已交付。此前“本地待提交”等段落保留为历史准备快照，准确回执见STRATIFIED_REFERENCE_PUBLICATION.json。

本次没有新模型PPL/GPU作业、未改TLM/PPA默认；PR52完整联合仍未收齐，恢复重新核状态。看板scope不足待同步。稳定manifest不含易变进度/交接/发布回执，后续元数据提交不改变已核验的方法和配置。

# Issue33：采用分层FFN作为后续仿真主参考（2026-10-19）

负责人amlink1219；分支task/33-stratified-ffn-reference，独立目录workspace_projects/fa33；base集成ed0c7a4e8e9546ec89895135efff36aa8a00d568（PR42已合并）。主参考B4/T32/K32，正式配置/复用入口architecture_tlm/ffn_stratified_reference；PR47已经合并，FFN-only完整WT2三seed11.736131±0.000243（BF1611.652735，+0.716%），为既有结果核查，本次未重跑PPL。代码/配置已通过13项核心测试、4profile接口和4源码SHA验证，本次采用变更尚待上传。

PR52读取e3c5e957c3769b5fc6867b42a52facace647a83b，仍Draft未合并；已发布B4T32联合S六档4096目标后缀曲线，完整2430/2461在公开记录中尚未收齐，本任务不重复其工作。FFN-only与联合、后缀与完整、T/K与Ising S分别记录。新参考不改变旧Attention-only原FFN控制或TLM物理PPA默认。

原Issue48/PR49结果已在8dd1b06a上传待审，34/34后缀实验完成；Issue33原PR42现已合并。旧进度段落仅为历史快照，最新协作状态以远端Issue/PR为准。交接见work/amlink1219/33/HANDOFF.md。

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

## PR42 原始交付状态（历史时点）

源head：ee47cb86c75f8a2bc049f25507f785f087ed671d。以下保留该任务新增的历史状态；最新合并状态以Issue55/相应Issue和GitHub为准。

# Attention历史质量证据核查（2026-10-19T06:28:37.698199+00:00）

负责人amlink1219；Issue33 / PR42补充。已确认历史全部24层decode Attention PPL：单独Ising、max4筛选、筛选＋准确Softmax IID及随机投影＋Ising；各自协议/FFN不同，所核Attention结果是WT2短后缀。尚未找到max4筛选→有限时间Ising同一路联合PPL，当前固定512候选/S32/128配置也未质量验收。

报告architecture_tlm/ATTENTION_QUALITY_EVIDENCE_AUDIT_ZH_20261019.md；固定源与SHA索引work/amlink1219/33/QUALITY_AUDIT_20261019.json。未启动新GPU/Slurm或重跑旧实验。后续只补该联合路径、原FFN隔离对照和当前成本模型配置的质量，完整WT2与decode后缀分别记录。其余PR仍待审未合并，Projects仍待授权。

以下保留此前五项发布时点进度：

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

## PR43 原始交付状态（历史时点）

源head：d95334373765d5952e023e00e20c1a7152bfaf95。以下保留该任务新增的历史状态；最新合并状态以Issue55/相应Issue和GitHub为准。

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

## PR44 原始交付状态（历史时点）

源head：1b0af7604037ce8a772063bd9583ce9e1f96f0e5。以下保留该任务新增的历史状态；最新合并状态以Issue55/相应Issue和GitHub为准。

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
