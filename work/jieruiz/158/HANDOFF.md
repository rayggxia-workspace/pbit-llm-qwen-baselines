# Issue158 Qwen3-4B 非Base迁移

## 已提交：2026-10-23 22:45 CST

固定执行源e174d91cfcdb318da6481884bbf17ff37c1e3797，包tmp/qwen3-issue158-source-v1.tar.gz，SHA7d840ad5f5b09bad8419c73d88b1e23499e02f7f62f90f81ece789c820120f65；44源文件及子baseline manifest核验通过，服务器快照ROOT/snapshots/e174d91cfcdb318da6481884bbf17ff37c1e3797只读不可改。本地/提取源5合同测试通过；CPU2869的2计分测试和原生tiny保存重载已通过，正下载10个新模型文件。GPU2870 PENDING Dependency，afterok2869且kill-on-invalid-dep。仅1GPU/4CPU/48G/6h；CPU16G/6h。后续CPU随机适配门槛须下载后才执行，目前不宣称已通过。

PR160 https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/160 draft/open，未合并；base task/144-qwen3-stochastic。分工已实际发表于Issue157评论6367526124。源码已推送，远端原字节核验以REMOTE_VERIFY.json为准。无新模型PPL，完整概率WT2未提交；不复用Base的基线/校准/token期望值。旧Issue144的定时检查已删除，本任务未新建自动检查。

恢复：先核对2869/2870及ROOT/logs/prepare-2869.log、pilot-2870.log；不要重复提交健康/完成作业或重复下载校验权重。CPU成功生成ROOT/prepared/Qwen3-4B.json（模型全文件SHA、新token SHA）和ROOT/preflight.json；GPU保存ROOT/results/Qwen3-4B.json原生完整基线，ROOT/anchor/results/Qwen3-4B.json精确复跑，ROOT/results/Qwen3-4B/下gates/real_model_equivalence/calibration/13病例/complete。收取仅小原件及sidecar/manifest，不能覆盖旧Base检查点；新模型数据绑定必须独立验证，不能直接用Issue144硬编码Base验证器。完整结果后更新同PR160/状态/记忆，不合并不关闭Issue。服务器提交回执ROOT/SUBMITTED.txt，本地SUBMISSION.json。

目录最小稀疏，只检出复用qwen3代码及任务状态；没有复制权重/历史大结果。唯一待审工作树保留；辅助上传包在本机tmp和个人服务器incoming，不改其他任务目录。

2026-10-23；负责人jieruiz。用户指定Qwen/Qwen3-4B，不使用Base。task/158-qwen3-4b-posttrained，独立tmp/qwen3-4b-posttrained-issue158-20261023；依赖PR147/base task/144-qwen3-stochastic@357db5884726a66d988d75f92447ff8ecf8698e6，旧Base证据不覆盖。Issue157的SparQ由amlink1219负责，本任务只提供新模型/基线接口并做原方案13项后缀。

固定HF revision1cfa9a7208912126459214e8b04321603b3df60c、hf-mirror。先CPU下载/文件SHA/tiny门槛，再1GPU原生完整WT2及精确复跑、真实SDPA wrapper bitwise、新TRAIN校准、13后缀配置。只换权重不换动态B4/T32/K32/max4/采样参数；原文PPL不加聊天模板、不生成thinking。详见qwen3/posttrained/README_ZH.md。

新ROOT /home/Hongjie_Zeng/projects/pbit-qwen3-stochastic-nonbase-20261023-issue158；原Issue136 venv只读复用，现有Base模型不能当作新权重。尚未提交作业/无新PPL；源SHA和ID冻结后追加。CPU/GPU失败原件保留，不修改快照、不重交健康或完成任务。完整概率WT2、任务准确率、新硬件验证不在本轮范围。PR待建立，不合并/不关闭Issue。Projects待权限；分工评论网络异常待确认后补。
