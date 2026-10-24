## Issue173 g/u多档扩展准备（2026-10-24）

用户授权接续同Issue/PR174，新增B2/B4/B8固定范围幅度编码、sigmoid整数真实尺度恢复、Wd同指数部分和移位后合并。旧执行与结果不改。5项新本地检查通过，CUDA1项待Slurm；新增45份后缀PPL计划，非训练。下一步冻结并提交multiscale.sbatch，执行/作业ID以MULTISCALE_SUBMISSION.json为准，未有回执前不得重复声称远端已运行。

## Issue173发布回执（2026-10-24）

PR174已转ready、待审未合并；结果提交898ba797，23个文件远端原字节核验一致，Issue173已同步。Slurm2881已退出队列，五片封存核验完成；无定时/健康任务遗留。FINAL_PUBLICATION.json记录回执，Projects未同步。

## Issue173有限AND直连Wd完成（2026-10-24）

Slurm2881五片完成，执行098c7a00db27dded1b7047dc5828871e4b057f70。每片12项检查通过，包括GPU有界整数GEMM与逐拍事件累加参考。27份封存计分/23唯一配置、documents与sidecar SHA、36层全前缀覆盖通过。后训练Qwen3-4B，8×128=1024目标后缀，非完整WT2；准确Attention。BF16五次完全一致13.566049，W8 13.414964；旧8位均值z再编码三seed13.428421，直连均值原尺度13.517797、有限系数13.498204。有限三流直连T64/256/1024/4096三seed分别8949057.252807/7735.004324/30.692997/14.937278。首层平均AND概率0.000910389，T64零事件95.02%；不能用旧均值PPL支持短流直连，也不能认为8位门限只需256次就充分。

新路径：幅度8+符号/驱动signed8/概率8+true-one，独立三流AND事件跨Wd输出共享；Wd固定W8，有限恢复系数16位、signed52输出累加、整数RNE BF16。无z重新统计/定标/采样。gate/up恢复仍FP32参考，无训练、RTL或PPA。建议先解决SgSu和稀少事件问题，再冻结训练硬件前向；勿把当前T64直连直接当可用训练配置。

负责人jieruiz/task/173-and-direct-wd，目录tmp/qwen3-and-direct-issue173-20261024，PR174依赖PR172，待审未合并。报告qwen3/results/and_direct_20261024/REPORT_ZH.md；归档project_archives/qwen3_and_direct_20261024/sealed-2881.tar.gz，SHA1f87f6f00a9ffda47ca03b0bca0d55d2236e6fe99cacd5c6bf88f9eed4d54309，RECOVERY.json包含源包恢复。无运行任务或新增定时；Projects未同步。结果远端发布以FINAL_PUBLICATION.json为准，勿重交。

恢复：先读Issue173/PR174。实验已完成，不重交2881。正式结果SUMMARY.json/RAW_INDEX.json含配置、模型、数据、校准及执行源码SHA，原始结果压缩包不必解压复制。重核验运行python work/jieruiz/173/summarize.py。发布阶段用同PR174，不合并。后续训练契约Issue159/PR170尚未自动采用本新路径；原57参数扫描不能直接沿用z重编码参数。当前输出恢复系数/宽累加为功能候选，没有硬件面积优越性证明。
