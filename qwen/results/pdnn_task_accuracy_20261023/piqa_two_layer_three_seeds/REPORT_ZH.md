# P-DNN任务准确率核验

状态：部分完成：4/21；不能作完整比较结论。

模型：两层为当前joint4权重的10/12子集，非历史6/12模型；四层为10/11/12/13的reference_1000现存权重。已逐一绑定本次SHA，不能直接套用旧四层PPL或宣称是旧checkpoint。N=4条完整随机路径，BF16浮点权重；未训练或W8量化。

PIQA、ARC-Easy使用完整指定split；HellaSwag只用预先固定的1000/10042题，非完整HellaSwag。

| 任务 | 模型 | acc (%) | acc_norm (%) | 相对BF16 acc / acc_norm (百分点) |
|---|---|---:|---:|---:|
| piqa | BF16 | 70.511 | 69.967 | 0 / 0 |
| piqa | P-DNN两层10/12 | 68.662 ± 0.094 | 68.317 ± 0.354 | -1.850 / -1.650 |

±为三个推理seed的样本标准差，不是题目统计误差、置信区间或训练初始化差异；不对三任务简单取平均。

官方lm_eval 0.4.8 process_results已在服务器逐题执行并对保存结果回读。此处仅审计原件、请求身份、分数、二值指标及数值聚合，没有本地重算官方指标或读取标签；acc_norm遵循官方选项字符长度归一化。

SUMMARY.json逐case列出软件推理耗时和峰值显存，仅是GPU随机仿真参考，不代表硬件功耗、面积或延迟。

待完成：pdnn4_joint1000_s0_piqa、pdnn4_joint1000_s1_piqa、pdnn4_joint1000_s2_piqa、bf16_arc_easy、pdnn2_subset_joint4_s0_arc_easy、pdnn2_subset_joint4_s1_arc_easy、pdnn2_subset_joint4_s2_arc_easy、pdnn4_joint1000_s0_arc_easy、pdnn4_joint1000_s1_arc_easy、pdnn4_joint1000_s2_arc_easy、bf16_hellaswag、pdnn2_subset_joint4_s0_hellaswag、pdnn2_subset_joint4_s1_hellaswag、pdnn2_subset_joint4_s2_hellaswag、pdnn4_joint1000_s0_hellaswag、pdnn4_joint1000_s1_hellaswag、pdnn4_joint1000_s2_hellaswag
