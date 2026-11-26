# T64：S/S2一位尺度选择的完整任务扩展

Issue225 / PR266，负责人rayggxia。接续已完成的S/S2八窗PPL，补完整PIQA validation1838题与ARC-Challenge test1172题；单部署seed101。四配置为x原四档/动态64共享 × GU16/Wd32、GU64/Wd128，共8完整任务组、100个128题以内分片。不新增训练，不改变准确SDPA Attention。

## 编码与原理

g/u各连续64项取覆盖最大绝对值的最小二次幂基准S，沿用指数下限2^-6及g256/u512上限。每元素一位选择：|v|≤S/2且指数下限允许时使用S/2，否则使用S；P8码、满幅256旁路、独立符号、真实幅度sigmoid LUT和联合分层AND直连Wd均保持。数值编码直接复用已执行90b7742a的half.py，不重写算法。

S/S2与S/S4同时改变小档及门限。对S/4<|v|≤S/2的值，S2概率翻倍、恢复尺度减半；对|v|≤S/4的值，S4分辨率更高。IID单流估计器的Var=|v|(L-|v|)/T说明这个取舍：|v|=3S/8时，使用L=S/2的方差为L=S时的1/5。该公式是解释用的IID参考，实际分层/三路联合方差及PPL由封存实验确定。不能断言S2对所有分布更优。

## 验证与执行

- CPU Slurm：原14项编码/整数测试，加4项case/grid/完整题覆盖/解析取舍测试。
- GPU Gate：重新完整BF16 WT2；模型/数据/官方harness身份与旧S4一致；BF16官方HFLM逐分数一致；四配置S4包装器logits逐位一致、S2重复一致；各case/任务前两题的旧S4逐答案分数和请求ledger逐位重放，然后验证S2。
- 两个GPU Slurm worker只执行100个新S2分片，复用只读模型和数据；旧S4不重跑全任务。所有输入、源码和执行快照SHA冻结，采样key与旧任务完全一致。
- 收集器核对原字节SHA、逐题分数、36层覆盖及配对ledger，只有8组全齐才报告全部完成。原始旧S4结果不可标为S2。

主入口runner.py --settings SETTINGS --phase cpu/gate/worker；collect.py ROOT。提交回执和准确路径见work/rayggxia/225/onebit_half_tasks_20261126/HANDOFF.md。当前源码准备不代表任务已提交或完成，以SUBMISSION及sealed结果为准。
