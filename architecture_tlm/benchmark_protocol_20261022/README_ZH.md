# p-bit LLM 的 benchmark、质量与 PPA：统一调研与建议协议

2026-10-22；Issue [98](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/98)。负责人 rayggxia。证据冻结基线：`pbit-tlm-attention-details-20261016@83e15289434af50fc09c35e699d8b39965389d98`。

**核心结论：目前不存在一组能够直接横比所有 LLM ASIC、CIM、随机计算论文的模型、质量阈值和 PPA 数字。可以建立可信的统一评估协议；关键是把数值质量、实际工作负载、物理成本和系统边界绑定到同一个配置。** 本报告给出适合本项目的提议，不改变当前默认算法，不宣布用户已经接受某个质量损失。

本轮重新核查原论文、官方评测实现并整合以前分散的调研；没有运行模型、训练、GPU、Slurm、TLM 或 EDA。论文中未披露的字段不推断为“没有考虑”。结构化逐篇证据见 [PAPERS.json](PAPERS.json)，可筛选表见 [PAPERS.csv](PAPERS.csv)，建议配置见 [PROTOCOL_PROPOSAL.json](PROTOCOL_PROPOSAL.json)。本报告不是系统性文献普查，也不据定向样本宣称“全领域大多数”。

## 1 先看这些真实的不一致

| 容易误读的表述 | 原文或代码实际含义 | 对我们的影响 |
|---|---|---|
| 都是 WikiText PPL | 模型/tokenizer、WT2/WT103、raw 处理、window/stride、计分位置可能不同 | 不能拿别人 Llama2 的 5.47 与我们另一个协议的 4.98 直接判断精度 |
| acc_norm 是按 token 数归一化 | lm-eval v0.4.8 默认多选题使用候选字符串的 `len`，即字符长度；自定义 task 可以覆盖 | 报告具体版本、YAML 和实现，保留 acc 与 acc_norm |
| SANTA 的 8.237 ms/token | decode 总时间除以 6×2048 个输出；不是单请求平均输出间隔 | batch 吞吐和每请求 TPOT 必须分列 |
| HSA 的 tokens/s | 该文定义 token 包含 prompt 与 output；其硬件主模型是 RetNet-1.3B | 不能与只计生成 token 的 Llama/Qwen 吞吐直接相除 |
| 都报告 TOPS/W | 可能是 1b 归一化、稠密等价、跳零后等价、不同 MAC 计数或峰值点 | SC 的 T 拍、位宽、稀疏率与利用率必须显式记录 |
| “生成一个 token 的能量” | 有的是核内动作，有的是芯片+DRAM，有的是整卡传感器，另有系统墙插功率 | 只有同一分子边界、同一输出分母才能互算 |
| 使用模拟器即可估计 PPA | 模拟器通常给动作数/时间，面积和每动作能量仍需综合、电路、存储或测量来源 | 不能把“周期级”当成自动具有可信功耗模型 |
| 统一到 7nm/40nm 后公平 | 可能只缩放数字逻辑或表中的 TOPS/W，DRAM/新器件/模拟外围不在同一缩放范围 | 原节点结果和投影结果分开，主架构对照尽量同库实现 |

