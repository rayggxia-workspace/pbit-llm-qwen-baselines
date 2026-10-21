# 2026-10-21 18:11 Llama2检查点：18/26，后续PR83

jieruiz；Issue73 open；后续分支task/73-results-followup，PR83 draft/open未合并，base5b26c80c28ab22383f12ab31046dd723ca985abb；独立目录tmp/llama2-task-accuracy-issue73-20261020。原PR75已合并3fe790ecc2d4849662b60216922fd45dc4300848，只验收代码/提交/恢复阶段，旧“未合并/GPU2584 pending”不再代表当前状态。

CPU Slurm2632、源86ccedc1f14432fc993b4032a9af7873bbf579c6完成exit0；7项本地/远端合同通过。18份sealed full JSON及documents SHA/全量唯一id/候选token/32层与active-dummy/输入与源身份链通过，逐题已存metrics重聚合一致；官方process_results尚未独立复算。未重哈希14GB权重，只核对已验identity manifest绑定，不冒充新模型完整质量验收。

2026-10-21 10:11:23Z：completed18（旧8＋修复10）、running2（2585_12/16）、pending6（2585_20～25），无无效或缺项；本轮比08:39检查点新增ARC-E FFN-only seed0/1。PIQA联合S512仍2/3、ARC-E FFN仍2/3，不算组均值。六项待运行按实测吞吐约7.98GPU小时；保持现有两卡估计还需4～6h，若单卡约8～11h，不是排程保证。原2572健康八项和2585十八项不动，没有新GPU推理或冻结源修改。

正式入口llama2/results/task_accuracy_20261020/PROGRESS_20261021_ZH.md；原件/checksum/ETA见checkpoints/20261021T101123Z/；命令work/jieruiz/73/CHECKPOINT_SUBMISSION_20261021.json。源码已用GitHub Git对象API逐SHA一致上传（原生Git两次连接超时）；后续报告发布以PR83/Issue73新回执为准，不宣称本地文件自动已远端。

下一步沿用同目录/分支和最新Issue73状态，只读收集26项；收齐后加官方lm_eval0.4.8/parquet/YAML逐题oracle和同轮BF16配对统计，再验收最终结果。现有checkpoint的complete仅指封存合同齐全，不替代官方指标复算。Apple FP32两模型单列；当前Attention是原有限CTMC/all-K短题，不是8位p-bit新驱动。heartbeat llama2-7b仍ACTIVE/每日，提示已纠正PR75关闭状态，完整26项核验交付后删除。Projects缺read:project依旧待同步。

以下为历史：

# 2026-10-20 17:40 显存修复与定时回查（最新）

Issue73/PR75继续，未合并。旧022db68中2572_1/2/3初始化OOM；3份原日志保留。15个尚未运行FFN项已撤回，不取消健康任务。原GPU预检成功属于当时空闲条件，不能代表之后共用显存时的初始化安全裕量。

- 原源022db6828c0caba96ae3d620f80b27c1ae3774b9及数组2572保留index0,4,5,6,13,17,18,19，输出原/full。PIQA BF16已完成，Attention seed0在跑。其余6个PD。
- 修复源309ca9c1629c364142ffdce474d5f6138da929c1：每层INT16 W8码无损打包INT8，存储省4.03GiB；FP32恢复权重、算术和RNG不变，新的allocator仅管理存储。CPU2583七项合同通过；GPU2584排队，严格WT2/cache/32层/pilot门禁尚待执行。
- 18项替换数组2585：index1-3,7-12,14-16,20-25；afterok2584，输出本项目/outputs/309ca9c1629c364142ffdce474d5f6138da929c1/full。不得重复运行旧3个失败或15个取消项；最终按8旧+18新构成26唯一任务。两快照请求/模板/Harness相同，见INPUT_EQUIVALENCE_REPAIR.json；最终汇总显式允许这两个执行版本，不能静默重命名。
- 当前真实完整WT2 BF16和原始任务参考沿用原快照；新门禁会再次运行验证。新GPU还未通过，不把CPU一致性写成7B修复已验证。
- 按实际decode工作量/吞吐，1卡剩40～55小时、较快2卡22～32小时；修复版尚未完整计时，保持情景区间。ETA原件与复算数据已保存。
- 用户要求的heartbeat已建：llama2-7b；每24小时，本对话续查；预计首检10月21日17:35北京时间。电脑关机不影响服务器运行，但本地SSH检查必须电脑和App在线；不保证错过即时补跑。后续每日检查直到26项核验交付后停用。配置索引FOLLOWUP_SCHEDULE.json；不要另建重复automation。

