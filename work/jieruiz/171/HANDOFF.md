## Issue171发布回执（2026-10-24）

PR172已转ready、待审未合并，科学提交7a8b5e6e；23文件远端原字节回读一致，Issue171已同步。28项结果核验完成，Slurm2880已结束；无定时、无待运行任务。原始结果和源码包归档未解压复制，RECOVERY.json记录位置/SHA。Projects未同步。

## Issue171非线性位宽初筛完成（2026-10-24）

Slurm2880已结束，执行71cb58d0；28/28封存documents/sidecar SHA、36层全前缀覆盖通过。后训练Qwen3-4B，16×128=2048目标后缀，不是完整WT2。BF16 12.791943，W8原非线性12.584887；g/u幅度6/7/8/10/12分别13.041899/12.607359/12.607722/12.581222/12.577710；组合8/8/8为12.662423(+0.616%)，8/10/8为12.602765(+0.142%)。固定四档T64矩阵三seed：原非线性12.599698±0.016841，8/8/8为12.673273±0.066138(+0.584%)，10/10/10为12.586853±0.026572(-0.102%)。幅度位不含符号，驱动含符号，概率另true-one；TRAIN固定PoT尺度2..256，非线性只有条件均值，无有限AND采样。矩阵恢复仍FP32参考，不是整链bittrue/PPA或训练。

负责人jieruiz/task/171-nonlinear-width，PR172依赖PR169，待审未合并。报告qwen3/results/nonlinear_width_20261024/REPORT_ZH.md；原件project_archives/qwen3_nonlinear_width_20261024/sealed-2880.tar.gz，SHA5ea60da95c0d186f5ac1b20b68ff4348fb04107fb411340a93762cda2b889ac4，成员索引RAW_INDEX。无运行任务/定时，不重交；候选8位幅度+符号/驱动8/概率8，10位留余量，下一步有限AND噪声与全链有限恢复仍待验证。远端发布以FINAL_PUBLICATION.json为准，Projects未同步。

## Issue171 Qwen3非线性位宽初筛（2026-10-24）

负责人jieruiz；task/171-nonlinear-width；目录tmp/qwen3-nonlinear-width-issue171-20261024；base PR169@1d16d8cc，拟PR base task/168-qwen3-fixed-scale，依赖其推理源码。Slurm2880已运行，执行71cb58d0冻结；服务器6项预检通过，28项后缀PPL（16×128目标），36层全部替换。非线性使用有限码/LUT的条件均值，不是有限三流AND采样；矩阵恢复仍为FP32参考。W8单因素扫描及固定四档T64三seed组合；无训练/RTL/PPA。模型/数据复用已验证manifest。成果root与包SHA见SUBMISSION.json。完成后核验complete.json的documents SHA、28唯一配置和层覆盖，勿重复提交。Projects未同步；发布回执待补。

