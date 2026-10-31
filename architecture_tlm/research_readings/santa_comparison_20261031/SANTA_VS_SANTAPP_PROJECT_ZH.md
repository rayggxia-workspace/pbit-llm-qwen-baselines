# SANTA、SANTA++ 与本项目的方法对照

2026-10-31；Issue139 后续文献比较；负责人 amlink1219。本文核对原文与固定提交的项目材料，没有运行新模型、RTL、EDA 或 p-bit 实验。

**我们的 V 地址采样与 SANTA 主方法最接近；max4 筛选后精算的 Attention 与 SANTA++ 结构最接近；随机 FFN 的乘法替代思路，则与 SANTA 另一个分支 Bernoulli QK 相近。** 不能只看论文名称中的 sampling，把三者当成相同算法。

## 1. 两篇论文到底改了哪里

阅读版本：[SANTA v2](https://arxiv.org/html/2605.01910v2)（2026-06-03，§2/§5/附录C）与 [SANTA++ v1](https://arxiv.org/html/2609.35629v1)（2026-09-28，§2/附录A/D/E）。下表的 SANTA 主方法指 AV 分支，QK 扩展另列。

| 环节 | SANTA：AV 主方法 | SANTA++ |
|---|---|---|
| 从哪里决定读取对象 | 完整 QK 和 softmax 后的 token 概率 | 先用代表 Key 估计 team 重要性 |
| 抽样单位 | V 行；基本版按类别分布有放回抽样 | team；Gumbel-top-K 不放回抽样 |
| 读到之后计算什么 | 读 V 并按抽样次数求和、除以样本数 | 读选中 team 的全部 K/V，准确算成员贡献，再校正和归一化 |
| 主要节约 | V 读取与 AV 乘法 | 路由以后的 K/V 读取；准确加权乘法仍存在 |
| 估计性质 | 给定准确概率，AV 估计无偏 | 校正后的未归一化分子、分母无偏；比值一般有偏 |
| 附加状态 | CDF/分块状态及采样状态，依 kernel 而异 | 代表 Key、成员映射、team 大小及打包布局 |

SANTA 的核心公式很直接。令 $p=\operatorname{softmax}(qK^T/\sqrt d)$，则

$$
J_t\sim p,\qquad \widehat o=\frac1S\sum_{t=1}^{S}V_{J_t}.
$$

重复抽到一个地址必须保留次数。其 $S^2$ANTA 包括 CDF 分层采样和单偏移 systematic sampling；二者不要与 GPU 的 Prop/Flash 调度版本混为一谈。主 AV 方法仍需先获得完整 K 的分数。

SANTA++ 在 prefill 后为 prompt 建 team，以真实 Key 作为代表 $\ell_g$；每个 parent 可有多个代表，再按最近代表分配成员。其路由分数为

$$
\phi_g=\log n_g+q^T\ell_g/\sqrt d.
$$

加独立 Gumbel 后取 top-K；根据选中 team 的条件纳入概率 $c_g$，分别累加 $U_g/c_g$、$Z_g/c_g$，最后相除。生成的新 token 属于 exact suffix。**它不是把 SANTA 的 V 样本数调小：抽样位置、单位及输出估计器都变了。** 这里的条件校正不能简单替换成首次抽取的 softmax 概率。[方法与校正原文](https://arxiv.org/html/2609.35629v1#S2.S3)

## 2. 容易漏掉的相似点：SANTA 也研究随机乘法

SANTA §5/附录C 还提出 Bernoulli QK。令 $c\ge\max_i|q_i|$：

$$
b_i\sim\operatorname{Bernoulli}(|q_i|/c),\quad
\widetilde q_i=\operatorname{sign}(q_i)b_i,\quad
\widehat{qK^T}=\frac cB\sum_{t=1}^{B}\widetilde q^{(t)}K^T.
$$

这使 Query 成为随机三值量，乘法转为带符号选择和累加；零特征可跳过对应 K 特征读取。**它筛的是特征维度；SANTA++ 筛的是 token team。** 线性 QK 无偏不保证经过 softmax 后的 Attention 无偏。[SANTA 附录C](https://arxiv.org/html/2605.01910v2#A3)

与我们的 FFN 相似的是“概率编码数值→事件门控→累加恢复”，也都可用分层样本降低随机误差。区别在于我们覆盖 gate/up/down、SwiGLU 门控和多档尺度，另有输入/权重双随机方案；SANTA 的此处主要是随机 Query 乘常规 K。SANTA++ 没有实现随机 FFN。

## 3. 对照我们的三条路径

| 项目路径 | 最接近哪部分 | 已有重合 | 关键差别 / 尚需证明 |
|---|---|---|---|
| 准确 softmax＋CDF/systematic＋V gather | SANTA AV | 分布到地址，再读 V 求均值；包含重复次数 | 数字基线已高度相同，不能作为我们新提出的算法 |
| 赢家保持 / 校正拒绝 / Ising 直接输出地址→V 平均 | SANTA AV 的目标估计器 | 都希望从注意力权重产生类别样本 | 省去显式概率向量的代价转到 LUT、更新、仲裁、拒绝/混合时间；有限位与相关性可使分布偏离目标 |
| max4→块筛选→候选准确 QK→候选采样 | SANTA++ 的粗筛后精算 | 便宜摘要先选，再付完整 K/V 成本 | 摘要、选择律、漏选校正及最终估计器不同；仅流程相近不证明质量或硬件更优 |
| 多档编码、分层短流 FFN | SANTA Bernoulli QK | 随机事件替代乘法，多样本累加恢复 | 我们含 FFN 非线性、Wd 和尺度恢复；共享事件拓扑改变协方差，不能继承其无偏或模型结果 |

项目依据为 [PR199 固定版本](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/0c7c2d8fe07c01ded6f2a4a1a117ab3fbeb688c8/architecture_tlm/attention_compare_20261027/README_ZH.md)、[PR221 的 P8 数值合同](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/2b6dadb0214f37b3f0b365e244db17411dc2b8c8/qwen3/training/attention_ten_case_20261031/NUMERICS_ZH.md)、[main FFN TLM 合同](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/7d42c7d30fa9c729c899ba7f815332dd6ed5671a/architecture_tlm/unified_v6/FFN_CURRENT_ZH.md)。PR221 是约定与建议，不代表训练或电路已验收。

### max4 与真实代表 Key 不能混称

我们已有 max4 合同：每 64-token 块的四个 16-token 均值摘要，各与 q 点积后取最大分数，再做 Bernoulli 门控和预算修复。这里的“4”不是四个真实 Key，也不是四个 GQA 头。SANTA++ 用实际 Key 建多个 team，另加 team 大小项，采用不同选择律。

平均摘要可能抹掉少数强相关 token；max4 有机会缓解，但没有消除这一风险。真实代表也只是路由近似。应比较同等实际 KV 读量下的遗漏质量，不能仅比较摘要数量或名义预算。

### 两种“校正”解决不同问题

假设我们硬筛后只保留候选集 C，随后完美地从 $p(i\mid i\in C)$ 采样；样本无限多时，输出仍趋向候选内重新归一化的 Attention，通常不等于完整 Attention。**候选内校正拒绝不会自动补回筛掉的概率质量。**

SANTA++ 则随机选择仍有机会入选的 team，并用各 team 的条件纳入概率重加权其准确贡献。这是不同层级的校正。它也没有使最终归一化比值完全无偏。若把我们目前的 Bernoulli＋强制块＋预算修复直接接入，必须推导其自己的真实纳入概率，不能套 SANTA++ 的 Gumbel 公式。

## 4. GQA、随机源与硬件上应怎样判断

GQA 下不能用单头保留率直接推整组物理流量：多个 Q 头共用 KV，需算所选集合并集。SANTA++ 已有 team/代表共读、各头独立选择和 head mask；这部分与我们的目标重合。[此前 Issue139 的具体分析](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/431856bec4038e8ee0ddba1ec957b53375e2b1f9/architecture_tlm/qwen3_gqa_literature/SANTAPP_GQA_COUPLING_ZH.md)

此前我们提出“同 team 的 Gumbel 跨头共享、各头保留自己的 top-K/校正”：相对该论文默认的独立选择是明确差异，但仍是方案与数学分析，联合输出方差可能增大，尚无模型质量或 PPA 验收。论文的并集共读本身不能作为新贡献。

随机源方面，SANTA systematic 已可用一次随机偏移生成整行阈值；我们 FFN 的全局 LFSR/二维分层是另一种联合分布，不能互称等价。省 PRNG 数量未必省总成本，还需计比较器、分发、计数、存储接口与相关性质量。双随机/SRAM 邻近 SNG 是项目后续方向；[main 中成员的合同记录](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/7d42c7d30fa9c729c899ba7f815332dd6ed5671a/progress/rayggxia/STATUS.md)不能当作新实测结果。

两篇的 GPU 加速不能直接大小相减或外推 p-bit PPA：SANTA v2 的最高 1.5× 是 RTX6000 Ada/Llama3.1-8B 的 attention kernel，另报最高 1.25× 端到端 decode；SANTA++ 的 1.69× 是 RTX5090 Laptop/Qwen2.5-7B 的固定单层 attention 算子，排除建 team 等准备。两者都不能证明我们假定的物理 p-bit 面积或 pJ/有效样本成本。原 KV 也不能因为少读就当作已删除。

## 5. 对我们贡献边界的判断

以下结论是**与这两篇论文比较**的判断，不是全领域新颖性证明：

- “采样代替 AV 乘法”“Attention 用分层采样”“便宜筛选后准确 QK”“GQA 读并集”均有明显已有工作，应作为基线或继承机制。
- 更值得验证的是：FFN/非线性完整映射、有限位直接类别采样、SRAM 与本地 SNG 接口、跨头选择联合分布，以及这些机制在同质量、同存储边界下的真实总成本。
- 最低比较组合应含：准确融合 Attention；数字 softmax＋systematic（SANTA 风格）；代表 Key 路由＋条件校正（SANTA++）；我们的摘要筛选＋直接采样。FFN 独立对比确定性低位实现。候选筛选误差、采样误差、实际读并集和随机源成本分别记录。
- 换成 p-bit 是实现差异。只有有效样本质量、全链延迟/能量/面积胜过对应数字实现，才能建立硬件收益。

## 6. 来源、版本与完成边界

- 项目阅读快照 main：`7d42c7d30fa9c729c899ba7f815332dd6ed5671a`。本报告不修改实现或默认方案。
- PR85、PR140：API 核验已合并；PR199、PR221、PR223：本轮核验 open/未合并；PR209：已合并。旧 Issue 正文或 STATUS 中的“待审”可能滞后，以实际 PR API 为准。旧集成分支已合并的资料未必存在于 main，因此引用准确提交。
- 论文 PDF/HTML 来源、下载原始 SHA-256、页数，以及项目文件 Git blob/提交，见 `PAPER_SOURCE_MANIFEST.json`、`PROJECT_SOURCE_MANIFEST.json`。
- Zotero 已复用两篇既有条目：SANTA `NPCE3YEN`（库内 PDF 为 v1），SANTA++ `F6DJ2FX7`（v1 PDF 哈希与本轮原件一致）。本报告读取的 SANTA v2 已下载核验；后台服务未连接，v2 补附件及本轮笔记保留待办，没有改写旧附件/批注，也没有声称已补入库。
- 模型/数据/随机种子/训练命令不适用：本轮为文献与固定源码比较，无新运行任务。
