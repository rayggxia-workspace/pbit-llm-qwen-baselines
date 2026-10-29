# Z1T源码结构、指标口径与本项目可计算项

日期：2026-10-29，北京时间；Issue206质量评估的只读派生补充。没有新GPU/训练/EDA/TLM运行，不改变模型或硬件默认。自己的质量数据使用已封存完整WT2，不混用双随机后缀结果。上游固定提交`8c0f7e66cfea794f70e81fcf289e179d9f58ed0d`。

## 1. components.py实际做什么

|类/阶段|源码运算|与Qwen/硬件的关系|
|---|---|---|
|SparseLinear|每输出保存k个权重及固定输入索引，gather→乘法→求和，加bias|真稀疏存储；不是稠密矩阵乘以mask；索引本身也有存储成本|
|TanhLinear|对Linear/SparseLinear输出执行tanh|概率硬件对应加权输入加非线性的融合目标；公开前向本身仍是浮点函数|
|DyT|gamma*tanh(alpha*x)+beta|不计算跨通道RMS；仍有逐元素缩放/偏置|
|PE|固定正弦位置表加到embedding|不是Qwen的RoPE|
|AFTConv|Q/V各D维，K只有H维；有界指数、因果局部卷积、历史累计和、除法、tanh门控和输出投影|不构造token×token的QK矩阵/Softmax；exp、乘法、除法、累加与残差仍需实现|
|MLP|D→4D→D两投影及可选tanh/SiLU|不是Wg/Wu三分支SwiGLU；主发布配置使用tanh路径|
|Block|x+=Attention(DyT(x));x+=MLP(DyT(x))|保留两次残差、两次DyT|
|Z1T|embedding+位置→blocks→末端DyT→独立稠密clf|clf不与embedding共享，也不包tanh|

配置可选AFT-full、recurrence和conv，不能把同一文件内的所有类都算作发布模型在运行。公开Z1T-0配置选conv、fan-in4、tanh_linear=true、tanh_mlp=true。

`model.py/create_model`会将clf以外的所有线性层包装成TanhLinear；`tanh_mlp`另外将MLP.act设置为tanh。因此这两个开关同时开启时，按实际函数组合：

`MLP(v)=tanh(W2*tanh(tanh(W1*v+b1))+b2)`。

第一投影后的两次tanh没有在源码中合并；Attention的Q/K也会在包装投影后再经过内部tanh。不能将代码简化描述成无条件的“每个矩阵后只有一次tanh”。这是源码结构观察，不断言这种组合错误。

初始化索引/权重会使用随机键，但公开前向没有逐p-bit Gibbs/32样本循环，也未在这些模块中实现4bit量化。训练函数/硬件有限采样评估必须分开。

