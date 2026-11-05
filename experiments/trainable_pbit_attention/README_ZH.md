# 赢家保持与校正拒绝：可训练 PyTorch 参考模块

Issue138。独立新增模块，沿用 `experiments/pbit_sampler_qkv_20261021/samplers.py` 的算法规则；不改旧实验、TLM、RTL或模型默认配置。这里是可以接入 Q/K/V 网络的随机前向和梯度接口，不是已完成 Qwen/Llama 微调的权重。

## 两种真实前向

输入 `scores[..., N]` 是已经算好的 QK/√d；`values[..., N, D]` 可向 scores 的前缀广播。输出是实际采样地址对应 V 的均值，不是准确 Softmax×V。外部筛选后的 mask 可直接传入；模块不实现 QK 筛选、QK矩阵乘法、RoPE、输出投影或残差。

| 模块 | 一次更新 | 输出规则 |
|---|---|---|
| `WinnerHoldAttention` | 所有有效位置独立以 sigmoid(zᵢ−max(z)−shift) 提议；当前赢家提议为1则保持，全零也保持；否则在所有1中均匀选一个 | 初始赢家为argmax；执行 `burn_in + samples × spacing` 次完整更新；热身后每spacing次取地址，保持也计入样本 |
| `CorrectedRejectionAttention` | argmax地址作全零参考；其余位置以 sigmoid(zᵢ−z_ref−m ln2) 提议。单1直接接受；全零以2⁻ᵐ概率接受参考；多1拒绝并m+1；全零拒绝时m−1 | 仅接受才累积V；接受后m不变；每次调用m重新从initial_shift开始。达到行级总提议上限就抛异常，无补样、无部分成功、无Softmax回退 |

偏移m约束0..max_shift，max_shift≤24。上限是 `samples × max_trials_per_sample`，**并非每个地址单独限次**，保持旧实现语义。全零校正用m个公平bit全为0，m=0必接受。均匀仲裁用有界整数拒绝采样，不使用取模偏差或“出现1最多就取谁”。

### 为什么分布成立，以及哪里不成立

赢家保持的理想稳态为 Softmax：pᵢ/(1−pᵢ)=exp(zᵢ−max(z)−shift)，任意两个地址的转移满足此稳态的详细平衡。但初始化、热身不足和连续保持都可能影响有限样本，不能把每次更新当成独立 Softmax 样本。

校正拒绝在固定m下：接受i的概率为 `P(全零) × exp(zᵢ−z_ref) × 2⁻ᵐ`；接受参考的概率为 `P(全零) × 2⁻ᵐ`。归一化后正好是 Softmax。新一轮独立提议、按拒绝历史改变m仍保留这一接受分布。**省略全零的2⁻ᵐ校正就不成立**。提议数是随机变量；cap是失败保护，不能静默删掉失败训练批次再声称得到了原目标的无偏梯度。

这些结论依赖独立、理想sigmoid响应。这里用PyTorch PRNG模拟独立随机数；没有验证物理器件相关性、非理想响应或真实随机架构的联合分布。Attention候选之间没有采用FFN的64路共享门限。`eval()`仍采样，显式传入的Generator会持续前进；重建同seed Generator用于复现。不同后端、不同批形状/消耗顺序不保证同seed得到同轨迹；旧NumPy只要求规则与分布一致。

## 训练：真实前向与梯度估计分开

模块本身不新增可学习权重；它提供让上游Q/K投影和V路径训练的梯度接口。shift、burn、采样预算及离散控制m是配置/运行状态，不是本版优化器自动学习的参数。

默认 `gradient_mode="score_function"`：前向完全按照上述离散规则；返回 `score_log_prob`，记录**全部**参数相关Bernoulli对数概率，包括热身、保持、未保留的间隔更新和被拒绝提议。公平仲裁/校正币给定历史后不含连续模型参数，故可略去它们的对数常数；此字段不是完整轨迹密度。

对一条轨迹的损失L，训练梯度估计为：

`直接沿 V 等连续路径的梯度 + (L − 基线) × 轨迹对数概率的梯度`。

