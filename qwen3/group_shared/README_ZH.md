# 每64元素共享四档尺度：Issue206

依赖PR202@fbd67c39，后训练Qwen/Qwen3-4B。x、g、u按每token的连续64通道分组；四档表来自原TRAIN冻结校准，所有候选均为精确二次幂。不在线估计新的尺度，不跨token共享，不把g/u合并成同一尺度表。现有逐元素选择作为严格回放对照。

六配置：lane、x_max、gu_max、all_max、all_trim1、all_trim4。前三个max变化分别只改x、只改g/u、都改；max选能容纳整组的最小既定档。trim1/4允许每64个值中最多1/4个超出该档，超出值按原码饱和，仍只一个共享档号；这两种是有意裁剪对照，不称无损。

实现用三组阈值超限标志的计数与小阈值比较选择档位，不运行排序或新max尺度生成。max也可用超过阈值的OR归约。比较器/归约/帧等待仍需电路收费，不声称零开销。尺度元数据由每64元素的64个2bit档号变成一个2bit档号，g/u各自一个，Wd同输入组恢复尺度可共用；本次没有实测PPA或更改TLM。

W8与四档实际取值、符号、x的full_one和NL的q<=255规则不变；sigmoid按照g码/符号/共享指数恢复真实signed8场，再P8 LUT，不能用sigma(g/S)。后级仍联合32格T128直接送固定W8Wd。原准确SDPA不改，36层及前缀全部执行替换。

两种GU控制分开：固定W64/K64；输入/权重联合16x16、GU256。权重随机侧仍独立，未研究共享W随机源；GU尺度恢复沿用FP32oracle，不宣称全FFN整数bittrue。Python浮点容器不改变P8比较、端点、整数移位和输出计数规则。

先通过CPU/CUDA验证和32目标pilot，再运行8x128=1024目标后缀（非完整WT2）。每配置三seed，新BF16须13.566049，lane固定/双随机须逐值复现PR202已有三seed。Slurm四片：固定W全部六配置一片；双随机每两配置一片，共40物理/37唯一主计分，另5份pilot独立。

报告每组尺度一致性、档位占比、输入和非线性编码NMSE/裁剪、三流事件密度与零事件比例。新尺度共享可能使小数事件变少；不只看饱和率。SHA、执行回执和恢复交接位于work/jieruiz/206；只按complete/documents记完成，不重交健康作业、不改冻结源码。

## 非线性条件均值诊断（额外独立，不改正式扫描）

在固定W GU64保持采样的前提下，移除非线性AND计数噪声，保留幅度码/真实sigmoid/P8与尺度，使用旧条件均值读出。它不是随机LLM整体期望，也不是有限采样硬件方案；用于判断共享尺度损失主要来自量化还是事件稀疏。六配置各三seed，另3个BF16，共21诊断输出/19唯一；两个新回放/边界测试，执行MEAN_SUBMISSION独立于main的SUBMISSION。原source4d6883b2和Slurm3211不变，不混算主表。

## 固定128拍的细联合分层补测

条件均值对照显示共享g/u编码本身误差小，原4x2x4各4次在共享尺度后事件稀疏。因此另测8x2x8、4x2x16、16x2x4各1次，仍总128拍。固定WGU64、lane/gu_max/all_max各三seed；3BF16+27配置=30份/28唯一。四项新数学/原law回放/整FFN回放与literal独立oracle验证，GRID_SUBMISSION独立，不改原4d扫描。此为额外采样分配消融，不能覆盖旧共享max失败结果，也不把条件均值当部署方案。

## 用户澄清后的完整契约：Wg/Wu/Wd也必须PoT

2026-10-28：x每token连续64通道共享一档；Wg/Wu算出的g/u各连续64通道共享一档，g与u分别选；Wg/Wu/Wd各64x64权重块共享静态二次幂LSB。前两者只从原TRAIN冻结四档选，权重LSB离线确定，不要求所有权重块共用同一指数，也不将权重指数限定为激活四档。

