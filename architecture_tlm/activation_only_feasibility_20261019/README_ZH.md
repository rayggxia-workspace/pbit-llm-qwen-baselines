# 保留Qwen门控结构、只替换p-bit激活：历史核查与可行性

2026-10-19；amlink1219；接续[Issue61](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/61)/[PR63](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/63)。本次是文献、源码审计和实验设计；没有新模型PPL、微调、GPU作业或PPA。

## 1 先固定“只换激活”的含义

Qwen保持三个投影 `g=Wg*x`、`u=Wu*x`、`y=Wd*z`，保留隐藏宽度、残差、归一化、Attention和连续value支路u。首轮不采样输入x，不对g/u幅度另编码，不把两个分支都改成随机bank。

| ID | 中间值z | 相对原模型 | 本地可达历史审计 |
|---|---|---|---|
| O | `u*g*sigmoid(g)` | 原SiLU/SwiGLU | 已有原模型 |
| A | `u*g*mean(b)`，`b~Bernoulli(sigmoid(g))` | 给定g/u时保留原均值，改变实现 | 找到设计提案，未找到该独立模式的执行/PPL |
| B | `u*mean(b)`，`b~Bernoulli(sigmoid(alpha*g+beta))` | sigmoid-GLU；去掉g幅度因子 | 未找到仅该激活采样的执行/PPL |
| C | `u*mean(s)`，`s=±1, E[s]=tanh(alpha*g+beta)` | tanh-GLU；双极门控 | 未找到仅该激活采样的执行/PPL |

A的单次激活输出为g或0；B为0/1，C为±1。逐样本读出时，B/C送入down的是0或±u；先平均门控再down时则为`u*(n/N)`或`u*(2n/N-1)`，n是1或+1状态的次数。两种方式都没有把连续u变成1bit，不能称所有矩阵只接收1bit。首轮alpha/beta每层共享；更细粒度、输出缩放/平移另列成本。

## 2 是否已经做过：相关不等于同一实验

核查21个固定远端refs；分支头涉及437个去重Python blob，进一步检查已获取、可达Git历史的506个Python对象。精确范围、refs和证据见[REPOSITORY_AUDIT.json](../../work/amlink1219/61/activation_only/REPOSITORY_AUDIT.json)。未推送/未提交/他人私人服务器脚本不在范围内，结论不是绝对“从未发生”。

- 旧v10：输入先采样，再对gate/value两支分别采样，以AND/AND-NOT双轨读出。**两支都随机化**，不是保留u连续的A/B/C。
- 多阈值AND-bank：原三投影初始化，gate和value都编码成概率bank，单bit及AND项展开读出。已有20层PPL，**不是只替换一个激活**。
- 两投影P-DNN：整个FFN结构改变，不能用它的多层负结果直接否定A/B/C。
- 历史`StreamingFFN.product_sum/product_only`：同时采样g幅度、sigmoid(g)和u幅度，以三流AND估计乘积。名称“product_only”不代表activation-only。
- 当前B4/T32/K32：采样x恢复g/u后仍执行连续FP32 `SiLU(g)*u`，再编码z。它没有单独采样激活。

现有持续设计文档§27已经明确提出 `G~Bernoulli(sigmoid(g))`、`g*u*G` 这个诊断，标题是“尚未训练”。因此A**曾被讨论，但未找到实现/正式PPL证据**；本研究报告此前A1/A3/A4公式和CPU恒等式校核也不能算模型实验。

这纠正上轮过宽的归类：旧双支门控和AND已经做过；用户本轮限定的单激活替换不能因同含“门控”而被一并视为完成或失败。旧负结果、质量/成本约束继续保留。

## 3 文献支持到哪一步

