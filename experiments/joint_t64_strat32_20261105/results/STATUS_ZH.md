# 联合PPL评测状态

Qwen3-4B，实际T64训练100M权重与匹配non_ffn；部署GU32分层、后级AND4×2×4/32。Attention未做概率化适配训练，SparQ r32/k128/recent32、赢家保持S64/burn0/slot0。

按用户确认的训练数制，候选分数先RNE signed12/F4，求max和差，再饱和U8/F4地址，查floor-P8 sigmoid表，与各候选独立R8比较。不是先signed8饱和，也不是连续精确sigmoid。筛选目前为既有FP32行为，未声称整Attention RTL位真。

CPU4641六项检查通过。GPU4642通过P8真实字节帧与独立赢家状态oracle、原logits无操作包装逐位相同、权重不变、36层覆盖。16目标门禁不是质量评测，不将其PPL作为结论。

正式Slurm4643，七项、最多两GPU；原BF16一次、FFN-only与联合各三部署seed101/102/103。固定8段×128后缀，共1024目标；前缀Attention准确，全部计分token都经过36层目标路径。旧FFN完整WT2 10.698±0.00993为另一个协议，不能直接相减；同预算训练BF16控制7.8958也不混成此处原始父模型。

|配置|seed|后缀PPL|目标数|状态|
|---|---:|---:|---:|---|
|bf16|101|13.580351|1024|封存SHA通过|
|ffn_only|101|13.567467|1024|封存SHA通过|
|ffn_only|102|13.422692|1024|封存SHA通过|
|ffn_only|103|13.126856|1024|封存SHA通过|
|joint|101|13.798633|1024|封存SHA通过|
|joint|102|14.836862|1024|封存SHA通过|
|joint|103|14.255849|1024|封存SHA通过|

仅从status=completed且封存documents逐SHA通过的结果计完成。当前不是完整WT2联合结果；不以部分seed平均冒充三seed。源码包56df7b93d4f4fa4296f1dc3c052b93194082f1667dc60967dab439ba580a2521；gate SHA a50b3f090d5d307079baa6906ba5101968ea626ada75202ddc048408aed30b2a。无训练、无GF64位真回放或PPA主张。
