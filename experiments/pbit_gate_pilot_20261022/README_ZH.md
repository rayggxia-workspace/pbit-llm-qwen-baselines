# 小型 p-bit QK 筛选网训练验证（Issue92）

第二轮直接质量目标、隐式预算梯度与90配置冻结盲评见[优化协议](OPTIMIZATION_PROTOCOL_ZH.md)及[独立留出结果](../../qwen/results/pbit_gate_optimization_20261022/README_ZH.md)。下文保留首轮协议，不能用它覆盖第二轮的输入、目标或数据版本。

本实验回答：四个子块摘要分数能否通过一个很小的可训练概率映射，在相同训练集平均选块预算下减少遗漏的重要 Attention 概率质量。Qwen 主模型、FFN 和 Attention 教师全部冻结。本目录不训练 LLM，也不把软件 Bernoulli 抽样称为物理器件训练。

本说明对应冻结执行代码 `53c24f28eb24d25f0edffc4e45354dab6cd86154`，参考配置为 [pilot.json](pilot.json)。这里给出协议与复现方法，不预先声称训练收益、完整模型 PPL 或硬件 PPA 改善。

## 数据与教师

- 模型：Qwen2.5-0.5B Base，原 BF16 权重、原 FFN、原 SDPA，context=2048。
- 仅使用 WikiText-2 raw **train** 语料，按顶层文章切分、正文内容去重，capture seed=42；选取足够长且不重复的文章，文档级划分为 train/val/holdout=32/8/8。每篇只使用首个2049 token，前2048 token用于观测；同一文章不得跨 split。
- 观测层0/12/23、Q头0/6/13、位置1023/1535/2047（从0计数）。每个完整 query/head 是一个训练组，含32个块槽，每块64 token，块内四个16-token子块。各位置实际可见16/24/32块，无效槽由独立 valid mask 标识。
- 捕获 post-RoPE Q/K 和真实 V；输入 `x[b,s]=q·mean(K[b,s])/sqrt(64)`。教师用全体因果可见 key 的 FP32 Softmax，记录块质量 `mass[b]=sum_i p[i]`、`block_v[b]=sum_i p[i]V[i]` 和完整教师输出。
- 首块与最后两个有效块强制保留。强制块计入预算，不参与自由块 BCE；不从未来 token 构造摘要。共1296组，三个 split 为864/216/216组；每层为288/72/72组。各层网络共享该层选定头和位置的数据，不跨层共享参数。

捕获钩子只观测，不替换 SDPA 返回值。原 BF16 前向一致性门禁与 FP32 教师对 BF16 SDPA 的差异诊断分别记录。捕获阶段的原模型 NLL/PPL 仅针对所选 **train文章**，不是 WT2 test PPL，也不是筛选网的模型级质量。

[capture_teacher.py](capture_teacher.py) 输出 `dataset.npz` 与捕获报告。NPZ 核心字段为 `x[G,32,4]`、`mass[G,32]`、`block_v[G,32,64]`、`teacher_output[G,64]`、`valid/forced/counts[G,32]`，以及逐组的 layer/head/document/split/position。原始文本、模型权重和数据集不提交 Git；位置与 SHA-256 由报告和 manifest 绑定。

## 网络、训练目标与预算

主网络是4→8→1：

\[
 a_j(x)=\sigma(xW_{:,j}+b_j),\qquad
 h_j\mid x\sim\mathrm{Bernoulli}(a_j(x)),\qquad
 z\mid h\sim\mathrm{Bernoulli}(\sigma(h\cdot v+d)).
\]

给定输入，8个隐藏 p-bit 条件独立，无隐藏位间耦合或 Ising 更新链。参数为32个输入权重、8个输出权重、8个隐藏偏置、1个输出偏置，即**每层49参数**。层0/12/23分别训练，三个训练 seed=0/1/2，共9个主网络；每个模型保留独立参数与日志。

训练时枚举全部256个隐藏态，精确计算边缘保留概率：

\[
 q(x)=\sum_{h\in\{0,1\}^{8}}
 \left[\prod_j a_j(x)^{h_j}(1-a_j(x))^{1-h_j}\right]
 \sigma(h\cdot v+d).
\]

这避免用有噪声的梯度估计训练本次极小网络，不是把随机隐藏层替换为均值隐藏层。评估使用真实的两级隐藏/输出 Bernoulli 抽样。训练四维标准化只拟合该层 **train自由块** 的均值、标准差；val/holdout沿用，不重新拟合。

教师块质量不是选择概率。软标签为

\[
 t_b=\sigma(\log(mass_b+10^{-12})-\tau_l).
\]

温度固定1；每层仅用 train 二分校准 `tau_l`，令强制块概率设为1、无效块概率设为0后的平均预算为8。损失为自由块 BCE 加预算正则：

\[
 \mathcal L=\mathrm{BCE}_{free}(q,t)
 +0.1\left[\frac1{G_{batch}}\sum_g\sum_b q^{eff}_{gb}-8\right]^2.
\]

batch必须由完整组组成；这里平方的是**平均组预算误差**，不惩罚每个 query 与8块的偏差平方。参考配置为 Adam、lr=0.003、100 epochs、group_batch=32。仅按 val 总损失选择 checkpoint；恢复所选 checkpoint 后，仅用 train 调整实际输出节点偏置 `d`，并重新精确计算边缘概率，校准平均8块。不得对边缘概率的 logit 事后平移冒充输出节点偏置校准。

