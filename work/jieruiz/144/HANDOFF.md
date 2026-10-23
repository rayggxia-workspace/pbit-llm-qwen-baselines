# Issue144 Qwen3概率架构交接

## 最新：2026-10-23 20:25 CST（下方初始状态为历史）

执行源8c35145e0073e48581640cd07c770631412a3f99已上传官方分支；[PR147](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/147) draft/open，未合并，base task/136-qwen3-bf16。包tmp/qwen3-issue144-source-v1.tar.gz，SHA81df52718c184f026b6cf62230ab2559473225bf8d64f40cd84363a07d4d0de4。ROOT/snapshots/8c35145只读不改。

CPU2827通过并生成preflight.json，含模型全文件SHA核验。GPU2828=1.7B、2829=4B，各1GPU/4CPU/48G/24h，正在跑首个FFN seed0；13配置每模型，完整候选WT2未提交。日志ROOT/logs/pilot-1p7-2828.log、pilot-4b-2829.log；结果ROOT/results/Qwen3-1.7B-Base、Qwen3-4B-Base。两项健康作业不能重复提交。无自动重试/断点覆盖，新请求恢复先检查日志/作业/已签结果。

GPU tiny及真实模型SDPA包装bitwise、kernel12组分布/轨迹和仲裁/cap门槛均通过；两个原始BF16完整锚点精确复现旧NLL。TRAIN独立校准完成。已签后缀BF16 PPL：1.7B 7.590088097428094（36.47s），4B 6.331574616885452（47.62s），4096目标。不能减完整基线；概率结果仍运行，无最终PPL增量。

首批原件为ROOT/exports/start-v1.tar.gz，SHA12e1110bedfc8bc1e390d10bc085f8d188c59e6aafdf1f88e88a604345224427；本地tmp/qwen3-issue144-start-v1.tar.gz，解包qwen3/results/stochastic_20261023/checkpoints/start。26文件，服务器原字节SHA和11sidecar、27执行源码blob、模型/数据/配置、全部后缀计分覆盖核验通过；8语义损坏负例均拒绝。独立收取脚本ROOT/collect_snapshot_v1.py在快照外，只读已签JSON/小日志；日志是收取时点快照，不是最终日志。警告：tiny的sliding-window通用提示实际层均sliding_window=None已assert；tokenizer长文本提示仅分词，全模型输入按窗口切片，不送入299078长度序列。

后续只需检查这两个作业，完成后用collect_snapshot.py --root ROOT --output ROOT/exports/<新唯一名称>.tar.gz取得小原件，按远端包SHA复制并解包到新checkpoint，再在本地 `python qwen3/stochastic/validate_results.py <checkpoint> --output <checkpoint>/VALIDATION.json`；同任务PR发布三seed均值/标准差/增量与耗时。不传权重，不改8c35145执行源码。后加验证器/收取工具不在8c执行manifest，不冒充原始推理源码。完整候选评测预算仍待先导实测，不自动新增大任务。

长期记忆canonical和本机根已同步同字节，保留其他并行条目。此前baseline的qwen3 heartbeat已删除；本任务没有新增定时。Projects read:project缺权限待有权限成员同步。结果与状态发布进度以PUSH/REMOTE_VERIFY回执为准。

2026-10-23，负责人jieruiz。用户授权两个Base模型迁移最新概率计算架构/PPL对照及参数说明。

独立稀疏目录tmp/qwen3-stochastic-issue144-20261023；分支task/144-qwen3-stochastic，base task/136-qwen3-bf16 @0829b9ce0fddef993475e53ecd7d3cba6bc776d6。依赖PR137完成未合并、PR143的固定执行源码7a286ec；不更改两任务快照。新Issue144已创建，PR尚未建立。实际本地验证仅语法compileall和diff --check，CPU/GPU测试待Slurm；没有新概率PPL。

实现/参数/口径见qwen3/stochastic/README_ZH.md。13配置每模型，4096目标suffix、batch2、随机3种子；完整候选WT2未提交。先CPU tiny原生Qwen3/全层计分/无损codes/保存重载门槛，再GPU tiny与真实模型SDPA bitwise、kernel oracle、原始全量BF16锚点复现、TRAIN校准和后缀评测。

服务器新ROOT /home/Hongjie_Zeng/projects/pbit-qwen3-stochastic-20261023-issue144，复用基线ROOT的venv/权重/数据，旧基线结果只读不覆盖。所有任务Slurm，最多2GPU；运行ID及冻结SHA待实际提交后追加。失败快照保留、不重复提交健康任务。成果只有小型manifest/log/result收取Git，不传权重。

待办：冻结发布源、CPU预检、GPU作业、取得真实PPL并独立SHA/覆盖复核、同任务PR/STATUS/长期记忆同步。Projects历史缺read:project待有权限成员同步。不合并PR、不关闭Issue。
