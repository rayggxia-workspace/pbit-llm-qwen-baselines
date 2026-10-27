# 给训练Agent：权重改为冻结64×64二次幂尺度

这是2026-10-27用户对原权重量化的明确修订。旧 `s=maxabs/127` 不是二次幂，旧PPL仅代表带任意tile尺度的W8。新版本必须记录不同weight_format，不覆盖历史结果。

1. 三个FFN矩阵均使用64×64 tile。总位宽b的整数范围为 `-(2**(b-1)-1)..+(2**(b-1)-1)`；符号参与累加，不参与输入幅度概率比较。
2. 加载父模型/warm-start后、创建optimizer前确定每tile整数指数k。首版采用cover-max的ceil-PoT初始化，全零块k=-24，支持k=-126..120；不是每个训练step重算。
3. 训练前向使用固定k，Q=RNE(W/2**k)后饱和；FP32 master及STE反向仍可用于离线训练。gu_weight_exponents和down_weight_exponents保存到模型state/checkpoint，激活检查点重算不得更改它们。
4. 用新权重格式重新校准x/g/u。当前calibrate.py输出的layers中保存weight_exponents；train.py拒绝旧格式校准和旧checkpoint的严格resume。旧模型只能显式warm-start，不能抵扣为新前向训练结果。
5. sigmoid仍必须使用g真实尺度对应的signed8驱动，不能计算sigma(g/scale)后在外部补尺度。非线性有限随机前向、RNG共享、输入/非线性采样预算等保持各自原任务定义不变。不得用本包joint32参考覆盖你们新IID执行快照。
6. Wd公共恢复系数来自二次幂权重步长及二次幂g/u顶档，必须精确表示为移位。当前实现保留16位系数及宽整数累加；若指数跨度超过15，先停止该格式的正式验收并扩展恢复表示，不静默截断。
7. 部署导出调用export_weights(module)，保存最终整数Q及训练期间使用的冻结k。不要只导出BF16权重后重新运行maxabs/127，或重新选k；那会改变部署函数。W9的int16是模拟容器，实际存储计费按所用打包格式说明。
8. 先做小形状校准→两步训练→checkpoint resume→导出后同随机键推理重放；再做当前4B的新BF16参考、未训练PoT权重量化/均值/有限流对照和PPL。没有新的完整WT2不得引用旧PPL宣布精度不变。

本次七组交付参考已验证52项，48通过/4CUDA跳过；完整方案见../seven_case_ffn_20261027/REMOTE_AGENT_PLAN_ZH.md。没有更改远端训练配置/作业，也没有训练后新PPL。需要在持有实际训练器的任务分支中移植、验证、记录源码/模型/配置/数据/校准和导出文件SHA后正式发布。