上游：[components.py](https://github.com/extropic-ai/sparse-transformers/blob/8c0f7e66cfea794f70e81fcf289e179d9f58ed0d/research/z1t/components.py)、[model.py](https://github.com/extropic-ai/sparse-transformers/blob/8c0f7e66cfea794f70e81fcf289e179d9f58ed0d/research/z1t/model.py)、[公开配置](https://huggingface.co/Extropic-AI/Z1T-0/blob/main/config.json)。

## 2. Z1T列出的指标，以及我们能否计算

|指标|Z1T中的用途|我们当前状态|
|---|---|---|
|训练/验证交叉熵|质量及训练曲线|测试CE可由完整PPL原始NLL直接计算；本轮没有训练曲线|
|代码命名bpb的loss/ln2|训练日志的比特化loss|可计算bits/token；真正BPB需按对应UTF8字节数归一|
|参数量/active_params|规模及稀疏性|可按结构精确计算；应另列embedding、head、主体、整数索引和固定buffer|
|训练FLOPs、iso-FLOP曲线、connectivity|规模律及算力预算|需要实际训练日志/多个预算点；不能把既有预训练模型的下载当本项目训练|
|训练tok_per_s、tokens_seen、泛化gap|训练过程|需要对应trainer记录；PPL评测吞吐不能当训练或decode吞吐|
|J/token及按模块拆分|能效|TLM可给条件估计；当前G64/risk4没有全模块同边界校准闭环，不从MAC或PPL推能量|
|延迟/token、decode token/s|性能|需要明确配置的decode/TLM结果；本次滑窗teacher-forcing耗时不当ASIC TPOT|
|采样数、频率、p-bit数、输入/输出链路、GPU MFU|解释硬件配置与能耗倍率|采样64/128已知；物理数量/时延需绑定映射和阵列，不等于软件随机变量数|
|芯片面积/容量及需用芯片数|资源|公开稿未给匹配该模型的完整卡数和系统面积；我们应另报PPA分级，不填零|

上游`train.py`在BPE语料上仍将CE/ln2命名为bpb。严格说这时是bits/token，不能当与Qwen分词器无关的bits/byte。`active_params`把全部浮点叶子相加，还会包含固定PE表；它也不是每token的实际权重读数。上游[训练代码](https://github.com/extropic-ai/sparse-transformers/blob/8c0f7e66cfea794f70e81fcf289e179d9f58ed0d/research/z1t/train.py)、[数据代码](https://github.com/extropic-ai/sparse-transformers/blob/8c0f7e66cfea794f70e81fcf289e179d9f58ed0d/research/z1t/dataset.py)。

公开博客的能耗/时延是4层、D512、k4示例；GFLOPs利用率分情景。32样本估算与未量化激活的质量曲线不可混成完整有限样本验收。公布0.29452µJ/token和58.8µs/token时排除了词表投影；能耗也排除Z1—FPGA数据搬运。公开checkpoint是D12288，不能套该示例。来源：[Z1T说明](https://extropic.ai/writing/z1t/)。

## 3. 我们已经计算的质量指标

同一后训练Qwen3-4B、准确SDPA；G64/B4全部36层FFN/所有前缀替换，GU64、NL128、原e888风险校准四档。完整WT2窗口2048/stride1024，每seed299077个目标；三个seed。用原始NLL/目标数计算CE，不对窗口PPL求平均。

|指标|未改动BF16|G64/B4|
|---|---:|---:|
|三seed PPL算术均值|11.537160|14.883993|
|平均CE，nats/token|2.445573|2.700286|
|平均bits/token|3.528216|3.895689|
|相对PPL变化|基准|+29.0092%|

新增loss为0.254713 nats/token=0.367473 bits/token。三seed平均CE再取exp为14.883985，和PPL算术均值14.883993略有差别，机器JSON分别保存。不同语料/分词器的Z1T loss不能直接放在这张表排名。未新计算BPB或任务准确率。

## 4. 我们已经计算的模型与原始算术规模

根据核实的Qwen3-4B revision1cfa9a7208912126459214e8b04321603b3df60c配置及标准结构计算，不是新权重加载实测。Embedding与lm_head共享权重，只计一次参数，但每次词表投影仍需要相应运算。

|组成|唯一参数个数|
|---|---:|
|36层FFN|2,689,597,440|
|Q/K/V/Wo投影|943,718,400|
|共享embedding/lm_head|388,956,160|
|RMSNorm及Q/K norm|196,096|
|合计|4,022,468,096|

FFN占参数66.8644%。其权重有效载荷BF16为5,379,194,880B，W8为2,689,597,440B（少50%，不含尺度/档号/对齐）；这是逻辑容量，不等于片上SRAM需求或DRAM流量减少50%。

原始稠密decode每生成token、batch1，K含当前token，主要矩阵运算如下：

|组成|K=2048，MAC/token|K=8192，MAC/token|
|---|---:|---:|
|FFN|2,689,597,440|2,689,597,440|
|QKV/Wo投影|943,718,400|943,718,400|
|词表投影|388,956,160|388,956,160|
|QK及PV|603,979,776|2,415,919,104|
|主要MAC合计|4,626,251,776|6,438,191,104|
|按2 FLOPs/MAC等效|9.252504 GFLOPs|12.876382 GFLOPs|

FFN算术占比从2K的58.1377%降到8K的41.7757%。未含Norm/RoPE/Softmax/逐元素SwiGLU/残差/控制/采样/转换。这是原功能主要MAC计数；随机实现改变物理执行方式，不能把这个数直接当实际AND数、周期、TOPS或J/token。

另按Z1T源码与公开配置推导，D12288 checkpoint约1,237,353,706个可学习参数，其中四个主体block共2,162,840；固定PE另外3,145,728个浮点数。源码浮点叶子计数可能得到1,240,499,434，不与学习参数混称。未加载checkpoint逐张量核验，整数索引和其他硬件存储另计。

## 5. 下一步最值得补的同口径指标

1. 质量—能量曲线：每个真实采样配置绑定其PPL与完整TLM动作账本，至少同时报主体及含lm_head两个边界；未标定能量项保持null。
2. 同质量比较：原BF16、成熟数字W8和随机W8使用同模型/文本/协议；不能只对不利用稀疏性的GPU或BF16核比较。
3. 如要与Z1T做质量横比，重新使用同一原文、各自正确分词并报告对齐的bits/byte；同时说明Z1T上下文256与Qwen上下文2048的差别。需另行授权模型运行，本次没有启动。

复核：运行`qwen3/group_shared/derive_z1t_metrics.py`；结果`Z1T_METRICS_DERIVED.json`包含原始汇总SHA与所有算式输出。源码读回SHA/上游提交记录于work/jieruiz/206/Z1T_METRICS_SOURCE.json。GU仍FP32恢复oracle，未新增全链bittrue或芯片结论。Issue206/PR207状态以发布回执为准，本报告本身不意味着已合并。
