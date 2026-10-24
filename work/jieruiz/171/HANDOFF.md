## Issue171 Qwen3非线性位宽初筛（2026-10-24）

负责人jieruiz；task/171-nonlinear-width；目录tmp/qwen3-nonlinear-width-issue171-20261024；base PR169@1d16d8cc，拟PR base task/168-qwen3-fixed-scale，依赖其推理源码。Slurm2880已运行，执行71cb58d0冻结；服务器6项预检通过，28项后缀PPL（16×128目标），36层全部替换。非线性使用有限码/LUT的条件均值，不是有限三流AND采样；矩阵恢复仍为FP32参考。W8单因素扫描及固定四档T64三seed组合；无训练/RTL/PPA。模型/数据复用已验证manifest。成果root与包SHA见SUBMISSION.json。完成后核验complete.json的documents SHA、28唯一配置和层覆盖，勿重复提交。Projects未同步；发布回执待补。

