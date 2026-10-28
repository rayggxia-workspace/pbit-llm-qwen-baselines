# Attention的KV读取与经典数字基线

2026-10-28，rayggxia，Issue198 / 草稿PR199。输入head346c6b2ec25f122ed4ca8643b261eb2c063e29f2；既有共同TLM基线main d83eeb1f，Issue186/PR192最新91f68416只读。本文是文献核查、静态代码审计和已有轨迹的地址算术；不是新TLM、DRAMSys、GPU、RTL、PPL或PPA实验，不改默认资源或旧实验。

## 先确认哪些问题

KV是Attention的重要成本，但还不能无条件称为整机最大瓶颈。我们首先需要闭合：KV具体布局与传输粒度；GQA组内真正的读出并集；相同质量下的采样预算；片存与DMA能否支撑稀疏访问。Softmax核的面积或吞吐不等于整条Attention的成本。

| 优先级 | 需要固定/补测的内容 | 对结论的影响 |
|---|---|---|
| P0 | K和V分别的地址公式、行/页/块尺寸、BF16或量化格式、对齐、DRAM请求粒度、页表位置 | token数少不保证实际字节少；K/V可用不同布局 |
| P0 | 同一KV组内各Q头的候选/采样地址及交集；合并、广播与计数保留 | 各头保留率不能直接作物理KV保留率 |
| P0 | 源/驱动到地址的时序、采样相关、S与真实质量曲线 | 控制器输出数不等于独立有效样本数；S512与数字S128不可忽略 |
| P0 | 真实后训练QKV及mask、Q/K norm、RoPE、score量化/温度 | 当前合成单头结论不能替代模型质量；必须相同目标分布 |
| P1 | SRAM驻留、双缓冲、bank映射、读写端口、DMA队列/SG描述符上限 | 有限缓存可能重复取同一burst；稀疏与顺序访问的有效带宽不同 |
| P1 | 摘要cold-build、warm维护、KV追加、跨层/跨token缓存命中 | 摘要生成不是免费K筛选；有容量不等于所有层KV都能驻留 |
| P1 | V重复计数、FP32累加依赖、稀疏gather返回与回压 | 保留重复权重；不能删重复采样后仍当均匀平均 |
| P1 | 数字QK/PV与Softmax同工艺PPA、互连/随机源/驱动 | 目前控制器PPA尚未闭合整条路径，hold限制仍保留 |

## 主数字基线应采用什么结构

以**已有模型的完整稠密Attention、分块在线Softmax/PV、GQA组内复用、有限双缓冲**作为基线。一次KV tile加载后供同组全部Q头使用；维护每头的max、分母和未归一化输出，只在末尾归一化。不要求形成完整概率行，更不要求L×L概率矩阵。改变分块/求和次序仍需验证有限精度误差，不能声称逐bit相同。

