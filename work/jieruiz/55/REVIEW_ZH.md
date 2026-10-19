# GitHub PR批量审查与合并记录

2026-10-19；正式仓库rayggxia-workspace/pbit-llm-qwen-baselines；任务与后续回执见[Issue55](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/55)。本轮审核22项，实际合并20项，#49和#52保留draft。此前单独完成的#47与后续发布本报告的PR不计入这22项。

最终科研集成为`20a2565e0465846891c0a4ad0976e4395e7d3ecf`。#11随#8、#45随#44、#54/#57随#29的内容均已进入该集成；19项非main合并提交的祖先关系已逐一核验。#2实际合入main。

| PR | 最初审核范围head → 最终放行head | 实际目标分支 | 实际merge SHA |
|---|---|---|---|
| [#2](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/2) | `8fb45388f51dcc4b6dcff2b25584da767ffd0575` → `8fb45388f51dcc4b6dcff2b25584da767ffd0575` | `main` | `35db82089ea6b76f5fcf76458c37d8ee59d4c7c9` |
| [#4](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/4) | `d9993288cdba0d605733dd37ff84ff1e9608f9bf` → `29a0677cebb7e09b9c15406b51fc4b76fcaa8d20` | `pbit-tlm-attention-details-20261016` | `7bf80c97b7a77050660e46f6b3a12d03039b4725` |
| [#6](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/6) | `9e842bc2a25be962471e5e230c56abd097955d02` → `79b0f7f6204bb78fc842b7c59855c51ed58ed1c1` | `pbit-tlm-attention-details-20261016` | `92234f3ffc1d91a301e2da8a635ed54e29c408ac` |
| [#8](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/8) | `dac6e0426da6421ccc62077275e236532ca3c3da` → `b08beef245dc19bb4e1587ecd84e22d3288e615f` | `pbit-tlm-attention-details-20261016` | `6e94bf15cb1a3523274f80a26f36e75604e3c8f8` |
| [#10](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/10) | `67effd8300284ffff3e49797a965a00f54fefc78` → `979ccb43556f1b85de38fc92a688f6a0b256a8f1` | `pbit-tlm-attention-details-20261016` | `fe9238ebb2b4e19d9ffa03e5b75eaa210cdab48e` |
| [#11](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/11) | `bc45bbebd8fef8ddad0ba450347b8398d0865edb` → `bc45bbebd8fef8ddad0ba450347b8398d0865edb` | `task/7-ffn-cim-scheduling` | `89c5725064bfa1827e28c6566e3899dbc5cb1f9e` |
| [#24](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/24) | `8cd5ed17ae31dae79eb71e9c74bce0e6e84da594` → `0792d23326c5fb7d745c2b1d0d954c1c7b1cf7a3` | `pbit-tlm-attention-details-20261016` | `2ede802c3725cceca50eb3bccfdb33653c3fcde5` |
| [#25](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/25) | `d81095f8cbd76fa496af7f294c57274d9a27734c` → `e25cb00648737177130e9573ebf58ddd1c40968c` | `pbit-tlm-attention-details-20261016` | `c0ca336657757967e9c0512da17453e1f3181586` |
| [#27](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/27) | `e848f791b11e7bc17f22d18323125f5928fbcd19` → `1984f17bf1fe11ea0a604c5096a384e9d9f8abe4` | `pbit-tlm-attention-details-20261016` | `1ec98aee2f28bd4f21f48bf6d31c95787e430e9b` |
| [#29](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/29) | `b347f6af7c003a1d6755ba27fba4b45487b5cb01` → `1ae17b04c6158d82a571e829271f69b285e6bf53` | `pbit-tlm-attention-details-20261016` | `20a2565e0465846891c0a4ad0976e4395e7d3ecf` |
| [#40](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/40) | `3fc3e07d74318d83f2657d8e2f58d87aa5c9ac7c` → `aa37983bfd78a8c83187ca0094b1d5b8cdff2080` | `pbit-tlm-attention-details-20261016` | `e4798f70cb57a864cbbfeb20b83674e1dadc1c4b` |
| [#41](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/41) | `6143aad1dbbd65ddf4420f2f1b1a37cc89cbb857` → `e28b3d57f004a4444bfd785c254e2e6ee2bd41af` | `pbit-tlm-attention-details-20261016` | `82229d54750d65b925f72050f0d8478bc2013c90` |
| [#42](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/42) | `ee47cb86c75f8a2bc049f25507f785f087ed671d` → `2566d17911a01644002356df72c1712e478d0286` | `pbit-tlm-attention-details-20261016` | `ed0c7a4e8e9546ec89895135efff36aa8a00d568` |
| [#43](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/43) | `d95334373765d5952e023e00e20c1a7152bfaf95` → `4f68285bcba81dbe36ed0999aa90294ff8626ade` | `pbit-tlm-attention-details-20261016` | `202eac13d17d88cf049330a620bec844b4c4037d` |
| [#44](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/44) | `0b1f71443107ef091063e04a6de08e3cd997a301` → `245da7a74cbae7866c0eeac783eb1cddfcbfc8d0` | `pbit-tlm-attention-details-20261016` | `46c12e5f6c1c07751272871abb360c35735e8d59` |
| [#45](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/45) | `f6544aafa0da2ddcc4b71a64c0d1a877d1371c42` → `f6544aafa0da2ddcc4b71a64c0d1a877d1371c42` | `task/36-digital-attention-reference` | `1b0af7604037ce8a772063bd9583ce9e1f96f0e5` |
| [#49](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/49) | `8dd1b06aa465b3bdaaed60ae321c5362983ae169` → `8dd1b06aa465b3bdaaed60ae321c5362983ae169` | `task/35-attention-e01` | 保留draft |
| [#52](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/52) | `53dd0ff6a04218dc9f2b692464d5b16da284cf17` → `e3c5e957c3769b5fc6867b42a52facace647a83b` | `pbit-tlm-attention-details-20261016` | 保留draft |
| [#53](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/53) | `a07d695ce703129635c14fe5bbaec249c3170c1d` → `a8794e163c50ac1571a77a2894d13ec5df6b7a97` | `pbit-tlm-attention-details-20261016` | `856105beaefaee307ba1a9b1972aa61d8f82ba59` |
| [#54](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/54) | `56e417eab5ca30354a1b1f960437f1352e736faa` → `52d0b905bac9c971fa45658168d40438db860cd6` | `task/28-project-memory` | `e0abc39fb4fb83510fabb5c6ef22dcc8e3c39a6b` |
| [#56](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/56) | `d8b4593e31b00c2f67fd6d1a77ccd2bfce593a97` → `1930d5b94ddcaec2535bda11db6623ca0244342e` | `pbit-tlm-attention-details-20261016` | `fdceb386d9abe993f494ec09945ef8da35863bb1` |
| [#57](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/57) | `0027d2c3ba8a5407e7a308c8b1f824336801c34a` → `dbf25a4786a1aa5be3505bc984b017689af80ace` | `task/28-project-memory` | `d3861072ff88dbc4e66f2a7844eed4f8ec97245b` |

上述“最初”表示本轮最初清单或新增发现时的精确head；并行作者更新与集成刷新后的实际放行head单列，未沿用旧head自动批准。JSON另保留独立内容复核head、精确base提交、回执时间与本地审计来源SHA。

| PR | 独立价值与验收范围 | 已核验内容 | 验证限制 |
|---|---|---|---|
| [#2](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/2) | TLM已有同版AGENTS，main仍缺模板和入口，未整体覆盖 | 9文档校验、8成果SHA、26链接 | 文档治理验收；不产生新实验。 |
| [#4](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/4) | 保留2026-10-17范围；新质量实验未替代硬件接口/PPA审计 | 5成果SHA、17本地源SHA、4链接 | 有日期的架构缺口审计；新质量结果不自动消除硬件缺口。 |
| [#6](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/6) | 有来源的新电流情景，保留旧默认；不是完整器件认证 | 13测试；15成果SHA；4旧迹重计价 | 核心电流情景/旧迹重计价；未新增DRAMSys或器件认证。 |
| [#8](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/8) | 独立RTL与调度证据，未默认用于模型 | 29成果SHA；LUT/65536点；RTL elaboration | 数字RTL与解析审计；未新跑许可EDA或模型PPL，不改变默认模型。 |
| [#10](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/10) | 解释逻辑稀疏与实际读取；并非新PPL的重复 | 14成果SHA；18旧证据；192等式 | 旧模型固定后缀与合成事务；不写成新完整WT2。 |
| [#11](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/11) | 补充8的独立工艺流程；本次未重跑许可工具 | 18工作负载、Tcl/单位/篡改/VCD拒绝检查 | 未新跑DC/VCS/PT或Icarus；交付的是可检查流程，真实TT/SS后续保持开放。 |
| [#24](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/24) | 原始选题与阅读顺序，27明确引用；并非重复总结 | 正文SHA/副本；7源SHA/7链接 | 定向阅读路线；不能据样本估计整个领域结论。 |
| [#25](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/25) | 硬件功能/条件能耗与47数值质量属于不同证据 | 34成果SHA；43旧日志；31RTL tops | Windows阻止新Icarus执行；新elaboration和历史日志可核，条件能耗非新物理PPA。 |
| [#27](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/27) | 详细机制/质量/PPA边界；明确补齐原摘要缺口 | 现有validator；2blob；26来源SHA | 一份用户CurrentDigitizers原PDF原路径已缺；其余26来源及已有原文提取可核，未实际操作Zotero。 |
| [#29](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/29) | 正式记忆与当前状态可合；科学原文/集成产物字节保留 | 最终1ae17b0；19回执逐核；反撤3项metadata精确还原 | 长期恢复文档；不替代原manifest/实时Issue或仍运行的完整联合确认。 |
| [#40](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/40) | 与47固定W多档不同；前缀负结果仍有独立价值 | 79原件、63执行blob、23发布blob；汇总复现 | 前缀PPL负结果及协议边界；不能等同完整WT2或PR47固定W多档。 |
| [#41](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/41) | 规则被42-45包含，但12份接入证据独有且被AGENTS引用 | 9历史+7发布+17源blob | 规则虽被后续并集覆盖，独有接入证据仍引用；保留历史快照日期。 |
| [#42](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/42) | 后续仅实施部分计划；历史协议与派发审计仍有用 | 27成果+32源blob；623计划行 | 历史方案/623配置计划及派发审计；计划行数不代表已运行实验。 |
| [#43](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/43) | 微基准和真实输入，不能冒称替换后全WT2 PPL | 47通过/1权限跳过；465 full微基准 | 数值微基准与真实输入；不是替换后的完整WT2 PPL或物理PPA；1符号链接权限跳过。 |
| [#44](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/44) | 在线Softmax/GQA完整边界；完整物理PPA刻意留空 | 16历史+7发布SHA；3上下文账本 | 解析数字参考；完整物理PPA刻意留空。 |
| [#45](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/45) | 条件CPU成本模型，与44相依；不是物理PPA | 68历史+7发布SHA；40原件/20执行blob | 条件CPU事务成本；无完整质量验收或物理PPA。 |
| [#49](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/49) | 后缀阶段无阻断；完整确认/质量验收仍待完成 | 38测试；144发布blob/119原件；34配置 | 34后缀配置可核；完整确认/质量验收和作者ready尚未完成，保留draft。 |
| [#52](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/52) | 联合与完整确认仍在推进；保留draft | 34后缀主项、12诊断、15次数扫描；12blob/25段NLL核验 | 34主项+12诊断+15次数扫描为后缀阶段；2430/2461完整确认未齐，保留draft。 |
| [#53](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/53) | 纠正5%阈值解释的新文献整理，非47结果重复 | 2成果、5PDF SHA、14算术；新head增量复核 | 定向文献证据；三篇全文仍缺，不把自定5%质量预算写成领域标准。 |
| [#54](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/54) | 3d6a194尚无10.2/51索引；保留并行5.7/50更新 | 基底/新增SHA；去增量还原原文 | 增量记忆补丁；不能替代原实验或单凭子分支回执声称进入集成。 |
| [#56](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/56) | 任务与评分解释独立于53预算报告；只处理共享状态冲突 | 120行正文；manifest/提交/副本字节；主源交叉核对 | 文献任务/指标解释；新ASADI网络读取超时，沿用已审原报告边界；没有新任务测试。 |
| [#57](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/57) | 新增任务入口/51状态；保留最新5.7.1，已随PR29进入集成 | 刷新dbf25a4；撤增量精确还原c87b；其他树保持 | 仅记忆入口/状态补丁；保留旧manifest历史签名，新head由刷新回执记录。 |

审核没有把历史资料直接判为重复：#24提供阅读路线，#27提供原文机制总结；#41的规则虽被后续AGENTS并集覆盖，接入快照仍有独立引用；#40保留裁剪前缀负结果，#47提供不同协议的固定W多档结果。科学成果与旧manifest按执行/发布版本保留，共享STATUS/README/AGENTS冲突采用并集及当前回执解决。

#29最终内容复核至`1ae17b04c6158d82a571e829271f69b285e6bf53`：新增Ising次数曲线与#52公开摘要匹配，12制品blob、25逐段NLL记录和六档均值核验通过；最新合并状态的3项元数据编辑可精确反撤，恢复原科学文字。19条历史合并回执逐项匹配，最终实际merge为`20a2565e0465846891c0a4ad0976e4395e7d3ecf`。

#49与#52后缀阶段的已发布证据可以检查，但完整确认与质量验收仍未完成，因此继续保留draft。#52最新补审head为`e3c5e957c3769b5fc6867b42a52facace647a83b`；两组完整任务2430/2461未收齐，不把已启动任务、局部统计或原BF16完整锚点写成联合完整结果。

本轮未启动新GPU、服务器、模型、DRAMSys或许可EDA实验；未实际操作Zotero。Windows限制影响新的Icarus执行，已有功能日志、可用elaboration及黄金数据交叉核验分别记录。散列核验说明制品字节与来源一致，不能替代所有历史实验的重新运行。前缀、后缀、完整WT2、条件成本和物理PPA继续分开解释。

#56/#57补充已实际验收；Issue51按验收处理，Issue28继续开放维护长期记忆。其他Issue的关闭与后续真实TT/SS、硬件质量验收按各自范围处理；精确关闭回执和追加测试记录由[Issue55](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/55)统一发布。Projects的read:project授权仍待同步，仓库合并已实际完成。

集成回归：科学提交`e4798f70`的102项CPU unittest为101通过、1项Windows符号链接权限跳过，另1个协议fixture通过；#43/#44/#45/#40汇总全部复现。硬件/TLM在`1ec98aee`通过DRAM13项测试、四组TLM数值重放及84个源码/结果blob保留检查。后续合并到`20a2565e`只新增文献与记忆文档，科学源码、配置及结果不变，见[树核验](FINAL_TREE_PROOF.json)、[CPU回归](evidence/attention_ffn_regression.json)和[硬件回归](evidence/hardware_regression.json)。

逐项完整SHA、base、验证范围、限制与来源见[REVIEW.json](REVIEW.json)，实际Issue处置回执在`issues/`。本文只陈述上述22项的审查和实际处置，不包含随后发布该报告的新PR。
