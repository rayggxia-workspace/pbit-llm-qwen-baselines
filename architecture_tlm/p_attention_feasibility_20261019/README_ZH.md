# 可训练能量采样 p-attention：可行性与实验设计

2026-10-19；负责人amlink1219；接续[Issue61](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/61)/[PR63](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/63)。这是调研、源码核查和待执行设计，没有新模型实现、训练、PPL、GPU作业或PPA。与Issue50/59现有执行快照不冲突，不重复提交其作业。

## 1 结论与当前项目的准确位置

**能量函数直接采样在数学上成立；项目现有Ising路径已做到不显式计算Softmax。真正值得训练的新部分，是更便宜的条件能量生成器和有限时间采样器，而非仅把Softmax改名为能量。**

标准Attention对位置j分配权重，不是对V的数值本身分配概率：

\[
s_j=q^Tk_j/\sqrt d,\quad p_T(j)=e^{s_j}/\sum_i e^{s_i},\quad y_T=\sum_jp_T(j)V_j.
\]

令类别能量 `E(j)=-s_j`、逆温度为1，则Gibbs分布本来就等于Softmax。若器件可采到该平衡分布，可直接输出索引j，均值 `mean(V[j])` 估计Attention，无须数字实现exp、行求和及归一化。这里的指数只定义数学分布；物理实现不必另算该公式。但生成/加载能量、局部场、互斥、建立与读出都有成本，有限时间观测也未必服从平衡分布。

三种研究层级不能混称：

| 层级 | 改动 | 当前证据/新工作 |
|---|---|---|
| P0 原分布直接采样 | E=-准确候选QK | 当前行为CTMC已实现；仍待物理误差与PPA闭环 |
| P1 学习能量与短链 | 低维/低位Eθ＋有限时间训练 | 本次优先；改变分布以换低成本，需要蒸馏与完整质量验证 |
| P2 新型p-attention | 独立/稀疏耦合mask，或学习树/二进制能量 | 有论文依据但结构变化大，独立列线，不与P1混算收益 |

## 2 当前Ising实际如何工作

实时核查PR52仍开放、未合并，head固定为 `e3c5e957c3769b5fc6867b42a52facace647a83b`。其Attention冻结源为 `11f1d6eea2776e201f2021081f8b0fbae2cc455e`。详见[REPOSITORY_AUDIT.json](../../work/amlink1219/61/p_attention/REPOSITORY_AUDIT.json)。

