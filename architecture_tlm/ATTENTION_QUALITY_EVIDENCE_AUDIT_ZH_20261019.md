# Attention 历史 PPL 证据核查（2026-10-19）

负责人 amlink1219；Refs #33，关联 #35/#36/#37。用户要求在继续计算前核对“QK概率筛选＋Ising Softmax”的完整模型PPL是否做过。本次只读核查历史分支、原始汇总、协议和执行分支；没有提交新的服务器作业。

## 结论与口径修正

以前确实做过**整模型、全部24层Attention的行为级PPL**。不能把“当前TLM分支没有PPL”写成“从未做过模型级验证”。但下列已核结果的算法、FFN状态和计分范围不同；目前没有找到**max4概率QK筛选→候选QK→有限时间Ising→V累加**同一路的联合PPL记录，也没有找到当前固定8块/512候选、S32/128/512配置的完整WT2质量验收。

“完整模型”说明误差经过完整模型传播；“完整WT2”说明覆盖全部计分目标。二者独立。下列历史Attention报告全部只计分固定WT2后缀：2K为32段×128=4096目标，8K为16段×128=2048目标。原始文本含299078 token，不代表这些替换结果计分了299077目标。prefill/decode也分别注明。

## 已核的模型级结果

| 方案 | FFN/Attention替换范围 | 2K PPL | 8K PPL | 实际含义 |
|---|---|---:|---:|---|
| 原SDPA匹配对照 | 原FFN，原Attention | 10.37356 | 9.41898 | 第一、二项的后缀协议参考；不能和完整WT2的11.652735直接相减 |
| Ising＋V采样，S512、burn16、gap4 | 原FFN；24层decode替换，prefill准确 | 10.43017±0.02268 | 9.46223±0.02126 | 5seed；理想强互斥CTMC，**未同时筛选QK** |
| max4概率筛选、动态阈值、目标30% | 原FFN；24层decode筛选，prefill准确 | 10.77160±0.00797 | 9.40979±0.02632 | 3seed；候选内仍为准确Softmax/PV；实际候选约27.94%/29.53% |
| max4筛选＋S512 IID PV采样 | 随机固定尺度FFN在prefill/decode均启用；24层decode筛选 | 12.976288±0.023460 | 11.238323±0.115898 | 3seed；**准确Softmax＋IID，不是Ising**；候选约27.93%/29.46% |
| 上一行的同FFN、不筛选、准确Attention | 同随机FFN；24层准确Attention | 12.312887±0.059804 | 11.119899±0.156802 | 联合FFN方案自己的匹配参考，不能把全部损失归因Attention |

±为推理seed总体标准差，不是数据集置信区间。小于基线的单个均值不构成能力提升或泛化结论。所有数值属于历史报告，本次未重新运行模型。

## 源码证明

- `experiments/pbit_softmax_router/attention.py:103–115`：准确Softmax用于诊断；`mode=='ising'`和`mode.startswith('block_')`为互斥分支。前者完整QK后进入Ising，后者选块后准确Softmax。因此分别存在Ising与筛选PPL，不能相加为联合方案的PPL。
- 同目录`sampling.py:18–39`：Ising由sigmoid出生速率、指数驻留时间和有限burn/spacing构造理想硬one-hot连续时间热浴。`multinomial`抽的是下一次出生事件，**不是从目标Softmax分布直接抽IID**。预热和间隔是动力学时间单位，不是物理ns。有限惩罚的小状态诊断不等于完整模型有限电路。
- `experiments/joint_router_ffn_20261009/attention.py:24–29`：候选精确QK后执行`softmax`、`torch.multinomial`及V均值；`screen_sampled`不能按名字改称Ising。`79–83`保留准确prefill，`100–104`安装全部24层。
- 同目录`model.py:21–25`和`evaluate.py:57–62`：FFN也在24层prefill/decode替换，明确记录WT2 suffix subset。
- `experiments/direct_router/sparse.py:22–35`是候选块数字在线Softmax和准确加权PV；CLI遗留的samples/burn/spacing字段不能证明启用了Ising。

另有随机Q/K**投影**＋Ising＋随机FFN的模型级后缀结果（2K 13.215760±0.081924）。它替换q_proj/k_proj的概率编码，不是概率块筛选，不能补上本次联合路径缺口。

## 与当前数字/PPA对比的关系

Issue37/PR45的完整模块事务对比已经执行，但`ising_macro_v4.py`默认用`categorical(softmax(logits))`生成理想地址；它不验证CTMC混合、反馈延迟、偏置量化或物理随机相关性。当前主要情景固定8块、512候选，样本数32/128/512；历史max4是约30%的变量候选。历史512样本的PPL也不能自动覆盖32/128样本。

因此，已有的局部Ising或筛选质量、完整模块TLM和原BF16完整WT2是三个互补证据，不构成同一个配置已通过质量与PPA双验收。当前完整物理PPA和联合PPL仍未闭合。

备忘录另记原FFN＋PV采样完整WT2 11.717755±0.002673；本次未定位其原始输出/配置，只作为待追溯条目，且它不证明筛选＋Ising联合质量。

## 接续实验只补缺口

1. 复用已审计的max4筛选、真实Ising CTMC与历史文本/模型协议，先冻结**原FFN**、QKV/Wo和数制，隔离Attention误差；保留原SDPA与手写数字在线Softmax匹配控制。
2. 明确实施筛选→候选QK→Ising→V的同一路组合。优先匹配当前PPA的固定8块/512候选与S32/128/512，另保留约30%变量预算作为历史桥接。固定预算补齐/裁减和强制近块策略必须与TLM一致。
3. 先做同协议短后缀桥接及一个小规模正确性/耗时preflight，再提交有质量根据的完整计分与3seed确认。完整WT2需单独记录全部目标NLL、窗口/stride及Attention在哪些查询启用，不能把decode-only短后缀改名为完整WT2。
4. 将通过质量预算的**相同候选、样本、预热和相关性配置**送入数字参考与概率方案的完整模块成本比较；CTMC时间与物理采样周期分开，物理转换未经标定时只给情景曲线。用户尚未固定可接受PPL增量，不擅自宣称某个阈值已经获认可。

本轮是证据核查与接续范围收敛，未启动新的PPL/GPU/RTL/PT计算。新的实现/正式执行需建立对应任务Issue、独立工作树并遵循Slurm门禁，不接管其他成员FFN任务。

## 可追溯入口

- [Ising原始汇总](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/03f0031b4c2952dae2775f01d6190105011ddaf1/results/pbit_softmax_router_20261006/summary.json)。
- [max4原始汇总](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/6cd34b5e5554dbd72e63a2e98d34b83cf32b3a01/results/router_metrics_20261007/summary.json)。
- [筛选＋IID联合原始汇总](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/03f0031b4c2952dae2775f01d6190105011ddaf1/experiments/joint_router_ffn_20261009/results/summary.json)。

完整源码/协议/报告路径、固定提交及SHA-256见`work/amlink1219/33/QUALITY_AUDIT_20261019.json`。历史结果继续保留原分支，不将参考材料冒称已合入集成分支。
