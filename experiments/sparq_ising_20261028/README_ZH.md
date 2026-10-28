# SparQ + winner-hold Attention-only PPL（Issue198）

用户2026-10-28授权GPU质量验证。Qwen/Qwen3-4B后训练revision 1cfa9a7208912126459214e8b04321603b3df60c，原BF16 FFN/投影/归一化/RoPE/output head不改，不训练。只替换每个计分预测器的全部36层单query attention；前缀使用原生dense。

固定SparQ论文GQA概率求和：同KV组sum(abs(Q))选r32；各头L1温度和全长度近似softmax；跨头概率求和，强制最近32占总候选128。候选完整维度QK后，直接由winner-hold输出的地址读取V并均值累加，无第二次PV抽样。短缓存不跳过采样，只使用全部可见候选。零覆盖按组回退全K采样；该少见分支成本统计不完整，必须报告次数。

主采样参数：argmax初始化、burn32、spacing1、shift0，S32/128/512与seed0/1/2。每帧所有候选独立sigmoid(logit-max) Bernoulli；旧赢家on或全部off则保持，否则在active集合无偏均匀选新赢家。FP32 sigmoid/Philox行为参考，不是物理p-bit实测、q/256有限精度或ASIC周期。有限链偏置/相关性保留。不同S使用独立按配置/层/call派生的随机键，不能宣称整模型共享采样前缀。

对照：原生BF16 cached SDPA、FP32纯SparQ准确候选softmax/PV、SparQ+winner、SparQ+IID128诊断。BF16 wrapper先要求与同形状原生logits逐字节相同，参数data_ptr/version不变，所有目标全层覆盖。实际GPU时间是Python/Triton数值实验耗时，不作为稀疏硬件速度。

初筛：8个均匀分布位置、context2048、每窗后缀128、共1024目标，batch8；所有方案相同目标，明确不是完整WT2。随后支持完整WT2 window2048/stride1024；每16窗成片配对，batch16，无BOS或chat模板，完整目标1..N-1各一次。不能用初筛选择最优后不披露选择，也不将旧Base或不同FFN结果当因果基线。

复用来源：PR163固定ca3da3a5308cdd820d1d9554b2866b9eb098d5a4，原始qwen3/stochastic/vendor/kernels.py、qwen3/sparq/core.py、qwen3/sparq/adapter.py保存于vendor。新core/adapter在本目录独立实现，未修改PR163。plans/support来自PR202本地已发布源码，执行包逐SHA登记；vendor原件不修改。

执行：CPU Slurm先运行python -m unittest experiments.sparq_ising_20261028.test_core -v；GPU通过python -m experiments.sparq_ising_20261028.run的preflight、short、full阶段。部署助手及准确快照/Slurm回执在work/rayggxia/198，服务器源冻结，结果按源提交另存。无新数字电路仿真run。
