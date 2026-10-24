# g/u固定多档、尺度感知sigmoid、Wd移位归约

接续Issue173/PR174。旧单档执行098c7a00与结果保留，新执行独立冻结。模型仍Qwen3-4B后训练、36层、准确Attention，入口x固定四档W8/A8共享64分层T64。

## 本轮预先确定的扫描

每层每64通道的最大量程S沿用TRAIN校准，不看测试集调整。每个值用比较器选择能容纳其绝对值的最小预设量程；没有在线absmax、没有重排权重。

| 名称 | 预设量程 | 成对指数偏移的不同取值数 |
|---|---|---:|
| B1 | S | 1 |
| B2 | S,S/64 | 3 |
| B4 | S,S/4,S/16,S/64 | 7 |
| B8 | S,S/2,S/4,...,S/128 | 15 |

B8同时增加档位密度及一位低端覆盖，不把差异全部归因于档数。g/u分别选档，码0..255、概率码/256、符号旁带；不新增幅度满一旁路，避免与旧接口同时改变。上端截断边界与旧版一致。

BF16、W8及旧z重编码对照，B1/B2/B4/B8条件均值各3seed；B2/B4/B8在T64/256各3seed，B4/B8另T1024。共45份计分（BF16五重复，共41唯一配置）。8×128目标后缀，不是完整WT2；非训练。

## 非线性不能忽略尺度

g=s_g*q_g*2^(e_g-8)，幅度流概率q_g/256。sigmoid驱动仍是原值g：signed8 field=clip(RNE(s_g*q_g*2^(e_g-5)),-128,127)。整数移位、舍入、饱和后查256项P8+true-one LUT，再与独立8位随机门限比较。不能使用sigma(q_g/256)，也不能在sigma后简单乘回2^e。

物理p-bit对应P(1)=(1+tanh(I))/2时要驱动I=g/2；选档改变的是码到真实驱动值的转换，不能改变sigmoid斜率。此轮模拟LUT+比较器，未模拟物理DAC误差/FSM稳态或自相关，不将它们的随机性自动等同IID。

三流AND概率p=(q_g/256)*(q_u/256)*P8(sigma(g))，真实乘积为sign(g*u)*S_g*S_u*p。幅度流的不同尺度需要指数标签；单独一根0/1线上不包含该标签。

## Wd对齐

设各档相对组最大量程的偏移为k_g、k_u，则乘积量程相对基准S_g0*S_u0为2^(-r)，r=k_g+k_u。相同r的带符号W8部分和先准确归约，再向最小公共单位左移R-r位，最后合并。B4的R=12；B8的R=14。此轮准确并行计数，不引入近似APC/OR误差。

64倍对应6位。若编码概率提高64倍，物理数值恢复要补偿除64；它可表现为较大尺度桶相对较小公共单位左移，而不是机械给放大概率的桶左移6位。两个输入都提高64倍，对应乘积补偿4096倍/12位。

所有局部桶须保留符号与Wd位平面位权，不能混合不同指数后只计一个总数。原Wd tile的16位定点恢复系数也保留：移位只解决g/u二次幂档位，不会自动消除权重量化尺度。最坏界N*T*127*65535*2^R检查不超过signed64；额外保护位带来面积/能量成本，未测PPA。

Python用Binomial精确压缩IID三流事件。加速归约把对齐整数拆成radix256数字，调用有界精确整数点积；逐拍按指数桶输出归约/移位的参考必须逐整数相同。它不要求电路先统计z，也不是把模拟器的数字分解器认定为真实硬件。

## 相关研究及适用边界

