# Llama 2 7B 代表任务对照（提交阶段）

2026-10-20；Issue73，负责人jieruiz。正式评测已提交Slurm，结果尚未收齐，空项不代表0分。

## 本轮对照

| 模型/配置 | 每任务运行次数 | PIQA | ARC-E |
|---|---:|---|---|
| Llama 2 7B 原始 BF16/SDPA | 1 | 等待正式结果 | 等待正式结果 |
| 仅 FFN B4/T32/K32 | 3 seeds | 等待正式结果 | 等待正式结果 |
| 仅 Attention Ising S128 | 3 seeds | 等待正式结果 | 等待正式结果 |
| FFN＋Attention Ising S128 | 3 seeds | 等待正式结果 | 等待正式结果 |
| FFN＋Attention Ising S512 | 3 seeds | 等待正式结果 | 等待正式结果 |

## Apple已完成基线（复用已合并PR67）

以下均为完整数据集、lm_eval0.4.8、zero-shot；百分数写作acc / acc_norm。

| Apple原始FP32模型 | PIQA 1838题 | ARC-E 2376题 |
|---|---:|---:|
| Softmax 7B | 75.5713% / 77.0403% | 72.1801% / 68.7710% |
| Sigmoid 7B | 76.4962% / 77.4211% | 73.2323% / 69.6970% |

这是已有完成结果的索引补充，并未重复运行Apple作业。两个Apple模型独立预训练，FP32/full-forward；Llama是BF16/cached decode，因此是跨模型参考，不能据此计算同权重替换的因果收益。原件、提交和SHA见APPLE_BASELINE.json及results/apple_sigmoid_7b_eval_20261019/。

## 执行及适用范围

- 选择两个完整任务控制7B运行时间，未使用HellaSwag固定1000子集；题目/模板/计分与Qwen一致，tokenizer独立核验。
- 总计26项；概率版本每档3种子，固定batch4、每任务相同请求顺序与原始BF16对照。
- FFN为固定W8、多尺度分层随机门限T32/K32，共享64路；SiLU和g*u连续，gate/up输入和down输入独立编码。不是双随机或自然IID。
- 注意力所有计分token走全部32层单token路径；多token前缀Attention保持原始SDPA。短题K长度不足512，不做QK筛选，不称长上下文K节省已验证。
- Ising为理想硬约束有限CTMC，burn16/spacing4；S128/512是观察次数，不是ESS或器件周期。
- Apple和Llama不同tokenizer，PPL不可直接作相同token尺度比较；本表只保留相同任务准确率。

源码experiments/llama2_task_accuracy_20261020/；冻结执行提交022db6828c0caba96ae3d620f80b27c1ae3774b9。
CPU2570，GPU预检2571，正式数组2572_[0-25]，afterok链保证预检失败不会开始正式任务。调度和原件索引见evidence/；评分未完成不写成已完成。

完整WT2原BF16复现、独立缓存评分、SDPA等价和概率路径pilot是门禁，pilot不算完整任务准确率。本轮没有训练或PPA。

## 已通过的门禁与当前状态

CPU2570：6项完整32层小模型功能合同通过。GPU2571：完整WT2 BF16复现4.979502845218782，335686目标；8个最长prompt pilot题与独立缓存参考逐候选总分最大差0.0，greedy全部一致；digital_sdpa原件逐字节一致。4个真实7B概率case pilot完成，最高分配显存32,091,221,504字节（约29.89GiB），单卡5090可运行。pilot不作为任务质量结论。

正式数组2572_[0-25]已经释放依赖，首项2572_0运行；其余等待Resources。上限两张GPU，当前其他7张由别人的任务使用，未取消或改动他人作业。完整分数仍pending。原始Slurm回执、READY和SHA位于evidence/。

精确执行源以execution_source_022db68.tar.gz保留（约192KiB）。Windows git archive对38个继承文件执行了LF→CRLF，75个文件均已核验原始执行SHA及与Git的内容等价；没有数值变更。不要归一化这些已记录SHA的原件；详见LOCAL_VERIFICATION.json。
