# 新架构与新器件LLM论文的测试任务和质量指标对照

更新日期：2026-10-19。

本文按论文列出前一轮调研中实际采用的模型、测试任务和质量指标，再解释各任务测试什么能力。重点覆盖DAC、MICRO、HPCA，补充与随机计算、PCM相关的DATE、CASES和器件研究。这是定向样本对照，不能据此统计整个领域采用某指标的比例。

**任务名称不等于指标名称。** ARC、BoolQ、WikiText是任务或数据集；Accuracy、F1、EM、PPL才是指标。同一数据集在不同任务变体、提示模板和评分脚本下，分数也不能直接比较。

## 1 各篇论文采用的任务

| 论文与出处 | 架构或器件 | 用于质量评价的模型 | 实际任务及指标 | 原文位置与范围 |
|---|---|---|---|---|
| [DS-CIM，DATE 2026](https://arxiv.org/html/2601.06724v1) | SRAM数字随机CIM、共享PRNG、互斥OR | LLaMA-7B | **BoolQ、PIQA、HellaSwag、WinoGrande、ARC-Easy、ARC-Challenge**；六项Accuracy及平均值 | §V-B、Table II。未报PPL；表头未区分`acc`与`acc_norm`。模型实验采用随机算术误差注入，不是物理p-bit整机实测 |
| [UniCAIM，DAC 2025](https://arxiv.org/html/2504.07479v1) | FeFET CAM/CIM、KV剪枝 | LongChat-v1.5-7B-32k | LongBench的**HotpotQA、NarrativeQA**；均为答案F1 | §IV-B、Fig.13。两个任务prompt约1.5K、2.5K；没有PPL。长上下文模型名称不表示每项质量测试都输入32K |
| [CQ-CiM，DAC 2026](https://arxiv.org/html/2602.20083v3) | 面向CiM非理想性的嵌入压缩与量化 | 主表all-MiniLM-L6-v2；泛化实验另用嵌入模型；端到端测试另接FP16 LLM | ArguAna、FiQA、CQADupStack（正文为CQADupStackGisRetrieval）、NanoHotpotQA、ARCChallenge等**检索任务**；Recall@5、nDCG@10；另有NanoFeverRetrieval的nDCG@5，以及相关文档选择Accuracy | §4、Table 2、Fig.6。LLM负责从top-5候选中选择相关文档；不能称为生成答案正确率或LLM内部存算质量 |
| [Kelle，MICRO 2025](https://www.saiqianzhang.com/gallery/Kelle_Camera_Ready.pdf) | eDRAM刷新、KV淘汰与重算、量化 | Llama 2、Llama 3/3.2、Mistral、Qwen2、OPT等 | **WikiText-2、PG19：PPL**；ARC-C/E、PIQA、LAMBADA、TriviaQA、Qasper：表中统称Accuracy；CNN/DailyMail：ROUGE-1；TruthfulQA：MC1；BBQ：bias evaluation scores | §7.1/7.2、Table 2/5。不同模型覆盖范围以原表为准；TriviaQA/Qasper评分细节和BBQ分数定义见第3节 |
| [SCARLET，DATE 2026](https://www.bu.edu/peaclab/files/2026/03/SCARLET_CameraReady.pdf) | 光学PCM、近似浮点乘法 | OPT-2.7/6.7/13B、Llama 2-7/13B、GPTNeo-2.7B | **WikiText：下一token预测Accuracy** | §IV-A/B、Fig.4。不是PPL；未锁定WT2/WT103与完整滑窗协议 |
| [ARTEMIS，CASES/TCAD 2024](https://arxiv.org/pdf/2407.12638) | 混合模拟与随机in-DRAM | OPT-350M、BERT-base、ALBERT-base；另有Transformer-base、ViT-base | **OPT：OpenAssistant-Guanaco，BLEU**；BERT/ALBERT：GLUE，作者称Accuracy；Transformer：TED-HRLR翻译，作者称Accuracy；ViT：ImageNet，作者称Accuracy | §IV-A、Table IV。未列GLUE子任务及聚合方式；翻译Accuracy口径、ImageNet top-k未明确，不能自行补写 |
| [Lightening-Transformer，HPCA 2024](https://scopex-asu.github.io/files/publications/ONN_HPCA2024_Gu.pdf) | 动态光子点积架构 | 8bit BERT-base；4bit DeiT-T | **BERT：SST-2情感分类Accuracy**；DeiT-T：ImageNet-1K图像分类Accuracy | §V-E、Fig.14。质量参照为同位宽无噪GPU，使用噪声感知训练；性能表中的更多模型不自动构成对应质量验证 |
| [Analog Foundation Models，2025公开论文v3](https://arxiv.org/html/2505.09663v3) | PCM噪声模型、模拟存算、硬件感知训练 | Phi-3-mini-4k-instruct、Llama-3.2-1B-Instruct；附录另有RoBERTa | 主表九项：**MMLU、GSM8K、BoolQ、HellaSwag、MedQA、AGIEval、ARC-C、ARC-E、ANLI**；任务正确率及均值。另有MATH-500、IFEval、XSTest及附录GLUE | Table 1、Appendix A/E、Table 14。附加任务不计入九任务均值；不是PPL，也不是全模型芯片执行。详细协议见第3节 |
| [14nm PCM ALBERT，Nature Communications 2025](https://www.nature.com/articles/s41467-025-63794-4) | 实测PCM芯片、漂移补偿、硬件感知微调 | ALBERT | **RTE、MRPC、CoLA、SST-2、QNLI、QQP、MNLI**；该文七项统一采用分类Accuracy | Fig.3/4。包括CoLA也用Accuracy，不能当作官方GLUE综合分。是encoder任务，非自回归LLM生成 |
| [ASADI，HPCA 2024](https://www.comp.nus.edu.sg/~tulika/HPCA24.pdf) | ReRAM模拟/数字存内稀疏注意力 | BERT/BART/GPT-2等工作负载 | 列出九项GLUE、SQuAD v1.1、WikiText-2、IMDB、ImageNet-1K；**已核主文未找到新的应用质量数值表** | §VI-A。只能记为工作负载清单，不能据任务名补出PPL/F1结果；Syn-4K/8K仅用于时延、能耗 |
| [3D-CIMlet，DAC 2025](https://engineering.purdue.edu/NanoX/assets/pdf/2025_DAC_3D-CIMlet_AAM.pdf) | RRAM/eDRAM异构chiplet | 含GPT-2等映射工作负载 | 列出GPT-2/WikiText-2等；取得的作者主文主要给出映射、能量、时延、热和可靠性评价 | §V。未找到新PPL或任务质量表，不据此推定质量指标或容错门槛 |

前九项包含明确的应用质量评价；后两项保留在表内，是为了区分“列出测试工作负载”和“实际报告该任务质量”。图像分类、encoder理解、生成式LLM和嵌入检索分别对应不同应用范围。

## 2 每种任务测试什么能力

### 2.1 常识 知识和推理

| 任务 | 模型要完成的事情 | 对应指标 | 本轮使用它的论文 |
|---|---|---|---|
| BoolQ | 阅读段落，回答是或否 | 二分类正确率 | DS-CIM、Analog Foundation Models |
| PIQA | 从两个方案中选择能完成物理目标的方案 | 选择题正确率 | DS-CIM、Kelle |
| HellaSwag | 从四个结尾中选择合理的事件续写 | 选择题正确率 | DS-CIM、Analog Foundation Models |
| WinoGrande | 二选一完成指代消歧或句子填空 | 选择题正确率 | DS-CIM |
| ARC-Easy / ARC-Challenge | 回答学校科学选择题；Easy和Challenge是不同子集 | 选择题正确率 | DS-CIM、Kelle、Analog Foundation Models |
| MMLU | 回答多个学科的知识和推理选择题 | 各科正确率及聚合分数 | Analog Foundation Models |
| MedQA | 回答医学考试选择题 | 选择题正确率 | Analog Foundation Models |
| AGIEval | 回答标准化人类考试题；该文采用选择题计分 | 选择题正确率 | Analog Foundation Models |
| ANLI | 判断前提和假设之间是蕴含、中立还是矛盾 | 三分类正确率 | Analog Foundation Models |
| GSM8K | 解答小学数学应用题，生成最终数值答案 | 提取最终答案后计算答对比例 | Analog Foundation Models |
| MATH-500 | 解答较难的数学问题 | 最终答案正确率 | Analog Foundation Models补充实验 |
| LAMBADA | 根据较长上下文补出最后一个词 | 最后一个词预测正确率 | Kelle |
| TruthfulQA | 回答容易受到常见错误认知影响的问题 | Kelle采用MC1，即单答案选择题正确率 | Kelle |

这里的“选择题正确率”描述任务输出的含义，不预设论文都采用相同的选项打分代码。例如`acc_norm`通常先按候选答案长度归一化似然，再选答案；它不是扣除随机猜测基线后的正确率。DS-CIM未给出足够信息将其表中Accuracy进一步锁定为`acc`或`acc_norm`。[DS-CIM](https://arxiv.org/html/2601.06724v1)、[AFM评测细节](https://arxiv.org/html/2505.09663v3)、[Harness HellaSwag配置](https://github.com/EleutherAI/lm-evaluation-harness/blob/main/lm_eval/tasks/hellaswag/hellaswag.yaml)

### 2.2 语言建模 阅读问答和生成

| 任务 | 测试内容 | 指标怎样理解 | 论文或协议 |
|---|---|---|---|
| WikiText-2、PG19 | 连续文本语言建模 | **PPL越低越好**；检查模型赋给真实下一token的概率 | Kelle |
| WikiText下一token预测 | 逐位置比较概率最大的token和真实token | **Token Accuracy越高越好**；只判断最高分token是否命中 | SCARLET |
| HotpotQA | 联合多份材料做多跳问答 | 答案F1：预测答案和参考答案的词重叠 | UniCAIM / LongBench |
| NarrativeQA | 阅读故事或剧本后回答问题 | 答案F1 | UniCAIM / LongBench |
| Qasper | 科研论文问答，有自由回答、是非题等变体 | 自由回答常用答案F1；具体输入范围及变体要单列 | Kelle只统称Accuracy，不能据此确认其F1口径 |
| TriviaQA | 事实性知识问答 | 可采用标准化EM或答案F1，依协议而定 | Kelle未锁定评分细节；当前Harness默认EM，LongBench采用F1 |
| CNN/DailyMail | 根据新闻正文生成摘要 | Kelle采用ROUGE-1，衡量与参考摘要的单词重叠 | Kelle |
| OpenAssistant-Guanaco | 根据指令生成回答 | ARTEMIS采用BLEU，衡量与参考回答的连续词组重叠 | ARTEMIS |
| TED-HRLR | 机器翻译 | ARTEMIS称Accuracy，但没有给出足以区分token或整句正确率的定义 | ARTEMIS；不能自行改写成BLEU |

**EM**检查标准化后的答案是否完全匹配；**问答F1**允许部分词重叠得分；**ROUGE/BLEU**是文本重叠指标，都不能直接解释为事实正确率。PPL与Token Accuracy也不能互换：最高概率token不变时，真实token的概率仍可能下降。[LongBench官方任务表](https://github.com/THUDM/LongBench/blob/main/LongBench/task_zh.md)、[TriviaQA默认EM配置](https://github.com/EleutherAI/lm-evaluation-harness/blob/main/lm_eval/tasks/triviaqa/default.yaml)、[ARTEMIS Table IV](https://arxiv.org/pdf/2407.12638)

### 2.3 GLUE语言理解

| 任务 | 测试内容 | 官方GLUE常用指标 | 本轮论文采用的口径 |
|---|---|---|---|
| SST-2 | 影评正面或负面情感分类 | Accuracy | PCM ALBERT、Lightening-Transformer用Accuracy |
| CoLA | 判断句子的语法可接受性 | **MCC，马修斯相关系数** | PCM ALBERT用Accuracy；AFM附录RoBERTa用MCC |
| MRPC | 判断两句话是否表达相同意思 | Accuracy、分类F1 | PCM ALBERT和AFM附录RoBERTa用Accuracy |
| QQP | 判断两个问题是否语义重复 | Accuracy、分类F1 | 同上 |
| MNLI | 判断蕴含、中立、矛盾 | 匹配/不匹配域的Accuracy | PCM ALBERT和AFM附录RoBERTa用Accuracy |
| QNLI | 判断句子是否包含问题答案 | Accuracy | 同上 |
| RTE | 判断一段文本是否能推出另一段文本 | Accuracy | 同上 |
| STS-B | 判断两句话的语义相似程度 | Pearson、Spearman相关系数 | ASADI列为工作负载；没有确认新的质量分数 |
| WNLI | 由指代消歧改写的蕴含判断 | Accuracy | ASADI列为工作负载；没有确认新的质量分数 |

GLUE本身是一组任务，不是单一准确率。PCM ALBERT的七项分类Accuracy、官方GLUE各任务指标，以及ARTEMIS未展开子任务的“GLUE Accuracy”不能视为相同口径。这里的**分类F1**根据预测类别统计precision/recall，与上文**答案词重叠F1**不同。[GLUE原始论文](https://arxiv.org/pdf/1804.07461)、[PCM ALBERT Fig.3](https://www.nature.com/articles/s41467-025-63794-4)、[AFM Appendix A](https://arxiv.org/html/2505.09663v3)

### 2.4 检索 指令遵循和安全

| 任务 | 实际评价对象 | 指标及方向 | 对应论文 |
|---|---|---|---|
| ArguAna、FiQA、CQADupStack等文档检索 | 相关文档是否被找回、排序是否合理 | Recall@k：相关文档进入前k名的比例；nDCG@k：考虑排序位置和相关性的归一化得分，均越高越好 | CQ-CiM |
| 从top-5候选中选择相关文档 | LLM是否选中正确文档 | 文档选择Accuracy越高越好；不是自由生成答案的EM/F1 | CQ-CiM |
| IFEval | 是否遵守字数、格式、关键词等可检验指令 | instruction-level或prompt-level通过率；后者通常要求该提示的全部约束通过；还需固定strict/loose版本 | Analog Foundation Models |
| XSTest | 对有害请求拒绝、对正常请求避免误拒 | IPRR为有害提示拒绝率，越高越好；VPRR为正常提示误拒率，越低越好 | Analog Foundation Models |
| BBQ | 有或缺乏充分证据时，回答是否受社会偏见影响 | 常涉及答题与偏见评价；Kelle只称bias evaluation scores，未给公式 | Kelle；不能把其95.21直接解释成95.21%的“无偏率” |

同名语料可能被重新构造成不同任务。CQ-CiM中的ARCChallenge或NanoHotpotQA是检索评价，不能直接与DS-CIM的ARC选择题、UniCAIM的HotpotQA生成问答比较。[CQ-CiM §4](https://arxiv.org/html/2602.20083v3)、[AFM Appendix E](https://arxiv.org/html/2505.09663v3)、[Kelle §7.2](https://www.saiqianzhang.com/gallery/Kelle_Camera_Ready.pdf)

## 3 复现和引用时需要保留的论文细节

**DS-CIM。** 六任务集合是BoolQ、PIQA、HellaSwag、WinoGrande、ARC-E、ARC-C。不要加入MMLU/GSM8K，也不要把六项均分解释成PPL。论文中的Accuracy没有进一步明确`acc`或`acc_norm`。[Table II](https://arxiv.org/html/2601.06724v1)

**Kelle。** Table 2的六个下游列是ARC-C、ARC-E、PIQA、LAMBADA、TriviaQA、Qasper。前四项任务含义明确；后两项不能只凭表头Accuracy判断评分脚本。当前Harness的TriviaQA默认采用标准化EM；Qasper freeform采用token-F1，而且该配置仅给标题和摘要、只覆盖自由回答子集。它们不能倒推为Kelle未锁版本的完整协议。Table 5的CNN/DailyMail明确是ROUGE-1，TruthfulQA明确是MC1；BBQ仅称偏见评价分数。[Kelle §7.1/7.2](https://www.saiqianzhang.com/gallery/Kelle_Camera_Ready.pdf)、[Qasper freeform官方配置](https://github.com/EleutherAI/lm-evaluation-harness/blob/main/lm_eval/tasks/qasper/freeform.yaml)

**Analog Foundation Models。** Table 1九任务的示例数依次为：MMLU 5-shot、GSM8K CoT 8-shot、BoolQ 0-shot、HellaSwag 5-shot、MedQA 2-shot、AGIEval 0-shot、ARC-C/E各10-shot、ANLI 7-shot。GSM8K生成答案后计分，不能与候选答案似然选择混为同一种推理流程。MATH-500、IFEval、XSTest及附录RoBERTa的GLUE不属于主表九任务均值。[固定版本v3，Table 1与Appendix E](https://arxiv.org/html/2505.09663v3)

**ARTEMIS。** 原文只写BERT/ALBERT使用GLUE，未展开子任务及综合方式；不能替它补成PCM ALBERT的七项集合。Transformer-base翻译列也不能因为常见翻译工作使用BLEU，就把原文Accuracy改写成BLEU。[Table IV](https://arxiv.org/pdf/2407.12638)

**SCARLET和Lightening-Transformer。** 前者的WikiText Token Accuracy不能换算成PPL变化；后者的BERT/DeiT质量点参照同位宽GPU，不能当成相对原始浮点生成LLM的损失。这两种口径都不提供一个可直接迁移到Qwen的PPL容差。[SCARLET Fig.4](https://www.bu.edu/peaclab/files/2026/03/SCARLET_CameraReady.pdf)、[Lightening-Transformer §V-E](https://scopex-asu.github.io/files/publications/ONN_HPCA2024_Gu.pdf)

## 4 非LLM样本与尚需补全文的论文

| 论文 | 本轮能够确认的任务范围 | 如何使用 |
|---|---|---|
| [All-in-Memory Stochastic Computing using ReRAM，DAC 2025](https://esim-project.eu/files/Images/people/chair-cc/publications/2506_deLima_DAC.pdf) | 图像合成、插值、matting，使用SSIM/PSNR等；没有LLM任务 | 可参考随机ReRAM电路与图像质量取舍，不能当作LLM准确率或PPL证据 |
| [VQT-CiM，DAC 2025](https://doi.org/10.1109/DAC63849.2025.11133264) | 已确认论文身份，尚缺可核的完整任务与质量表 | 保留下载入口；不补猜具体基准和容错数字 |
| [HEIRS，DAC 2024](https://doi.org/10.1145/3649329.3657327) | 同上 | 需核多任务集合、精度及RRAM误差进入应用评价的方式 |
| [DBC，DAC 2025](https://doi.org/10.1109/DAC63849.2025.11132851) | 同上 | 需核PCM漂移下的实际模型、任务、基线和寿命判定 |

## 5 本项目选择基准时的对应关系

完整WikiText-2 PPL对应现有连续语言建模基线；DS-CIM六任务适合增加常识答题对照；HotpotQA/NarrativeQA的答案F1适合补充长文注意力验证。它们分别反映不同能力，应逐项报告，不能互相换算或用一个均值代替所有结果。若只替换decode路径，评测也要实际触发该路径。

每项结果应记录模型/数据版本、任务变体、shot、提示模板、上下文长度、生成方式、评分脚本版本与实际指标名。Accuracy从80%降到78%是下降2个百分点；PPL相对变化按`PPL_new/PPL_ref - 1`计算，不能套用同一百分比解释。

质量预算和论文数值对照见[新器件与随机LLM架构的PPL及任务质量指标](EMERGING_LLM_QUALITY_METRICS_ZH_20261019.md)。