1. Zhou等，*Scaled Population Arithmetic for Efficient Stochastic Computing*，ASP-DAC2020：[IBM作者页面](https://research.ibm.com/publications/scaled-population-arithmetic-for-efficient-stochastic-computing)。引入显式缩放并采用并行population表示，说明尺度和小概率精度是已有SC研究问题；不是我们串行三流Qwen实现，也不能继承其能效。
2. Ardakani等，*VLSI Implementation of Deep Neural Network Using Integral Stochastic Computing*：[原文](https://arxiv.org/abs/1509.08972)，§II-C/III/IV。用整数随机流扩展范围，并修改FSM非线性；常规Stanh近似的斜率依赖状态数。其DBN结果不能证明SwiGLU或未经训练Qwen的短流精度。
3. Li等，*Hardware-Driven Nonlinear Activation for Stochastic Computing Based Deep Convolutional Neural Networks*，IJCNN2017：[原文](https://arxiv.org/abs/1703.04135)。使用APC、饱和计数状态及输出历史等机制实现SC激活；不是一个AND门即可得到sigmoid，有限状态/流长/相关性仍须验证。
4. Kani等，*A Design of Fully Stochastic Computing Neurons Focused on the Gain of Sigmoid Functions*，2021：[官方摘要](https://search.ieice.org/bin/summary.php?abst=j&category=D&id=j104-d_7_552&lang=J+&year=2021)。明确研究sigmoid增益与训练。这里只读取公开摘要，全文未访问，不引用其具体电路参数。

因此本轮采用明确的整数幅度/指数→signed8驱动→LUT+比较器，将范围恢复与非线性斜率分开。可借鉴FSM或物理p-bit，但需另行测试它们的响应、有限时间及输入/输出相关性。

## 2026-10-24补充：前级采样核验与直接SiLU状态机

本节为源码复核、数学分析和文献调研，没有新增PPL、训练或RTL/PPA；Slurm2881/2886封存执行与结果不变。远端核验PR174 head=0c94a2d82e028791115b77180852a052497efe87。

### 前级确实是四档、64次，但不是IID

multiscale_run.py的有限AND与mean_B配置均指定matrix_mode=sampled，再调用configure(model,mat,64,seed,xztables,True,True)。configure将cycles=strata=64；MultiScaleFFN.forward先调用_stage(x,'x','gu',rng_input)，之后才编码g/u。BF16和明确标记w8_oracle的对照例外，不混称随机矩阵。

- x：每层每64通道的TRAIN冻结四档S、S/4、S/16、S/64；推理只选档，无在线absmax。
- Wg/Wu/Wd：固定INT8；输入随机，权重不随机。
- x随机字：8位范围0..255分64个区间，每区间独立随机取1个数；每个64通道组共享随机字。T=K=64，不等于64个IID随机字。
- 后级g/sigma(g)/u三流：条件于编码值，分支/通道/拍独立IID；有限AND计数用严格等价Binomial压缩，不是前级分层流。
- 新非线性用了八位幅度/驱动/概率边界；gate/up的恢复与跨tile求和仍为FP32数值参考，未宣称整个FFN已完成有限位宽电路仿真。

前级分层采样的单个固定门限只有一个边界区间不确定，T=K=64时计数相对期望误差小于1次。后级三流AND概率为p=(|g|/Sg)*sigma(g)*(|u|/Su)（忽略量化），IID相对标准差为sqrt((1-p)/(T*p))。因此前级64次可用，不能证明后级64次同样可用。该误差表达式针对单通道事件均值，不直接等于模型PPL。

### 四档是否足够，不能由RMS大小判断

首层0.115725/0.211005/0.178412分别是x/g/u的RMS，不是带符号平均值，也不是所有层的分布结论。相关量是典型幅度相对固定最大量程的占比、离群尾部，以及AND的乘积概率。

对于处于档位覆盖内部的值，四倍间隔通常给出幅度概率(1/4,1]，两倍间隔给出(1/2,1]（当前码最大255/256，端点按量化处理）；低于最小档的值例外。两个幅度概率相乘使档距的影响进一步放大。

可以保持四档，只把最低档扩至S/128，或整体降低最高量程，但前者会扩大某些中间档距，后者增加上端截断。仅用S和S/128会留下更大的中间空档；已测B2=[S,S/64]在T256的PPL为2294.61，说明这一特定两档配置不可用，不代表所有两档都不行。下一轮如扫描，需在TRAIN上选表，分别控制档数、覆盖下界与顶部截断；目前没有新的四档位置扫描结果。

### 文献中确有直接Swish/SiLU随机状态机

新增一手来源：Feng等，*Stochastic Multivariate Universal-Radix Finite-State Machine: a Theoretically and Practically Elegant Nonlinear Function Approximator*（SMURF，ASP-DAC2025；[公开v1全文](https://arxiv.org/html/2405.02356v1)、[会议程序](https://www.aspdac.com/aspdac2025/pdf/final_program.pdf)）。

其FSM由输入比特逐拍更新状态，状态选择预先拟合的输出采样概率；不先统计输入为连续值。§IV-A实际展示tanh及swish近似，报告swish在64/256比特下平均绝对误差0.033/0.010。这是该文函数测试口径，不是Qwen PPL。网络验证为MNIST/LeNet-5，不是LLM。§III还给出多变量结构，但状态组合/输出系数随变量数增长，不能把整个SwiGLU无成本塞进一个小状态机。其硬件数值来自其他函数案例，不能套给我们的SiLU。

传统Stanh/NStanh也可通过sigma(g)=(1+tanh(g/2))/2生成sigmoid流，参见上方Integral SC原文§II-C/III-E/IV；输入编码、状态数与增益必须匹配。当前sign+magnitude流不能无条件当作其bipolar流。IEICE2021的增益设计仅核验公开摘要，未取得全文。

结合SMURF思想，可以研究直接拟合以下单变量概率映射（这是我们的候选设计，不是已实现或已验证结果）：

    p=|g|/Sg，s=sign(g)
    P(B_silu=1)=p * sigmoid(s*Sg*p)
    SiLU(g)≈s*Sg*E[B_silu]

这样B_silu再与独立的Bu做AND即可输入固定W8 Wd；符号与Sg*Su仍通过既定指数/系数路径恢复。函数参数必须感知真实Sg与符号，不能只按相对档编号配置。若只实现g→sigmoid(g)，再把FSM输出与原Bg直接AND，会有输入/输出相关性，不能自动按独立乘积解释。

同一量程下，把两路AND换成一根具有相同IID边缘概率的理想SiLU流，不改变最终事件的IID方差；实际FSM有时间相关性和暂态，可能改善或恶化，必须按真实状态链模拟。后续最小验证应含：输入码/符号/绝对尺度覆盖、状态更新和初始化、32/64/128/256拍偏差及自相关、与u/权重扇出的相关性、跨token重置、最终Wd误差。不能调用理想sigmoid后抽Binomial来冒充FSM，也不能将热身周期和复位成本隐去。比较对象应保留现有小型8位LUT+比较器，不能直接继承论文的大LUT面积倍率。