- [ctmc.py L102](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/e3c5e957c3769b5fc6867b42a52facace647a83b/experiments/qwen_joint_stratified_attention_20261019/upstream_attention/ctmc.py#L102)选择最大score作为参考r，其余类birth=`sigmoid(s_i-s_r)`、death=`1-birth`，空态代表r，硬互斥保证最多一bit有效。参考最大值是数值/状态选择，非Softmax。
- 合法态的比值满足 `π_i/π_r=birth/death=exp(s_i-s_r)`，因此平衡分布是候选Softmax。事件压缩里的`torch.multinomial`按出生率选择下一事件，配合等待时间还原占据过程，不是Softmax IID。
- [attention.py L243](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/e3c5e957c3769b5fc6867b42a52facace647a83b/experiments/qwen_joint_stratified_attention_20261019/upstream_attention/attention.py#L243)仍先读取全部候选K并准确计算候选QK，再采索引并gather V。只有准确控制组计算候选Softmax/PV。
- 当前初态为最大score类；观测时刻为 `burn+spacing*k, k=1..S`，默认16/4。单位是单site单位率Poisson时钟的无量纲时间，不是硬件拍、纳秒或独立样本数。S不是ESS；必须分别记录转移数、观测时间及相关性。
- 多token prefill仍原SDPA，仅单token decode替换；QKV、RoPE、GQA、KV及输出投影保留。有限抑制、反馈延迟、器件偏差和驱动量化尚未成为该PPL链的物理实证。
- TLM `ising_macro_v4.py`的Softmax IID是地址oracle，与以上真实CTMC不同；500ns/2000ns/100ns等是未标定情景，不能直接对齐CTMC时间或继承为芯片结果。

所以P0无需训练便有数学成立性。训练应针对P1/P2的表达误差、短链偏差和样本方差；不能宣称现有路径还多付了一套数字Softmax而把它再次扣除。

## 3 文献支持和证据强度

| 一手来源 | 实际证据 | 对本项目的限制 |
|---|---|---|
| [Boltzmann Attention, 2606.12478v1](https://arxiv.org/html/2606.12478v1) | 直接训练Ising场与位置间耦合，使用归一化自旋边缘构造Attention | 主实验单层d64/单head、TinyShakespeare100K字符、上下文≤14，括号≤16，主要精确枚举；短序列DQA/Trotter数值模拟不等于p-bit芯片或LLM完整PPL |
| [Sigmoid Self-Attention, 2409.04431v2](https://arxiv.org/html/2409.04431v2#S5.SS5) | 逐元素sigmoid替代行Softmax，确定性1B/7B语言模型训练；4K上下文稳定性需额外处理 | ALiBi/相应训练配方，不是Qwen/RoPE checkpoint转换；确定性sigmoid不等于有限Bernoulli采样。数字H100核提速不等于p-bit功耗收益 |
| [LoLCATs, 2410.10254](https://arxiv.org/abs/2410.10254) | 用Attention输出MSE迁移，再做低秩适配恢复语言模型；大模型已有实证 | 是线性Attention而非能量/p-bit，借鉴训练步骤，不能继承质量或加速数值 |
| [Barker proposal, DOI10.1111/rssb.12482](https://pmc.ncbi.nlm.nih.gov/articles/PMC9303935/) | 文中回顾Barker接受率t/(1+t)及详细平衡，说明能差logistic可组成合法MCMC | 本报告仅借用接受率原理，不把论文的梯度型proposal当现有CTMC；有限时间混合需另测 |
| [Hopfield Langevin Attention, 2603.06875](https://arxiv.org/abs/2603.06875) | 能量/随机动力学解释Attention | 其算法每步仍调用Attention/Softmax，不能因能量命名就当省Softmax先例 |
| [Extropic Z1T官方](https://extropic.ai/writing/z1t/) | 支持训练结构与概率硬件协同设计 | GCA是tanh(Q)与N/D组合，仍含exp(K)、位置指数、除法及FPGA；不是本方案单索引能量采样，公开扩展曲线未含激活量化 |

Boltzmann Attention是直接先例，但不能说该方向从未有人做，也不能说已有大模型硬件证明。其softmax跨位置导数相关表述不用于本报告论证：归一化Softmax已有 `∂p_j/∂s_k=-p_j*p_k (j≠k)`。

## 4 推荐的P1结构与训练

推荐结构：**蒸馏块筛选器 → 低成本条件能量 → 现有类别CTMC → 被选V累加 → 输出投影**。首先保留原BF16 FFN和准确Attention接口，后续才组合固定W8/B4T32/K32 FFN。

最小条件能量候选为 `Eθ(j|q,K)=-scoreθ(q,k_j)`。从准确score开始，依次试逐层/头温度、8/6/4bit场量化、较小维度的低秩点积、少量Q/K适配。低秩在RoPE之前还是之后必须固定；首轮建议在原RoPE后的q/k上增加低维投影，保留原接口，并将动态k特征增量计算、缓存和GQA复用成本单列。它可能只是增加旁路而非删掉原QKV；不能自动把投影参数/MAC削减记入收益。

若仍先算全部准确候选QK再套一个小网络，只减少分数格式/采样难度，不减少QK计算及K读数。要省K搬运，必须由筛选器减少候选，或从实际更便宜、可增量维护的压缩K/块摘要生成能量，且验证原K是否真的无需读取。

训练分四步，逐项分离误差：

1. **筛选器单独蒸馏。** 完整准确教师提供块概率质量；先固定8个64-token块，再试6/4。报告相对完整教师的漏失质量 `1-sum_{j∈C}pT(j)`，不能只在已选候选内评估。
2. **能量表达。** 固定同一C和准确V，定义候选内教师 `pT,C(j)=pT(j)/sum_{i∈C}pT(i)`、`yT,C=sum_{j∈C}pT,C(j)*V_j`。用候选内分布蒸馏与 `||yθ-yT,C||²` 隔离能量表达误差；另列yT,C对完整yT的筛选误差，以及学生对完整yT的总误差，端到端阶段可蒸馏完整教师。准确归一化/理想IID只用作训练或诊断参考，允许训练时算Softmax。教师AV可即时由准确Attention计算，分布标签按层/头/查询抽样，不落盘全部N²权重。确定性均值与采样分开。
3. **有限链训练。** 使用真实部署初态、预热、观测间隔、温度、场量化、随机相关和有限反馈前向，再做输出蒸馏＋logit KD/CE。平滑代理/STE有偏，明确标注；不能将理想独立采样训练叫CTMC感知训练。验证未见seed、冷启/暖启和预算变化，防止只适配一个reset或观测计划。
4. **组合与端到端适配。** 联合少量Q/K/O适配、筛选器与能量生成器；原FFN下完成Attention-only，再接当前B4T32联合参考。公平数字继续训练对照使用相同训练数据/token/teacher资源。

只拟合E=-score没有新增表示优势，但低复杂度Eθ可能以适当质量偏差换更低硬件成本。输出重建应直接优化最后用到的AV，而非强求每个教师概率完全复刻。更尖锐的能量未必更快混合，可能增加滞留；不把熵降低等同样本数降低。

附加可检验诊断：对称proposal下，类别j→k接受率 `σ(E(j)-E(k))`满足详细平衡，无需显式配分函数。但这是另一种链，不是当前CTMC。非对称proposal必须加入正反proposal比；用学习筛选分布提案后直接忽略该项会改目标。该路线不作为本轮默认实现，以免同时改变链与能量。

## 5 P2：更原生的p-attention及限制

**独立sigmoid mask**更贴近p-bit输出：`b_j~Bernoulli(σ(scoreθ_j+bias))`，使用 `yhat=mean_t(sum_j b_j(t)*V_j)`。其均值是未归一的sigmoid Attention，不是类别Softmax；加上可学习增益/HybridNorm需单列成本。若预期每轮约一个位置激活，均匀稀疏情形全零概率接近e^-1，单轮约36.8%，不能由确定性7B结果直接判断单bit可用。除以当轮激活数会变为随机比值，需定义全零处理并独立训练/验收。所有场仍需要生成；V稀疏不自动省K。

**可训练稀疏耦合mask**可用 `E(b|q,K)=-hθ·b-sum Jθ_jk*b_j*b_k`，表达多个位置协同，但允许multi-on后输出契约及归一化改变，可能增加V读出和混合成本。优先固定低度局部/块耦合，不先构造C²稠密动态耦合。

若要求严格one-hot，0/1指示变量满足 `b_j*b_k=0 (j≠k)`，该二次项不增加合法类别分布的表达能力。换成±1自旋约定后，受约束二次项可归并为常数/有效单体场，仍无新的合法单选协同自由度；它仍可能改变非法态/转移障碍。Boltzmann Attention的多激活自旋模型不能直接贴到当前单索引路径。

**紧凑binary/学习树**可减少状态bit，但不是免费精确编码。512类需要9个binary bit；纯二次能量只有46个含常数系数，而任意类别分布有511自由度。一般需要隐变量、高阶项、查表或受限分布。树形精确Softmax分支依赖子树配分和；学习局部分支可以省去精确计算，但已是新近似，动态KV插入、摘要与路径控制都要计费。

## 6 可执行实验矩阵和验收

结构化计划见[PLAN.json](PLAN.json)。所有数值都是待试预算，非已完成结果：

- 保留原BF16；既有max4/8块＋准确能量＋CTMC作冻结参考，不重跑同事仍在收集的基线作业。
- 候选C=256/384/512，对应4/6/8块；64仅作微基准。与无筛选准确Attention及同候选准确PV分别匹配。
- 先能量mean/IID诊断，后有限CTMC；观测S=32/64/128/256，512作高预算参考。预热16、间隔4为原控制；逐一试预热0/4、间隔1/2，使用适当query子集，胜出后完整PPL，不做所有轴的盲目笛卡尔积。
- 先4M-token转换pilot，32M训练筛选，胜出后128M确认；这是拟议预算。训练/校准/validation/WT2 test隔离，数据revision、SHA与分词器固定。至少3训练seed、3部署RNG seed，含独立未见seed和不同上下文。
- 完整WT2 window2048/stride1024；计分必须实际执行所有被替换层的部署路径。当前仅decode替换时，使用已验证cached评分，不以多token准确SDPA的分数冒充p-attention。另测ARC-Easy/HellaSwag及较长上下文，禁止用短后缀代替完整PPL。
- 质量指标：漏失教师质量、能量表达误差、AV误差、logits、完整PPL/任务准确率、种子方差；链指标：初始化偏差、非法态、转移/等待时间、相关性及输出相关的ESS，S不替代ESS，去相关间隔不保证无偏。
- 数字硬件基线仍为分块在线Softmax＋GQA复用的完整Attention；另设相同低维/低位打分＋数字Softmax、数字sigmoid＋PRNG、准确/学习能量＋相同读出。把训练带来的打分简化同样提供给数字对照，避免全归功于物理采样。
- PPA边界包含压缩K/摘要构建和更新、能量生成/加载、max/ref、随机源及分发、物理驱动/校准、互斥与反馈、建立/预热/观测、地址编码、V访问并集/累加、QKV/O、GQA组并集、SRAM/DRAM突发与格式转换。候选数、唯一访问与实际字节分开，不用MAC比例直接当能量比例。

尚未约定可接受质量退化阈值，因此输出质量—成本曲线，不自定通过线。只有较少候选/转移/观测在公平数字对照下仍降低完整成本，才算优势。若仅高预算成立或混合/配置成本吞没收益，应报告负结果。更改函数和训练本身不构成硬件优势。

## 7 交付和未完成项

本次没有实现能量学生、训练、完整PPL或物理PPA；数学检查仅验证详细平衡、有限时间偏差、编码表达及mask契约。PR52/62为同事任务，本报告只读并明确状态。恢复时先核对Issue/PR及交接，再单独确定执行环境、数据版本和allocation；不要自动重交旧作业。
