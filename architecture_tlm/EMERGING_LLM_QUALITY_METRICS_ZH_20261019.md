# 新器件与随机LLM架构的PPL及任务质量指标

更新日期：2026-10-19。重点为DAC和体系结构会议，补充与随机计算、PCM直接相关的DATE、CASES及器件研究。

**“PPL相对增加5%以内较好”应作为本项目可选择的工程目标，不能称为DAC或新器件领域的统一标准。** 原文样本中既有超过5%的PPL增幅，也有只用问答F1、任务准确率、BLEU、检索指标或下一token准确率的工作。新器件主要增加了噪声、漂移、故障和校准等验证维度，并不自动改变应用质量的含义。

本次为定向原文核查，不统计全部会议论文的比例。没有用纯数字量化论文的损失水平代替RRAM/FeFET/PCM或随机计算的证据；没有把BERT、图像模型和现代生成LLM混作同一类验证。

## 1 原文样本的指标与验证范围

| 工作与出处 | 新结构或器件 | 应用质量实际看什么 | 证据及重要边界 |
|---|---|---|---|
| [UniCAIM，DAC 2025](https://arxiv.org/html/2504.07479v1) | FeFET CAM/CIM，静态与动态KV剪枝 | LongChat-v1.5-7B-32k，HotpotQA/NarrativeQA的F1 | §IV-B、Fig.13；没有PPL。应用剪枝质量与FeFET电路PPA分别评估 |
| [CQ-CiM，DAC 2026](https://arxiv.org/html/2602.20083v3) | 面向FeFET/ReRAM等的嵌入压缩、量化与抗噪 | Recall@5、nDCG@10/5、相关文档选择准确率 | §4、Table2、Fig.6；生成LLM保持FP16，不能视为其内部矩阵已上新器件 |
| [3D-CIMlet，DAC 2025](https://engineering.purdue.edu/NanoX/assets/pdf/2025_DAC_3D-CIMlet_AAM.pdf) | RRAM/eDRAM异构chiplet | 取得的作者主文主要评估映射、能量、时延、热和可靠性 | §V列GPT-2/WT2等工作负载，未找到新的PPL/任务质量表；不能据此推出误差容忍线 |
| [Kelle，MICRO 2025](https://www.saiqianzhang.com/gallery/Kelle_Camera_Ready.pdf) | eDRAM刷新、KV淘汰/重算、量化共同设计 | WT2/PG19 PPL，常识/问答与生成任务 | §7.1、Table2/5；有PPL超过5%的点；eDRAM不是RRAM/PCM |
| [Lightening-Transformer，HPCA 2024](https://scopex-asu.github.io/files/publications/ONN_HPCA2024_Gu.pdf) | 动态光子点积架构 | BERT-base/SST-2、DeiT-T/ImageNet准确率及噪声鲁棒性 | §V-E；质量基线为等位宽GPU，不能当作7B生成LLM对FP16的PPL损失 |
| [ASADI，HPCA 2024](https://www.comp.nus.edu.sg/~tulika/HPCA24.pdf) | ReRAM模拟/数字存内稀疏注意力 | 主文侧重性能与能耗 | Float32表示、1bit/cell；未找到新PPL/任务质量数值表。列出WT2不等于报告PPL |
| [ARTEMIS，CASES/TCAD 2024](https://arxiv.org/pdf/2407.12638) | 混合模拟与随机in-DRAM | BERT任务分数、OPT-350M BLEU；局部MAE另报 | §IV-A、TableIV，第9页；不是7B生成LLM的PPL验证 |
| [DS-CIM，DATE 2026](https://arxiv.org/html/2601.06724v1) | SRAM数字随机CIM、共享PRNG及互斥OR | LLaMA-7B六任务准确率 | §V-B、TableII；T256误差注入，不报PPL；不是物理p-bit阵列实测 |
| [SCARLET，DATE 2026](https://www.bu.edu/peaclab/files/2026/03/SCARLET_CameraReady.pdf) | 光学PCM和动态近似FP乘法 | WikiText下一token预测准确率 | §IV-A/B、Fig.4；没有PPL；未见漂移等器件误差进入该模型质量实验的证据 |
| [Analog Foundation Models，2025公开论文v3](https://arxiv.org/html/2505.09663v3) | PCM噪声模型下的模拟存算与硬件感知训练 | Phi-3-mini、Llama-3.2-1B的九任务分数、指令遵循等 | Table1；不是DAC/体系结构四会样本，作为现代LLM噪声鲁棒性补充；硬件噪声仿真非全模型芯片运行 |
| [14nm PCM ALBERT，Nature Communications 2025](https://www.nature.com/articles/s41467-025-63794-4.pdf) | 实测PCM芯片与硬件感知微调 | 七项GLUE任务、编程误差、30天漂移及补偿 | Fig.3/4；投影/FFN在芯片，动态注意力和其他运算由软件协作；不是7B自回归LLM |

DATE、CASES、ASP-DAC和DAC是不同会议。上表保留会议身份，不用“DAC相关”将它们合并统计。BERT和ViT的准确率可说明评价方法，不能直接决定Qwen/Llama的PPL门槛。

## 2 Kelle直接显示PPL并没有统一5%上限

*Kelle: Co-design KV Caching and eDRAM for Efficient LLM Serving in Edge Computing*的Table2（PDF第9页）给出下列结果。百分比由表中舍入后的数值复算，因此不是更高精度原始评测值。

| 模型和语料 | 原FP16 | Kelle | PPL绝对增加 | 相对增加 |
|---|---:|---:|---:|---:|
| Llama2-7B，WikiText-2 | 5.47 | 5.74 | 0.27 | 4.94% |
| Llama2-13B，WikiText-2 | 4.88 | 5.62 | 0.74 | 15.16% |
| Llama2-7B，PG19 | 10.51 | 12.59 | 2.08 | 19.79% |

同表Llama2-7B的ARC-Easy为74.62→72.78、PIQA为79.11→77.35，分别下降1.84、1.76个百分点。作者用comparable描述任务表现，未提出5%的PPL通用阈值。[作者全文](https://www.saiqianzhang.com/gallery/Kelle_Camera_Ready.pdf)

这些是W8A16、KV淘汰和模拟eDRAM retention故障等整套方案相对原FP16的总变化，不是单独器件噪声造成的变化。它证明已发表架构存在更大的PPL取舍，但不能据一篇论文推定其它设计的可接受损失。

## 3 随机计算论文的百分比需要重新识别

### DS-CIM报告的是六任务准确率

LLaMA-7B六任务平均分：Full precision为66.3%，FP8为66.0%，DS-CIM1为62.6%，DS-CIM2为58.8%。相对FP8分别损失3.4、7.2个百分点；换成相对下降为5.15%、10.91%。原文简写的3.4%/7.2%不应读成PPL增幅。[TableII、§V-B](https://arxiv.org/html/2601.06724v1)

该表使用256次采样对应的误差注入，包含FP8→INT8对齐和随机算术误差。最高能效的短流点不能直接与该质量点组成同一个操作点。对我们有用的做法是同时保留浮点与量化参考，再隔离随机计算额外造成的损失。

### ARTEMIS报告的是BLEU等任务分数

OPT-350M的BLEU为FP32 18.07→8bit 17.79→8bit+SC 17.49：相对FP32总损失0.58（3.21%），随机计算在量化之上额外损失0.30（1.69%）。这是生成文本的任务指标，不是PPL。[TableIV，PDF第9页](https://arxiv.org/pdf/2407.12638)

因此，“随机计算的应用精度下降约百分之一”必须带上任务、分数定义和参考精度，不能转换成“LLM PPL只能下降/上升百分之一”。

### DAC随机ReRAM论文不一定测试LLM

*All-in-Memory Stochastic Computing using ReRAM*（DAC 2025）的摘要提到平均5%的图像质量下降，但评估的是图像合成、插值和matting，使用SSIM/PSNR与故障场景。它没有LLM/PPL实验，其5%不能迁移为语言模型的容忍线。[作者全文，TableIV](https://esim-project.eu/files/Images/people/chair-cc/publications/2506_deLima_DAC.pdf)

## 4 FeFET和PCM为什么常用其它指标

UniCAIM验证的是稀疏KV下能否回答长文问答，所以使用F1。LongChat的HotpotQA、NarrativeQA实验prompt分别约1.5K和2.5K；Fig.13展示与full-cache接近的趋势，图未标精确数值，本报告不将目测值写成精确结果。它并未验证同等PPL可以损失多少。[UniCAIM §IV-B](https://arxiv.org/html/2504.07479v1)

CQ-CiM改的是嵌入检索：128维、2bit的ArguAna设置中，Vanilla的Recall@5/nDCG@10为0.468/0.385，CQ-CiM为0.529/0.433。其端到端实验让FP16 LLM从top-5候选选择相关文档，因此这些指标不能称为“把LLM内部换成FeFET后仍保持生成质量”。[CQ-CiM Table2、§4.4](https://arxiv.org/html/2602.20083v3)

SCARLET使用WikiText token-level下一token准确率，Fig.4(a)的Llama2-13B准确率差值为−0.11%（保留原图%口径）；它没有报告PPL，也没有给出足以复原WT2/WT103、window/stride等全部计分设置的信息。[作者全文 §IV](https://www.bu.edu/peaclab/files/2026/03/SCARLET_CameraReady.pdf)

下一token准确率只检查argmax，PPL还检查正确token的概率。即使所有argmax保持不变，正确token概率从0.8变成0.4，也会使这些位置的PPL加倍。这个数学例子说明两指标不能互换，不能用token准确率几乎不降证明PPL也几乎不变。

实测PCM ALBERT工作用七项GLUE任务验证，并将iso-accuracy定义为硬件准确率超过对应浮点准确率的99%；还单独研究漂移与重新校准。这里的目标依然是接近软件质量，只是指标适配encoder任务。[PCM ALBERT，第4–6页](https://www.nature.com/articles/s41467-025-63794-4.pdf)

## 5 新器件的基线可以不同但需要全部列出

Analog Foundation Models的Table1尤其能说明基线差异：Phi-3-mini的FP参考九任务均分70.03，模拟硬件噪声下的Analog FM为66.22，下降3.81个百分点；无噪声的静态输入8bit、权重4bit LLM-QAT参考为65.70。Analog FM这一点本身标为SI8–W16_hw_noise–O8，W4A8是比较对象；W16软件表示不等于模拟16bit有效精度。因此，“接近或优于W4A8参考”与“接近原FP16”是两个不同主张。[固定版本v3，Table1](https://arxiv.org/html/2505.09663v3)

Llama-3.2-1B的FP参考45.49→Analog FM噪声40.91，均分下降4.58个百分点，但GSM8K为45.79→30.75，下降15.04个百分点。平均损失不能代替逐任务检查。该工作有硬件感知再训练、静态输入/输出量化和10次噪声重复；不能作为无训练p-bit替换的直接容差。[同表及§3](https://arxiv.org/html/2505.09663v3)

我们的质量分解至少保留原BF16、匹配确定性量化、有限样本/器件误差这三层，并另外报告FFN-only、Attention-only与联合替换。在相同模型、分词器、语料、上下文和计分位置下，可用对数形式分解：

```text
随机相对BF16的NLL增加
= 确定性编码/量化相对BF16的NLL增加
+ 随机/器件路径相对该确定性参考的NLL增加

ΔNLL = ln(PPL_new / PPL_ref)
```

PPL相对上涨5%对应ΔNLL=ln(1.05)≈0.04879 nat/token。这只是数学换算，不表示下游准确率会下降5%，也不是器件允许的噪声百分比。

## 6 本项目的质量与性能应该怎样一起比较

建议把5%从“是否可发表”的判断改为预先声明的一个质量预算。可以展示PPL增幅≤1%、≤3%、≤5%三个工程档位，再保留更激进的探索点；这些数字是我们选择的比较条件，不是文献统计出的会议门槛。若论文主张接近原模型，应优先证明任务质量匹配，而不是只满足其中一个数。

| 层次 | 建议主指标 | 必须带出的条件 |
|---|---|---|
| 连续语言建模 | 完整WT2 PPL、原始NLL；可补第二语料 | 同模型/tokenizer、window/stride、目标token；随机至少3个独立运行 |
| 常识和推理 | ARC-E/C、PIQA、HellaSwag；较大模型可补MMLU等 | 固定shot/prompt/计分方式，逐任务差值与置信区间，不只报均分 |
| 长上下文注意力 | 选定问答/长文本任务的F1或EM | 上下文、KV预算、生成长度及真正执行的采样路径 |
| 器件与算术 | 偏差、方差、相关性、局部NMSE、故障/漂移敏感性 | 它们用于解释质量；不能单独代替完整模型质量 |
| 系统性能 | TTFT、TPOT、J/token、面积、SRAM/DRAM流量 | 在同一质量档位比较；计入概率转换、随机源、存储与调度 |

decode专用Attention若只在q_len=1路径替换，质量评测也要真正执行该路径；普通整窗teacher-forcing可能只执行另一条prefill路径。评测应记录实际触发次数、采样预算、GQA/因果条件和有限时间采样，不用准确Softmax IID结果代替拟实现的有限Ising路径。

对比图应以PPL/任务分数为约束，展示采样数、能量和时延的前沿。若某个随机方案PPL更差但模块更小，它可以是一个取舍点；要声称架构优于数字方案，还应比较数字低位/剪枝/缓存方案在同等质量下能达到什么结果。

## 7 值得补全文的DAC器件论文

下面三篇已确认论文身份，但本次没有取得可核对质量表的全文。其摘要或二手转述不足以支持PPL阈值。

1. **VQT-CiM: Accelerating Vector Quantization Enhanced Transformer with Ferroelectric Compute-in-Memory**，DAC 2025，DOI [10.1109/DAC63849.2025.11133264](https://doi.org/10.1109/DAC63849.2025.11133264)。[官方摘要](https://62dac.conference-program.com/presentation/?id=RESEARCH1261&sess=sess124)。重点补码本/量化、BERT等实际任务及基线；不采用二手“0.8%精度下降”作PPL证据。
2. **HEIRS: Hybrid Three-Dimension RRAM- and SRAM-CIM Architecture for Multi-task Transformer Acceleration**，DAC 2024，DOI [10.1145/3649329.3657327](https://doi.org/10.1145/3649329.3657327)。重点补多任务、精度/量化与RRAM误差是否进入完整应用质量。
3. **DBC: Drift-aware Binary Code for Drift-tolerant Deep Neural Networks**，DAC 2025，DOI [10.1109/DAC63849.2025.11132851](https://doi.org/10.1109/DAC63849.2025.11132851)。[作者摘要](https://insuofficial.github.io/publication/dbc/)。PCM可靠性编码与漂移，需核对所谓精度阈值、模型和寿命定义，不能把漂移容忍时间直接换成PPL容差。

这三篇优先补齐，特别是DBC能提供电学PCM的DAC对照。既有[推荐清单](C:/Users/86134/Documents/a_P_BIT/pbit_llm_master_report_20261012/PBIT_LLM_RECOMMENDED_READING_ZH_20261018.md)与[17篇机制总结](C:/Users/86134/Documents/a_P_BIT/pbit_llm_master_report_20261012/PBIT_LLM_READING_SYNTHESIS_ZH_20261018.md)继续保留；本报告修正的是质量目标的解释，没有重写历史实验或启动新模型测试。
