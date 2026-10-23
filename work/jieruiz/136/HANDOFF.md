# Issue136 Qwen3 BF16 基线交接

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
