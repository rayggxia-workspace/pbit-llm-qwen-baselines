# 第七轮PR审核与整合

本轮8项103/105/106/108/109/111/113/114均通过各自交付范围审核，保留作者原head，经本审核集成PR进入正式分支。**本文是合并前冻结审核报告；实际合并SHA、来源PR状态及目录回收见Issue55最终回执。** 负责人jieruiz；base pbit-tlm-attention-details-20261016@eb317e4f。逐head、验证和原blob证明见REVIEW.json及evidence。

| PR | 验收内容 | 独立核对与边界 |
|---|---|---|
| 103 | 有限随机服务进入整机默认，100MHz核/源与80MHz SRAM | 93机制/回归、40情景1421合同；独立3项完整Qwen24层重放，每项26字段全等。新q/256不继承PPL |
| 105 | 检查台与旁路stage/query观测 | 52旧快照686不变量；保留旧版本源/结果；与103组合后另重跑完整24层拒绝诊断，336query守恒、26原字段全等 |
| 106 | 16篇频率/时钟域文献补充 | manifest/原文保留与关键一手频率点检；AttAcc核心频率仍pending，不将接口速率当核时钟 |
| 108 | prefill与完整请求评估建议 | 25文档/算术检查，SANTA版本和两阶段口径复核；只是协议/分工计划 |
| 109 | 非随机RTL与周期审计，另补新仿真缺口清单 | 原29执行源、66功能组/12870输出与63活动文件核对；新增head82b17a1的32源/11任务/288整数等价、9626核对通过，无新RTL工具执行 |
| 111 | 统一数字电路台账 | 8守卫、157文件/26tar成员SHA通过，35记录/516配置行/117发现归档；check/render通过 |
| 113 | 随机架构交互图 | 12场景372沿与原模型一致，11节点、三屏宽度、下载/错误输入/无JS错误；修正整机接入状态的过时说明 |
| 114 | 资源/SRAM/同面积探索计划 | 12固定链接、工作集与带宽下界复算；2/4MiB仍只是候选，未启动搜索 |

## 本轮修正

1. 103与105在sample_row和run返回处有真实代码冲突：同时保留真实source参数、finish端点计费和完整观测字段。整合后的109项CPU测试通过，另8登记守卫通过。五个旧接口及六个真实接口的完整输出hash来自合并观测前的原PR103，联合测试核对无观测字段的输出全部不变；历史eb317e4f快照原件不改。没有把更新golden当作修复算法。
2. 架构图、检查台及资源计划混有“默认尚未换源”的早期描述。架构图更新为PR103已接入；检查台和规划的旧52项明确标冻结版本并链接新40项。原trace/执行JSON保持原字节。两套页面独立无头Edge交互检查通过；检查台3模型×5视图及21节点，随机图12场景及1440/768/390宽度。
3. 审核期间Issue107继续编辑临时README，触发登记SHA守卫。未改旧哈希：按aedc08d Git blob恢复7251B、SHA d7b42439…的原件到固定本地归档；记录保留原路径与恢复来源。最终157/26 SHA和确定性render重新通过。没有用新README冒充原功能实验，也没有改他人任务目录。
4. PR109在发布前由aedc08d更新82b17a1，追加11组表征需求。增量仅文档/数学，不是新仿真或可执行新顶层；重新检查原生门禁、32源Git SHA、路径和位宽/单位后带入。9.6倍为状态bit比，非PPA结论；单发64B/100MHz上限6.4GB/s，不能证明16GB/s。

## 验证与来源

组合命令：`python -m unittest architecture_tlm.unified_v6.test_rng_integrated architecture_tlm.unified_v6.test_rng_interface architecture_tlm.unified_v6.test_model architecture_tlm.random_service.tests.test_model architecture_tlm.random_service.tests.test_sampler_adapter architecture_tlm.checks.test_parallel_sampler_v5 architecture_tlm.checks.test_screen_ising_v4 architecture_tlm.checks.test_observation_hooks_v6 architecture_tlm.inspector.test_inspector -v`；109通过。登记另运行unittest discover及registry.py check --local --members、render；8通过且生成表原字节一致。Python3.12，TEMP/TMP显式指向本人项目scratch；首次精简导出遗漏映射/CSV/Git上下文及沙箱默认临时目录错误保留本地诊断，补实际原blob/项目TEMP后通过，未改上游测试来跳过验证。

单项原PR103完整重放：BF16准确234.36001ms、SC筛选PV198.00316ms、SC拒绝S8诊断201.38461ms，均26字段全等。整合后再独立重跑拒绝同案例，336query输出、busy和stage守恒且26原字段全等。S8不是默认S128质量预算；这些是合成事务CPU执行，不是权重推理或芯片时延。

RTL原始归档RAW_VALIDATION.zip保持既有SHA012add32…；本轮读取v6日志，以独立Python参考重建输入/黄金输出并逐笔比较，检查29源、63VCD原字节。没有重跑电路工具或把63活动预检当63项工艺PPA。PPA profile来自台账100MHz默认网表的stream/idle三seed均值；加速reseed300独立网表不混用面积。完整随机前端/整机PPA、512MAC等峰值供给、真实CDC/互连及新组合PPL仍未验收，未知保持null。

文献一手点检包括MoNDE作者PDF §4.3的NDP1GHz、Kelle作者PDF §8的逻辑1GHz、Anda v1 §V-A的285MHz、SANTA v2 Table3及SANTA++ v1计时排除项。文档170项与上述机制/归档检查有范围重叠，不相加宣称新的独立实验数。

## 协作与恢复

8个来源原head均保持祖先可达，作者分支不推送、不重写。本人STATUS/备忘录冲突保留双方有序历史；amlink1219 STATUS直接采用其最新PR108原blob，PR106原状态另冻结在evidence；rayggxia状态由作者两项原提交自动合并，未人工改写。原科学结果未被后续文档覆盖，路径级blob证明在SOURCE_BLOB_PROOF.json。原生门禁没有CI/check运行，不能写成CI跑过；未解决线程0、无changes_requested，实际合并仍由正常GitHub API处理，不绕过保护。

用户新登记规则已执行：本轮没有新RTL/工艺实验，只核对已登记同一批原件及重复的软件模型验证；未新建重复run。Issue95/96/98/104/107/110/112保持原负责人，由实际回执同步阶段，有限PR通过不自动关闭后续研究。Projects待read:project，不代表仓库合并权限不足。未启动GPU/Slurm或恢复已删除定时。

中断恢复时，本轮新建空稀疏目录的index未初始化；已备份其空index，确认只有.git且无用户文件后由HEAD恢复本人index，未清理或重置他人工作树。只保留一个本轮稀疏checkout；完成后先按SHA归档独有材料，再回收本人review/scratch。固定恢复入口project_archives/pr_review_issue55_round7_20261022/。共享Git对象、原实验归档及进行中任务保留。
