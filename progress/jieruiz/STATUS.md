# Issue50：Ising次数后缀PPL曲线完成，完整确认运行中

2026-10-19；负责人GitHub jieruiz；正式目标rayggxia-workspace/pbit-llm-qwen-baselines。

- Issue50 / PR52草稿未合并；分支task/50-joint-ffn-attention，base pbit-tlm-attention-details-20261016；目录C:/Users/86134/Documents/a_P_BIT/tmp/qwen-joint-issue50-20261019。原依赖PR47已合并bef83e54。
- 本次只测PPL，固定B4T32/K32、max4固定8块、burn16/spacing4；全24计分decode Attention，FFN在prefill/decode均替换，Attention多token prefill仍准确SDPA。保留有限hardonehot CTMC，不替成Softmax IID，V索引平均即PV采样。
- 主阶段34项＋12诊断此前已发布。新增Slurm2440门禁与2441的15项（三seed）已完成；49执行源Git blob和模型/文本哈希通过，未改BF16后缀10.37155678462956重新复现，2采样计划测试通过。16新计分原件＋5准备文件共21原件SHA已索引。
- 新报告已推送9e146e99a0865f31f07e3a1fb78358eaeedf4219：S32/64/128/256/512/1024的B4T32联合后缀PPL为12.065755/11.514886/11.197813/11.066594/11.055307/11.006579。准确PV参考10.970368；原BF16后缀10.371557。256/512均值差约0.011，三seed尚不支持明确质量差异或等价结论。所有这些是4096目标后缀，不是全量。
- S128/512及FFN-only复用旧d61/batch8。原FFN六档曲线复用成员Issue48/PR49公开summary（publication8dd1b06a/execution11f1d6ee），未访问其个人目录、未重复作业。权重/文本/token/目标一致，配置和分词器部分原始元数据字节不同，已记录，不能宣称所有文件相同。
- 新执行c0fd54446d843f0b21e94bf138c692048e518c86，原d61与53dd快照均不修改。Slurm2461已提交6项B4T32 S256/512各3seed完整cached确认；同299077目标、2048/1024、batch32。复用53dd实际显存门禁，worker检查数值内核未变。完整2461尚未收齐。
- 原完整Slurm2430的22项仍运行，含B4T32 S128、FFN-only/原BF16；不重复提交。其新cached BF16已11.652118067865489；完整联合结果未收齐不提前填值。sacct存储关闭，以completed原件/READY/实时squeue核验。
- 正式新成果qwen/results/ising_sample_sweep_20261019/{RESULTS_ZH.md,SUMMARY.json,PPL_CURVE.png/svg/csv,PREPARATION.json,ARTIFACT_INDEX.json,references/}。早期三FFN联合报告仍在qwen/results/joint_stratified_attention_20261019/，保留原协议。
- 服务器本人项目/home/Hongjie_Zeng/projects/pbit-qwen-joint-ffn-attention-20261019-issue50；新outputs/c0fd5444...、旧full outputs/53dd0ff6...；源码分别冻结在snapshots/对应SHA/。大权重/文本/运行校准不上传。
- 随机数说明：S为每query/head保留观测数，时间16+4k，不是ESS或物理更新拍。FFN32拍是独立参数；未训练/新增任务指标/PT/PPA/TLM。seed标准差不等于语料CI。
- 下一步：核对远端Issue/PR、本人队列及回执再收集2461与2430。待相同full协议对照齐全后追加全量结论；不要修改运行快照或重复提交。Projects缺read:project，看板待有权限者同步；Issue50保持open，不因后缀阶段结束而关闭。

发布回执SAMPLE_PUBLICATION_RECEIPT.json；PR52仍草稿未合并，Issue50已更新已完成/待完成项，完整2430/2461尚未收齐。
