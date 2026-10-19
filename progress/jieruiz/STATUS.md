# Issue50：后缀联合验证已发布准备，完整WT2运行中

更新时间：2026-10-19；负责人：GitHub jieruiz。Issue50 / PR52草稿，未合并。

- 目标：rayggxia-workspace/pbit-llm-qwen-baselines；分支task/50-joint-ffn-attention；原始base task/46-fixedw-multiscale@5518a0a；PR47已合并bef83e54，PR52已改为pbit-tlm-attention-details-20261016。独立目录C:/Users/86134/Documents/a_P_BIT/tmp/qwen-joint-issue50-20261019。
- 本地完成：34主项＋12准确Softmax诊断，三seed、4096后缀目标。已生成正式报告、三seed/逐段NLL/交互汇总、64服务器原件SHA及输入版本索引；结果等待本次任务提交和推送，不能提前写成远端结果已完成。
- 原BF16匹配后缀10.371557；B2T32/B4T32/B4T16的Ising128联合PPL为11.232234/11.197813/11.402422，Ising512为11.066401/11.055307/11.201607；主要损失来自Attention，未见明显联合放大。这不是完整WT2结论。
- 主执行d61b2861edc91e00495268d39a738edb3599f87f；Slurm2381、2382、2412完成；模型/文本哈希及原BF16完整门禁11.652735复现；38上游＋10联合＋13FFN测试通过，2完整计划测试通过；SDPA包装器计分logits双路径逐字节一致。
- 全部24层计分decode Attention和FFN真实执行；FFN同时作用prefill；prefill Attention准确SDPA。筛选为max4/Bernoulli/固定8块修补，并非Ising退火；有限硬onehot CTMC Ising直接V索引平均，没有二次PV抽样。无新训练、PT、TLM或芯片PPA。
- 完整执行53dd0ff6a04218dc9f2b692464d5b16da284cf17；Slurm2429显存门禁通过，峰值16.23/16.31GiB；Slurm2430运行22项完整299077目标cached对照（batch32、S128、三seed），尚无收齐的完整质量结论。运行快照不修改，已存在结果不覆盖，不重复提交。
- Slurm2425保留失败诊断：原过大32×2047-prefix pilot OOM，实际完整计划没有这个形状；新pilot覆盖32×1023正常前缀。早期aeccb归档CRLF检查在提交作业前拒绝，未运行；该归档也保留，已加LF规则。
- 正式成果：qwen/results/joint_stratified_attention_20261019/{RESULTS_ZH.md,SUFFIX_SUMMARY.json,FALLBACK_SUMMARY.json,INPUT_IDENTITY.json,ARTIFACT_INDEX.json,FULL_PREPARATION.json}；执行代码experiments/qwen_joint_stratified_attention_20261019/。
- 服务器：/home/Hongjie_Zeng/projects/pbit-qwen-joint-ffn-attention-20261019-issue50；outputs/d61b2861...保存后缀，outputs/53dd0ff6...保存完整。moment.pt为公开历史train校准，只记录SHA，不重上传。
- 协作：Issue48/amlink1219的独立Attention扫描不覆盖、不访问其个人目录；已在两Issue记录分工。Projects缺read:project，看板待同步。PR47已合并；PR52未合并，Issue50保持open。
- 下一步：核对当前远端状态后，按HANDOFF收集Slurm2430；22项齐全时用summarize_results.py --phase full生成FULL_SUMMARY，核验每目标一次/24层audit/原件与Git blob SHA，追加完整结论后再结束任务。当前不能把启动任务或后缀完成写成完整已完成。
