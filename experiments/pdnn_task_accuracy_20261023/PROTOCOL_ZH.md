# Issue145：现成两层、四层 P-DNN 的代表任务准确率

负责人 amlink1219。目标是评估已有权重，不训练模型、不修改 Attention、不恢复暂停的 TLM 任务。源集成提交为 `6966739a5223680888bf0315f7bb4f73423a1ae6`。

## 模型身份与边界

- 教师／对照：`Qwen/Qwen2.5-0.5B` Base，BF16，原 SDPA、原 tokenizer，无 chat template，24 层。
- 四层：本人服务器 `pbit-qwen-joint-ablation-20260929/results/reference_1000/` 中 step1000 联合蒸馏的层 10/11/12/13。每个 FFN 是 `896 → 4864 → 896` 的原始串联双投影 P-DNN，输入与隐藏层均为 bipolar p-bit，每次平均 N=4 条完整随机路径，权重／读出仍连续。
- 两层：上述同一组权重中层 10/12 的子集，其他 22 个 FFN 恢复原 Qwen 模块。这是新的子集消融，**不是历史层 6/12 的两层独立训练模型**，也不是内部网络深度为 2。
- `config.json` 绑定四个 checkpoint 的路径、大小和 SHA-256。它们与旧公开 joint4 报告的文件 SHA 不同；本次不继承旧报告 PPL，也不宣称仅序列化不同。旧的 `{6,12}` 文件在本次检查的本人存储中尚未找到。
- 本次只测任务准确率，不推导硬件 PPA，不将软件随机数当作物理 p-bit。

## 与仓库 Qwen 准确率协议保持一致

沿用 Issue59 / PR62 的 `experiments/qwen_task_accuracy_20261019/task_data.py`，固定 lm-evaluation-harness 0.4.8，官方 prompt、tokenizer `_encode_pair` 和 `task.process_results`，0-shot：

| 任务 | split | 题目数 | 选择 |
|---|---|---:|---|
| PIQA | validation | 1838 | 完整 split |
| ARC-Easy | test | 2376 | 完整 split |
| HellaSwag | validation | 1000 / 10042 | 推理前用 Python `Random(20261019)` 无放回固定抽样 |

三个 parquet SHA 与旧协议逐字节核对；HellaSwag 不按本次预测选样。任务标签只进入官方计分，不进入模型、随机种子或候选排序。`acc` 为候选总对数似然最大者；`acc_norm` 按原候选字符串的字符长度归一化，不按 token 数。

每个任务先重跑匹配 BF16，再跑两层／四层各 seed0/1/2，总计 21 个完整 case。按相同 prompt token 长度、候选数分组，batch 上限 16，无 padding，无截断。组大小不足时保留实际大小。每个候选为 teacher-forced token likelihood；不是生成答案后字符串匹配。

## 随机与 KV 协议

prefill 用 `context[:-1]`，最后一个 prompt token 走 q_len=1 生成首答案 logits，所有候选共用该 logits。每个候选分支深拷贝 KV，并恢复全局 CPU 及模型实际 CUDA 设备 RNG。候选按 token ID 字典序执行，再映射回原顺序；不使用标签。完成候选的 dummy 行只维持 batch 形状，绝不计分。

P-DNN 原算子使用全局 `torch.rand_like`。新适配器显式处理它，不能沿用只保存随机计算 FFN 自定义 RNG 字段的旧 wrapper。每个 batch 的种子由任务／doc ID／case seed 的 SHA-256 产生；调用后恢复调用者 RNG，异常也恢复。不同替换层数会改变随机数消耗，相同 seed 不表示两层／四层逐个 draw 配对。与最早 batch32、单全局 seed 的历史 lm_eval 结果也不是逐位相同随机协议。

Guard 检查原层／替换层、采样数、完整配置、BF16 参数、参数及 buffer 的身份／版本、实际设备、eval/frozen 状态。保留原模型按加载器构建的 buffer dtype，不通过整个模型 `.to(dtype=...)` 改写 RoPE buffer。每次 forward 审计全部 24 层在 prefill 和 decode 都执行，指定 P-DNN 层在两路径均替换。

## 执行、验收与制品

所有计算在 Slurm allocation 中进行。CPU 预检隐藏 CUDA，完成机制测试、数据／模型／checkpoint 身份检查与 tokenization；GPU 首先做真实模型 smoke 和独立 BF16 cached oracle 对照，通过后才跑完整 case。只用本人目录，不读写其他用户的私有存储，不改已有模型／数据／环境。

源快照、配置、模型／tokenizer、checkpoint、数据、选题 ID、harness 文件均记录 SHA-256。每 case 保存每题各候选 logprob、greedy 标志、官方 acc/acc_norm、执行覆盖计数、实际环境／命令／GPU／Slurm job、耗时和显存；中断保留 progress，不能把前缀写成完整 split。已完成 case 只有经 provenance 与散列复核才可跳过；部分 case 不自动覆盖续跑。

报告给出新 BF16、两层／四层三个 seed 的均值、样本标准差与相对 BF16 的百分点差；区分 seed 波动与任务有限样本误差。按任务分别报告，不把不同任务的准确率简单平均成总体指标。大权重与数据保留服务器；Git 提交必要配置、代码、汇总、原始小型结果和散列索引，通过任务 PR 交付。
