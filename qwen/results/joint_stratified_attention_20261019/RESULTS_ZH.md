# 三种短流FFN与筛选＋有限Ising＋V采样：实际联合验证

2026-10-19，Issue50 / [PR52](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/52)，负责人jieruiz。34项主对照及12项准确Softmax诊断已完成，三seed；完整cached WT2的22项补测已提交Slurm2430，尚在运行，未提前写入全量PPL。PR为草稿，未合并。

**目前可以同时替换，未看到明显的误差相互放大；这组实验的主要质量损失来自Attention。** 四档32拍FFN联合S128为11.197813，单独Attention为11.163005；FFN单独为10.427377，原模型同口径10.371557。不能把这些后缀数值与旧完整WT2的11.65直接比较。

## 一眼看结果

全部为相同32段×128目标＝4096目标的后缀PPL，context起始2048、batch8。±为seed0/1/2总体标准差；原模型为确定参考一次。

| FFN方案（全部24层） | 原始Attention | 筛选＋Ising＋V采样 S128 | 同路径 S512 |
|---|---:|---:|---:|
| 原始FFN | 10.371557 | 11.163005 ± 0.007407 | 10.980212 ± 0.001083 |
| 2档 / 32拍 / K32 | 10.476808 ± 0.030525 | 11.232234 ± 0.084453 | 11.066401 ± 0.050922 |
| 4档 / 32拍 / K32 | 10.427377 ± 0.012884 | 11.197813 ± 0.032905 | 11.055307 ± 0.017385 |
| 4档 / 16拍 / K16 | 10.628582 ± 0.044771 | 11.402422 ± 0.047416 | 11.201607 ± 0.034823 |

S128约为本批2K上下文的1/16；S512是四倍预算的保守对照。对四档32拍，联合PPL相对原模型增加约7.97% / 6.59%（按平均NLL比值）；单独Attention约增加7.63% / 5.87%。提高到512次仍有损失。尚不能判断继续增加采样是否足够，需要筛选后准确PV对照进一步区分筛选误差与采样误差。B2/T32与B4/T32的联合差异较小，尤其S512，不能由三seed小样本宣布显著优劣。

## 具体执行了什么

每个被计分token的24层Attention都实际执行：原Q/K/V投影和RoPE → max4块摘要 → 固定train标定的sigmoid/Bernoulli筛块并修补为8块 → 候选准确QK → burn16、spacing4的有限时间硬one-hot CTMC Ising → 输出索引直接gather并平均V → 原O投影/残差。没有先算Softmax再冒称Ising，也不在Ising后额外抽一次PV。

筛选器当前不是耦合Ising退火；它用概率筛选和固定额度修补。CTMC属于理想硬互斥过程的有限时间行为参考，不是器件实测、有限抑制延迟p-bit电路或完整物理Ising网络PPA。

FFN使用相同历史固定INT8权重，A8幅度码、共享64路的分尺度分层随机流；入口和SwiGLU乘积z分别编码，SiLU(g)×u仍为连续FP32，结果回BF16。FFN在prefill和decode均替换。Attention多token prefill保留原SDPA，所有被计分decode查询才走替换；所以不声称所有预填充token也已随机化。未训练或对测试标签拟合。

## FFN与Attention是否互相放大

令L为每token平均负对数似然，逐seed计算 `I=L联合−L仅FFN−L仅Attention+L原始`。I>0表示比单独误差之和更差，不能直接相加PPL。

| FFN | S128的I（nats/token） | S512的I |
|---|---:|---:|
| 2档 / 32拍 / K32 | -0.003938 ± 0.004179 | -0.002284 ± 0.005296 |
| 4档 / 32拍 / K32 | -0.002258 ± 0.003481 | +0.001448 ± 0.002753 |
| 4档 / 16拍 / K16 | -0.003259 ± 0.001015 | -0.004513 ± 0.002492 |

交互项约−0.0045～+0.00145，当前没看到联合后明显额外放大。小负值也不足以证明相互补偿或协同增益；这里的标准差只表示同一固定文本上的采样变化，不是语料置信区间。

## 准确Softmax诊断

相同筛选与候选QK，改为候选准确Softmax＋IID采样128次；Ising完全退出。控制项复用主表的相同FFN单独对照，未重复运行。

