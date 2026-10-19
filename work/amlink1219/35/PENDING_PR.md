> 已发布：[PR #43](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/43)，待审、未合并。当前正文见PR_BODY_CURRENT.md；以下为原待发布草稿，权限/发布状态仅指当时时点。

# Attention E0/E1 数字基线与有限Ising采样实测

现有Attention的理想Ising接口不能证明原生p-bit优于数字Softmax。本变更新增常规数字数值参考、online PV、数字IID/systematic和有限串行Ising对照，以及有源/输入hash和CPU/GPU门禁的Slurm驱动。

Refs #35；承接#33有限E0/E1范围，base pbit-tlm-attention-details-20261016。Qwen2.5-0.5B原BF16完整WT2已精确复现11.652735047455899；CPU39测试、真实无扰QK/V、12pilot+465full均通过。三个固定真实输入上同M2048/S128时systematic均值V误差低于串行Ising；单窗口三seed、不作普遍排序和硬件PPA结论。

正式结果qwen/results/attention_e01_20261019，代码experiments/attention_e01，源8790500、原始记录和SHA齐全。大trace/NPZ留个人服务器，Git仅小型指标/索引；早期漏fixture的2159失败与修正CPU预检如实保留。AGENTS追加快照依赖与CPU预检防错规则，原规则保留。

没有完整随机Attention PPL、物理器件/随机源、RTL/PT或能耗实测；旧FFN并行任务未改。当前无push权限，本文为待创建PR正文；PR未创建/分支未上传，Projects待同步。
