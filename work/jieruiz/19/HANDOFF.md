# Issue19 可执行交接

当前状态（2026-10-18）：已收回16/26项，见文末“用户授权合并本阶段基线”与个人STATUS。以下较早段落作为带时间的历史保留；其中“待提交”“12项”等不是当前状态。用户已授权合并PR20，剩余评测继续，Issue19保持开放。

更新时间 2026-10-18T14:54:31+08:00，负责人@jieruiz。状态细节见../../../../progress/jieruiz/STATUS.md。

1. 本任务checkout/branch见startup.json，base dd9f12b；数值代理提交a03fde7已cherry-pick e10896e，原代理目录无并行写入。
2. 服务器个人目录 /home/Hongjie_Zeng/projects/pbit-llama2-ffn-precision-20261018-issue19/。BF16不可变snapshot和作业2081见baseline_submission.json。原sbatch带CRLF，未提交成功；保留原字节另新增LF驱动run_bf16_lf.sbatch后成功提交。提交后的快照禁止修改。
3. SSH使用本机已授权lab-server-ai配置，不提交配置文件。Slurm在/opt/slurm/21.08.8/bin/；环境/home/Hongjie_Zeng/.conda/envs/pbit_llm/bin/python，torch2.7.1+cu128/transformers4.45.2。
4. 模型沿用/home/Hongjie_Zeng/pbit_llm/models/Llama-2-7b-hf，不复制大权重；身份manifest在architecture_tlm/llama2_7b/configs/model_identity.json。语料在pbit_llm/data/wikitext-2/，固定原始字节，trainSHA6707892f...、testSHA173c87a5...完整值写run.py。
5. 待执行：提交当前源码为不可变快照→Slurm Tensor/CUDA测试→afterok BF16+tests 后校准→afterok校准后完整PPL。通过每个输出的ARTIFACT_MANIFEST校验后收回小型汇总。完整结果未完成前不得将任务写为完成。
6. full WT2=335687tokens/335686targets，2K/512。全部注意力保持BF16准确SDPA；严禁称PV采样联合结果。Q10与原RTL按整数oracle对齐，但矩阵是FP32统计恢复，不是bit-true完整硬件。
7. GitHub仅workspace目标仓库，任务PR到pbit-tlm-attention-details-20261016；不推origin，不混入Issue7工艺资料。上传前核对身份、远端规则/Issue/PR、文件清单和Git blob字节哈希。Projects无权限待同步。

## 已更新的远端状态

BF162081完成且复现旧结果；CUDA2082的17测试全通过；校准2083完成；完整PPL数组2084（0-25%2）运行中。见numeric_submission.json和suite_submission.json。快照a8ea21f不可改。首批是w8_only、a8_exact，后续a8_q10/enum256_q10再到准确SiLU的随机采样。完整日志留服务器logs/ppl-2084_<array index>.log；squeue/sacct使用绝对Slurm路径。获取脚本本机tmp/issue19_collect.py，只取有最终manifest的目录并逐SHA核验；不把半成品summary视为完成。

已收回并逐SHA验证：bf16_reference、calibration、w8_only、a8_exact，位于llama2/results/ffn_precision_20261018。实际完整PPL W8=4.9809463739276145，W8+A8=5.038304561452122。其余不虚报完成；PUBLICATION_MANIFEST负责本次发布的文件字节。

## PR20和追加结果

任务分支已推送，草稿PR20已创建并附本任务，未合并。4/26项替换PPL完成：W8-only、A8精确、A8 Q10、enum256 Q10。最后二者完整PPL5.048801081382167及total_nll543526.2572862941完全相等。数值误差参考为FP32矩阵恢复，不是整个硬件的bit-true仿真。额外只增测试快照3ea0541的Slurm2090已18/18通过；评测快照a8ea21f不变。

数组2084的IID4/5已启动；对任务5以及待测6-15、22-25设置Nice=1000，让后续64/128拍分层优先；仍最多2GPU，没有取消或覆盖任何数值产物。该变更只影响调度顺序，不改变配置或样本。没有自动心跳/自动收集作业；下次接续需主动squeue/sacct、运行本机tmp/issue19_collect.py和issue19_results_doc.py后核验manifest，再更新同PR/Issue。

## 追加分层/能耗/文献分析 2026-10-18T16:21:20+08:00

已有10/26完整PPL，见新分析报告及EFFECT_AUDIT_20261018_v1.json。分析源码commit1d8be3a8ecd04b1a9904324f388cf844e28c5abe，执行快照a8ea21f不变。64三种子约6.758，相对5.038量化基线仍差；128已有结果明显改善但未收齐时不得虚报三种子。逐层小概率统计是线索，不是严格down因果消融。

文献4篇primary已核实，包括P2LSG直接测试LHS；有序单边分层不是通用双流AND/Ising替代。功率和能量分开，尚未生成新PT数据。优先级24/25已设Nice0，等待midpoint64/128；其他旧对照保留，不取消。新输出获取仍使用同collector/renderer；analysis工具只接受已提交LF源码，并要求新JSON文件名，旧分析v1不覆盖。新增结果后可生成v2并更新报告表，而不是改v1字节。

## 追加分层/能耗/文献分析 2026-10-18T16:25:25+08:00

