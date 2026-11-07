# T64分层32 FFN＋当前概率Attention：匹配快速PPL结果

七项全部完成，原件封存SHA、同一目标位置、同权重及36层计分覆盖均通过。这是**1024个WT2后缀目标的快速评测**，不是完整WT2。

|配置|后缀PPL|相对同轮原BF16|
|---|---:|---:|
|原BF16父模型|13.580351|参考|
|T64训练权重，分层T32 FFN|13.372338 ± 0.224580|-1.53%|
|上述FFN＋概率Attention|14.297115 ± 0.520343|+5.28%|

±是三个部署seed的样本标准差，不是多训练seed或文本抽样置信区间。联合相对FFN-only增加0.924776 PPL（+6.92%）。这是当前小样本中的Attention附加代价，完整WT2仍需另外确认。

FFN采用实际T64训练100M checkpoint及匹配non_ffn、冻结四档尺度、W8；部署GU分层32、后级g/sigmoid/u联合4×2×4，共32次AND，事件直接进入Wd。上轮全模型训练更新了non_ffn，但Attention当时准确计算，本次没有概率Attention适配训练。

Attention：SparQ r32/k128/recent32、无mean-V补偿；signed12/F4 RNE饱和分数→max与差→饱和U8/F4 LUT地址→floor-P8 sigmoid阈值→独立R8比较。赢家保持初始slot0/burn0/S64，实际选择V并累加，重复地址重复计入。各候选IID R8；没有冒充GF64位真。筛选沿既有FP32行为，不宣称整Attention硬件位真。

原文不套聊天模板。八段各128目标、固定linspace位置、三个部署seed101/102/103；准确Attention前缀逐样本生成KV再拼batch，计分阶段每token都走36层单query路径。FFN在前缀和计分均替换。原BF16是未改动父模型，不是100M继续训练数字控制。

|seed|FFN-only|联合|
|---:|---:|---:|
|101|13.567467|13.798633|
|102|13.422692|14.836862|
|103|13.126856|14.255849|

旧Issue204完整WT2分层T32 PPL10.6981±0.00993与这里的目标位置/调用协议不同，不能直接相减。16目标接入门禁不作质量结论。CPU4641六项、GPU4642 P8字节帧独立oracle、32token前缀包装等价及权重不变通过；cached Attention dispatch继承已验Issue198源码。正式Slurm4643，没有新训练、PPA或GPU时间当ASIC时间的结论。

RESULTS.json包含模型export/non_ffn及36FFN文件SHA、目标位置SHA、原件小索引与每seed量化统计。执行源码21文件同本地SHA，包56df7b93d4f4fa4296f1dc3c052b93194082f1667dc60967dab439ba580a2521，gate a50b3f090d5d307079baa6906ba5101968ea626ada75202ddc048408aed30b2a。所有计分层每层1024目标，联合每层32768个Q头采样查询；三seed完整，未将部分结果当最终。
