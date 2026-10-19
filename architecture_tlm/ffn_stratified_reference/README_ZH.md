# 后续FFN仿真的分层采样参考

用户2026-10-19要求后续本人的仿真采用已验证的分层FFN。负责人amlink1219，接续Issue33；正式配置为[reference.json](reference.json)，复用入口为[reference.py](reference.py)。默认 **B4/T32/K32**；B2/T32/K32为尺度简化对照，B4/T16/K16为更短流对照，B4/T64/K64为较低误差对照。原BF16 FFN始终保留为匹配对照。

本次采用的是PR47已合并的行为模型，不改原模型基线、旧实验、TLM时序/能量默认。源码来自`db27fa3d7ed8eced13513f0cad10061a3cc59a71`，发布head `5518a0a23e2bfec2b428542a9e4ce94b27c78d4a`，合并`bef83e54b9da0081c51f393044d2156ce11a34b9`；四个运行核心文件的Git原字节SHA-256锁在配置中。

## 分层的含义

分层对象是8位随机门限范围0..255。划成K个等宽区间，每个区间随机取T/K个门限；不同区间、token及64通道组的随机偏移独立。每组64路、不同幅度档共享同一门限。K1是自然IID；K大于1是受控随机分层，不能标成自然IID。

T32/K32时，每个区间宽8，每区间抽一次，可写为`R_k=8k+U_k`，k=0..31，U_k为独立均匀3位随机数。对于幅度码q/256，一帧计数等价于`floor(q/8)+Bernoulli((q mod8)/8)`；同组且边界落在同一区间的通道共享同一层内随机偏移，不同余数阈值形成嵌套相关事件。因此仿真必须复用精确联合计数，不能将每通道改为独立Binomial或高斯近似。

这不是对Transformer网络层分配不同采样数，也不是把Ising链隔几个时刻取样。FFN概率在每次投影帧内固定，准确线性归约后可以压缩时间展开；Ising有状态转移和有限预热，继续使用其独立burn/spacing/S配置。

## B、T、K及三个投影

- B为输入幅度尺度档数，不是权重/激活位宽。每token的64通道组先取S=ceilPow2(absmax)，B4尺度为S、S/4、S/16、S/64；每元素选能容纳自己的最小档，保留原通道位置。B2仅S和S/4。
- 权重保持历史64×64 tile对称INT8，一次量化后不再随机化或概率重编码。tile权重尺度为absmax/127，不保证是二次幂。
- 激活是A8幅度q/256、独立符号、档号及满幅旁路；q255表示255/256，概率1单独走恒1旁路。不能混称总共8位的有符号整数。
- gate/up共享同一次x采样和输入计数；恢复FP32 g/u后计算连续`SiLU(g)*u`。z再次编码，并用独立随机流采样后执行down；最终输出恢复BF16。
- T32指x阶段32次、z阶段另32次。整FFN还有投影调度、尺度恢复和非线性；不能将它记作整FFN或整token32个硬件周期。FFN流长度T、区间数K与Attention观测数S分别记录。
- 全部24FFN在prefill和decode均替换；FFN-only验证保留原BF16 Attention。联合Attention时独立记录Attention的替换范围与准确prefill。

## 已发布质量证据

FFN-only：同Qwen2.5-0.5B、原BF16 Attention、无训练、WT2 2048/1024完整299077目标。随机项均三个seed，±为总体标准差。

| 配置 | 完整WT2 PPL | 相对原BF16 |
|---|---:|---:|
| 原BF16 | 11.652735 | — |
| B2/T32/K32 | 11.769199 ± 0.001183 | +0.999% |
| **B4/T32/K32** | **11.736131 ± 0.000243** | **+0.716%** |
| B4/T16/K16 | 11.900826 ± 0.003825 | +2.129% |
| B4/T64/K64 | 11.693775 ± 0.001432 | +0.352% |

同B4/T64，IID为13.038027±0.010666，K64分层为11.693775±0.001432。T16/T32没有同T IID对照，不能为其编造同预算改善倍率。完整证据在[qwen原比较报告](../../qwen/results/multiscale_stratified_20261019/COMPARISON_ZH.md)。这些是对现有结果的核查，本次没有重新运行完整模型PPL。

联合PR52当前读取版本`e3c5e957c3769b5fc6867b42a52facace647a83b`，仍Draft未合并。B4T32在固定4096目标后缀上的Attention S32/64/128/256/512/1024分别为12.065755/11.514886/11.197813/11.066594/11.055307/11.006579；同FFN筛选后准确PV为10.970368。该批匹配原BF16后缀为10.371557，不能与上表完整WT2直接相减。

Issue50公开交接记载完整cached 2430/2461仍未收齐，仅完整cached BF16参考11.652118067865489已发布。本任务没有登录其他成员服务器核实作业；恢复时重新查Issue50/PR52。完整联合结论、用户允许的PPL增量及物理PPA均未由本次采用动作验收。

## 后续如何使用

在仓库根、隐藏GPU的CPU环境检查版本及复用接口：

```text
python -B -X utf8 architecture_tlm/ffn_stratified_reference/reference.py --smoke
python -B -X utf8 experiments/qwen_multiscale_stratified_20261019/test_stratified_core.py
```

新FFN数值仿真用显式配置，不沿用原类的`cycles=128,strata=1`默认：

```python
from architecture_tlm.ffn_stratified_reference.reference import build_ffn
# 在新加载的模型上，每层分别传实际layer和本次seed。
model.model.layers[i].mlp = build_ffn(
    model.model.layers[i].mlp, name='b4_t32', seed=seed, layer=i)
```

原FFN对照保持原Qwen2MLP，不调用此工厂。联合评测复用PR52已审计的双路径runner及Guard，并锁定其准确head；不能直接替换FFN后继续使用Issue48只接受原Qwen2MLP的Guard，也不能放宽Guard绕过核验。每case使用新加载模型，独立FFN/selector/Ising随机域，保留实际24层计分调用审计。

PPL运行仍走Slurm和个人目录；先核模型、分词器、文本/token SHA并在实际环境复跑未修改BF16。完整WT2、后缀、prefill/decode和三个seed分别标记。Issue50现有全量确认由原负责人继续，采用此参考不产生重复作业。

## 硬件仿真的边界

后续RTL/TLM至少显式建模：动态absmax与PoT编码、档号/符号/端点、门限区间计数器、独立随机低位及64路分发、W8/尺度存储与读出、跨档恢复/对齐、精确计数与累加位宽、连续SiLU/乘法、x到z重编码、BF16接口、缓存和资源复用。相同T改K不会减少阵列采样拍数；T32也不自动等于整FFN32周期或能量缩小到旧值的固定比例。

还应比较直接随机舍入＋确定性低位矩阵与逐拍展开实现。当前模型以精确联合计数＋FP32归约加速软件仿真，尚无有限位宽/周期精确RTL或真实随机源偏差/相关性的保证；B4T32的PPL不能直接继承给这些新实现。分层使用结构化门限生成，不能作为原生物理p-bit与数字电路已存在优势的证明。
