# Issue19 可执行交接

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
