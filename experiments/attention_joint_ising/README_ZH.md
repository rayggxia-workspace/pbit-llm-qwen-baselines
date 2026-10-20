# 联合 max4 概率筛选与有限时间 Ising：模型 PPL

负责人 amlink1219；[Issue48](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/48)。本任务复用Issue35的原模型/数据核验入口，PR依赖其分支，不改变旧执行快照。历史核查在Issue33/PR42；完整模块成本对照在Issue37/PR45。

目标路径为 **max4概率筛块 → 候选精确QK → 有限预热/间隔的Ising类别竞争 → 采样索引V gather/均值**。原FFN、QKV/RoPE/cache/Wo和BF16残差保留；全部24层单token decode替换，多token prefill仍调用原SDPA。

## 数值与筛选契约

- 64位置一块，4个16位置子摘要取最大q点积。采用历史WT2-train校准的bias/temperature、当前分数均值/标准差和独立Bernoulli。`moment.pt`的固定Git源与SHA见`calibration_provenance.json`，没有新拟合。
- 主对照采用v4的Bernoulli后配额修复，首块及最近两块计入8块预算；修复按mandatory、原始选中、分数和索引排序。不是把概率筛选替成纯Top-K。
- 8块最多512个有效候选。部分尾块按实际长度计数，padding为负无穷，不允许参与类别抽样。完整KV保留；Q头每7个共享一个KV头。逐Q头候选率不能代替共享KV头的候选并集及物理访存量。
- `ctmc.py`压缩硬one-hot热浴的empty/active驻留时间，从最大logit类别开始，按`burn+spacing*k`观测。出生事件的multinomial不是Softmax目标IID。固定256事件块在同logits、相同sampler起始RNG状态的一次调用内保持各S共享样本前缀；覆盖不足追加，事件上限明确报错。不同S消耗的事件块数可能不同，后续query的sampler RNG位置会分叉，不能宣称整场逐query都共享样本前缀。
- Ising主路径不计算Softmax目标概率；`screen_iid`是单独的数字控制组。采样索引映射到原V地址，FP32均值后恢复BF16。这里是理想强互斥CTMC行为模型，不包含器件偏差、有限反馈延迟或已标定的物理时钟。

## 预注册首轮矩阵

2K初始上下文、原始FFN；128个计分query的实际KV长度为2048..2175，不做滑窗截断。固定8块、burn16、gap4，S=32/64/128/256/512/1024，各seed0/1/2。共34项：原SDPA与手写FP32 full-core数字参考2项；筛选后准确PV三seed3项；联合Ising六档×三seed18项；筛选后IID的S32/128/512×三seed9项；无筛选Ising S512 seed0及变量约30%筛选Ising S512 seed0各1项。

Router与sampler使用独立的逐层随机域，种子不含S/backend。固定batch与步序下控制router的uniform流；S改变会改变后续模型hidden/score，因此候选可以自然改变，不能冻结教师候选冒充模型级评估。不同batch排程不宣称同一逐样本随机轨迹。

手写`digital_exact`使用显式FP32 QK/Softmax/PV，与原BF16 fused SDPA的数值路径不同；质量报告分别列相对两者的变化。`digital_sdpa`使用与原模型相同的BF16 SDPA核心，只用于接入门禁，不能把两类数字控制之间的差异全部归因于筛选或Ising。

## 计分范围

首轮为整模型decode后缀PPL：在完整WT2 token序列上固定32个linspace起点，每段先精确prefill2047个已知token，再用单token decode预测128个目标，共4096计分token。每个目标都须触发24层替换；起点、目标位置、token SHA和逐段NLL保存。不同S使用相同文本、起点和batch。

原BF16参考另按原`baselines/perplexity.py`完整2048/1024滑窗复跑，要求299078源token、299077目标、PPL11.652735047455899。它是环境和数据锚点，不是把后缀结果与全量基线直接相减。

`full`协议提供单独cached计分器，保持原窗口/stride及每个全局目标恰好一次；只在首待计分查询之前做准确prefill，每个计分查询都执行单token替换。其匹配原SDPA也走相同cached排程；不要求逐tokenBF16重排与原整窗计算逐bit一致。原整窗scorer的q_len>1会绕开decode补丁，不能拿它验证候选完整WT2。

完整确认在后缀扫描和耗时门禁后，仅选择至多一个S，必要时再加邻档，配cached原SDPA及候选IID控制；先seed0、边界结果再扩三seed。该选择属测试集探索，不能当独立泛化验收。用户未固定允许的PPL增量，本轮报告质量曲线而不替用户设定通过阈值。

## 执行与证据

`job.py`只在明确Slurm分配、Weican_Chen及其canonical home下运行；CPU阶段隐藏GPU。先不可变源快照/CPU测试与模型数据SHA，再一个GPU preflight：完整原BF16、真实模型短对照、Ising S变化耗时；通过后才提交34项正式sweep。最多一个本人GPU任务，锁内核队列，失败/超时保留已完成结果。

每阶段保存source/config/input SHA、Slurm job/node、环境、registered_cases、case JSON、逐项journal与成果manifest。原参数/缓冲在阶段前后全量SHA一致；所有FFN仍为Qwen2MLP。大模型/语料/原始长产物留本人服务器，Git只放代码、配置、小型汇总和SHA索引。GPU运行耗时不用于声称ASIC延迟或能耗。

本地CPU测试（Torch环境，隐藏GPU）：

```text
python -B -X utf8 -m unittest discover -s experiments/attention_joint_ising -p test_*.py -v
```

运行状态、实际job_id、通过/未通过项以`work/amlink1219/48/HANDOFF.md`和个人STATUS为准，不把代码就绪或作业提交写成实验完成。

## 首轮已执行结果

Slurm2380已完成34/34项；[结果表与范围](../../qwen/results/attention_joint_ising_20261019/RESULTS_ZH.md)、[曲线图](../../qwen/results/attention_joint_ising_20261019/sampling_ppl.png)、[SHA索引](../../qwen/results/attention_joint_ising_20261019/ARTIFACTS.json)。匹配SDPA=10.371557，筛选准确PV三seed=10.895520。这是全部24层decode的4096目标/seed后缀PPL；联合完整WT2确认尚未执行，不能将上方full协议实现或完整BF16锚点当作该确认。
