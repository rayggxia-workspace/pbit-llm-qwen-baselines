## 最新：门禁通过，四卡正式运行

独立CPU Slurm62231九项PASS；Gate62228 completed，原完整BF16 PPL11.5364289819／299077目标，整数核oracle、两预算原四档包装器逐位一致／采样重复逐位一致、官方HFLM两个任务短题逐位一致及16个候选短任务全部通过。62229_0～62229_3已实际RUNNING，四张A6000；62230等待汇总。当前只是正式任务启动，不是全量准确率完成。源仍ea293cae，未修改冻结数值代码。验证摘要experiments/t64_scale_task_accuracy_20261126/VALIDATION_AND_SUBMISSION.json；原Gate SHA38e6384f00b6ba79b5be2e95c90d6a96f2393ee592f9cf5e8184ca44edb8d7cb。主机Torch2.6.0／Triton3.2.0／Transformers4.51.3，lm-eval0.4.8。短任务吞吐初估完整评测3～5小时，待首批完整分片修正，不以2题pilot判断任务准确率。

# 共享尺度任务准确率：已提交，尚未完成

2026-11-26，Issue225／PR266，负责人rayggxia。同task/225-cim-bank32-20261124；数值源ea293caea14b8ec5b271a937919ae21693ccae9c的5文件已推送并逐字回读一致。

PIQA1838题、ARC-Challenge1172题；三候选dynamic32／gu_onebit64／all64_onebit，各16/32和64/128、seed101。另加同预算原四档lane及原BF16参考，共9配置×2任务、18组、225个128题以内的分片。T64 trained100M W8／原non_ffn，Attention全程准确SDPA；题干和答案位置均用所选FFN。官方lm-eval0.4.8零样本、原文无聊天模板、无截断，输出acc及acc_norm。

Slurm Gate62228已实际运行，九项编码／整数单测PASS；完整BF16参考、官方HFLM计分一致及所有候选短任务尚待门禁封存。正式62229_[0-3]在afterok62228后启动，4张A6000分配GPU内执行、持久worker复用模型；CPU汇总62230依赖afterany62229。当前不能宣称完整准确率已得到。

方法／配置：experiments/t64_scale_task_accuracy_20261126/README_ZH.md及PLAN.json。runner复用冻结数值源与原官方计分helper；不改变原lab完整WT26355_5、不重交旧学院任务、不训练或更改RTL／TLM。私有输入manifest／共享路径／完整命令保存在本地任务交接，不发布模型、数据和连接信息。

恢复时先查Gate sealed RESULT及最新Slurm／HANDOFF。只有225个sealed completed分片及18组完整doc_id集合、数据／模型／代码／配置SHA、36层输入覆盖和配对请求ledger均通过才称完成。失败或中间PROGRESS单列；不要按分片百分比简单平均。最终与同预算T64 lane对照，BF16原预训练仅作参考；一个部署seed不宣称训练seed置信区间。发布小型SUMMARY／manifest／SHA，逐题大结果留既有共享存储。PR保持open未合并，Projects待维护者同步。
