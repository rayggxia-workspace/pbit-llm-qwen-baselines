# 完整WT2：T64训练权重分层T32 FFN＋概率Attention

**单seed完整结果：PPL=11.30082805。** 作业4652完成，292窗/299077目标均计分，全部36层每个计分query走采样路径；11原件SHA、代码/driver/配置、语料/token/目标位置、逐窗NLL/PPL重算通过。实际计分4.100小时，另有模型校验/加载；峰值Torch allocated约18.41GiB。没有新训练。

|项目|设置|
|---|---|
|权重|Qwen3-4B后训练revision1cfa9a72的T64训练100M导出，匹配non_ffn及冻结校准|
|FFN|GU分层32、g/sigmoid/u联合4×2×4，共32次AND，事件直入Wd|
|Attention|SparQ r32/k128/recent32，赢家保持S64/burn0/初始slot0|
|数制|signed12/F4 RNE饱和→max与差→饱和U8/F4地址→floor-P8 sigmoid表→独立R8比较|
|协议|完整WT2/window2048/stride1024，raw文本，无chat/thinking模板|
|执行|单seed101，cached batch8；未计分前缀Attention准确、FFN分层T32|

这与昨天8段1024目标、联合三seed后缀PPL14.2971不是同一计分集合，不能用11.3008减14.2971解释改进。完整结果仅一个部署seed，还没有本轮cached同路径FFN-only或原BF16完整对照；不计算训练seed置信区间。

此前同T64训练权重分层T32 FFN-only完整WT2为10.6981±0.00993（vectorized FFN评测），未继续训练BF16父模型约11.54。只能作参考：缓存调用/RNG分组路径不同，不能把差值直接当严格同执行路径的Attention消融；T64训练也更新了non_ffn，因此低于未续训BF16不证明随机替换本身优于同预算数字训练。

SparQ筛选仍是FP32行为参考，采样端遵守上述S12/P8数制；当前未做GF64位真回放或概率Attention适配训练。GPU计分时间不是ASIC/token时延，也不能把另一路C20/T64 TLM能耗直接赋给本轮T32质量结果。

FULL_WT2_RESULT.json保留导出/non_ffn/36FFN SHA、原件与协议身份和量化计数。原件恢复见同Issue work/rayggxia/242/FULL_SINGLE_COLLECTION.json；无需重跑已完成4652。PR243尚未合并，新增结果随同PR同步。
