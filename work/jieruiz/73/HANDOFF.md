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
