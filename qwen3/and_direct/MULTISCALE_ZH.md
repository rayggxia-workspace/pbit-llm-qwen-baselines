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
