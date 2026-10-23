# 两层／四层 P-DNN 的任务准确率

Issue145 / PR149，负责人 amlink1219。当前为运行中，**已核验 1/21 个完整 case**；不是最终两层／四层比较结论。

首个新 BF16：PIQA validation1838，acc **70.511425%**，acc_norm **69.967356%**，与 Issue59 的缓存评分协议一致。三任务官方数据／prompt／0-shot／选题 ID 已核；18项CPU机制检查、4份真实checkpoint的严格加载，以及9项真实GPU smoke（重放、选项置换、独立BF16缓存参考）均通过。

正在 RTX5090 单 GPU Slurm2835 执行 21 个完整 case。执行源码 `f4eb25e53834e06220cbfad670ae03195eba8706`，CPU预检2834 COMPLETED/0:0。首次GPU2833因runner进度回调字段不匹配失败，修复后使用全新源快照与输出目录，旧失败证据保留在 `work/amlink1219/145/failed_attempt1/`。

模型口径：N=4条完整随机路径；四层为现存joint step1000 的10/11/12/13；两层是同组10/12子集，**不是旧6/12模型复测**。现存checkpoint SHA与旧公开joint4不同，不继承旧PPL。基模型Qwen2.5-0.5B Base，原Attention与连续BF16权重，不训练、不W8量化，不作硬件PPA结论。

- [完整协议与配置](../../../experiments/pdnn_task_accuracy_20261023/PROTOCOL_ZH.md)
- [预检及首个完整基线的审计报告](preflight_and_first_baseline/REPORT_ZH.md)
- [独立核验](preflight_and_first_baseline/VALIDATION.json)与[原件归档索引](preflight_and_first_baseline/ARCHIVE_INDEX.json)
- [接续记录](../../../work/amlink1219/145/HANDOFF.md)

归档不含模型权重、parquet或tokenized prompt；它们保留本人服务器，位置与SHA见TASK_DATA及manifest。完整结果齐备后，按任务分别给两层／四层三seed均值、样本标准差和相对新BF16的百分点差，不把seed波动当题目统计置信区间。