恢复先看本节、Issue73/PR75、最新squeue、2583/2584/2585日志。若GPU门禁失败，保持原件并按既有授权在新快照修复；不改已提交snapshot。只回收sealed完整分数，三seed未齐保持pending。新的75份源直接等于Git blob，精确小归档evidence/execution_source_309ca9c.tar.gz。

以下为此前提交时点的交接，不能覆盖本节：

# Issue73 远端评测已启动：可执行交接

2026-10-20；jieruiz；https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/73；PR75 draft/open、未合并。目标workspace正确；本地tmp/llama2-task-accuracy-issue73-20261020，分支task/73-llama2-task-accuracy，基线18b887bd2d0cd6c06d070d8dafaf8b979742fdcf。

## 已完成

- 新增Llama32层专属守卫/安装和缓存MC评分，原Qwen代码未改。共享原B4/T32/K32和有限CTMC数值核；本轮不训练，不校准/启用长上下文筛选。
- 完整PIQA1838/ARC-E2376官方0shot、lm_eval0.4.8、明确no-extra-BOS。两个task与Qwen选择/原始数据SHA一致；Llama tokenizer独立重新编码。Apple已合并PR67完整FP32两模型baseline索引补充，绝非重跑或相同模型因果替换。
- CPU Slurm2570：6项微型32层合同全部通过，数据/model hash验证；GPU2571：full WT2 BF16严格4.979502845218782/335686目标，8题原始独立cache逐选项误差0.0，SDPA wrapper逐字节一致；4个真实7B概率pilot/32层覆盖通过，peak32,091,221,504B。
- 正式数组2572_[0-25]已提交并因2571成功自动开始，资源上限2卡，目前只有1卡空闲。26项正式分数仍pending。

## 冻结与位置

执行提交022db6828c0caba96ae3d620f80b27c1ae3774b9；snapshot /home/Hongjie_Zeng/projects/pbit-llama2-task-accuracy-20261020-issue73/snapshots/022db6828c0caba96ae3d620f80b27c1ae3774b9；outputs同项目/outputs/<该SHA>/；正式/full、预检/pilot、请求/tokenized、suite.json和READY.json。绝不编辑快照/原结果或重启覆盖。服务器模型和数据复用本人既有路径，不新存14GB模型。环境/home/Hongjie_Zeng/.conda/envs/pbit_llm；全部推断Slurm。

正式index0..12是PIQA，13..25是ARC-E；每组依次BF16、FFN seed0/1/2、Attention S128 seed0/1/2、联合S128 seed0/1/2、联合S512 seed0/1/2。配置/命令/依赖完整见llama2/results/task_accuracy_20261020/evidence/{suite.json,SUBMISSION.json}。

## 恢复步骤

1. 核Issue73/PR75和最新本人STATUS，再通过已有SSH alias lab-server-ai读squeue -u Hongjie_Zeng；Slurm路径/opt/slurm/21.08.8/bin。不修改他人作业。sacct存储不可用，以实际scontrol短期记录和应用sealed completed原件证据区分状态。
2. 查看本项目logs/full-2572_<index>.log；进度文件不是完整结果。完整JSON须status=completed、任务全量、合法docid、无重复及SHA匹配documents.jsonl。
3. 只读回收full JSON和对应逐题原件，验证冻结source/identity/task-data/config/dataset/model SHA和每题所有选项计分、32层审计、active/dummy。按三seed齐全汇总acc/acc_norm均值/波动、相对本轮BF16配对变化；acc_norm是字符长度归一化。未齐保持pending，不拿pilot代替。随后同PR更新结果与Issue。
4. 没有本任务专用自动collector；不要直接用Qwen硬编码24层collector。可按上述契约写Llama32层collector并测试缺失/篡改等拒绝路径，原数值源和作业不改。

原始执行源Git archive在Windows对38继承文件LF转CRLF。75源文件已逐项验证与Git仅换行不同；精确执行原件压缩包196792B入Git evidence/execution_source_022db68.tar.gz，LOCAL_VERIFICATION.json列各源SHA和转换。原tar服务器incoming保留；本地临时tar交付后可删，按包SHA可恢复，不删除实验历史。

发布代码和证据在PR75；canonical长期备忘录既有Issue55审核追加仍保持原样，本任务只增Issue73入口，不擅自提交其他任务未提交delta。Projects缺read:project范围待有权限者同步；该项不阻止Issue/PR发布。不写本地完成为远端已完成。
