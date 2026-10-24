## Issue175：固定g数制FSM进入模型试测（2026-10-24）

用户明确要求实际测试FSM以减少g分档。新模块qwen3/smurf_swish/model_*，固定G=8/16、幅度P8＋符号，无在线max或g逐值选档。真实G写进SiLU目标；有限T状态占用拟合，theta0=0、复位0，无预热；逐拍R8输入更新→状态系数比较→独立u比较AND→固定W8 Wd，仅最终整数统计恢复。负输出单位Sf=.5或G另测，不保证可拟合。u沿用TRAIN固定四档，前级x固定四档共享64 T=K64；准确Attention。四组(G,N,Sf)=(8,4,.5)/(8,8,.5)/(16,8,.5)/(8,8,8)，各含BF16及LUT均值/FSM64和128均值/实际64和128，概率三seed，64份后缀计划。IID FSM基线，未混称分层；模型前级恢复仍FP32参考，非整链bittrue/PPA。

Slurm2894四片均在CUDA编译预检失败，模型未启动；uint32随机键类型已修复，新冻结462d4fe168fbb7168a5cd742ec1270f02f6ce466、Slurm2898_[0-3]已提交。源包SHAf50ebe7c4b00a7c599bd86fedb677f9c3eddcf5c7bdc28b369a67759ef12180c，原失败快照保留。当前无封存新模型结果；本机7项通过、3项CUDA待服务器。个人目录pbit-qwen3-smurf-model-20261024-issue175，MODEL_SUBMISSION.json含准确快照/作业/日志，健康任务不重交。无新定时。

负责人jieruiz，task/175-smurf-swish，tmp/smurf-swish-20261024，沿用Issue175/PR176待审未合并；新发布以MODEL_PUBLICATION.json为准，Projects缺read:project待同步。完成时核对complete/documents/sidecar SHA、36层全前缀、同轮BF16和1024目标位置一致，再汇总；不是完整WT2，不用函数MAE冒充PPL。

## Issue175发布回执（2026-10-24）

Swish FSM独立重建已通过PR176上传、待审未合并；结果提交8d7ce13b，核验提交2f56108b。全部变更文件Git blob/长度核验，小于64KB另原字节回读；51函数配置、8测试，无新模型PPL/训练/RTL/PPA。PUBLICATION.json含准确SHA/Issue评论和校验索引。Projects查询实际因缺read:project权限失败；Issue、STATUS和交接已同步，看板待维护者。Issue173短流封存结果另行汇总，未改其冻结执行。

## Issue175：Swish状态机函数级重建（2026-10-24）

用户要求复现64拍Swish并核验固定权重位平面接口。已独立重建SMURF，冻结ba7ff03d（完整SHA见MANIFEST）；51配置、3seed、P8整数比较及逐拍状态，8项功能/统计测试，有限时长Markov二阶矩与结果SHA交叉核验。正半轴0..1的4状态IID T32/64/128 MAE=.062395/.044052/.031188；32层打乱输入T64=.033992，属于我们变体，排列成本未计，不是论文精确复现。按序分层均值曲线偏差.032165，顺序不可忽略。原论文0.033是MAE，不是相对误差；图9只有0..1。16状态64拍更差.057807，不能用更多状态保证短流效果。

带符号固定S扩展未用真实模型分布；S64负分支P8系数全零，低平均误差不代表保留SiLU。固定W8可保留，但原始位平面不等于单Bernoulli流，进入普通FSM前需带权/符号/尺度合并并形成g幅度码或另研整数流FSM；权重双随机也不免除矩阵求和。建议先保留中间g/u定点统计、FSM输出接独立u流AND再Wd；不存在本次整FFN/PPL/PPA证据。前级64拍后再FSM64拍至少128拍加归约等，不能说全FFN64拍。

负责人jieruiz，Issue175，task/175-smurf-swish，独立稀疏目录tmp/smurf-swish-20261024；base PR174@bec546d4，报告qwen3/results/smurf_swish_20261024/REPORT_ZH.md。发布以work/jieruiz/175/PUBLICATION.json为准，未合并；Projects尚未确认。无新GPU/定时，不修改Issue173 Slurm2891冻结执行；其完成结果需单独按封存SHA汇总，不能从队列消失直接宣称交付。

恢复步骤：先核对Issue175、关联PR、PR174的实时head及本人身份。不要在Issue173目录切分支。所有结果是本地函数探针，运行源码ba7ff03d，无远端作业。本次不改已有GPU任务，不启动PPL/训练。按MANIFEST核验RESULTS，运行test_core.py及report.py；如需重放run，检出执行提交或确保四个文件原字节相同。所有正式文件在qwen3/smurf_swish与qwen3/results/smurf_swish_20261024。没有受限工艺/凭据上传。PDF原件仅本机归档，SHA在config。函数数据不依赖模型/语料，相关字段N/A。下一步是否进入真实模型需明确实际g/u尺度、序列顺序、共享及边界编码；本次尚未进行。
