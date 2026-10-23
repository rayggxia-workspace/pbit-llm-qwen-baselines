# Issue136 Qwen3 BF16 基线交接

## 最终实验状态：2026-10-23 双模型完成并通过独立归档核验

正式成果qwen3/results/bf16_20261023/REPORT_ZH.md。1.7B PPL8.36733951656172，4B PPL7.038611601266219；两者299077目标/299078token/292窗口，token SHA一致，GPU评测16.9192/32.9219秒。CPU2799完成4B 10文件校验，GPU2800_0和2801_1均有COMPLETE和完整结果；旧2797失败/2798依赖取消日志保留。当前任务没有待跑基线，其他任务2804/2805不属本任务且不触碰。

11个服务器原字节小文件已收取并按SERVER_SHA256SUMS.txt验证；源码/config/model/data绑定、逐窗口覆盖、NLL/PPL重放与10个损坏负例均通过，VALIDATION.json已生成。执行源码仍968046f，未再跑推理、未修改冻结快照。结果SHA分别c32023b48fdfd30aab715e00ac90a26d905ea2f965e5b63475bcb9b977a15a53与39fb5f1dae739f5925836a6b4525733ab31e57a7ba5d72e6380ec88a61606e64。Slurm accounting关闭且旧job已被scontrol清理，不虚报sacct记录。

后续：同PR137发布结果并转待审，不合并/不关闭Issue；停止已完成目的的qwen3定时检查。权重仍在服务器ROOT/models，Git只含小型原件/索引。PR待审保留本稀疏目录；镜像/任务状态旧文字仅作历史，恢复不得重跑这两个基线。发布与停表实际回执见FINAL_PUBLICATION.json。

## 最新状态：2026-10-23 19:20 CST（覆盖下方旧运行记录）

2797于19:13:25 FAILED/1:0：1.7B已下载并校验7文件，4B镜像连接在准备阶段被远端关闭；2798未分配GPU，因DependencyNeverSatisfied自动CANCELLED。原日志/源码保留，没有更改冻结快照。

恢复作业：2799为4B-only CPU下载重试（4CPU/16G/3小时，原prepare.py --index 1，最多3次失败重试、间隔30秒，仍hf-mirror）；2800_0为已经校验的1.7B独立GPU评测，已完成；2801_1为4B GPU评测，依赖afterok2799且kill-on-invalid-dep=yes。不要重交这些任务。新日志为logs/prepare-retry-2799.log、logs/evaluate-2800_0.log、logs/evaluate-2801_1.log。

1.7B日志结果：完整WT2 PPL 8.36733952，299077目标/299078 token、292窗口，评测16.9秒；结果results/Qwen3-1.7B-Base.json的服务器SHA256 c32023b48fdfd30aab715e00ac90a26d905ea2f965e5b63475bcb9b977a15a53，与同目录.sha256.json匹配。尚待收取小型manifest/结果并独立重放计分覆盖后正式结果发布。4B暂无结果，仍下载准备，网络正常时估计20–40分钟，不保证完成时点。

用户要求定时：当前对话heartbeat automation id=qwen3，ACTIVE，每10分钟检查；仅有意义进展/完成/失败时通知，双方结果验证发布后停用；不新增独立任务、不重复健康作业。首次约19:29 CST。定时运行需本机/app保持可用，服务器Slurm独立运行。具体恢复JSON见RECOVERY_20261023.json；PR137继续draft/open，不合并。

- 负责人：jieruiz（API /user 已核实），官方仓库 rayggxia-workspace/pbit-llm-qwen-baselines，有 push/admin 权限。
- 用户要求：先用镜像在现有服务器建立 Qwen3-1.7B、4B 基线；采用此前讨论的 Base 版本。只做原始BF16，不进行FFN/Attention替换。
- 分支：task/136-qwen3-bf16；PR base pbit-tlm-attention-details-20261016 @6966739a5223680888bf0315f7bb4f73423a1ae6。
- 独立稀疏目录：C:/Users/86134/Documents/a_P_BIT/tmp/qwen3-baseline-issue136-20261023。
- 服务器ROOT：/home/Hongjie_Zeng/projects/pbit-qwen3-baseline-20261023-issue136。
- 执行源码：968046f9346258029192983000b4def643667cca，SRC为ROOT/snapshots/968046f；8源码文件原字节和execution.json打包冻结。
- 包：qwen3-issue136-source-v1.tar.gz，SHA256 a84df4a66a624eac27b9da551ecca5be022265a7fe6f69cda5c32d9aec151053，服务器已复核。根tmp亦保留源包；Git包含全部可恢复源码。
- CPU Slurm 2797 已提交（2026-10-23），安装隔离环境、CPU测试、镜像下载与哈希校验。GPU尚未提交，无新PPL结果。
- 本地验证：计分覆盖/无效参数2组通过（36覆盖情形），git diff --check通过。服务器检查：旧环境Transformers4.45.2不能原生支持Qwen3，故新venv；现有train/test SHA与config完全一致；镜像两个版本接口200。
- 版本：1.7B ea980cb0a6c2ae4b936e82123acc929f1cec04c1；4B 906bfd4b4dc7f14ee4320094d8b41684abff8539。
- 评测：完整WT2 window2048/stride1024，seed0，BF16 SDPA、无chat/BOS/cache。每个目标恰好计分一次；不直接与Llama的不同分词器PPL解释为质量增益。
- 下一步：检查2797的sacct和logs/prepare-2797.log；成功后按qwen3/README_ZH.md提交GPU数组，不重复下载/建新环境；源快照不可编辑，有修复须另提交新快照并留失败日志。
- 发布：尚未推送/创建PR；Issue https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/136 。Projects权限待核（历史缺read:project），不得声明已同步。模型权重留服务器个人项目；无工艺/凭据上传。

本文件为首轮冻结交接；后续实际作业与发布回执追加于下方。

## 后续实时进度

CPU2797已通过全部覆盖测试和原生tiny Qwen3保存重载，镜像1.7B权重下载中。GPU数组2798（0=1.7B，1=4B，每项一GPU）已提交，依赖afterok:2797且kill-on-invalid-dep=yes；CPU作业失败不会分配GPU。日志ROOT/logs/evaluate-2798_0.log及_1.log。不要再次提交重复数组。网络直连github.com的git push两次失败（连接重置/超时），改用GitHub API发布完全相同的Git blob/tree/commit，仍核验jieruiz且不force、不合并。API结果以PUSH/PUBLICATION回执为准。

代码已按原SHA发布至官方仓库，PR137 draft/open，未合并。Projects本轮GraphQL确认缺read:project，待有权限成员同步；Issue/PR/个人STATUS已记录真实作业，不将等待下载写成PPL完成。本任务长期记忆条目同步到正式维护阅读源及本机同字节镜像，未覆盖其其他未发布条目。

发布核验：a335ea9dccb0a5141ffa23b9722c34f579bcb7aa的全部17个改动文件从GitHub逐blob读回，与本地Git原字节完全相同（REMOTE_VERIFY.json）。旧环境复查仍Transformers4.45.2，新venv为4.51.3。镜像下载持续前进；后续运行结果仅在服务器，当前PR仍draft。PUSH.json是各次推送生成的本地回执，最终推送会产生一处更新，可用于恢复核对；不要将此回执更新误认作未提交执行代码。PR待审期间保留本稀疏目录；未创建额外全量helper/模型副本，源包仅约8KB留存用于恢复。
