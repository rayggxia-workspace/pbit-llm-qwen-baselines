# jieruiz 项目进度

更新 2026-10-18T14:54:31+08:00；实际GitHub登录@jieruiz；目标rayggxia-workspace/pbit-llm-qwen-baselines。

## 当前 Issue19：Llama2 FFN精度与低于256拍

- 分支：task/19-llama2-ffn-precision；PR base=pbit-tlm-attention-details-20261016 @dd9f12b8cc25f474cafb54b1a58f2be20506cd9e。
- 工作目录：C:/Users/86134/Documents/a_P_BIT/tmp/llama2-ffn-precision-issue19-20261018。数值子任务独立目录tmp/llama2-ffn-numeric-issue19-20261018，提交a03fde7已cherry-pick为e10896e。
- 范围：只读核对Qwen既有PPL；Llama2全32FFN的W8/A8/Q10/采样消融。Attention保持准确BF16 SDPA。Llama1不测，不训练。
- 实际状态：新BF16作业2081已完成：2K PPL4.979502845218782、4K4.895831220529201，与旧参考完全一致；CUDA作业2082的17项验证全部通过，无跳过。校准2083完成，26项完整PPL数组2084已启动、最多2GPU并行。已收回W8-only PPL4.9809463739、W8+A8精确SiLU PPL5.0383045615（均全335686目标）。其余运行/排队；尚未发布PR。
- 方案：完整WT2 noBOS，2K/stride512；新BF16同时重跑2K/4K。固定尺度取train前8192tokens，测试数据不参与校准；A8为8位幅度+符号，不是通常signed INT8。
- 已知缺口：Qwen旧A12结果不等价当前A8；新Q10从未接LLM PPL。统计计数参考使用FP32矩阵恢复，不是完整有限位硬件模型。
- 成果：experiments/llama2_ffn_precision/；辅助与交接work/jieruiz/19/。
- 阻塞/待同步：无模型或语料阻塞。Projects缺read:project待同步。Issue7的脏工艺checkout只读，不覆盖或发布。
- 下一步：收集数组2084确定性精度分解与低T分层/中点/历史IID三种子完整PPL；通过各输出ARTIFACT_MANIFEST验证实际产物；任务分支/PR交付并持续记录完成项。源码快照a8ea21f75ae6d736b2bc0136f8ee55977b082060。

## 已交付

Issue14/PR15 Llama2 BF16+116 TLM已合并7a506365；Issue16/PR17三模型入口和PR18状态回执已合并，当前base为dd9f12b。
Issue12/PR13 Llama1已合并07d0338。此前治理/硬件/筛选等独立分支维持原审查状态。