`result.objective(loss, baseline)`实现这个目标，返回值与loss相同，反向额外加入score-function项。argmax只选择参考下标，参考的logit数值仍参加求导，没有detach掉max值。固定唯一argmax的局部参数区间内，使用完整轨迹得到该有限采样目标的期望梯度；赢家初始化在最大值切换/并列处可能不可微。REINFORCE通常方差较高，正确性不等于大模型训练一定高效。该做法遵循[PyTorch score-function说明](https://docs.pytorch.org/docs/2.14/distributions.html#score-function)；实测版本是Torch2.4.1 CPU。

```python
import torch
from experiments.trainable_pbit_attention import WinnerHoldAttention

sampler = WinnerHoldAttention(samples=64, burn_in=16)
scores = torch.randn(8, 128, requires_grad=True)  # 实际使用时来自QK/√d
v = torch.randn(8, 128, 32, requires_grad=True)
rng = torch.Generator(device=scores.device).manual_seed(73)
result = sampler(scores, v, generator=rng)
loss_per_row = result.output.square().mean(-1)
result.objective(loss_per_row, baseline=0.0).mean().backward()
# scores.grad和v.grad都有训练路径；单独loss.backward()不会训练离散地址选择。
```

换成 `CorrectedRejectionAttention(samples=64)` 即可用同样接口。默认64只是接口参数，**不是质量最优或已验收的采样预算**。

LLM中scores通常为 `[B,H,Q,N]`，V为 `[B,H,N,D]`，传入 `v.unsqueeze(-3)`；mask显式广播并使用True表示有效位置。GQA需由调用者明确展开/映射头，不能错误广播。若最终损失是 `[B]` 的序列损失，应将本次计算图中所有相关层/头/query的 `score_log_prob` 相加成 `[B]`，再调用 `score_function_loss(sequence_loss, joint_log_prob, baseline)`。不能逐query乱配全局损失，也不能把每层贡献平均掉。基线必须来自输入/历史或独立估计，不用当前样本自己的损失直接作基线。

另有两个显式选项：

- `none`：只有抽样V路径的普通反向，不给Q/K提供采样梯度，适合评估。
- `softmax_surrogate`：前向值仍是真采样，Q/K反向采用准确Softmax×停止梯度的V作为**有偏代理**；V梯度仍来自实际抽样次数。它会额外计算稠密Softmax，不能拿训练开销声称硬件节能，也不等于有限赢家链/量化分布的真实梯度。

## 8位与概率量化

两种量化独立设置，默认均关闭：

1. `drive_step=0.125`：sigmoid输入按步长舍入，幅值code限0..255，再恢复驱动值。这对应旧数值驱动量化，不等于概率本身8位。
2. `probability_bits=8`：阈值q=round(256×sigmoid(drive))，范围0..256；R为0..255均匀整数，用 `R<q` 输出bit。q=256需要满幅表示，不能截成255。

量化会改变采样分布和连续参数梯度；因此开启任一种时，禁止声称精确score-function梯度，必须显式选`none`或有偏`softmax_surrogate`。校正拒绝此时仍执行全零校正，但不再保证精确Softmax。没有将这一模块的R8结果继承为已测模型PPL。

## 随机活动、数值和边界

`stats`按输入行返回真实活动：完整更新/提议、有效p-bit次数、保持/切换、碰撞、零拒绝、参考接受、公平bit需求和接受数等。已完成行停止提议，padding和参考不虚算p-bit。`record_trace=True`保留规则检查轨迹；训练/大规模评估默认关闭。公平bit统计是算法实际需要的有效位，不等于Torch底层PRNG耗电或物理时钟数。

BF16/FP16 scores的sigmoid和对数概率用FP32；FP64输入保留FP64。V求均值用FP32（V为FP64则FP64），结果返回V类型。随机训练保留每次提议的计算图，会随候选数和提议数增长；本版是正确性/训练研究参考，未做CUDA融合、图重算或大模型内存优化。不自动生成因果mask，不跨forward保留赢家/m，不把这些算法当成原逐节点Gibbs电路。

## 本地验证与结果

从仓库根运行（已有torch、numpy）：

```text
python -m experiments.trainable_pbit_attention.demo_train --output experiments/trainable_pbit_attention/results/TRAINING_SMOKE.json
python -m experiments.trainable_pbit_attention.validate
```

检查包含规则轨迹、独立小状态穷举、有限赢家链分布、详细平衡、校正拒绝各m的接受定律、拒绝轨迹及有限目标梯度、三seed历史NumPy分布对照、掩码/批处理/提前结束/cap、seed重放、BF16接口、量化端点、默认不调用Softmax和小训练。验收数值与源SHA见 `results/VALIDATION.json`、完整测试名见 `results/UNITTEST.txt`。

小训练仅有3个地址、V=[−1,0,1]、目标1；两个方法各3seed、100步，实际随机输出均方损失降低。它验证训练路径可用，**没有启动Qwen/Llama训练，也没有新增PPL、CUDA、器件或RTL/PPA结果**。沿用旧模型数据和权重的字段在本次合成测试中不适用。