旧4d/be/a1实验权重LSB=absmax/127，并未强制PoT。因此结果保留为legacy权重对照，不能当本澄清方案。新pot_weight.py对原BF16每块重新量化：LSB=ceilPow2(maxabs/127)，q=RNE(W/LSB)限制[-127,127]。Wd恢复系数严格用PoT对齐，16位容器存2的幂；指数跨度超过15则明确失败，不静默舍入。代码中的整数乘系数是移位的功能参考。

新pot_run四片：各BF16、PoT W8-only精确SiLU控制、各一种lane/x_max/gu_max/all_max的finiteNL128三seed与条件NL均值三seed；片0另有legacy W8-only控制。33物理/27唯一计分。固定W GU64、准确SDPA、sigmoid真实g signed8/P8、四档与NL joint32不变；不训练。权重量化精确SiLU、条件均值均是诊断，不能宣称为电路。GU恢复仍FP32 oracle，尚非全链路bittrue。本轮无RTL/PT或TLM默认改变。

## sigmoid独立读取正常g（用户2026-10-28确认）

新independent_gate.py：sigmoid从Wg累加恢复的g直接RNE到原signed8 field（步长1/8、饱和[-128,127]），再查既有P8 LUT；不经过g幅度编码的裁剪/尺度，也不调用浮点sigmoid。g/u幅度各连续64共享四档PoT，分别允许0或1/4项超出所选尺度，选最小可用档。所有元素仍参与乘积，不是丢弃异常值。

gate_run五规则max、g_trim1、u_trim1、both_trim1、both_trim4，各有限NL128三seed及条件NL均值诊断三seed；另旧耦合all_max三seed逐值回放＋每片BF16。共36物理/34唯一，1024后缀目标非完整WT2。x只用groupmax，不裁剪；固定PoT W8、GU64、NL联合32层T128、准确SDPA不变。只复用原冻结四档，尚非专门校准的新尺度表。条件均值仅定位偏差，不能当部署电路。GU恢复仍FP32数值oracle，硬件需由定点累加器作等价移位舍入得到field；本轮无RTL/PT/PPA/TLM变化。

## 面向共享64的TRAIN独立四档校准（2026-10-28）

用户要求重新选择g/u四档。新recal_core/recal_run分别校准各层、各连续64输出组的g/u四个PoT指数。候选为训练拟合组最大幅度指数附近8档，从中选4档，不再固定四倍间隔。dense2为相邻2倍四档；risk4为有限误差拟合；risk4_active另允许选档时忽略sigmoid码严格为0的无贡献通道。g/u表不同，不在线搜索16组合，不排序，不动态生成新尺度；部署仍按最大有效幅度从4档选择最小能容纳的档（最大档不足时饱和）。

校准以BF16 teacher提供正常逐层输入，再实际执行固定PoTW8、x共享、GU64/K64采样，采16个训练512token窗口中每窗16行，共256行/层。前12窗192行拟合、后4窗64行仅报告验证；测试文本/PPL不参与表选择。sigmoid仍原g signed8/P8。目标是Wd列范数加权的逐通道平方偏差+精确joint32NL128方差，明确忽略通道/组间偏差交叉项，不冒称完整Wd输出MSE。两初值、三轮坐标离线选g/u目录；指数范围/四档和结果全部封存。实际GU恢复仍FP32oracle。

计划校准门控成功后，dense2/risk4/risk4_active各三seed有限NL128+条件均值诊断；三片各BF16及旧表正常g一个seed完整控制，共24物理/22唯一1024目标后缀计分，非完整WT2。PoTW8/准确SDPA/x groupmax/GU64/NL128不改，无训练/RTL/PPA/TLM。系数16位精确PoT与signed64归约边界不放宽，失败需保留快照另修。源75blob，测试新8+既有41共49。
