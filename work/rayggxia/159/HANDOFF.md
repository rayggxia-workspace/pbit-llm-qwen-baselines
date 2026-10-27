# Issue159：七组随机FFN训练交接

日期2026-10-27；身份rayggxia。正式repo rayggxia-workspace/pbit-llm-qwen-baselines；分支task/159-seven-case-pot64-plan；base PR178/task/177-trainable-and-ffn@216f2b9939e9984f140290c98edb05db3aad5c0f。旧57项方案保留历史，不启动。本次接续原Issue159，不重复新建同范围Issue，不修改jieruiz STATUS或远端运行快照。

用户最终定义固定为CASES.json七行：B0/W6/W10/S1/S3/T16/T64，三因素是位宽、共享粒度和采样。B0 W8/tile64-PoT/T32。不可把第三组改成全局少数codebook，不扫描组合。

成果入口：qwen3/training/seven_case_ffn_20261027/REMOTE_AGENT_PLAN_ZH.md；共同量化/导出qwen3/weight_quantization/pot64.py；共享尺度离线生成scale_maps.py。输入表、随机非线性、数据/损失/预算等共用，所有权重尺度二次幂并冻结。

实际验证52项48通过4CUDA跳过；七组单因素和13本地文件入口检查通过。源码均UTF-8/LF；正式GitHub发布后逐文件原字节及blob SHA回读。无真实模型权重读取/分布统计、无新4B PPL、无GPU/Slurm/RTL/PPA。

已知执行缺口：原PR178训练器仅FFN-only、输入64/joint32；需要在对方实际全模型IID训练器接入七组目标T（前后两段）、冻结格式、整数边界、checkpoint/分叉和导出。不能把CASES.json直接传旧Config。两步GPU/吞吐预算通过后才启动正式长训。本机root长期备忘录未同步，避免侧会话覆盖主线程；正式分支PROJECT_MEMORY保留原内容并追加决策。Projects未同步，待维护者。

恢复：先读最新Issue159/177和本分支publication回执，再核对正在运行的旧任务，避免重复；将执行分支/runner文件/SHA/配置和Slurm回执写入自己的HANDOFF。此交付PR不自动合并，也不关闭Issue159/177。
