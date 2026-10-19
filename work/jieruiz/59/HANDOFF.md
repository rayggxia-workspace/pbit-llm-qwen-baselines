# Issue59：代表任务准确率评测

2026-10-19；负责人GitHub jieruiz；目标rayggxia-workspace/pbit-llm-qwen-baselines。

- Issue59，分支task/59-qwen-task-accuracy；独立目录C:/Users/86134/Documents/a_P_BIT/tmp/qwen-task-accuracy-issue59-20261019。基线e3c5e957c3769b5fc6867b42a52facace647a83b，依赖PR52未合并；PR base暂为task/50-joint-ffn-attention，发布前核实。
- 用户要求PPL外增加代表任务准确率。选择PIQA1838、ARC-E2376全量，HellaSwag预定1000/10042子集。官方lm_eval0.4.8零样本模板/计分与分词边界；acc_norm按字符长度。新原BF16、B4T32 FFN-only三seed、联合Ising64/128/512各三seed。
- 实现无padding缓存候选评分，第一答案token从最后prompt token的单tokenforward预测，全部24层FFN/Attention执行审计；分支恢复KV、摘要和RNG。数值内核不改，未训练。
- 数据/环境只读盘点与2项计划测试已通过，实际GPU准确率尚未测，不能引用历史原版分数作为新结果。三任务全部短于512 token，固定8块筛选会保留全部K，不能证明长上下文筛选效果。
- 依用户授权，仅取消本人尚未开始的2430_19/20/21(B4T16冗余全量PPL)；保留当前最佳B4T32完整2430/2461及已完成原件，回执work/jieruiz/59/PPL_PRIORITY_CHANGE_20261019.json。
- 服务器个人项目/home/Hongjie_Zeng/projects/pbit-qwen-task-accuracy-20261019-issue59。准备不可变snapshot、Slurm CPU预检和GPU pilot，成功后正式评测；当前未提交新GPU任务。
- 下一步：完成scorer与CPU测试，Slurm预检、重跑未改BF16完整WT2及12题cached/vector桥接，pilot估时再提交39项任务。保留逐题原件/哈希、实际任务ID与pending状态。
- 看板此前缺read:project；Issue/PR可写，看板待同步。不把本地完成称为远端完成。
