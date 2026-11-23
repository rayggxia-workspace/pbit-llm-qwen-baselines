# 硬阈值剪枝的完整WT2与精选任务评估

Issue261 / PR262，2026-11-23，rayggxia。用户授权单seed完整验证，继续同一独立任务目录。

主候选是训练集固定幅度阈值20%，未剪枝T64为配对对照，范数PoT加权20%作为
PPL对照，另重新运行原父模型BF16参考。全部固定seed101、T_x64/T_AND64，
准确SDPA Attention不改。复用已封存校准，不看新测试结果重新选择阈值。

完整WT2：window2048/stride1024、292窗口、299077唯一目标；每组首窗NLL须与
此前同seed封存筛选逐位一致，再累计完整语料。不能用原8窗口PPL充当完整值。

精选PIQA validation1838、ARC-Challenge test1172、WinoGrande validation1267。
已有Qwen3质量表中，相对原BF16的旧联合低采样设置分别下降5.44/8.11/6.95个百分点，
覆盖物理常识、科学问答和指代消歧。它们用于选任务，不作为本轮配对基线；旧
联合方案的Attention/权重不同。本轮使用完整划分，官方lm-eval0.4.8的0-shot原文
似然协议，PIQA/ARC同时报acc与acc_norm，WinoGrande报acc。提示前缀与答案位置
都经过同一个P-FFN/剪枝模型，不能用精确前缀隐藏误差。数据SHA与官方模板/计分
源码SHA、逐题结果、输入批次和36层覆盖、运行配置与结果SHA均留存。

PPL先行提交独立冻结执行快照；下游任务评分器另做小样本门禁后提交。所有GPU
计算通过Slurm，个人项目临时目录显式配置，不修改原mild/旧address源码和输出。
源码包、任务/参数范围、Slurm回执与准确发布状态见本Issue的work目录及PUBLIC_STATUS。
