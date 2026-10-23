# Issue144 Qwen3概率架构交接

## 最新：2026-10-23 21:50 CST，26/26全部独立核验，准备发布

2828/2829均已结束，两个PILOT_COMPLETE及complete.json齐全；没有重跑、源码8c35145未改。收取ROOT/exports/complete-v1.tar.gz，SHA a3d0df3f043d4a1fee23f9da547d585bcde0f28e9c325d665880fdd5c1a2ace3，本地tmp/qwen3-issue144-complete-v1.tar.gz，原件qwen3/results/stochastic_20261023/checkpoints/complete。78文件、77清单原字节、37 sidecar、27执行源blob、26病例全目标全层覆盖/NLL/PPL/各SHA绑定核验通过，17篡改负例通过；最终SUMMARY.json/REPORT_ZH.md包含三seed与时间、全部参数、legacy burn字段解释、GQA union和完整WT2预算。

1.7B BF16/FFN/screen/rejection/winner为7.590088/7.666993/8.067234/8.249476/8.091915；4B为6.331575/6.365253/6.676899/6.810810/6.700177。随机均值各3seed，严格4096目标后缀，不是完整WT2。完整26项外推156 GPU小时，若两卡固定分模型约3.7天（规划±30%约2.6–4.8天），未提交全量。

当前仅本地收尾完成；待同branch task/144-qwen3-stochastic推送、逐Git blob/远端原字节核验、Issue清单/PR147 ready与停止heartbeat qwen3。最终实际发布/停表回执以FINAL_PUBLICATION.json和下次顶部为准。PR base仍task/136-qwen3-bf16，不合并、不关闭Issue。Projects仍待有权限成员同步。除最终发布外没有运行实验/待补病例；禁止按下方旧状态重交作业。审计脚本增强不在冻结执行源中；不更新服务器snapshot。保留最小待审工作目录，无新helper/权重。

## 最新：2026-10-23 20:54 CST，用户要求完成全部方案

2026-10-23 20:54 CST用户要求“请做完全部方案”。继续已冻结两模型各13配置共26项4096目标后缀，不重复健康作业、不扩大为完整WT2；目前日志16/26已完成（1.7B拒绝seed2运行，4B拒绝seed0运行），2828/2829均RUNNING，无错误，未收取的阶段数字不作为正式结果。依据OpenAI Docs官方定时说明通过应用工具实际建立本对话heartbeat id=qwen3，名称“完成Qwen3全部概率方案”，ACTIVE每10分钟，限定收齐26项后核验/汇总/同PR147发布并通知，随后删除定时；无变化保持安静，失败/新权限或范围修改需报告。旧基线同名id曾删除，本次是新建收尾检查。需要本机及桌面应用运行以执行本地SSH/发布，服务器Slurm独立继续。发布源仍8c35145不改，最新科学结果672ad88；此前head5ce00f6的94文件GitHub逐blob原字节通过。

恢复需完成：每模型bf16_s0、ffn_s0/s1/s2、screen_exact_ffn_s0/s1/s2、rejection128_ffn_s0/s1/s2、winner1024_ffn_s0/s1/s2，加complete.json；validate_results两模型均COMPLETE才算本轮26项完成。后续用新唯一名归档（勿重用start-v1/ffn-v1）；源ROOT/collect_snapshot_v1.py可复用。最终更新报告/参数表/每seed与平均±std/相对BF16增量/实际时间，按目标调用量估算完整WT2预算，不自动启动全量。需补源边界负例及所有原件Git blob核对；*.log被全局ignore，明确git add -f自己的小型归档日志，且保留results/**的-text属性。完成后PR转ready、Issue清单更新但不关闭/不合并，删除heartbeat qwen3并记录实际回执。未失败前不修改源、不另提交作业。

## 最新：2026-10-23 20:33 CST，双模型FFN三seed已验证

源码审计补充：args中的legacy burn16/spacing4是旧scorer默认字段，新adapter从未将其传入kernels.sample；实际winner burn0/spacing1、rejection无burn，已在sampling_stats.sampler_parameters明确。不要改运行源或原结果字段，报告按真实调用参数。该说明是元数据解释，不是行为变更。

两个模型BF16+FFN-only共8配置完成；1.7B FFN平均7.6669926785±0.0086502594（样本std）、相对7.5900880974为+0.0769045811/+1.013223827%；4B平均6.3652531446±0.0029902575、相对6.3315746169为+0.0336785277/+0.531913935%。都是相同4096目标后缀，不是完整WT2，也不是Attention联合结果。FFN每配置约156/204秒。

GPU2828/2829进入screen_exact_ffn seed0阶段，随后会顺序做其余2seed、拒绝128三seed、赢家1024三seed；不要重复提交。ROOT/exports/ffn-v1.tar.gz SHA53d085047ee27025f2ef42bf04c2ee7c863ae5cb09dcd4eab733c3557af8ab63，38文件；本地tmp/qwen3-issue144-ffn-v1.tar.gz和qwen3/results/stochastic_20261023/checkpoints/ffn。17已签JSON、全部8病例源码/模型/数据/配置/校准SHA、逐层全部4096目标与NLL/PPL重算通过，结果见REPORT_ZH.md。完整候选任务仍未提交，联合结果待跑，初步FFN结论不能代替全量/联合结论。

启动记录head bab6688161e0a5c4ea3c9fb029a6d67e6d1882b0的55文件已经从GitHub逐blob原字节读回通过；后续本FFN结果发布以最新PUSH/REMOTE_VERIFY回执为准。原始3日志最初被全局ignore遗漏，已用3877987显式补齐且25源原件Git blob SHA通过；没有改动任何冻结执行源。

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
