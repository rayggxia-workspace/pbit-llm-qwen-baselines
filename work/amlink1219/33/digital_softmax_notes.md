# Attention 数字基线文献核查（2026-10-18）

本笔记为调研和实验建议，未运行 RTL、工艺综合或模型评测。未将论文数字作为本项目 PPA；Zotero 由主代理统一去重与收录。

## 可核验文献与阅读范围

1. Maxim Milakov, Natalia Gimelshein. **Online normalizer calculation for softmax** (2018). arXiv:1805.02867; DOI:10.48550/arXiv.1805.02867. [原文](https://arxiv.org/abs/1805.02867), [合法PDF](https://arxiv.org/pdf/1805.02867), [作者CUDA](https://github.com/NVIDIA/online-softmax)。阅读算法3/4、§3在线递推、§4融合、§5基准相关段落。算法在一遍读取中维护 running max 与 rescaled denominator，完整softmax由4次访存/元素降至3次；报告GPU最高1.3倍，非ASIC PPA。不能把这些次数当所有硬件必须发生的DRAM流量。

2. Tri Dao, Daniel Y. Fu, Stefano Ermon, Atri Rudra, Christopher Ré. **FlashAttention: Fast and Memory-Efficient Exact Attention with IO-Awareness** (NeurIPS 2022). arXiv:2205.14135; DOI:10.48550/arXiv.2205.14135. [原文](https://arxiv.org/abs/2205.14135), [合法PDF](https://arxiv.org/pdf/2205.14135), [作者代码](https://github.com/Dao-AILab/flash-attention)。阅读§3.1–3.2、算法1与相关IO分析；另核对作者README中的 KV-cache decode 与GQA接口。分块QK、online softmax、PV融合避免完整score/probability矩阵物化，保持attention数学语义。原文训练GPU加速比不能移植为ASIC decode收益；单query decode的score仅O(N)，主要KV读取仍为O(Nd)。官方代码明确query长度1场景受KV加载限制。

3. Jacob R. Stevens, Rangharajan Venkatesan, Steve Dai, Brucek Khailany, Anand Raghunathan. **Softermax: Hardware/Software Co-Design of an Efficient Softmax for Transformers** (DAC 2021). DOI:10.1109/DAC18074.2021.9586134; arXiv:2103.09301. [作者页](https://research.nvidia.com/publication/2021-12_softermax-hardwaresoftware-co-design-efficient-softmax-transformers), [合法PDF](https://arxiv.org/pdf/2103.09301)。阅读§III–VI相关算法、结构与表I–IV。更换e为2、8-bit定点、整数ceil max、4段PWL exp2、移位重归一、PWL倒数后乘法。表I输入Q(6,2)、unnorm Q(1,15)、sum Q(10,6)、输出Q(1,7)。TSMC7nm/0.67V，16/32lane MAGNet HLS与DesignWare FP16对照；N=384，Full PE面积0.90倍、能量0.43倍，并非softmax独立总面积。BERT/GLUE/SQuAD精度依赖aware fine-tuning；不能据此保证未训练Qwen。未核实作者公开RTL。

4. Gamze İslamoğlu, Moritz Scherer, Gianna Paulin, Tim Fischer, Victor J. B. Jung, Angelo Garofalo, Luca Benini. **ITA: An Energy-Efficient Attention and Softmax Accelerator for Quantized Transformers** (ISLPED 2023). DOI:10.1109/ISLPED58423.2023.10244348; arXiv:2307.03493. [原文](https://arxiv.org/abs/2307.03493), [合法PDF](https://arxiv.org/pdf/2307.03493), [作者RTL/测试生成器](https://github.com/pulp-platform/ITA)。阅读§III–V、图4、表I相关段落。INT8 logits和输出，log2(e)吸收进scale，移位实现exp2，DA→共享serial DI→EN，两个串行divider与DA重叠。16PE×64INT8 MAC、24-bit累加；22FDX/0.8V/500MHz，完整加速器0.173mm²/60.5mW；含64KiB SRAM系统0.407mm²/121mW。数据为综合/布局后、synthetic switching功耗估算，非硅实测；softmax占功耗1.4%。Compact Transformer激活MAE0.0046，不是LLM PPL。

5. Run Wang, Gamze Islamoglu, Andrea Belano, Viviane Potocnik, Francesco Conti, Angelo Garofalo, Luca Benini. **VEXP: A Low-Cost RISC-V ISA Extension for Accelerated Softmax Computation in Transformers** (ARITH 2025). DOI:10.1109/ARITH64983.2025.00016; arXiv:2504.11227. [原文HTML](https://arxiv.org/html/2504.11227v1), [合法PDF](https://arith2025.org/proceedings/215900a037.pdf)。阅读§III–VI算法、§V物理实现与表III–IV脚注。BF16 Schraudolph+分段多项式修正，每核4元素/2cycle；8核64-bit Snitch、128KiB SPM。GF12nm/TT0.8V/1GHz P&R，cluster面积+1%，EXP6.39pJ/op。表IV的968µm²仅是每核EXP单元，7.1mW/0.45Gitems/s是每核整softmax均值，不能合成整softmaxPPA。162.7倍加速对比软件math.h exp基线，不能当专用数字硬算softmax优势。GPT2/ViT无需重训的质量证据仍须本项目再验；未核实对应公开RTL分支。

## 推荐数字基线

- D0 数学参考：FP32/BF16 logits，减max、exp、sum、每行一次倒数、逐元素乘倒数。BF16输入/exp，FP32 sum/output也单列；FP32 exp为质量参考而非声称零误差物理算子。
- D1 常规专用电路：D0三遍流水版本，1/4/16lane，FP16/BF16 exp范围约简+LUT/PWL精度可配，shared reciprocal。所有输入/exp暂存容量、SRAM端口、格式转换、输出写入明确计费。不能为每元素配置独立divider制造弱基线。
- D2 精确语义online/fused：tile=32/64/128，维护max/sum和未归一PV；最后每行倒数一次，缩放d维输出。数字不显式写出N维概率。包括运行最大值改变时对d维累加器的缩放成本。
- D3 数字采样：相同logit、相同候选、相同sample预算，用数字exp/累计和/有序systematic阈值生成类别计数并读取相同V。用D3隔离物理p-bit的收益，用D2衡量总attention价值；D1先满足用户的常规硬算对照。
- D4 文献强基线：BF16 VEXP式exp算法+D1/D2；ITA/Softermax定点变体作为质量匹配后才有效的进一步Pareto点。Softermax的e→2若不乘log2(e)，等于改变温度，应独立标签。

## 仿真参数与验收建议（本项目拟定，非论文现成结果）

先单query batch=1，N={512,2048,8192}，d={64,128}，Qwen GQA与Llama MHA分别计账。lane={1,4,16}，tile={32,64,128}；BF16 logits/FP32 accum为主，定点score={8,12,16}、prob={8,16}作敏感性。任何整数累加宽度由exp有效位数+ceil(log2N)+保护位显式推导，禁止默认长N不溢出。

对每种logits做真实逐层逐头trace，以及uniform、双峰、近delta、大动态范围、长尾、masked/all-masked定义等压力输入。近均匀p=1/N在N大于256时已可能低于8-bit概率量化步长；不能照搬短序列INT8输出。优先保留未归一PV和每行倒数，或至少16-bit/BF16概率。

质量逐级报告：row sum误差、TV/KL、输出relative-L2/cosine、全WT2 ΔNLL/ΔPPL，采样方案固定至少3种子/95%CI；同等模型质量下比较latency/energy/area，预设例如完整WT2 ΔNLL≤0.01 nats/token作为主门槛并报告更宽松点。对于无采样数值实现，首先要求不出现NaN/溢出/全行归零，再评估相对BF16的额外误差。

三种资源口径同时保留：相同lane/频率（明确面积差）、相同吞吐（比较面积与能量）、相同面积（比较延迟与能量）。统一PDK/角/电压/综合约束，并对相同trace采集SAIF/VCD；无工艺库时仅报RTL cycles、计数和能量系数扫描。

软max替代不能单看exp。完整边界包括max、sum、shared reciprocal、logit/exp SRAM、格式转换、decoder、计数器、采样源与分发、V读取、加法/缩放、控制、clock及泄漏；attention总账还包括summary构建/更新/读取、QK和K/V物理burst。统一内存边界，用all-resident SRAM和KV外存两档，不能把原始三遍都算DRAM却让p-bit配置与抽样免费驻片。

推荐停止条件：若p-bit仅赢D1而输D2/D3，应表述为特定数字基线优势；若softmax所占fraction=f，则仅替换softmax的理论总能量改善上界为f，不把PV稀疏收益归因于物理随机性。最终画p-bit混合时间、有效独立样本率、编程能耗与数字baseline的break-even边界。