已有10/26完整PPL，见新分析报告及EFFECT_AUDIT_20261018_v1.json。分析源码commit1d8be3a8ecd04b1a9904324f388cf844e28c5abe，执行快照a8ea21f不变。64三种子约6.758，相对5.038量化基线仍差；128已有结果明显改善但未收齐时不得虚报三种子。逐层小概率统计是线索，不是严格down因果消融。

文献4篇primary已核实，包括P2LSG直接测试LHS；有序单边分层不是通用双流AND/Ising替代。功率和能量分开，尚未生成新PT数据。优先级24/25已设Nice0，等待midpoint64/128；其他旧对照保留，不取消。新输出获取仍使用同collector/renderer；analysis工具只接受已提交LF源码，并要求新JSON文件名，旧分析v1不覆盖。新增结果后可生成v2并更新报告表，而不是改v1字节。

## 追加分层/能耗/文献分析 2026-10-18T16:29:42+08:00

已有12/26完整PPL，见新分析报告及EFFECT_AUDIT_20261018_v2.json。分析源码commit1d8be3a8ecd04b1a9904324f388cf844e28c5abe，执行快照a8ea21f不变。64三种子约6.758，相对5.038量化基线仍差；128已有结果明显改善但未收齐时不得虚报三种子。逐层小概率统计是线索，不是严格down因果消融。

文献4篇primary已核实，包括P2LSG直接测试LHS；有序单边分层不是通用双流AND/Ising替代。功率和能量分开，尚未生成新PT数据。优先级24/25已设Nice0，等待midpoint64/128；其他旧对照保留，不取消。新输出获取仍使用同collector/renderer；analysis工具只接受已提交LF源码，并要求新JSON文件名，旧分析v1不覆盖。新增结果后可生成v2并更新报告表，而不是改v1字节。

## 本轮最终统计

12/26项完整替换PPL已收回并核SHA；64分层三种子6.7583712077±0.0084644937，128分层三种子5.3089041807±0.0016423594；IID256已有两种子6.252346/6.254443。128相对同量化5.0383045615仍约+5.37%，不视为同精度。新报告、v2分析和4篇primary来源随本次PR20更新；v1为上一阶段分析原件，不覆盖。尚无分层PT功耗结果。

## 追加分层/能耗/文献分析 2026-10-18T16:36:42+08:00

已有14/26完整PPL，见新分析报告及EFFECT_AUDIT_20261018_v3.json。分析源码commitcb1b9a561f233a437cb0612fad0ade309da6f339，执行快照a8ea21f不变。64三种子约6.758，相对5.038量化基线仍差；128已有结果明显改善但未收齐时不得虚报三种子。逐层小概率统计是线索，不是严格down因果消融。

文献4篇primary已核实，包括P2LSG直接测试LHS；有序单边分层不是通用双流AND/Ising替代。功率和能量分开，尚未生成新PT数据。优先级24/25已设Nice0，等待midpoint64/128；其他旧对照保留，不取消。新输出获取仍使用同collector/renderer；analysis工具只接受已提交LF源码，并要求新JSON文件名，旧分析v1不覆盖。新增结果后可生成v2并更新报告表，而不是改v1字节。

最终补收midpoint64=5.9955130639、midpoint128=5.4120198259，均完整PPL；目前14/26替换结果。分析v3保留新数据且不重写v1/v2。64拍随机不如midpoint，128随机略好但对照为有偏截断，不是最优RNE。源码快照始终未改，既有0..25数组不新增或取消；后续按squeue查剩余6..15、22/23。

## 本轮发布回执 2026-10-18T16:41:08+08:00

数据/分析已实际推送a691fece94858fe751da78ccea74077df865c10f，PR20草稿未合并，Issue19最新评论：https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/19#issuecomment-6247732705。EFFECT_PUBLICATION_RECEIPT.json为已完成远端动作回执。共165个Git blob原始SHA/大小匹配；14/26项完整替换PPL收回。剩余12项仍运行或排队（交接时6/7运行）。这次没有新PT测量或RTL修改；论文调研与条件能耗情景已完成。下一步主动收集其他结果，按同manifest验证后更新同PR；不要重跑已完成作业或修改快照。

## 用户授权合并本阶段基线 2026-10-18T17:53:23+08:00

此前按时间追加的10/12/14项段落均为历史状态；以本节及STATUS为当前事实。新收回IID256_s2和IID4096_s0，现16/26项。分析v4保留新数据、不覆盖v1～v3。DS_CIM_COMPARISON_AND_BASELINES_ZH.md记录原文p2～p6核对及128拍分类、比较缺口。无源码/RTL修改，无新模型作业。

数组2084_8/9运行，其余10-15、22/23待排队；数据仍在个人项目outputs，获取脚本tmp/issue19_collect.py核全部原始SHA后只收小型JSON。更新RESULTS与publication manifest，analysis输出必须新文件名。GitHub实际已核jieruiz管理员；PR20干净可合并、无保护/ruleset/required checks，不需绕过审查。先推本次更新，再核head SHA、ready并merge；实际merge回执另同步，未发生前不写已合并。保留Issue19开放和源分支，下一次追加结果使用合并后的独立任务分支。
