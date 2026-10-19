# Issue30 精确双随机短流核查交接

- 日期2026-10-18；负责人GitHub@jieruiz；正式仓库rayggxia-workspace/pbit-llm-qwen-baselines。
- 用户要求先整理长期备忘录；Issue28/PR29已完成文件交付后才开始本任务。恢复先读a_P_BIT根PROJECT_MEMORY_ZH.md与本任务Issue。
- 分支task/30-qwen-dual-iid-exact；base pbit-tlm-attention-details-20261016 @3553996bf014a29dee7fdb2250a3965e8fd881a4；独立目录C:/Users/86134/Documents/a_P_BIT/tmp/qwen-dual-iid-issue30-20261018。
- 实现experiments/qwen_dual_iid_exact_20261018/。保持旧8个源码及2份校准归档字节，精确Binomial、Gaussian和固定W对照独立进程，所有24FFN，准确Attention、固定Sz、A8共享64、W/127；不训练，不引入OR/SRR，不选种子。
- 本地AST、45唯一配置、冻结源码/校准SHA验证，不代替服务器CUDA测试。完整原BF16复现通过后才跑短128token三种子对照，共47输出，其中只有BF16 full是完整WT2。
- 已实时SSH核验Hongjie_Zeng、个人projects目录和gpu5090分区；本人squeue为空；9个模型/语料文件SHA重新计算匹配正式基线。expected_identity.json保存安全身份，不含凭据。
- 远程个人项目：/home/Hongjie_Zeng/projects/pbit-qwen-dual-iid-exact-20261018-issue30。代码部署到snapshots/<execution_commit>/experiments/qwen_dual_iid_exact_20261018；原模型/data仅链接pbit_llm。输出outputs/<execution_commit>，不得改已提交快照。
- 已实际提交Slurm2111，单GPU5090，源码快照ad14096615054a7ef0a72e43f670863e4a205b11，不可改；SUBMISSION.json记录命令/路径。完整BF16已复现11.652735047455899，299077目标，门禁通过；10个冻结文件与9个模型/语料及token hash验证通过。短测正在运行，不把部分结果写成47项齐全。
- 结果复核：先看Slurm日志及identity/BF16门禁，再核summary完整数47与逐文件SHA。短片段不能与已有全量Gaussian PPL混比；采样后端运行耗时不是ASIC周期。
- 精确全量旧实现粗估每配置20～30GPU小时，不盲目追加几十个全量。先用本次短测决定是否值得优化精确内核和选代表配置。
- 不接管Issue19/Llama2或Issue22/短流RTL；不取消原作业，不把旧结果覆盖为本次结果。Projects此前权限待同步。
- 收集工具：本地tmp/project-memory-20261018/collect_issue30.py；只收完整原子JSON，逐SHA验证。结果位于qwen/results/dual_iid_exact_20261018/，COLLECTION_MANIFEST保存当前收回范围；当前源snapshot不可变。
- 下一步：发布任务PR并继续核查2111，收回47项后更新最终汇总、同PR及长期备忘录；数据权重不入Git。

## 安全公开交付修订

原执行分支尚未推送；两次网络失败后，自动审批拒绝含大份校准原始数据的公开推送。未绕过审批：另建task/30-qwen-dual-iid-public，自3553996开始，仅复制可公开代码、结果摘要及校验索引，排除两份原件和原分支提交历史。原始校准留现有服务器，正在运行的Slurm2111快照不变。公开目录C:/Users/86134/Documents/a_P_BIT/tmp/qwen-dual-iid-public-issue30-20261018；原执行源码SHA仍ad14096615054a7ef0a72e43f670863e4a205b11。复现需要授权原件，不能称公共Git单独包含全部输入数据。

## 47项最终完成

2111已完成所有47输出：完整BF16参考、BF16前缀和45随机前缀；收回逐SHA全部通过。公开结果表为qwen/results/dual_iid_exact_20261018/ANALYSIS_ZH.md及summary.json，逐配置原件见ARTIFACT_INDEX.json服务器路径。完整精确随机WT2未做，本次只补短片段精确分布对照。后续不需重复本次47项。
