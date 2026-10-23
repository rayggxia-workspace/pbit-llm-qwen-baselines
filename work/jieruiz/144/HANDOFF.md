# Issue144 Qwen3概率架构交接

2026-10-23，负责人jieruiz。用户授权两个Base模型迁移最新概率计算架构/PPL对照及参数说明。

独立稀疏目录tmp/qwen3-stochastic-issue144-20261023；分支task/144-qwen3-stochastic，base task/136-qwen3-bf16 @0829b9ce0fddef993475e53ecd7d3cba6bc776d6。依赖PR137完成未合并、PR143的固定执行源码7a286ec；不更改两任务快照。新Issue144已创建，PR尚未建立。实际本地验证仅语法compileall和diff --check，CPU/GPU测试待Slurm；没有新概率PPL。

实现/参数/口径见qwen3/stochastic/README_ZH.md。13配置每模型，4096目标suffix、batch2、随机3种子；完整候选WT2未提交。先CPU tiny原生Qwen3/全层计分/无损codes/保存重载门槛，再GPU tiny与真实模型SDPA bitwise、kernel oracle、原始全量BF16锚点复现、TRAIN校准和后缀评测。

服务器新ROOT /home/Hongjie_Zeng/projects/pbit-qwen3-stochastic-20261023-issue144，复用基线ROOT的venv/权重/数据，旧基线结果只读不覆盖。所有任务Slurm，最多2GPU；运行ID及冻结SHA待实际提交后追加。失败快照保留、不重复提交健康任务。成果只有小型manifest/log/result收取Git，不传权重。

待办：冻结发布源、CPU预检、GPU作业、取得真实PPL并独立SHA/覆盖复核、同任务PR/STATUS/长期记忆同步。Projects历史缺read:project待有权限成员同步。不合并PR、不关闭Issue。