FlashAttention提供IO感知的精确分块结构；Flash-Decoding进一步拆分长KV并合并partial output/LSE。后者应作为并行资源足够时的候选，合并和状态缓冲需要计费，不能给小ASIC凭空增加并行核。[FlashAttention原论文修订版](https://arxiv.org/abs/2205.14135v2)，[Flash-Decoding作者说明](https://princeton-nlp.github.io/flash-decoding/)

FlashInfer针对短query把同组Q头融合，让一次KV加载供多头使用；这说明GQA复用应成为数字对手的基本能力。PagedAttention解决分页和存储管理，不自动证明减少一次稠密decode必须查看的KV内容。GPU实现只提供数据流/布局参考，GPU时间或带宽不能直接移植为55nm ASIC性能。[FlashInfer v1，Appendix A/B](https://arxiv.org/html/2501.01005v1)，[GQA v3](https://arxiv.org/html/2305.13245v3)，[PagedAttention原文](https://arxiv.org/abs/2309.06180)

基线分四个可分辨的对照，不更改现有D0/P0–P4命名：

| 对照 | 用途 |
|---|---|
| D0：全KV、原模型数制、融合数字Attention | 主准确对照，固定模型/权重与质量协议 |
| P1：相同筛选集合、候选内数字精确Attention | 隔离筛选收益，不能把筛选收益全归于Ising |
| P2：相同筛选与采样预算的数字CDF采样 | 隔离采样电路；再做同质量预算，而非只比相同S |
| 量化数字候选：KV8/4bit等，重新评估 | 更强的低成本对手；需计scale/zero-point/高精度残余/反量化，不能继承BF16质量 |

仅输出地址时，数字CDF可直接累加w=exp(score−max)，比较uΣw与未归一化前缀，避免逐元素输出w/Σw。数学抽样分布等价不保证有限位宽逐bit等价；此优化尚未实现。KV量化参考KIVI对K逐通道、V逐token的区分，原论文质量与速度不自动适用于我们的后训练模型。[KIVI v2](https://arxiv.org/html/2402.02750v2)

## KV字节基线：先把边界写清

设上下文L包含当前token，Hq/Hkv为Q/KV头数，d为head维度，b为每元素字节。没有跨token片存命中、没有压缩时，全量逻辑KV扫描每层为

`B_KV = 2 × L × Hkv × d × b`；`QK+PV MAC = 2 × L × Hq × d`。

前者是有效数据，不含传输放大、页表/描述符、重复读取、ECC与KV追加；也不是有片存命中时的外存下界。GQA组内同一K/V只读一次是可实现的数据复用目标，实际必须由并行Q头状态、广播和端口保证。若MAC按2 FLOP计，理想融合算术强度为`2(Hq/Hkv)/b FLOP/B`。

沿用当前TLM的Qwen/Qwen3-4B后训练**形状**：36层、32Q/8KV头、d128、BF16 KV，g=4。准确revision和配置SHA见审计JSON；这里没有加载权重或进行PPL。[固定官方配置](https://huggingface.co/Qwen/Qwen3-4B/blob/1cfa9a7208912126459214e8b04321603b3df60c/config.json)

| 上下文 | 每层全KV有效扫描 | 36层合计/生成token | QK+PV总MAC |
|---:|---:|---:|---:|
| 512 | 2MiB | 72MiB | 150994944 |
| 2048 | 8MiB | 288MiB | 603979776 |
| 8192 | 32MiB | 1152MiB | 2415919104 |

追加K/V每层4096B，是否对当前token旁路、是否写分配/读改写另记。共享8MiB不代表2K每层8MiB KV可免费驻留：还有缓冲/状态，36层总量更大；需明确跨层和跨token替换政策。跨请求prefix共享也不等于所有batch请求共用相同动态KV。

2K时，若全KV来自外存，288MiB除以29.851GB/s约10.117ms，除以256GB/s约1.180ms；若512 MAC/拍、100MHz且理想利用率，QK/PV MAC下界约11.796ms。这些是**条件算术下界**，不是本次时序结果，不能相加，也没有包含Softmax、FP32 PV代价差异、片存和控制。因此当前小资源档不能预先认定“只要省DRAM，Attention就等比例变快”。整机稠密权重流量还须另计。

## 地址布局会怎样改变稀疏读量

当前unified_v6的`kv_ranges`是NHD式：`((token*Hkv+head)*d+channel)*2`，每token的一个head行连续。FlashInfer支持NHD/HND及分页形式，页是存储分配单元，并不必然是最小读取单元。[官方布局文档](https://docs.flashinfer.ai/tutorials/kv_layout.html)

vLLM v0.18.0文档展示另一ABI：K `[page,H,d/x,T,x]`，V `[page,H,d,T]`。这不是所有vLLM后端的统一布局。本次按其ABI构造**64B传输、T16、d128、BF16、x8、对齐基址**的地址算术示例：

| 只选择一个token | 有效V/K行 | 需触及的64B burst总字节 |
|---|---:|---:|
| 连续行K或V | 256B | 256B |
| ABI示例的向量分组K | 256B | 1024B |
| ABI示例的通道交错V | 256B | 4096B |

原因是单个token的不同通道分散在多条burst。4096B覆盖该head整页V的传输行；这是一种地址几何结果，**不是实测GPU或所有ASIC必然16倍放大**。真实GPU有自己的事务粒度/缓存，真实ASIC也可选择不同布局。全页/全量扫描时，两种布局可读相同有效总量；稀疏时差异才突出。原ABI代码阅读锁定bcf2be96120005e9aea171927f85055a6a5c0cf6。[v0.18.0源文档](https://github.com/vllm-project/vllm/blob/bcf2be96120005e9aea171927f85055a6a5c0cf6/docs/design/paged_attention.md)

## 用旧轨迹验证风险，而非猜测

复用Issue198已归档的2K/d128/S128、seed17/503/1009共18个单头案例，原ZIP与18成员SHA逐字核验。没有重新抽样，也没有构造真实GQA。下表是三seed平均，映射到上述两个布局后的唯一burst集合；假定理想合并，有限缓存/队列实际可能多次取同一burst。

| 方案 | 连续行K KiB | 连续行V KiB | 页ABI示例K KiB | 页ABI示例V KiB |
|---|---:|---:|---:|---:|
| D0全量 | 512 | 512 | 512 | 512 |
| P0准确Softmax后采样 | 512 | 32 | 512 | 456 |
| P1筛选后准确 | 128 | 128 | 128 | 128 |
| P2筛选后数字采样 | 128 | 29.917 | 128 | 128 |
| P3校正拒绝 | 128 | 23.5 | 128 | 126.667 |
| P4赢家保持 | 128 | 23.75 | 128 | 125.333 |

筛选是完整64-token块，恰好覆盖多个16-token页，所以K没有额外放大；稀疏V则几乎触及全部已选页。该表不是相同质量结论：旧S128时P3/P4未满足先前探索性质量阈值；不能据此省略其S512成本。真实后训练头之间的候选相关、分布和GQA并集仍需采集。

还有一个纯解析检查：L2048、同组4头，每头独立均匀IID抽128次、无K筛选时，组内预期不同V比例为`1−(1−1/L)^(4×128)=22.125%`，总K+V有效比例为61.062%。如果每头512次，V比例为63.221%、总KV为81.611%。上述交错V页示例的预期触页比例则约98.197%/99.99999%。这些不是Systematic、赢家或真实模型的预测，只说明采样事件、唯一token、唯一页和物理字节必须分层计数。

## 我们已有的基线能复用多少

静态核对输入head中的unified_v6/model.py：`qk`已对各Q头候选取组内并集，fused路径执行online Softmax/PV；`sampled_attention`已做计数、GQA sorted union和V广播；core.py的DRAM.ranges按burst对齐/去重并接有界SG/DRAMSys。因此不能称此前完全没有GQA或实际地址模型，也不应重写另一套整机。

但仍有限制：第一阶段attention_compare仅单头，`kv_union`只是工具，schedule.py是Link/宏；主TLM的shape/合成logit不能验证真实头间相关；head依次服务与局部资源的时序仍须审计。PR192可选分slice/本地端口优化已经有结果，但未合并，且其Ising sink尚未拆成真实beat；不能将该后端的数字时延或旧功耗套到我们的采样控制。

## 建立基线的具体顺序和验收

1. **冻结协议与数据。** 先B1单token decode，L512/2048/8192、原32Q/8KV、d128、2B KV；prefill/TTFT另测。捕获后训练模型的Q/K norm、RoPE之后真实QKV与mask，记录model/权重/tokenizer/文本SHA，重跑匹配未修改BF16参考。使用SDPA时记录backend；q_len=1、KV含全部过去token时不要误用上左对齐的非方阵causal mask，只开放实际有效过去/当前位置、屏蔽padding/未写入slot。dropout=0。较低精度与后端求和差异单列。[PyTorch SDPA官方合同](https://docs.pytorch.org/docs/2.14/generated/torch.nn.functional.scaled_dot_product_attention.html)
2. **落实融合数字数据流。** 沿主unified_v6，以T64、g4为首个点，两个BF16 K/V tile槽共64KiB；Q约1KiB，FP32输出/max/分母约2080B，额外score tile和FIFO另计。实际512 MAC宏的QK和FP32 PV、exp/倒数、重缩放、累加回路分别标定，不能将独立MAC II1当同一输出反馈II1。
3. **先核字节，再核时间。** 输出每层/每KV组的候选token、采样事件、唯一V、burst地址、相邻span、重复读、页表/描述符字节、SRAM读写及追加写。若数据经DRAM→SRAM→算术，填入与读出各收费；若改本地直达，双方必须计相同可行的接口/缓冲。B1/全KV、P1/P2/P4用同一内存配置、布局和地址集合接口，不只按token比例乘带宽。
4. **在既有DRAMSys与片存后端做微基准。** 先顺序全KV、同地址稀疏gather、64-token块选取，比较连续行/页布局、排序前后、MLP1/8/32、有限SG与1/2 tile槽。记录bank/row命中、读写切换、有效带宽、响应/credit停顿与消费者等待，正确区分channel burst和DMA入口粒度。不要默认稀疏与顺序读具有相同有效GB/s。按Issue186接口增量接入，不重跑其已完成整机矩阵。
5. **再做同质量和PPA闭环。** 同一筛选集比较P1、优化数字CDF P2、P4；S扫描并报告真实后训练输出/PPL及相关性，不仅计相同S。只在调用链闭合后综合/功耗：数字QK/PV、Softmax、SRAM/驱动、采样源/仲裁、gather/累加、互连/时钟分别报界限。用本项目指定工艺原面积×0.81一次；功耗/时间不缩放。HBM能量模型未校准不能输出有效HBM节能结论。

建议第一份可验收表是“2K、一个真实KV组4个Q头”：D0/P1/P2/P4各自K有效字节、V有效字节、burst实际请求、SRAM读写、各阶段周期、MSE和S。先让这张表闭合，再扩展8KV组/36层；单组乘法只能标上界/形状推算，不能冒称完整运行。

## 本次证据与复现

- [KV_READ_AUDIT.json](kv_baseline_20261028/KV_READ_AUDIT.json)：100个地址核验、18旧案例/原件SHA、形状与解析公式，明确下界和未知项。
- [SINGLE_HEAD_LAYOUT_REPLAY.csv](kv_baseline_20261028/SINGLE_HEAD_LAYOUT_REPLAY.csv)：逐seed/方案数据。
- [KV_DIGITAL_BASELINE_SOURCES_20261028.json](KV_DIGITAL_BASELINE_SOURCES_20261028.json)：论文、官方文档pin、现有代码审计SHA与局限。
- 复现：`python -B -m architecture_tlm.attention_compare_20261027.kv_read_audit --archive-index work/rayggxia/198/RAW_ARCHIVE.json --output NEW_DIRECTORY`。需要原ZIP可访问；输出目录必须不存在。仅标准库，使用已有Git对象中的shape配置，不加载模型。
- 新增数字仿真run为0；没有新服务器作业，不修改unified_v6/默认配置、旧轨迹、既有功耗系数或他人STATUS。后续新物理/模型实验按原门禁和统一台账登记；当前交付不是已完成经典数字Attention全链芯片基线。
