# Issue50：短流FFN与真实Attention联合PPL

更新时间：2026-10-19；负责人：GitHub jieruiz。

- Issue：https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/50
- 分支：task/50-joint-ffn-attention；PR52草稿、已推送未合并；PR base task/46-fixedw-multiscale@5518a0a（依赖PR47）。
- 独立目录：C:/Users/86134/Documents/a_P_BIT/tmp/qwen-joint-issue50-20261019。
- 冻结执行：d61b2861edc91e00495268d39a738edb3599f87f；Attention源11f1d6eea2776e201f2021081f8b0fbae2cc455e，保持上游字节和来源。
- 路径：24层FFN在prefill/decode均替换；24层Attention计分decode为max4概率筛选+候选QK+有限CTMC Ising+索引V平均；prefill Attention准确SDPA；Ising索引直接实现PV采样，无第二次抽样。
- 已验证：Slurm2381完成；模型/分词器/语料SHA门禁；原BF16完整WT2 299077目标PPL11.652735047455899复现；38项上游、10项联合、13项FFN测试通过；原FFN及B4T32的SDPA wrapper计分logits SHA相同；8项16目标GPU pilot及独立24层hook审计通过。
- 运行中：Slurm2382，34项4096目标后缀评测（三seed、S128/512、batch8），最多4GPU并发；原模型匹配后缀PPL10.37155678462956。尚未收齐，不将片段结果叫完整WT2。
- 服务器本人目录：/home/Hongjie_Zeng/projects/pbit-qwen-joint-ffn-attention-20261019-issue50；快照snapshots/d61b2861edc91e00495268d39a738edb3599f87f/；结果outputs/同SHA/，保留原件。
- 代码/说明：experiments/qwen_joint_stratified_attention_20261019/；正式结果计划qwen/results/joint_stratified_attention_20261019/。提交回执见本目录JSON，不上传原权重/数据/moment.pt。
- 协作：已在Issue50及48记录接口；Issue48/amlink1219的Slurm2380不接管、不取消、不访问其个人目录。Projects缺read:project待有权限者同步。
- 下一步：收齐34项后核对原件SHA/目标位置/24层执行，分析同协议三seed PPL与NLL交互；必要时运行预注册screen_iid诊断；通过显存pilot后再提交独立冻结完整cached确认，原快照不可修改。
