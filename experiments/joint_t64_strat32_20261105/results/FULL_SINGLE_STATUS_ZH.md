# 完整WT2单seed：已提交运行

用户要求先申请一个任务观察实际耗时和效果。复用Issue242/PR243，不展开其余seed或对照。

|项目|本次设置|
|---|---|
|Slurm|4652，已核RUNNING|
|提交时间|2026-11-05 22:00:03 北京时间|
|模型/权重|实际T64训练100M导出＋匹配non_ffn，冻结校准|
|FFN|GU分层32、三路AND4×2×4共32、直接Wd|
|Attention|SparQ r32/k128/recent32，赢家保持S64/burn0/slot0，独立IID R8|
|数制|signed12/F4分数→max差→饱和U8/F4地址→floor-P8阈值|
|计分|完整WT2，window2048/stride1024，292窗、299077目标|
|部署seed|仅101|
|资源|1×RTX5090，4CPU，48GiB主存，12小时作业时限|
|预计耗时|启动后4–8小时，尚非实测完成时间|

逐token计分、batch8，共39组/40005次单token模型调用。前缀Attention准确；FFN前缀和计分均替换，所有计分token36层走概率Attention。不能按292次整窗调用估计，不能把早期部分PPL当完整结果。

复用原已验证21文件数值快照，未改随机/量化/权重/计分方程。新增驱动只做小候选冷启动检查及只读forward观察，每128次调用写进度，不改变张量或随机序列。实际driver SHA afd284c33749e7dbff8377ba41cdf38413c128326f24a55087e636252c8a2346；执行manifest SHA 1ac92b3d9a3df8ec1dbc50272624b3414bf0e12a5d3c247e19706e2e66168709。N1/S64两行128个索引均为0的GPU检查已通过；本地/服务器计划均确认目标不重不漏。

完整PPL尚未产出。已有后缀七项结果保持原样。恢复用本人工作区work/rayggxia/242/full_ops.py status，先读FULL_SINGLE_SUBMISSION和最新FULL_SINGLE_STATUS，不重复submit；全部完成后核验results/COMPLETE.json的documents SHA、299077目标及36层覆盖，再收取结果。状态以最新原生队列和封存结果为准；GPU运行时间不是ASIC时间。
