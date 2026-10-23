# 两层／四层 P-DNN 的任务准确率

Issue145 / PR149，负责人amlink1219。21/21完整case与9/9真实GPU预检均已完成并独立核验；未训练新模型。

执行：RTX5090单GPU Slurm2835，COMPLETED/0:0；CPU2834 COMPLETED/0:0。模型执行源f4eb25e53834e06220cbfad670ae03195eba8706；报告／审计工具后续提交与执行源明确区分。18项机制测试通过，原始失败2833及其旧快照／partial保留。

# P-DNN任务准确率核验

状态：21项完整评估均已核验。

模型：两层为当前joint4权重的10/12子集，非历史6/12模型；四层为10/11/12/13的reference_1000现存权重。已逐一绑定本次SHA，不能直接套用旧四层PPL或宣称是旧checkpoint。N=4条完整随机路径，BF16浮点权重；未训练或W8量化。

PIQA、ARC-Easy使用完整指定split；HellaSwag只用预先固定的1000/10042题，非完整HellaSwag。

| 任务 | 模型 | acc (%) | acc_norm (%) | 相对BF16 acc / acc_norm (百分点) |
|---|---|---:|---:|---:|
| piqa | BF16 | 70.511 | 69.967 | 0 / 0 |
| piqa | P-DNN两层10/12 | 68.662 ± 0.094 | 68.317 ± 0.354 | -1.850 / -1.650 |
| piqa | P-DNN四层10–13 | 67.791 ± 0.144 | 66.794 ± 0.175 | -2.720 / -3.174 |
| arc_easy | BF16 | 64.394 | 58.333 | 0 / 0 |
| arc_easy | P-DNN两层10/12 | 61.897 ± 0.409 | 54.068 ± 0.088 | -2.497 / -4.265 |
| arc_easy | P-DNN四层10–13 | 59.287 ± 0.232 | 50.940 ± 0.064 | -5.107 / -7.393 |
| hellaswag | BF16 | 41.900 | 52.400 | 0 / 0 |
| hellaswag | P-DNN两层10/12 | 39.400 ± 0.361 | 48.300 ± 0.400 | -2.500 / -4.100 |
| hellaswag | P-DNN四层10–13 | 37.633 ± 0.058 | 44.300 ± 0.557 | -4.267 / -8.100 |

±为三个推理seed的样本标准差，不是题目统计误差、置信区间或训练初始化差异；不对三任务简单取平均。

官方lm_eval 0.4.8 process_results已在服务器逐题执行并对保存结果回读。此处仅审计原件、请求身份、分数、二值指标及数值聚合，没有本地重算官方指标或读取标签；acc_norm遵循官方选项字符长度归一化。

SUMMARY.json逐case列出软件推理耗时和峰值显存，仅是GPU随机仿真参考，不代表硬件功耗、面积或延迟。


正式证据：[SUMMARY.json](complete_21/SUMMARY.json)、[独立核验](complete_21/VALIDATION.json)、[原件索引](complete_21/ARCHIVE_INDEX.json)、[原始小型结果归档](complete_21/originals.tar.gz)。

[协议与配置](../../../experiments/pdnn_task_accuracy_20261023/PROTOCOL_ZH.md)；[接续记录](../../../work/amlink1219/145/HANDOFF.md)。模型权重、parquet与tokenized prompts保留已登记本人服务器位置和SHA，Git归档排除它们。早期1/21快照保留在preflight_and_first_baseline，不能代替本次完整结果。