| FFN | 准确Softmax＋PV采样128 | 有限Ising128 |
|---|---:|---:|
| 原始FFN | 11.094049 ± 0.022229 | 11.163005 ± 0.007407 |
| 2档 / 32拍 / K32 | 11.212366 ± 0.042075 | 11.232234 ± 0.084453 |
| 4档 / 32拍 / K32 | 11.166155 ± 0.056379 | 11.197813 ± 0.032905 |
| 4档 / 16拍 / K16 | 11.357033 ± 0.015879 | 11.402422 ± 0.047416 |

原FFN下，准确Softmax诊断仍为11.094049；切到有限Ising为11.163005。说明损失不全是Ising混合问题，筛选保留集与有限PV估计本身也要改善。当前没有筛选后准确PV的同协议对照，因此不能把剩余差额全归到筛选；也不能凭相邻重复率单独推断有效样本数或混合充分。

## 候选、执行和计分核验

- 每个结果分别核对Attention和FFN在24层按序执行，4096个目标每层均实际通过；Attention逐层512个decode forward、4个prefill forward。
- 相同模型revision、token SHA、4096个目标位置SHA、batch和窗口顺序；主表34项/诊断12项全部齐全且有限NLL。
- 实际候选QK约为全量22.756%；GQA后K候选并集约44.5%。后者不能用22.756%替代，也不能将这些行为统计直接称为DRAM节能比例。
- Ising相邻输出重复约32.5%～32.9%，未触发event cap/丢弃/IID fallback；last_sampler_stats只代表每层最后一次调用，不拿它累计全运行事件成本。
- Slurm2381准备完成，原BF16完整WT2参考重新复现11.652735047455899（299077目标），只作为环境门禁；38上游＋10联合＋13FFN测试通过，另2完整计划测试通过。
- 原FFN及B4T32下，同BF16 SDPA包装器与原SDPA的计分logits SHA完全一致；之后才运行实际有限Ising。

## 完整WT2确认与运行状态

新执行源 `53dd0ff6a04218dc9f2b692464d5b16da284cf17`，Slurm2429真实显存pilot通过：16×2047和32×1023前缀分别峰值16.23、16.31GiB。Slurm2430已提交22项：BF16×1、三种FFN单独×3seed、原FFN/三种FFN配S128 Attention×3seed。统一cached batch32、window2048/stride1024，292窗口覆盖299077目标且不重不漏。所有计分query仍独立核验24层，不使用会绕过decode补丁的整窗前向。结果未收齐。

首个过大32×2047-prefix显存pilot（Slurm2425）在31.37GiB卡上OOM，未启动完整worker；失败版本及日志保留。实际完整计划不含这个形状：首长窗batch1且无prefill，其余正常前缀1023，所以新pilot覆盖实际形状。没有通过改写已提交快照修复。完整S128为固定预算，上下文逐query变化，不能称为全程固定L/16；cached BF16会另测，与历史向量化11.65不要求逐bit一致。

## 复现与制品位置

主执行 `d61b2861edc91e00495268d39a738edb3599f87f`；上游Attention固定 `11f1d6eea2776e201f2021081f8b0fbae2cc455e`；模型Qwen2.5-0.5B revision `060db6499f32faf8b98477b0a26969ef7d8b9987`。Slurm2382完成34项，2412完成12项；本人目录 `/home/Hongjie_Zeng/projects/pbit-qwen-joint-ffn-attention-20261019-issue50`。原件54项计分（8小pilot、34主项、12诊断）＋10准备文件共64项由ARTIFACT_INDEX逐一索引大小和SHA-256。原moment.pt为公开历史train校准，85,917字节、SHA `fefbb90c4f38c5f7a6d51a672550bd684ffe3a1415d36dc115a8ca5e05c5db0b`，只在服务器运行，不重上传。

仓库文件：SUFFIX_SUMMARY.json、FALLBACK_SUMMARY.json保留每seed/每段NLL与审计；INPUT_IDENTITY.json记录模型/语料/源码版本；ARTIFACT_INDEX.json指向服务器原始文件。完整命令/环境/配置SHA在原件及work/jieruiz/50回执中。可复用的只读收集器与离线统计分别为experiments/qwen_joint_stratified_attention_20261019/collect_results.py及summarize_results.py；接续命令见work/jieruiz/50/HANDOFF.md。种子FFN和Attention分域独立；相同种子也不保证不同logit下CTMC消耗相同轨迹。

本次不提供新的TLM、PT或芯片能效结论。Issue48成员的Attention独立扫描不覆盖；PR47已合并bef83e54，PR52已改为TLM集成分支且仍为草稿、未合并，Projects缺read:project看板待同步。