acc_norm 依据固定版本的 [task.py，1376–1393 行](https://github.com/EleutherAI/lm-evaluation-harness/blob/v0.4.8/lm_eval/api/task.py#L1376)；它的多选输出通过各选项 loglikelihood 选答案，不等于自由生成答案后的字符串匹配。任务若覆写 `process_results`，须以任务代码为准。

### SANTA 的表格应怎样复算

S²ANTA，ICML 2026，[v2 §3.5 / Table 3](https://arxiv.org/html/2605.01910v2#S3.SS5)：Llama-3.1-8B-Instruct、RTX 6000 Ada、BF16、约30K prompt、batch6、每请求2048输出，prefill保持稠密。

- Baseline：101.22 s / (6×2048) = **8.2373 ms/全批次归一化输出 token**；101.22 s / 2048 = **49.4238 ms/批次平均 decode 步**。
- S²ANTA-flash：80.97 s / (6×2048) = 6.5894 ms/token；平均步时间39.5361 ms。
- decode 加速101.22/80.97 = 1.2501×；prefill+decode 合计加速(56.69+101.22)/(56.61+80.97) = **1.1478×**。

这些是根据表格复算的平均值，不是逐请求 ITL 分位数。完整请求、完整 decode 和注意力 kernel 的倍数不同。该工作是 GPU 软件算法，不存在用 ASIC 工艺节点解释表中速度的问题。[正式发表入口](https://proceedings.mlr.press/v306/lee26j.html)

## 2 代表工作到底测了什么

下表为16项定向方法样本，DAC与四大体系结构会议共11项，另列5项随机、光子及阶段评估参考。不同年份版本按 PAPERS.json 标注。不是把各篇最大倍率汇总成性能排行榜。

| 工作 / 会议 | 模型与质量证据 | 性能 / PPA / 存储证据 | 应怎样使用 |
|---|---|---|---|
| [OPAL，DAC 2024](https://arxiv.org/html/2409.05902v3) | Llama2/OPT；WT2、C4 PPL，ARC-C、PIQA；BF16与OWQ参考 | 65nm DC，SRAM CACTI；生成token能量、core面积/功率；未给足外存命令功耗细节 | 学习“量化参考+新算术”分层；不能默认是全芯片后布局 |
| [MoNDE，DAC 2024](https://jaewoong.org/pubs/dac24-monde.pdf) | Switch / NLLB-MoE；GPU/CPU专家执行剖析 | 28nm DC、同工艺buffer compiler；专家周期模型+Ramulator；Micron DDR4计算器按电压调整至LPDDR | GPU+NDP系统、MoE，不是独立稠密Qwen ASIC的直接数值基线 |
| [UniCAIM，DAC 2025](https://arxiv.org/html/2504.07479v1) | LongChat-7B-32k；LongBench HotpotQA/NarrativeQA F1 | 45nm BSIM+Preisach FeFET HSPICE、寄生、SAR ADC；注意力电路AEDP | 算法质量和器件电路分别验证；AEDP不是完整LLM的J/token |
| MBA，DAC 2026，用户提供全文 | Llama3.1-8B / Qwen3-14B；WT2生成工作负载；未报告PPL/任务分数 | 行为级图模拟器；引用45nm PE经DeepScaleTool到7nm，FinCACTI、SFU/NoC文献成本，HBM固定pJ/bit | 高层仿真可用于架构评估；不能据此把引用的eDRAM testchip认作MBA整芯片实测 |
| [Kelle，MICRO 2025](https://www.saiqianzhang.com/gallery/Kelle_Camera_Ready.pdf) | Llama2 / Mistral；WT2/PG19 PPL、常识与生成任务 | 45nm逻辑DC；65nm/105°C Destiny SRAM/eDRAM；CACTI7 LPDDR4；计入外存时延能量 | 同面积调配算力/存储、算法消融值得借鉴；成本并非全来自一个节点 |
| [AttAcc，ASPLOS 2024](https://scale.snu.ac.kr/papers/2024-04-Conference-ASPLOS-AttAcc.pdf) | Llama65B / GPT3-175B / MT-NLG530B配置；性能校准用实机OPT66B | 自建Ramulator扩展、ASAP7 DC、FinCACTI；HBM文献能量及路径长度模型；SLO下最大batch | 主要是系统容量/性能设计；校准延迟不等于新器件能量全部实测 |
| [NeuPIMs，ASPLOS 2024](https://arxiv.org/html/2403.00579v3) | GPT3 7/13/30/175B配置；ShareGPT/Alpaca长度分布 | ONNXim+DRAMsim3；内存功率含PIM命令假设与额外row buffer背景；大batch吞吐 | 不能把内存功率表当完整NPU系统功耗，也不能把配置称作真实GPT3权重测试 |
| [CENT，ASPLOS 2025](https://arxiv.org/html/2502.07578v3) | Llama2-7/13/70B；功能/系统轨迹 | Ramulator2扩展、动作功耗模型；A100板卡测量参考；512输入+3584输出 | 分阶段、功率与token/J可追溯；最大batch对比须同时看单请求延迟和容量 |
| [Anda，HPCA 2025](https://arxiv.org/html/2411.15982v1) | LLaMA/Llama2/OPT；2048长度PPL；参考OmniQuant，另报BOPs | 16nm/0.8V/285MHz Genus与网表VCD，周期模拟器；HBM2 3.9pJ/bit | 重点FP-INT GEMM；BOPs减少不等于完整模型同倍率加速 |
| [LLMCompass，ISCA 2024](https://github.com/PrincetonUniversity/LLMCompass) | dense模型形状/映射，实机性能校验 | tile级模型与局部周期估计，面积/成本；v1报告LLM平均时延误差4.1% | 证明高层模型可校准；4.1%不是能量误差，框架也不自动给出本p-bit PPA |
| [Splitwise，ISCA 2024](https://www.microsoft.com/en-us/research/wp-content/uploads/2023/12/Splitwise_ISCA24.pdf) | BLOOM176B / Llama70B与请求分布 | 实机profiling+离散事件；TTFT/TBT/E2E、SLO；性能模型MAPE<3% | 服务调度研究；资源功率预算不是每请求实测能量 |
| [DS-CIM，DATE 2026](https://arxiv.org/html/2601.06724v1) | FP8 LLaMA7B误差注入，六任务acc；不报PPL | 40nm定制单元、DC/Innovus/Virtuoso后仿真；1b/40nm归一化峰值 | T256质量点不能搭配T64最高能效点；不是完整LLM/DRAM仿真 |
| [ARTEMIS，CASES/TCAD 2024](https://arxiv.org/pdf/2407.12638) | BERT等；OPT-350负载用BLEU，非PPL | Python逐层映射；LTSPICE、Genus、CACTI-3D；HBM ACT及数据路径能量表 | 随机乘法和模拟累加的相关参考，不能当7B自回归整机质量对照 |
| [SCARLET，DATE 2026](https://www.bu.edu/peaclab/files/2026/03/SCARLET_CameraReady.pdf) | OPT/Llama2/GPTNeo；WikiText下一token准确率 | OPCM/动态光乘、转换/激光等成本；SRAM从GF22FDX缩至7nm；HBM 20pJ/bit | token准确率不等于PPL；数字节点归一化不能覆盖整套光子器件 |
| [HSA，ISLPED 2025](https://arxiv.org/html/2507.09010v1) | 硬件主模型RetNet1.3B；量化质量另含Llama的PPL/GSM8K | 28nm后布局VCS/PT；分prefill/decode，外存32pJ/Byte | token统计含输入输出；不能把RetNet的PPA与另一个Llama质量点绑定 |
| [SANTA，ICML 2026](https://arxiv.org/html/2605.01910v2) | Llama3.1-8B-Instruct，推理/长文本任务 | RTX6000Ada实测kernel及完整decode；稠密prefill | 是采样算法/软件直接基线；不是p-bit电路PPA基线 |

MBA来源：`509_Camera_Ready_Paper.pdf`，§6、Fig.7/8，DOI [10.1145/3770743.3803981](https://doi.org/10.1145/3770743.3803981)，原始文件SHA-256与本机索引在 PAPERS.json；不上传用户PDF。其峰值、端到端和buffer管理消融的收益范围应分开。

已有14篇模型选择审计的样本中，直接命名Llama家族9/14、Llama2 7/14、OPT 6/14，集合有重叠；这说明这些模型便于文献对接，不是全领域流行率。旧审计与新表样本不同，不把分母混合。旧源：本机 `pbit_llm_master_report_20261012/LLM_HARDWARE_BENCHMARK_MODEL_SAMPLE_20261017.json`。

## 3 “LLM benchmark”至少需要冻结五件事

1. **模型与数值语义**：checkpoint revision/hash、Base/Instruct、tokenizer、原生上下文、MHA/GQA、W/A/KV/accumulator位宽、尺度/舍入/溢出规则，哪些投影/非线性被替换。
2. **任务与计分**：数据版本/split/hash、raw拼接、prompt/chat模板、shot数、答案格式、评测代码commit/YAML、所有目标token或题目ID。
3. **执行工作负载**：prefill/decode范围、B、输入/输出长度或分布、cache增长/复位、固定token重放还是自由生成、EOS、warm/cold、是否包括加载。
4. **机器与映射**：计算资源、SRAM容量/bank/端口、外存容量/类型/带宽/时序、调度/融合、频率与随机源服务率；每种方案分别搜索合法映射。
5. **度量边界与证据**：时间戳起终点、能量电源域和面积边界、实现阶段/PVT、成本来源、校准误差、未覆盖项。

只给出“Llama2-7B / WT2 / 55nm”远远不够。相同SRAM容量、相同PE数与相同总面积是三个不同约束，不应同时默认成立。

### 有标准，但不能把标准中的单个数字移植过来

[MLPerf Inference 5.1小模型说明](https://mlcommons.org/2025/09/small-llm-inference-5-1/)采用Llama3.1-8B-Instruct、CNN/DailyMail摘要、ROUGE；closed division要求相应分数达到FP16参考的99%。该版本server约束TTFT≤2s/TPOT≤100ms，interactive为0.5s/30ms。它证明质量、任务和响应约束应一起冻结；**99% ROUGE不能解释成PPL允许增长1%，这些时延也不是所有ASIC论文的验收门槛**。本项目可以借鉴协议，不把自建TLM称为MLPerf合规提交。

[MLPerf公开功率规则](https://github.com/mlcommons/inference_policies/blob/master/power_measurement.adoc)测量SUT系统墙插功率；所读文件标记v2.0/2022。这里仅引用测量边界原则，不据此声称已逐条核查2026全部提交规则。NVML板卡能量与墙插能量不是同一个指标。

## 4 质量指标应怎样组合

| 指标 | 检查什么 | 建议用途及限制 |
|---|---|---|
| token PPL / NLL | 正确后续token的概率 | 连续、对概率误差敏感；主质量曲线；必须相同tokenizer/目标集合/上下文 |
| acc | 任务答案是否判对 | ARC/PIQA等实际任务；多选loglikelihood与自由生成须区分 |
| acc_norm | 候选总loglikelihood归一化后判对 | 与acc同时保留；不能在看到结果后挑更有利的一项 |
| EM / QA F1 | 生成答案的精确匹配或规范化重叠 | 长文本问答；固定规范化代码、最大输出和截断规则 |
| ROUGE / BLEU | 与参考生成文本的重叠 | 摘要/翻译等适用任务；不是通用LLM概率指标 |
| NMSE、分布距离、相关性、ESS | 局部数值/采样误差 | 解释硬件；不能取代完整模型PPL和任务分数 |

`PPL = exp(总NLL / 有效预测token数)`；
`ΔNLL = ln(PPL_new / PPL_ref)`。
相对PPL增加5%对应约0.04879 nat/token，与任务准确率下降5%无换算关系。不同tokenizer、不同语言/语料的原始PPL不可直接横比。[PPL定义与滑窗影响](https://huggingface.co/docs/transformers/perplexity)

随机方案保留每seed的NLL、目标数、PPL与任务逐题记录；声明报告的是PPL算术均值，还是先平均NLL再指数。把多seed预测概率平均后再计分属于另一种ensemble算法，若硬件没做ensemble则不能用它的分数。

**本报告不规定“DAC允许PPL增加多少”。** 可提议PPL相对变化1%/3%/5%曲线作为工程预算，但正式非劣阈值尚未确定；任务还需逐项约束，不能只看平均。原文中Kelle的Llama2-13B WT2为4.88→5.62，约15.16%增加；这证明发表工作存在不同取舍，不能反过来当我们的容忍授权。[Kelle Table2](https://www.saiqianzhang.com/gallery/Kelle_Camera_Ready.pdf)

统计上区分三件事：跨seed方差、有限题集不确定性、硬件成本估计误差。任务差分使用同题配对的对→错/错→对记录及配对区间；PPL可用文本段/文档的配对重采样，不能把相关token简单当独立样本。至少3seed是本项目现有最低重复规范，不意味着已充分证明等价。

### 必须让质量评测执行实际替换路径

decode-only Attention若在 `q_len==1` 才触发，普通整窗teacher-forcing可能完全绕过它。需要记录各层prefill/decode调用、active/dummy、候选比例和目标覆盖。短题all-K下精度好，不能证明8K筛选有效；理想CTMC、准确Softmax后IID采样、新赢家保持/拒绝法和真实RNG是不同实现配置。

## 5 性能与能量的统一定义

请求到达a，第1个输出t1，第G个输出tG：

- `TTFT=t1-a`；设备执行起点版本另称device TTFT，避免混入/漏掉排队。
- `TPOT=(tG-t1)/(G-1)`，G>1；G=1时不定义TPOT。ITL为逐个相邻输出间隔，另给p50/p95/p99。
- `E2E=tG-a`；batch输出吞吐=`ΣG_i / 批次测量时间`，不是单请求TPOT的倒数。
- `decode J/output_token=E_decode / N_decode_output`；
  `request J/output_token=E_request / ΣG_i`。两者分子范围不同。
- `平均功率=E/测量时长`，不能用TDP替代；`EDP=E×T`，`AEDP=A×E×T`，同时保留各原量。

prefill通常已产生首token所需logits。模拟器若定义“prefill仅建KV，再做G次decode”，必须记录首token约定；不能把G与G−1个间隔混用。阶段交接、源启动、KV布局/筛选摘要构建、cache flush、DMA、主机处理按实际边界计入。重叠时间用关键路径，不把各模块服务时间直接相加。

固定token重放适合相同物理工作量的性能/活动比较；真实闭环生成适合应用验证。近似模型自由生成后token及EOS会分叉，应分别报告实际长度和质量；不能强迫所有输出相同再声称闭环生成质量保持。PPL、multiple-choice评分、整窗prefill也不自动等同完整生成请求。

## 6 PPA要到什么证据层级

PPA是功耗、性能和面积；任务能量另用J/请求或J/输出token表示。降低平均功率但延长执行时间，未必节能。面积效率也应明确采用输出token/s/mm²还是算子TOPS/mm²。

| 层级 | 能支持的结论 | 仍需补什么 |
|---|---|---|
| 操作账本+文献pJ/op | 给定假设下的趋势、数量级 | 数据搬运、活动、状态、物理成本和校准 |
| RTL综合+网表活动+PT/同类工具 | 给定库/PVT和活动下的模块P/A与时序估计 | 线RC、CTS/扇出、宏外围、真实调度 |
| P&R+CTS+提取寄生+代表活动 | 更有把握的模块/子系统PPA | 系统组合、外存/PHY、电源域与实际工作量 |
| 资源/事件/TLM或周期模型+上述成本库 | 给定配置的全模型时延/能量估计 | 接口校验、来源误差、未覆盖项 |
| 芯片或板卡测量 | 对应设备/软件/工作负载的实测 | 不同设备之间仍须对齐边界和质量 |

不是要求整个LLM逐门仿真，也不是只要写了cycle-accurate就足够。LLMCompass与Splitwise分别用更高层模型并校验性能；误差不能从时延自动外推到能量。对于本设计，长采样、反馈、回压和动态稀疏访存会影响收益的局部路径，应使用足够细的资源/事件乃至周期模型，再用RTL/详细内存子集交叉核验。[LLMCompass v1方法](https://arxiv.org/html/2312.03134v1)、[Splitwise §V-B](https://www.microsoft.com/en-us/research/wp-content/uploads/2023/12/Splitwise_ISCA24.pdf)

本项目主对照应尽量在现有可用PDK/相同PVT/同阶段流程中实现数字和概率模块。完整列出工艺/库/Vt、电压/温度、频率与时序裕量、活动来源、寄生/时钟树状态。SS角不自动等于最大功耗角。面积分别给cell、macro、core/die及利用率；外部DRAM/stack/chiplet面积单列，不能把所有层投影面积直接加成单die面积。

跨节点文献表可保留原值和标注的投影值，但不能把GPU整体“折成55nm”后声称实现优势。[DeepScaleTool](https://arxiv.org/pdf/2102.10195)是根据工业数据拟合的数字技术缩放模型；它不等于目标PDK重做，也不能自动缩放HBM、FeFET、MTJ或光子外围。若做投影，给出每类对象的系数、工具版本、原/目标条件、是否缩能量或功率/频率及敏感性。

### 能量账本需要闭合

`E = Σ(动作数×每动作增量能量) + Σ(状态功率×状态持续时间)`。

如果动作单价已包含某段总能量，不能再次加同段背景能量。等待、源持续偏置、clock gating、唤醒、刷新和漏电单独定义。面积按物理实例求和，不按模型展开的操作数求和。

至少拆成：数字计算、随机计算、原始熵/PRNG/扩展/分发、概率比较/编码/归约、BF16↔定点转换与尺度恢复、非线性、片上存储、NoC/DMA/控制、DRAM core、DRAM I/O/PHY、其他电源域。未知项用null和覆盖率说明；不能填零后输出“完整能量”。

TOPS/W补充表写清：MAC算1还是2ops、W/A位宽、SC时间长度/空间复制、真实硬件bitops与有效dense等价ops、稀疏率、峰值/实际利用率。用同一个sample完成多个输出的计费规则也应固定。不能以1b峰值除以全模型BF16 FLOPs得到可信J/token。

“距离下界”也应附带条件：在固定算法、质量、资源和计费模型下，分别构造计算吞吐、必需访存、随机服务和依赖链的合法下界，取其最大值作为时间下界，再报告T/T_LB−1。某次映射的实际字节量不能直接冒称所有映射的最小字节量；无限缓存、理想重叠或免费独立随机数的下界须显式标注。接近该下界只说明接近所声明模型的限制，不能证明物理实现或所有LLM部署最优。

## 7 DRAM功耗尤其不能只写“用了模拟器”

| 方法 | 原文例子 | 如何看待 |
|---|---|---|
| 字节/bit × 固定能量 | MBA/Anda各采用3.9pJ/bit；HSA外存32pJ/Byte；SCARLET20pJ/bit | 有明显不同的来源和范围；不能挑最低系数，需核对供电域、数据路径与是否含背景 |
| 命令+状态模型 | NeuPIMs的DRAMsim3/Micron，额外PIM功率假设 | 可体现ACT/PRE/RD/WR/REF和等待；新计算命令仍要另外标定 |
| 厂商平均活动计算器 | MoNDE的Micron DDR4计算器与电压调整 | 工程估计，不等同目标LPDDR测量 |
| 电路/路径成本表 | ARTEMIS、AttAcc | 能支持新PIM数据路径，需说明缩放和未覆盖外围 |

细粒度模型建议沿用现有DRAMSys/DRAMPower接口，而非为统一名称重写内存模型；版本、标准、器件组织、IDD/V、bank/row映射、burst、控制策略和命令trace必须冻结。[DRAMPower官方说明](https://github.com/tukl-msd/DRAMPower)明确它不检查命令时序合法性，I/O还涉及独立计费字段，因此“跑出DRAMPower数字”并不是有效trace和完整PHY的证明。

对采样Attention至少同时保存逻辑访问数、去重后V行数、SRAM命中、实际DRAM请求字节、ACT/PRE/row-hit/队列stall。S个样本不等于S次外存读取，也不保证流量正比于S；GQA共享、重复索引、burst浪费、row locality都改变结果。随机FFN若tile驻留，T拍不应每拍重复读外存权重；但变长的执行时间可能增加DRAM背景能量。

## 8 建议本项目采用的最小benchmark

**主线：Qwen2.5-0.5B Base用于快速数值/接口闭环，Llama2-7B Base用于模型规模与MHA对照。** 已有LLaMA-1保留历史兼容。现代GQA可选增加Llama3.1-8B，但须先落实checkpoint与计算预算，不能用只跑形状的结果冒充其质量；本轮不下载或启动新模型。

| 层次 | 建议内容 | 验证目的 |
|---|---|---|
| 算术/模块 | 真实层张量；GEMV/GEMM、SwiGLU、QK/归一化/PV、RNG、转换；覆盖零、outlier、偏斜概率与端点 | 对齐软件语义、RTL活动、动作单价；64×64不是必须固定的benchmark |
| 完整模型质量 | 完整WT2滑窗PPL/NLL；PIQA、ARC-E主任务；Qwen的HellaSwag1000明确是子集，后续完整版本另立协议 | 复用现有证据，排查FFN/Attention联合误差 |
| 长上下文质量 | 若主张筛选/KV节省，补固定的LongBench问答/检索任务，记录EM/F1与有效长度 | 短题全保留K不能证明稀疏筛选 |
| 固定工作量性能 | B=1、4；输入/输出128/512、2048/128；Qwen另加8192/128；固定cache 2K/8K decode诊断另列 | 同时观察prefill-heavy/decode-heavy、GQA与存储瓶颈 |
| 资源/映射扩展 | B16为可行时的补充；SRAM/DRAM带宽、tile/并行度、流长/采样数扫描 | 找Pareto前沿，检验容量和排队；不得静默换资源 |
| 应用与GPU | 固定真实prompt集合，自由生成；GPU保留既有栈并增加优化栈对照时另记版本 | 应用价值与外部参考；不把GPU上的p-bit软件仿真当p-bit硬件 |

所有工作负载先检查 `input+output <= 所选checkpoint允许上下文`；Llama2原生4K不默认跑8K。LLaMA-1旧2K模型也不能直接套2048+128；应缩输入或另立扩展上下文协议。固定2K cache诊断和2048输入后增长128步是不同曲线。模型/任务版本与hash应复用经过核验的manifest，不靠本报告重新猜填。

### 对照组与消融

- BF16完整数字模型；匹配W8/激活编码、尺度和接口的确定性数字模型。
- FFN-only、Attention-only、联合版本，各自保留可复算质量和硬件配置。
- RNG先对照理想参考、LFSR/共享扩展、替代PRNG，再接物理源模型；数字SC与物理p-bit贡献分开。
- 同资源预算对照让数字和p-bit各自优化合法映射；另做总面积/存储/带宽预算一致的设计空间比较。两种实验分开命名。
- 数字低位/确定性查表或稀疏算法是可选强基线，需满足相同质量；不能只与未优化BF16做核心能效比较。
- 对Attention将“准确分布后采V”“筛选K”“有限时间归一化/采样器”逐项消融；计入筛选器、索引、重排、转换与随机源。

随机源的原始bit率、逻辑随机字、比较概率bit、样本观察次数与ESS分别报告。共享扩展不会凭空增加物理熵；分层序列也不能称物理IID。ESS需对应具体估计量与相关序列，非平稳/有偏链还需检查分布偏差；不能把S直接当成S个独立类别样本。PVT可能同时改变翻转速度、相关性和功耗，质量与成本须一起变化。

建议主图使用“质量损失—J/output token”“质量损失—TPOT”与等面积前沿；每点一个配置ID。PPA表同一行链接该配置的质量记录。若某点只有成本预测或只有局部QKV误差，明确留空另一半，不从其他流长/算法拼接。

## 9 与我们现有结果怎样衔接

| 已有证据（冻结基线） | 能支持什么 | 尚不能支持什么 |
|---|---|---|
| [Qwen39项任务](../../qwen/results/task_accuracy_20261019/RESULTS_ZH.md) | PIQA/ARC-E完整；HellaSwag固定1000子集；旧有限CTMC和四档T32 FFN联合质量 | 新赢家/拒绝法、长上下文筛选、真实RNG、完整硬件PPA |
| [Llama2最终26项/官方oracle](../../llama2/results/task_accuracy_20261020/FINAL_RESULTS_20261022_ZH.md) | 两个完整任务、三seed替换，已逐题核验；非旧pending | 没有在这批结果中测新采样器；短题all-K不证明长KV节省 |
| Qwen完整联合PPL，见既有Issue50/PR52及结果索引 | 同轮cached BF16、FFN-only、联合S128/256/512 | S256/S512缺匹配原FFN完整Attention-only控制；不能算全部交互项 |
| [新采样器v5 TLM](../PARALLEL_SAMPLERS_V5_ZH.md)、真实QKV结果 | 局部误差、明确资源下的时序与动作 | 新采样器整模型PPL、目标PVT下完整能量/面积仍缺 |
| [现有SRAM校准](../SRAM_CACTI_CALIBRATION_V1_RESULTS_ZH_20261016.txt) | 实际宏优先查表、未知尺寸带误差估计 | H独立验证读能量约9.3–9.5%误差，写能量64–73%；不能统称全部≤10% |
| [旧成本来源](../configs/cost_provenance.json)与各新版本manifest | 识别旧2pJ/MAC代理、历史55nm SC活动标定和参数情景 | 不能把旧T4096核心系数无条件移植到新T32、共享源或新采样器 |
| [Issue95 / PR97](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/95) | 本地随机源操作模型、核心RTL和供用户EDA的输入 | RTL匹配不等于物理熵/PPL/PPA验收；未知成本保留null |
| [Issue96](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/96) | 正在接统一整模型TLM；本协议可提供输出/对齐字段 | 本报告不接管其实现，不预报它尚未完成的数字 |
| 本机GPU 20261011报告 | RTX5090、Qwen0.5B/B1、SDPA/eager、真实token重放的板卡能量 | 非自由生成请求、非优化GPU下界、非墙插；模块独立重放不可相加当分摊 |

一个可以直接利用的质量例子：Llama2新最终表中，FFN-only的PIQA acc_norm与BF16同为78.99891%，但联合S128为77.87450%，差−1.12441个百分点；联合S512为78.67247%，差−0.32644个百分点。这是两任务协议下旧有限CTMC结果，不是新采样器已达成同样精度。不能只选ARC-E或只选acc_norm宣布整模型无损。

GPU历史2K decode为14.033ms/步、1.8832J/步，测量窗口cache2048–2175；含全部层与lm_head，不含CPU选词/tokenizer等。它是**已有GPU真实测量**，不是算子单价推算；比较ASIC时应匹配这段工作量与电源边界，同时另给同库数字ASIC对照。本机证据：`gpu_energy_20261011/GPU_ENERGY_REPORT_ZH.txt`。不要用仅FFN理想并行时间或不同质量T64条件点与其合成“整机更快更省电”结论。

## 10 最值得先落实的交付顺序

1. **冻结一个可联结的配置清单。** 每个quality_run_id / hardware_config_id / rng_config_id / workload_id绑定同一个design_point_id。先复用已有manifest，列出不匹配，不重复昂贵评测。
2. **统一结果表。** 主列为模型、任务质量与区间、B/长度、TTFT、TPOT、输出吞吐、分阶段与总J、PVT/证据层级、面积边界、成本覆盖率。结构化字段见JSON提议。
3. **先补同工艺数字对照和缺失外围成本。** 优先实际库、代表张量活动；关键共享分发、反馈、归约、转换路径尽量P&R/CTS验证。未知部分先做明确情景和敏感性，别伪造完整PPA。
4. **复用Issue96系统调度和现有外存后端。** 校验依赖、并发、SRAM端口/容量、GQA、实际burst与背景功耗；找代表点与RTL/详细DRAM交叉核验，报告各指标误差。
5. **在相同质量约束下比较前沿。** 质量预算待预先确定；完整任务和长上下文证据匹配后，再挑最终硬件点。论文主结果给绝对值及对照倍率，峰值和节点投影放辅助表。

本轮完成的是可审查的调研与协议提议。没有改变质量阈值、没有新实验结果，也没有宣称现有TLM已完成完整芯片PPA标定。
