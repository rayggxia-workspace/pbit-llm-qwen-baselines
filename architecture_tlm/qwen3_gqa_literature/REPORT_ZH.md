# Qwen3-4B：GQA 下的 QK 筛选文献与设计建议

2026-10-23，Issue139，负责人 amlink1219。范围是原文/实现调研和后续设计建议；未训练、未替换模型、未运行新仿真或 PPA。本报告中的方案均未获本项目质量验收。

## 1. 结论与模型边界

建议以 **一个 KV head 及其 4 个 Q heads 为一次候选调度单元**：筛选得到共享的 KV 块/位置，读取复用，但最终各 Q head 的点积、归一化和输出保持独立。优先比较免训练的组内概率汇总、逐头筛选后并集，以及已经提供 Qwen3-4B 门控权重的 SeerAttention-R。GQA 本身不规定必须用 mean、max 或 union。

官方 `Qwen/Qwen3-4B` 配置为 36 层、32 Q heads、8 KV heads、head_dim=128、hidden_size=2560、FFN intermediate_size=9728。每组 4 个 Q 头；不能用 hidden_size/num_heads 推导 head_dim，本模型两者不相等。来源：[config.json](https://huggingface.co/Qwen/Qwen3-4B/blob/main/config.json)、[模型卡](https://huggingface.co/Qwen/Qwen3-4B)。

本次用户确认名称为 Qwen3-4B。与此同时，远端 [Issue136](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/136)/[PR137](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/137) 由 jieruiz 建立 **Qwen3-4B-Base** 下载与 WT2 基线。二者分开记录：SeerAttention-R 的公开推理成绩/门控对应后训练 Qwen3-4B，不能直接证明 Base 的效果，也不能未经验证假定门控适配 Base。这里不接管其基线工作，也不据文献启动训练。

## 2. 各文献到底在组内合并什么

| 工作 | 便宜的筛选信号 | GQA 合并规则 | 适用阶段、训练和局限 |
|---|---|---|---|
| [SparQ Attention](https://arxiv.org/html/2312.04985v6)，§4、附录B | 只扫描少数 K 通道，估计各头 attention | 先对组内 `abs(q)` 求和选共享通道；各头近似 softmax 后，再把概率求和选共享 token | 免训练 decode。仍需扫描全序列的部分 K；论文含 Llama3/Mistral GQA，未验证 Qwen3-4B |
| [ReSA](https://arxiv.org/html/2506.04108v2)，§2.1–2.3、图3 | 每块 K 的逐维 min/max 摘要，Quest 式估分 | **先对 Q 向量求均值**，再算一个组的块分数；共享所选块 | 免训练 decode，另有周期性 dense 重编码修复 KV；不能漏计重编码与摘要刷新。实验不是 Qwen3-4B |
| [Twilight](https://arxiv.org/html/2502.02770v3)，§4、附录B.2 | 宽候选后用 INT4 K 估分，再 top-p 缩减 | 各头所选位置取 **union**，形成组级物理访问集 | 自适应 decode 预算。第二阶段估分仍收费；组并集可大于各头预算。未见 Qwen3-4B 直接结果 |
| [SeerAttention-R](https://arxiv.org/html/2506.08889v1)，§2.2–3 | 拼接组内 pre-RoPE Q 后经可学习投影；K 块 max/min/mean 摘要另经投影，产生组级门控分数 | 训练标签先在块内 token 取 max，再在同组 heads 取 max 并归一化；推理时是**一个学得的组级 gate**，不是现场计算完整 attention 后取 max | 面向 decode；冻结原模型但要训练 gate。直接测试 Qwen3-4B，已发布门控权重 |
| [Native Sparse Attention](https://arxiv.org/html/2502.11089v2)，§3.3.2、式9–12 | 压缩分支的 attention 转为块重要性 | 组内各头块重要性 **求和后统一 top-n** | 压缩/选择/滑窗联合训练的架构；不能直接当作现有 Qwen 的免训练插件 |
| [RocketKV](https://arxiv.org/html/2502.14051v3)，§3、算法1、附录A.3 | 先永久缩减 KV，再用通道/页面摘要做细筛 | HSA 阶段组内 `abs(Q)` 汇总选通道、逐头近似概率汇总选共享 token | 免训练两阶段方案；若只借用 HSA，应明确未采用第一阶段永久淘汰，不能继承完整方法的容量收益 |

上述三种“平均/求和”不是同一运算：SparQ 聚合的是逐头归一化后的概率；ReSA 平均原始 Q；NSA 汇总压缩分支块重要性。固定组大小下 sum 与 mean 对同一组分数的 top-k 排序相同，但不代表阈值、数值误差或其他预算规则相同。由于 softmax 非线性，`softmax(mean(Q)Kᵀ)` 一般不等于 `mean(softmax(QKᵀ))`。

Quest 是重要的块摘要基线，其分数为

\[
u_{h,b}=\sum_{j=1}^{128}\max(q_{h,j}k^{\max}_{b,j},q_{h,j}k^{\min}_{b,j}).
\]

它在实数精确 min/max 条件下给单头、单块内点积的上界，但 top-k 上界排序本身不保证无遗漏；量化后也需要重新分析。这里的 `max` 是对 min/max 边界取值，**不是跨 Q heads 的 max**。原 Quest 未规定 GQA 聚合。RocketKV 附录的 Quest 对照另做了组级改造。[Quest §3](https://arxiv.org/html/2406.10774v2)

作为背景：[Ada-KV §3.5](https://arxiv.org/html/2407.11550v5) 用组内平均 attention weight 选共享 KV，主要实验在 prefill 后淘汰；[SnapKV](https://arxiv.org/abs/2404.14469) 利用 prompt 尾部观察窗压缩 KV，其 max pooling 主要是序列邻域聚合，不能当作跨 Q heads max 的依据。这类永久淘汰与每步重新从完整 KV 检索需分别比较。

Prefill 另有 [QUOKA](https://arxiv.org/html/2602.08722v1)：归一化 Q 后在组内求均值，代表查询轴取 max；以及 [CompactAttention](https://arxiv.org/html/2605.16839v1) 跨 Q blocks/同组 heads 的 OR 并集。它们主要针对 chunked prefill；不能把 prefill 的时间收益移到单 token decode。

## 3. 最直接的 Qwen3-4B 证据与代码边界

[SeerAttention-R 官方仓库](https://github.com/microsoft/SeerAttention) 提供约 66.1 MB 的 Qwen3-4B AttnGate；原模型不动，仅门控学习。官方 [模型卡](https://huggingface.co/SeerAttention/SeerAttention-Decode-Qwen3-4B-AttnGates) 的 4K token 预算结果为 AIME24 68.75 对 dense 71.25，AIME25 57.60 对 66.41；AIME 每题 64 次采样后平均 pass@1。它是可复现的直接对照，但不能概括为所有任务无损，也不是我们重跑的成绩。论文的 H100 sparse-kernel 加速不能等同整模型加速或本项目 ASIC PPA。

官方 `decode_sparse/attention_forward_sparse.py` 对多 token 输入仍走 dense prefill，单 token 才走 sparse decode；首块和末块有强制保留逻辑。因此实际读取数量应按强制块与 top-k 候选的最终并集统计。[门控代码](https://github.com/microsoft/SeerAttention/blob/main/seer_attn/decode_sparse/attn_gate_inf.py)、[执行代码](https://github.com/microsoft/SeerAttention/blob/main/seer_attn/decode_sparse/attention_forward_sparse.py)

代码复用时不能只看方法名称：

- Quest 官方 `evaluation/quest_attention.py` 精度验证路径先重复 KV 并计算完整 QK，再施加候选 mask；不是实际绕过完整 QK 的性能证据。[源码](https://github.com/mit-han-lab/Quest/blob/main/evaluation/quest_attention.py)
- SparQ 论文附录有 GQA 聚合，但官方 `sparq-gpt-fast/with-sparq` 演示先 repeat KV，再逐 Q top-k；该分支不能代替论文组级共读实现。[源码](https://github.com/graphcore-research/sparq-gpt-fast/blob/with-sparq/sparq.py)
- RocketKV `gpt-fast/rocket.py` 的 HSA 明确保留 KV group 维度并共享 gather，可参考索引组织；它的摘要近似不自动继承每头 Quest 上界。[源码](https://github.com/NVlabs/RocketKV/blob/main/gpt-fast/rocket.py)
- Twilight 的 `pyimpl/attention.py` 是全量 QK 的精度模拟；效率代码单独存在。ReSA 原文已查，官方重定向未能解析，源码未核。[Twilight 源码](https://github.com/tsinghua-ideal/Twilight/blob/main/twilight/pyimpl/attention.py)

## 4. GQA 下应如何计费

令一组四个头分别选择 A₁…A₄，共同访问集 U=∪Aₕ。每头各选 k 个位置时：

\[
k\le |U|\le\min(N,4k).
\]

例：16 个块，每头选 4 块。若完全重合，组读 4 块；若完全不重合，组读 16 块。每头都可以报告 75% 稀疏，但后一种情况完全没有减少组级 KV payload。这是集合推导，不是实测。

BF16、head_dim=128、块长 b 时，一个 KV 组每个块的 K+V payload 是 `2×b×128×2 = 512b` bytes，若 K/V 访问相同集合 U，则为 `512b|U|` bytes。8 个 KV 组应按各自 U 求和；不存在让 8 个不同 KV heads 共享同一 K/V 张量的理由。采样 PV 时 K 与 V 的访问集可能不同，应分别算 `256b|U_K|+256b|U_V|`。

完整账本还要包含摘要初建/增量更新、摘要读取、近似分数与归一化、top-k/top-p或阈值、union/位图/目录、地址突发放大、缓存读端口与广播、每头最终 QK/PV、采样状态和输出写回。若摘要是同 dtype 的 K min/max，两份摘要占完整 K 的约 2/b，或 K+V 的约 1/b；这是理想数据量，不是时延/PPA结论。SparQ 的部分通道扫描与可能双份 K 布局也必须单列。

“共享候选”只保证索引相同，硬件还需实现真实共读。选择所有 head 都在 U 上算，或仅在各自 Aₕ 上算并复用 K/V，是两个不同执行方案；后者还要维护消费者掩码。无论哪种，不能把四个 Q 向量在最终 attention 中合为一个。

## 5. 对本项目的建议（未执行）

优先保留完整 KV，先比较动态筛选，避免与永久淘汰混淆。首轮至少三条对照：

1. **逐头筛选后 union**：保留旧筛选输出，建立真实共读账本，是接口/质量对照。它不保证读量按单头保留率下降。
2. **组级共享候选**：以 SparQ 式逐头近似概率求和为免训练文献基线；以跨头 max、ReSA 的 mean-Q 作消融。max 可保护单头的强响应，但未证明在本模型更优。各头分数的尺度/归一化必须明确，不能对不可比 raw logits 随意平均。
3. **SeerAttention-R gate**：若实际采用 Qwen3-4B 后训练模型，核验固定 revision 后可用公开门控作强对照；若采用 Issue136 的 4B-Base，需单独评估门控迁移，必要时校准/重新蒸馏，当前没有可直接继承的成绩。

本项目小型 p-bit 筛选网可研究“4 个 Q 的组级摘要输入→每 KV 组一个块保留决策”，但这是我们的待验证适配。旧 `max4` 名称不等于“四个 Q heads 取 max”。需保留原 valid/forced masks、自由块归一化、std floor/temperature，并在新训练/验证/测试集上按**最终组级访问预算**比较；不可复用已经看过的盲集调参仍称独立验证。

后续验收按顺序进行：固定模型/分词器/revision、Q/K norm与RoPE边界；每层8组真实Q/K探针；按组记录候选并集与每头遗漏attention mass；完整模型质量；最后接在线选择器到周期后端。decode补丁必须逐token经过被替换层评测，不能用dense多token窗口冒充候选PPL。建议扫描2K/8K/32K上下文、16/32/64块长、若干**实际组预算**，这是设计建议而非已接受的参数或启动指令。

完整验证需要同时记录 mean/worst-head retained mass、attention输出误差、完整WT2 PPL、长上下文检索及（后训练模型）推理质量与生成长度；报告候选索引/摘要成本、物理KV bytes、访存事务和端到端延迟。随机筛选至少3个seed。完整QK后top-k仅作精确分数选择的参考对照，不是整模型质量上界，也不能算成节省QK的实现。

## 6. 项目状态和资料归档

实时核查集成分支为 `6966739a5223680888bf0315f7bb4f73423a1ae6`。PR126 已在 2026-10-23 合并，但 Issue116/123 的暂停仍有效。当前 GQA 后端已接受预先给定候选并复用一个 KV 组；在线选择器尚缺，不能因已有 group executor 就称 QK 筛选完成。[集成版本接口](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/6966739a5223680888bf0315f7bb4f73423a1ae6/architecture_tlm/cycle_v1/GQA_GROUP_ZH.md)

本次12篇相关文献的书目/PDF已核验并暂存，清单见 SOURCES.json。Zotero 当前未运行、后台接口拒绝连接；已只读核查 `D:/ZoteroData` 个人库，未向数据库写入，也未启动前台窗口。12篇保持待导入状态，不能称已入库；可恢复清单和PDF位置见 HANDOFF。未上传论文全文、模型、凭据或工艺资料。
