# 原始Qwen3-4B W8 dense完整WT2 PPL

Issue259，负责人rayggxia。原始后训练Qwen/Qwen3-4B revision `1cfa9a7208912126459214e8b04321603b3df60c`。

仅36层FFN的Wg/Wu/Wd量化为W8。每64×64块根据原始权重离线选择覆盖最大幅值的最小二次幂LSB，固定尺度，最近偶数舍入，码范围[-127,127]；全零块LSB为2^-24。该数制沿用已有PoT64初始化。量化权重解码到BF16后可逐值精确表示，用于软件评估。

激活、原始SiLU和逐元素乘法、Attention、Norm、残差、embedding及LM head均保持原始BF16路径。Attention使用原生稠密SDPA，没有K筛选或概率采样。本项为W8权重量化质量控制，不是P8激活或硬件逐拍定点运算重放。没有继续训练，也没有借用T64训练后的non-FFN权重。

完整WT2采用既有固定评测器的2048窗/1024步长，292窗、299077个不重复目标，不使用聊天模板；文本和token SHA与历史记录一致。先在同一环境运行完整BF16参考，再原位替换108份FFN权重，运行W8；所有36层逐窗检查覆盖。

执行：`python experiments/w8_dense_original_20261118/ops.py stage`。只允许新建执行；已有SUBMISSION时使用`status`。CPU Slurm前置检查通过后，GPU依赖任务才运行。执行源码/输入/配置被冻结到本人服务器新目录，原有快照不改；`collect`核验封存及逐窗覆盖并归档结果。

已完成：W8 dense original完整WT2 PPL=11.4832106452，同轮BF16=11.5371603731。详细配置及核验见[REPORT_ZH.md](REPORT_ZH.md)，逐文件SHA见RESULTS.json。CPU5896通过，GPU5897正常完成。8.742652是此前T64训练权重的确定性FFN结果，不属于本项original W8 dense。
