# 共享尺度任务准确率：已提交，尚未完成

2026-11-26，Issue225／PR266，负责人rayggxia。同task/225-cim-bank32-20261124；数值源ea293caea14b8ec5b271a937919ae21693ccae9c的5文件已推送并逐字回读一致。

PIQA1838题、ARC-Challenge1172题；三候选dynamic32／gu_onebit64／all64_onebit，各16/32和64/128、seed101。另加同预算原四档lane及原BF16参考，共9配置×2任务、18组、225个128题以内的分片。T64 trained100M W8／原non_ffn，Attention全程准确SDPA；题干和答案位置均用所选FFN。官方lm-eval0.4.8零样本、原文无聊天模板、无截断，输出acc及acc_norm。

Slurm Gate62228已实际运行，九项编码／整数单测PASS；完整BF16参考、官方HFLM计分一致及所有候选短任务尚待门禁封存。正式62229_[0-3]在afterok62228后启动，4张A6000分配GPU内执行、持久worker复用模型；CPU汇总62230依赖afterany62229。当前不能宣称完整准确率已得到。

方法／配置：experiments/t64_scale_task_accuracy_20261126/README_ZH.md及PLAN.json。runner复用冻结数值源与原官方计分helper；不改变原lab完整WT26355_5、不重交旧学院任务、不训练或更改RTL／TLM。私有输入manifest／共享路径／完整命令保存在本地任务交接，不发布模型、数据和连接信息。

恢复时先查Gate sealed RESULT及最新Slurm／HANDOFF。只有225个sealed completed分片及18组完整doc_id集合、数据／模型／代码／配置SHA、36层输入覆盖和配对请求ledger均通过才称完成。失败或中间PROGRESS单列；不要按分片百分比简单平均。最终与同预算T64 lane对照，BF16原预训练仅作参考；一个部署seed不宣称训练seed置信区间。发布小型SUMMARY／manifest／SHA，逐题大结果留既有共享存储。PR保持open未合并，Projects待维护者同步。

