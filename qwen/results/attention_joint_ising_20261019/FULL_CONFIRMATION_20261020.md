# 原FFN＋筛选Ising Attention：S128代表性完整WT2确认

2026-10-20，Issue55对PR49追加审阅。本段引用本人Issue50已有完整对照，不改PR49原34项后缀结果、执行快照或amlink1219个人状态，不访问其服务器目录。

完整原件和逐项证据位于[25项联合路径报告](../joint_full_wt2_20261020/RESULTS_ZH.md)及[原件目录](../joint_full_wt2_20261020/originals/53dd0ff6a04218dc9f2b692464d5b16da284cf17/full/)。该目录由PR52发布，原始结果SHA、每段NLL和计分审计独立核验通过。

原FFN（ffn=none）＋screen_ising S128，三个seed 0/1/2，完整WT2 PPL均值12.3186764361、seed总体SD0.0050345839。匹配cached BF16为11.6521180679，几何PPL比约+5.720491%。299078测试token、299077目标各一次，window2048/stride1024/batch32、burn16/spacing4、固定最多8块，所有计分目标真实通过24层decode；Attention多token前缀仍准确SDPA，原FFN保持不变。

PR49冻结执行11f1d6ee的Attention/CTMC/scoring/evaluator由Issue50 UPSTREAM_MANIFEST锁定、逐blob一致。joint ffn=none分支与原49按batch的数值循环相同；门禁/audit包装没有替换成准确Softmax IID。两套小模型config原件仅28个CR换行字节不同，解析JSON相同；模型revision/权重/text/token/校准SHA均一致。完整执行源53dd0ff6a04218dc9f2b692464d5b16da284cf17保持原样，不把本轮只读核验写成新GPU运行。

这只完成S128三seed代表性完整确认；本包没有原FFN S512完整原件，原六档曲线的其他S仍为4096目标后缀。不得将完整PPL与旧后缀PPL直接相减，也不声称六档均有完整确认。无full IID控制，不作全量误差归因；seed SD不是语料置信区间。用户未指定可接受质量阈值，本次验收的是实现与如实报告，不宣称质量等价、芯片PPA或TLM默认已验收。

2430旧scontrol记录已过期、sacct storage disabled，完成依据为封存completed原件、输入/source/config SHA、7300段整体NLL核验及逐目标/层审计；未伪造调度会计终态。原PR49的失败门禁与修正历史继续保留。