保留两个对照：

| 方法 | 概率映射与训练 |
|---|---|
| max4＋sigmoid | 每块四输入取最大；每个 query 仅以自由有效块计算均值/标准差，标准差下限0.01，温度1；仅用train校准标量偏置 |
| 4→1线性 p-bit | 同一套按层train拟合的四维标准化；4权重＋1偏置，按同目标与预算训练，三个seed |
| 4→8→1随机网 | 每层49参数、256态精确边缘训练、真实两级抽样，三个seed |

三种方法均为**可变选块数**。只校准 train 平均8块；不做 top-K、固定8块修复，不用 val/holdout重校准。val/holdout预算漂移、尾部选中数和超过512 token比例必须如实报告。此对照不能单独证明隐藏随机性优于同规模确定性网络。

## 评估与成果

每层、每个模型、每个 split 分别保存组数、文档数、期望遗漏质量 `mean(1-sum_b q_eff[b]mass[b])`、期望选块数与 token数。抽样评估 seed=101/202/303，每seed16次，记录遗漏均值、选块/选token均值、P95、最大值和选token数超过512的比例。

选中子集输出使用准确教师分数重新归一化：

\[
 \hat o=\frac{\sum_b z_b\,block\_v_b}{\max(\sum_b z_b\,mass_b,10^{-12})}.
\]

相对完整教师输出记录 NMSE，另记录选中质量最小值及分母触发epsilon保护的次数。这是局部准确 PV 子集误差，不包含 Ising 采样误差；不能叫模型 PPL。选中 token数也不能直接换算成真实 GQA/KV 物理传输字节或带宽收益。

`train/` 内的 `SUMMARY.json`、各模型参数/标准化JSON、逐epoch日志、`DATA_BINDING.json` 和 `RESULT_MANIFEST.json` 保留精确配置、源码、数据 SHA-256 和校准/选择依据。每文档配对指标供后续按文档 bootstrap 使用，不把同一文章的多个 query 当独立统计样本。

## 调度与复现入口

所有服务器计算通过 Slurm 分配运行，不在登录节点捕获模型或训练。先核实登录身份 `Weican_Chen`、规范 home、个人任务根和环境路径；快照、环境、输入和输出均位于本人已核验的个人根。提交前固定不可变源码快照与配置，记录 SHA；已有作业状态不明确时先核查，不重复提交。

`run.sbatch` 使用以下环境变量：`GATE_SNAPSHOT`（源码快照）、`GATE_CONFIG`（配置文件）、`GATE_PYTHON`（个人环境解释器）、`GATE_SOURCE_COMMIT`（执行版本）、`GATE_OUTPUT`（阶段输出）、`GATE_STAGE`。各路径须为已核验绝对路径；`gpu_pilot` 的输出目录必须尚不存在，防止覆盖。

```bash
# 在核验路径、配额和现有作业后设置上述变量；按集群实际资源覆盖调度参数。
export GATE_SOURCE_COMMIT=53c24f28eb24d25f0edffc4e45354dab6cd86154
export GATE_CONFIG="$GATE_SNAPSHOT/experiments/pbit_gate_pilot_20261022/pilot.json"
export PYTHONPATH="$GATE_SNAPSHOT"

# 分别给两个CPU阶段设置不同且位于个人根的GATE_OUTPUT。
export GATE_STAGE=cpu_tests
sbatch --export=ALL "$GATE_SNAPSHOT/experiments/pbit_gate_pilot_20261022/run.sbatch"
export GATE_STAGE=cpu_preflight
sbatch --export=ALL "$GATE_SNAPSHOT/experiments/pbit_gate_pilot_20261022/run.sbatch"

# 确认两项CPU门禁成功后，设置新的GATE_OUTPUT，仅提交一个GPU作业。
export GATE_STAGE=gpu_pilot
sbatch --gres=gpu:1 --export=ALL "$GATE_SNAPSHOT/experiments/pbit_gate_pilot_20261022/run.sbatch"
```

CPU阶段由脚本显式设置 `CUDA_VISIBLE_DEVICES=''`。GPU入口 [run.py](run.py) 依次执行分配内GPU预检、冻结教师捕获、训练与评估；命令、job/node、实际代码版本及所有成果 SHA 保存在 `RUN.json` 和 `MANIFEST.json`。环境或输入门禁失败时保留日志并停止，不绕过校验。

已经获得分配、只需重跑训练阶段时，使用模块入口并指定已验证的NPZ和新的输出目录：

```bash
"$GATE_PYTHON" -P -u -m experiments.pbit_gate_pilot_20261022.train \
  --config "$GATE_CONFIG" --dataset "$GATE_DATASET" --output "$GATE_OUTPUT"
```

参考配置固定文本SHA `6707892fa3788b5ab9ed78ab5ff37d9fe825f6011a2ad4fcd6a6d467f0e7da57` 与模型权重SHA `88c142557820ccad55bb59756bfcfcf891de9cc6202816bd346445188a0ed342`；tokenizer/config等原件另逐文件记录。此实验的完成范围是训练与局部质量/预算验证。完整模型接入与PPL、同规模确定性小网、物理随机源及完整面积/能量/时延仍需独立验证。
