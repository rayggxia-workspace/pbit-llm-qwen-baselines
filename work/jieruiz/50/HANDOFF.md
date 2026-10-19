# Issue50：后缀联合验证已发布准备，完整WT2运行中

更新时间：2026-10-19；负责人：GitHub jieruiz。Issue50 / PR52草稿，未合并。

- 目标：rayggxia-workspace/pbit-llm-qwen-baselines；分支task/50-joint-ffn-attention；原始base task/46-fixedw-multiscale@5518a0a；PR47已合并bef83e54，PR52已改为pbit-tlm-attention-details-20261016。独立目录C:/Users/86134/Documents/a_P_BIT/tmp/qwen-joint-issue50-20261019。
- 已推送阶段结果：34主项＋12准确Softmax诊断，三seed、4096后缀目标。已生成正式报告、三seed/逐段NLL/交互汇总、64服务器原件SHA及输入版本索引；阶段结果已推送ae4bd9a1ddd160c06175863eef3862d5cf7409f0；PR52草稿未合并，完整联合评测仍运行。
- 原BF16匹配后缀10.371557；B2T32/B4T32/B4T16的Ising128联合PPL为11.232234/11.197813/11.402422，Ising512为11.066401/11.055307/11.201607；主要损失来自Attention，未见明显联合放大。这不是完整WT2结论。
- 主执行d61b2861edc91e00495268d39a738edb3599f87f；Slurm2381、2382、2412完成；模型/文本哈希及原BF16完整门禁11.652735复现；38上游＋10联合＋13FFN测试通过，2完整计划测试通过；SDPA包装器计分logits双路径逐字节一致。
- 全部24层计分decode Attention和FFN真实执行；FFN同时作用prefill；prefill Attention准确SDPA。筛选为max4/Bernoulli/固定8块修补，并非Ising退火；有限硬onehot CTMC Ising直接V索引平均，没有二次PV抽样。无新训练、PT、TLM或芯片PPA。
- 完整执行53dd0ff6a04218dc9f2b692464d5b16da284cf17；Slurm2429显存门禁通过，峰值16.23/16.31GiB；Slurm2430运行22项完整299077目标cached对照（batch32、S128、三seed），尚无收齐的完整质量结论。运行快照不修改，已存在结果不覆盖，不重复提交。
- Slurm2425保留失败诊断：原过大32×2047-prefix pilot OOM，实际完整计划没有这个形状；新pilot覆盖32×1023正常前缀。早期aeccb归档CRLF检查在提交作业前拒绝，未运行；该归档也保留，已加LF规则。
- 正式成果：qwen/results/joint_stratified_attention_20261019/{RESULTS_ZH.md,SUFFIX_SUMMARY.json,FALLBACK_SUMMARY.json,INPUT_IDENTITY.json,ARTIFACT_INDEX.json,FULL_PREPARATION.json}；执行代码experiments/qwen_joint_stratified_attention_20261019/。
- 服务器：/home/Hongjie_Zeng/projects/pbit-qwen-joint-ffn-attention-20261019-issue50；outputs/d61b2861...保存后缀，outputs/53dd0ff6...保存完整。moment.pt为公开历史train校准，只记录SHA，不重上传。
- 协作：Issue48/amlink1219的独立Attention扫描不覆盖、不访问其个人目录；已在两Issue记录分工。Projects缺read:project，看板待同步。PR47已合并；PR52未合并，Issue50保持open。
- 下一步：核对当前远端状态后，按HANDOFF收集Slurm2430；22项齐全时用summarize_results.py --phase full生成FULL_SUMMARY，核验每目标一次/24层audit/原件与Git blob SHA，追加完整结论后再结束任务。当前不能把启动任务或后缀完成写成完整已完成。

## 可直接继续的命令

首先按AGENTS核对memo§0/1/12/5.7、最新Issue50/PR52、PR47和Issue48；确认当前squeue/sacct，不重复提交。SSH只使用本机已有配置，凭据不进Git。仓库根执行：

```powershell
python experiments/qwen_joint_stratified_attention_20261019/collect_results.py --ssh-config C:/Users/86134/.ssh/lab-server-ai.ssh_config --host lab-server-ai --remote-root /home/Hongjie_Zeng/projects/pbit-qwen-joint-ffn-attention-20261019-issue50/outputs/53dd0ff6a04218dc9f2b692464d5b16da284cf17 --output C:/Users/86134/Documents/a_P_BIT/tmp/joint50_full_collected.json
python experiments/qwen_joint_stratified_attention_20261019/summarize_results.py C:/Users/86134/Documents/a_P_BIT/tmp/joint50_full_collected.json qwen/results/joint_stratified_attention_20261019/FULL_SUMMARY.json --phase full
```

第二条只在全部22项完成后运行；不齐会拒绝缺seed/缺对照。使用可用的Python3（本机现代路径为C:/Users/86134/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe）。远程推理仅通过Slurm，不在login节点运行。所有完整任务已提交，重交前必须核实失败项和制品，不重复计算。

FULL_SUBMISSION.json给出2430完整命令；FULL_PREPARE_SUBMISSION.json为2429，FAILED_MEMORY_PREPARE_2425.json保留失败前置；PREPARE/SUFFIX/FALLBACK_SUBMISSION.json为2381/2382/2412。SLURM_ACCOUNTING.txt为收集时快照，不代替恢复时实时查询。完整结果与旧向量化BF16、batch8后缀严格分开；完整原始BF16参考应取本批full/none_sdpa_S128_s0.json。

完整状态更新后，重新生成制品SHA索引、核对代码源53dd0ff与服务器identity.joint_sources中的45个Git blob；每种FFN与Attention种子分域独立。不要用last_sampler_stats当全程事件计数；不要把同seed当完全相同CTMC轨迹。正式结果不要放个人work目录；未提交的原始收集JSON仍在本机tmp及服务器，不公开权重/数据/校准/工艺库。

完整阶段最新快照：新cached BF16已完成299077目标，PPL11.652118067865489（约149.46秒）；其余完整联合对照尚在运行，见FULL_PROGRESS.json，不用原向量化11.652735直接代替本批匹配参考。Slurm历史sacct接口返回“accounting storage is disabled”，因此完成依据为status=completed计分原件、READY及实时squeue，未把空sacct响应当成功。

发布回执：PUBLISHED_RESULTS_RECEIPT.json；正式阶段结果提交ae4bd9a1ddd160c06175863eef3862d5cf7409f0，Issue50已更新，完整Slurm2430未收齐，不能关闭任务。
