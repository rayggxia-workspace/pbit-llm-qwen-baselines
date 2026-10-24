## Issue175：Swish状态机函数级重建（2026-10-24）

用户要求复现64拍Swish并核验固定权重位平面接口。已独立重建SMURF，冻结ba7ff03d（完整SHA见MANIFEST）；51配置、3seed、P8整数比较及逐拍状态，8项功能/统计测试，有限时长Markov二阶矩与结果SHA交叉核验。正半轴0..1的4状态IID T32/64/128 MAE=.062395/.044052/.031188；32层打乱输入T64=.033992，属于我们变体，排列成本未计，不是论文精确复现。按序分层均值曲线偏差.032165，顺序不可忽略。原论文0.033是MAE，不是相对误差；图9只有0..1。16状态64拍更差.057807，不能用更多状态保证短流效果。

带符号固定S扩展未用真实模型分布；S64负分支P8系数全零，低平均误差不代表保留SiLU。固定W8可保留，但原始位平面不等于单Bernoulli流，进入普通FSM前需带权/符号/尺度合并并形成g幅度码或另研整数流FSM；权重双随机也不免除矩阵求和。建议先保留中间g/u定点统计、FSM输出接独立u流AND再Wd；不存在本次整FFN/PPL/PPA证据。前级64拍后再FSM64拍至少128拍加归约等，不能说全FFN64拍。

负责人jieruiz，Issue175，task/175-smurf-swish，独立稀疏目录tmp/smurf-swish-20261024；base PR174@bec546d4，报告qwen3/results/smurf_swish_20261024/REPORT_ZH.md。发布以work/jieruiz/175/PUBLICATION.json为准，未合并；Projects尚未确认。无新GPU/定时，不修改Issue173 Slurm2891冻结执行；其完成结果需单独按封存SHA汇总，不能从队列消失直接宣称交付。

恢复步骤：先核对Issue175、关联PR、PR174的实时head及本人身份。不要在Issue173目录切分支。所有结果是本地函数探针，运行源码ba7ff03d，无远端作业。本次不改已有GPU任务，不启动PPL/训练。按MANIFEST核验RESULTS，运行test_core.py及report.py；如需重放run，检出执行提交或确保四个文件原字节相同。所有正式文件在qwen3/smurf_swish与qwen3/results/smurf_swish_20261024。没有受限工艺/凭据上传。PDF原件仅本机归档，SHA在config。函数数据不依赖模型/语料，相关字段N/A。下一步是否进入真实模型需明确实际g/u尺度、序列顺序、共享及边界编码；本次尚未进行。