| 来源 | 与本方案直接相关的证据 | 不能外推的结论 |
|---|---|---|
| [GLU Variants](https://arxiv.org/abs/2002.05202) | 三投影门控允许不同激活，sigmoid-GLU本身有Transformer训练依据 | 不保证现成Qwen切换激活后可保持质量 |
| [Stochastic activations](https://arxiv.org/html/2509.22358v3#S3.SS2) | §3.2尝试按sigmoid概率输出x或0，报告初步表现不好 | 未完整报告多样本均值/蒸馏条件，不能据此证明A所有N都失败 |
| 同文附录F | 三投影门控架构下，确定性tanh的LM1.5B验证NLL2.155，SiLU为2.122 | 是从头训练、非WT2；不是SiLU checkpoint转tanh，更不是有限p-bit实证 |
| [Threshold Gating](https://arxiv.org/html/2607.03148v1) | SiLU/tanh的确定性soft-gate分解及预训练网络代数改写 | 分数不变来自确定性等式；没有证明有限采样无损，硬件集成仍待验证 |
| [Bengio随机梯度](https://arxiv.org/abs/1308.3432)、[ARM](https://arxiv.org/abs/1807.11143) | 提供离散随机节点训练/梯度估计方法 | 不保证24层Qwen的代理梯度或收敛；相关采样不自动满足独立性假设 |
| [LLM-QAT](https://aclanthology.org/2024.findings-acl.26/) | 教师logits蒸馏使模型适应部署算术 | 是量化训练，不能当作本项目p-bit激活已成功 |
| [Extropic Z1T](https://extropic.ai/writing/z1t) | tanh原生结构协同训练的实例 | 多处结构同时修改；其扩展曲线未含激活量化，不是本方案验证 |

因此可行性分两层：**确定性sigmoid/tanh门控能训练，有依据；现成Qwen转换及少量p-bit采样可保持质量，仍需实测。** A均值等价但已有直接负面先例，适合诊断；B/C可能简化门控，但引入函数偏差，先验证确定性版本能否适配。

## 4 为什么保留均值仍可能失败

固定g/u、边际概率校准为sigmoid(g)、时间独立时，A满足：

\[
E[z\mid g,u]=ug\sigma(g),\qquad
\operatorname{Var}(z\mid g,u)=\frac{(ug)^2\sigma(g)(1-\sigma(g))}{N}.
\]

随后还有非线性、Attention、归一化和下一层；局部条件均值相同不代表完整模型logits/NLL/PPL相同。时间相关改变均值估计方差，空间共享产生跨通道协方差，不能直接套独立通道误差公式；未充分建立或器件概率偏差还可能改变均值。大量采样也不是免费收益。

B/C的均值本身改变了原SiLU：单个仿射sigmoid/tanh有界、单调，无法在整个实数域严格复现SiLU的幅度与非单调负半轴。可以通过投影重训练在数据分布上适配；这并不证明不可能，也不能省略转换训练。多个相同概率p-bit主要降低方差，不增加均值函数的表示能力。

训练目标也要区分 `loss(E[z])` 与 `E[loss(z)]`。对A的单bit门控，若p=sigmoid(g)，随机loss还显式依赖g，精确梯度包含两项：

\[
\frac{dE[L(g,b)]}{dg}=E[\partial_g L(g,b)]+E[L(g,b)(b-p)].
\]

首项是连续幅度路径，次项是采样分布项。不能只算gate的score梯度，也不能把连续均值反传称为精确随机梯度。初版允许真实采样前向＋有偏平滑代理反向；用小模块枚举/有限差分检查，并以真实硬件前向最终验收。ARM只作为小模块梯度对照，不能把共享/相关门控强称无偏。

## 5 建议的最小实验

### 5.1 先解耦，不同时改矩阵算术和激活

第一阶段使用原BF16投影、原Attention和原模型接口，只改变激活；先层12，再0/12/23，胜出后全部24层。O、A/B/C的确定性均值和有限采样分别记录，激活样本N=1/4/16/64；需要边界确认才加32/128。

原生BF16 SiLU与显式FP32 `g*sigmoid(g)*u`各有匹配无采样对照。代数等价不保证不同内核/精度逐位相同；相关差异不能记为p-bit采样误差，也不放宽原BF16门禁来掩盖。

第二阶段才接当前固定W8＋B4/T32/K32的投影，保留gate/up共享x与独立z编码。此时g/u本身带相关误差；A仅保证条件激活关系，不保证恢复BF16整FFN。对照保留准确激活的当前SC，以及直接数字低位/随机舍入。

N是**单次FFN调用内、固定g/u时的激活采样次数**，不是完整模型独立运行N次，也不是旧P-DNN完整路径数。可以先平均门控/中间z，再做一次线性down以加速软件；若硬件逐样本累加，两者仅在线性段代数等价，调度和有限精度需另核。

### 5.2 训练阶梯与对照

1. 无训练：记录原SiLU、B/C均值直接替换、A/B/C有限N质量。若B/C函数变化即明显失效，先解决确定性转换。
2. 转换：训练集上按完整FFN输出 `Wd[u*f(g)]` 做局部重建，再做全模型教师logits蒸馏＋CE。alpha/beta、Wdown-only、全FFN权重更新分开；三矩阵的形状保持。
3. 有限采样训练：固定目标N先32M token预选；4M token用于pilot，胜出后128M确认。预算是建议值，没有开始执行。对照同token数字继续训练与只训均值后部署采样，不能给概率路线额外教师资源后宣称全是硬件收益。
4. 至少3训练seed，固定3个推理RNG seed；训练/校准/validation与WT2 test隔离。准确模型、未训练替换、训练后替换分别报告，最终完整WT2 2048/1024、另一未见语料与下游任务。test不用于选N/超参。
5. 优先验证A的采样损失、C的确定性转换与有限采样；B作为sigmoid-GLU对照。共同数据/训练预算下比较，不凭函数名字排序胜负。

本计划不重交Issue50/59已有Attention PPL/任务作业。执行前单独明确数据revision、资源allocation和本人存储；当前仅知道用户有充足H100，没有验证可用集群或提交作业。

## 6 是否值得硬件化

A用原生概率响应替代数字sigmoid，但保留 `u*g` 幅度乘法及三投影；B单样本可选择u/0，C选择±u，减少g的幅度乘法。计数/均值恢复、u保持、驱动/校准、累加和格式转换仍计费。添加可学习输出平移时，还需计算其与u相乘的项，不能当免费偏置。

软件使用sigmoid/tanh定义概率，不意味着原生器件前还要数字计算一次函数；数字比较器/LUT＋PRNG是另一个明确基线。物理p-bit响应所需局部场增益、建立时间、概率偏差与读出带宽必须具备可追溯参数。

面积/能量/延迟至少比较：数字准确SiLU、相同质量的低位LUT/分段近似、数字概率生成＋采样、原生p-bit＋相同读出。包含完整FFN成本；只替换一个非线性即使局部省电，也不自动显著改善整模型。N太大时可能得不偿失。

验收是**相同可接受质量下完整FFN及整模型成本改善**。尚未约定PPL容忍阈值，报告曲线，不自定“通过”。确定性转换失败则不急于加采样；只有大N才可用且完整成本更差则停止；新增器件/分布条件必须重新验证。

## 7 当前交付边界

本次完成公式、文献及可达历史核查；数学检查只验证条件均值、方差、梯度和相关性示例，不是模型PPL。结构化计划见[PLAN.json](PLAN.json)。源码审计、来源索引、Zotero本批摘要和验证见 `work/amlink1219/61/activation_only/`。所有A/B/C模型实现、训练、完整PPL和物理PPA均仍待执行。
