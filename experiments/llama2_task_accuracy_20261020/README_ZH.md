# Llama 2 7B 代表任务（Issue73）

原始 BF16 与固定权重 B4/T32/K32 FFN、有限 Ising CTMC＋V 选择平均对比。
任务为完整 PIQA validation1838、ARC-E test2376，官方 lm_eval0.4.8 的零样本
模板、pair编码与 process_results；显式不额外添加 BOS，不用聊天模板，不截题。
acc_norm 使用原选项字符长度，不是 token 长度。

每任务13配置：BF16一次；FFN-only三seed；Attention-only S128三seed；联合
S128和S512各三seed。T32属于32区间各一次随机偏移的分层采样，不是自然IID。
共享64路、gate/up共享x抽样、z独立编码、连续FP32 SiLU和g*u、W8归约的数值核
直接复用已合并版本，不训练。不模拟电路周期/功耗。

Llama专属32层适配未修改Qwen守卫。注意力保留原始Q/K/V/RoPE/Wo；原多token
prefill attention保持SDPA，每个答案目标都通过全部32层真实单token decode。
FFN在prefill和decode均替换。候选分支回滚KV及全部抽样状态，按无标签的token
字典序执行，再恢复原选项次序。统计排除dummy，完整计分逐题保存。

这些短题的K少于8×64预算，故本轮显式使用ising_only保留全部K，不借用Qwen
的筛选校准。结果不能证明Llama长上下文QK筛选质量。CTMC为理想硬one-hot有限链，
burn16、spacing4；S是观测数量，不是ESS，也不是物理电路周期。

执行三阶段：CPU Slurm完整32层小模型合同测试＋数据SHA准备；GPU重跑完整WT2
未修改BF16基准（335686目标，2K/stride512，参考4.979502845218782），独立缓存
逐候选评分核验和digital_sdpa相同操作数值等价，真实7B概率路径/显存pilot；
所有门禁通过后才运行正式26项。源快照/输出分离，任何失败保留原快照和日志。

Apple两组现成完整任务结果见 `llama2/results/task_accuracy_20261020/APPLE_BASELINE.json`，
来自Issue65/已合并PR67。它们是独立预训练7B且FP32/full-forward，是跨模型参考，
不能当作Llama上的匹配精度激活替换或p-bit测量。本轮不重复下载其50GB权重。
