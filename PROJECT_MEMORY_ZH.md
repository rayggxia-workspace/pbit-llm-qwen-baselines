# p-bit LLM 项目长期备忘录

更新日期：2026-10-19。负责人：GitHub `jieruiz`。本次整理任务：[Issue 28](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/28)，通过 [PR 29](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/29)交付，2026-10-19正文审核通过，实际合并回执以[Issue55](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/55)为准；旧任务索引保留日期并由第12.1节更新。

本文件保存项目目标、用户决策、算法分支、实验口径、架构与证据入口，用于长对话压缩、换会话或换人后的恢复。它不替代原始结果、manifest、最新 Issue/PR 和运行日志。历史讨论不等于已实现；以下明确区分已验证、情景估计和待验证。

## 2026-10-19 可训练能量p-attention调研

接续Issue61/PR63，核查PR52 e3c5e957c3769b5fc6867b42a52facace647a83b仍开放未合并。现有screen_ising已经不显式计算Softmax，直接score差热浴CTMC；新路线是蒸馏筛选器＋低维/低位条件能量＋实际有限链训练，独立mask与binary/tree作为另一结构。报告architecture_tlm/p_attention_feasibility_20261019/README_ZH.md；计划未执行，没有新模型/PPL/GPU/PPA。现有原始/负面证据保持，Issue50/59作业不重交。数学核验与文献入库回执在work/amlink1219/61/p_attention/。Projects仍按既有scope待同步。

## 0 恢复工作先读这里

1. 目标是利用物理随机源/p-bit降低LLM的能量、面积，同时保持可接受的质量与速度；不能为了利用随机源就假定随机计算一定胜过定点计算。
2. 正式仓库是 `rayggxia-workspace/pbit-llm-qwen-baselines`，当前主要集成分支为 `pbit-tlm-attention-details-20261016`。`main` 和历史个人仓库都可能落后。2026-10-19 PR47按用户授权实际合并后，集成提交为 `bef83e54b9da0081c51f393044d2156ce11a34b9`；其Git树与已审核head `5518a0a23e2bfec2b428542a9e4ce94b27c78d4a` 相同。
3. 三个模型入口是 [qwen](qwen/README.md)、[llama1](llama1/README.md)、[llama2](llama2/README.md)。Qwen3.5是另一组历史实验，不能默认已并入本分支。
4. FFN有两大方向：重新训练的P-DNN/多阈值AND网络；保留预训练权重、改变矩阵算术的随机计算。不能把前者N=4/16路径与后者T=256/4096拍混用。
5. 当前随机矩阵参考使用INT8权重、概率幅度码和单独符号；主接口/残差保留BF16。固定权重随机输入、双侧随机、普通OR、互斥OR是不同算法。
6. 已做过双侧随机FFN。固定Sz和8位共享64路版本的完整PPL有明显短流退化，但双侧权重噪声的全量结果用了条件高斯近似，不能叫逐连接精确实测。见第5、10节。
7. 物理随机源不需要特定种子才能用于矩阵乘法。AND两侧的独立性、时间相关和概率偏差仍需检验。区域互斥可以由组合逻辑保证；优化PRNG前缀只是一种有限样本优化。
8. Attention的准确Softmax后PV采样已有质量基线；筛选可进一步减少QK。当前max4筛选不是耦合Ising退火。随机Q/K投影不等于随机动态QK点积。
9. TLM是宏级系统估计：Python计算/片上调度，外存可接真实SystemC/TLM DRAMSys+DRAMPower；Ising仍有宏级参数。不能把情景结果称为芯片实测或最优设计。
10. 开始或恢复任务必须核对远端Issue/PR、个人STATUS及HANDOFF。这里的运行状态只是记录时点快照，不能据此断言作业今天仍在运行。

## 1 用户已经确定的方向与约束

| 方面 | 已确定的要求 |
|---|---|
| 主要目标 | 尽可能用概率计算替换FFN和Attention，两者可以叠加；整体比较质量、能量、面积、速度，而非只报告AND门数量 |
| 物理随机源 | 应允许自然随机输出；不能将精心预设的确定序列或挑选种子作为必须条件。受控映射和共享是否合适需说明成本 |
| 当前编码 | 新版优先0/1幅度流，独立处理符号；历史bipolar checkpoint缺coding字段时仍按原规则解释为-1/+1 |
| 偏置/温度 | 温度缩放容易；器件无需额外偏置端，但输入驱动可已经包含矩阵偏置。原Qwen FFN无bias，学生网络新增bias需单独说明 |
| 采样长度 | 重点探索小于256拍；4096不是硬件必然要求。128拍分层保留作基线，但不能冒称纯物理IID |
| 训练 | 先看算法和数值效果，再决定误差感知训练；不要用“必须重训”跳过当前无训练验证 |
| 存储 | 权重写入后驻留SRAM抽象模块；不接受默认用海量DFF保持全部权重并称为SRAM方案。SRAM外围及读出成本需计入 |
| 随机源分发 | 已有分层随机源和FFN本地PRNG、A8共享64路；Attention也应有随机服务，不能把全模型简化成只有FFN一个PRNG |
| 数制接口 | 固定权重可以离线准备；动态BF16/定点/概率转换必须收费。当前保留BF16残差是允许的 |
| 评估 | 完整WT2滑窗PPL优先；按需要补基础任务。单独测试FFN时Attention保留原模型；不要把后缀PPL叫完整PPL |
| 远程执行 | 新实验通过Slurm提交；个人项目目录存临时checkpoint；不覆盖已提交执行快照，不重复提交仍运行的任务 |
| 报告 | 总括表清晰可读，再给细节；结果与方法逐项对应；不能用操作数比例直接冒充整机能量比例 |
| 协作 | 一任务一Issue、独立分支和目录，通过PR交付，维护progress和handoff；正式成果与个人辅助资料分开 |

## 2 模型与逐层结构

| 模型 | 结构与当前定位 | 入口/证据 |
|---|---|---|
| Qwen2.5-0.5B Base | 24层；D=896，FFN=4864；14个Q头、2个KV头，head_dim=64；GQA；约494,032,768参数；原FFN为SwiGLU | `qwen/`、`results/base_bf16/`、本地 `pbit_llm/model_config/config.json` |
| LLaMA-1 7B | 32层；D=4096，FFN=11008；32个Q/KV头，head_dim=128，MHA；已迁移当前标准TLM | `llama1/`；Issue12/PR13已合并 |
| Llama 2 7B Base | 核心层宽/头结构与LLaMA-1 7B接近，模型权重、tokenizer/上下文规范必须独立核验；已有BF16完整基线及116项TLM | `llama2/`；Issue14/PR15已合并 |
| Qwen3.5-0.8B | 24个FFN，18个Gated DeltaNet、6个完整门控Attention；FFN/固定投影实验与Qwen2.5分开。线性状态更新不可套普通KV/QK流程 | 本地 `qwen35_publish_20261013/`，另有分支；未自动集成 |

Qwen2.5每个decoder层的主流程：

```text
BF16残差x
 ├─ RMSNorm → Q/K/V固定权重投影 → Q/K RoPE → 更新KV cache
 │            → 全部或候选QK → Softmax/Ising → 准确PV或采样V累加
 │            → O投影 → 与x相加
 └─ RMSNorm → gate和up两分支 → SiLU(g)×u → down投影 → 残差相加
重复24层 → 最终RMSNorm → lm_head → logits/下一token
```

硬件可以时分复用同一组算子执行不同层，但每层有不同权重、尺度和KV/状态；并行度、SRAM驻留、权重搬运和状态容量必须调度。不能把“重复24次”理解为容量和带宽也只有一层。Embedding与lm_head权重共享并不取消词表读出运算。

## 3 FFN算法路线与演进

原模型三个矩阵的关系为 `g=Wg·x`、`u=Wu·x`、`z=g·sigmoid(g)·u`、`y=Wd·z`。gate/up为D→F，down为F→D；三个均为稠密线性投影。

| 路线 | 计算方式 | 需要记住的结论 |
|---|---|---|
| 初版P-DNN | 连续输入→矩阵→p-bit隐藏→读出矩阵→平均 | 整个FFN换成两矩阵student，p-bit承担隐藏非线性；第一矩阵仍接收连续数，改变原SwiGLU结构 |
| 全路径P-DNN | 输入p-bit→矩阵→隐藏p-bit→矩阵→末端平均 | 每个矩阵入口二值；中间不能随意平均再称全路径二值 |
| 逐层编码/联合训练 | 学习尺度、阈值、温度；从单层扩展10/20层 | 单层局部MSE不能预测组合质量；layer0/部分末层特别敏感；联合训练有效但不能消除结构误差 |
| 门控/宽度/入口多位 | 双分支、更宽网络、K位/多阈值编码 | 曾做过，不能重复当全新方案；增加容量并非保证解决多层累积误差 |
| 多阈值AND拟合SwiGLU | 两分支p-bit bank，单比特项及AND交叉项，经读出恢复 | 曾有较好的20层及24层联合训练版本；K与输出路径N是不同参数 |
| 固定权重随机算术 | 输入幅度比特选择固定量化权重，空间/时间准确累加 | 不必把权重也随机化；消掉通用乘法后仍有计数、尺度和采样成本 |
| 双侧随机算术 | 输入、权重幅度各转独立随机流，AND再准确计数 | 已测过；短流权重噪声明显，完整精确分布验证仍需补 |

P-DNN原理和后续变更的正式长期文件继续是 [P_DNN_FFN_DESIGN_ZH.md](experiments/pdnn_ffn/P_DNN_FFN_DESIGN_ZH.md)，不能被本备忘录替代。

历史训练式多阈值AND：20层N16完整WT2 PPL为12.741809（单seed）；24层N16为13.587396±0.003214（3 seeds），N4为15.128474±0.007446。这些使用连续投影/读出，不代表4096拍随机矩阵已被压到16拍。来源：本地 `pbit_llm_master_report_20261012/PBIT_LLM_MASTER_REPORT_ZH.md` 第3.1节及其结果索引。

### 3.1 面向现有硬件的训练研究增量：Issue61（2026-10-19）

用户说明有较充足H100，希望针对硬件训练/微调，重点为SiLU与p-bit sigmoid/tanh。负责人amlink1219；[研究计划](architecture_tlm/HARDWARE_AWARE_TRAINING_PLAN_ZH_20261019.md)和[结构化矩阵](architecture_tlm/hardware_training_plan_20261019.json)明确为待执行，尚无新训练/PPL/PPA。

`x*sigmoid(x)`本来就是SiLU；保持函数的有限Bernoulli/双极均值，与sigmoid/tanh GLU及两矩阵tanh是不同实验。Extropic Z1T确有原生tanh/稀疏结构从头训练，但扩展曲线未含激活量化，不能据其32样本延迟估算宣称有限采样质量已验收。

优先三线：现有B4/T32/K32下的真实共享短流感知微调，目标T16；教师蒸馏QK筛选器，再微调有限Ising；原生激活转换与从头训练。已有sigmoid/tanh P-DNN、多阈值AND和方差正则不可重复当新尝试；20层K4/N4方差正则三seed未胜过control，见报告原件。

本轮用户限定三投影＋连续up＋仅激活p-bit；精确A/B/C未找到执行/PPL，A只在历史§27提案。旧双支/AND/SC不得按名称迁移结论。activation_only报告、结构化计划、21tip/506历史对象审计、StochA直接负面先例和Zotero本批核验已整理；未训练。

用户再次核实门控历史：双路gate/value及三投影K4 AND-bank均已做，不能把保留门控/多位编码当新主线。当前优先训练B4/T32/K32随机计算FFN；旧结构须明确新增条件和数字/原实现对照。报告§4.2与JSON已纠正，未启动训练。

用户随后纠正：旧两投影全路径扩层已失败，不能因改量化重新优先推荐。匹配20层取消入口量化仍N4=27.127764（sigmoid入口38.764105）；4位入口只核到四层12.909709，hidden仍单bit。新试验先分离表示/隐藏/结构及训练，再决定W8，旧两矩阵降为诊断对照；详见计划§4.1。

训练保持分层/共享相关结构，不能只训练期望或独立Gaussian后宣称部署有效。T（FFN）、N（激活）、S（Ising）分别记录；W8 shadow/QAT或LoRA合并后要重新导出量化。两矩阵同参数比较宽度为原GLU的1.5倍；DyT含初始化/embedding缩放对照，后续单独消融。

Issue50/PR52联合质量和Issue59代表任务仍属jieruiz，本任务只读公开成果，不重复其作业或改变其状态。执行训练前另明确子任务、数据revision/SHA、scheduler资源与本人存储；本研究未申请或验证H100分配。协作/来源/数值校核与Zotero摘要入口 `work/amlink1219/61/`。

## 4 随机矩阵运算的定义

### 4.1 编码与数制

幅度v以固定尺度S表示：`q=clip(round(|v|·256/S),0,255)`，概率 `p=q/256`；符号另存。比较器每拍取均匀8位整数R，输出 `R<q`。因此这里A8是**8位幅度加另一个符号**，不等于传统总共8位的有符号INT8。最高码概率是255/256。

BF16有指数和尾数，转概率不是直接截取某8位。动态输入需经过符号提取、尺度对齐、舍入/饱和，随机输出经过计数、符号/尺度恢复再转BF16。tile尺度若不是2的幂，不能把恢复一律当免费移位。

固定权重保留二进制INT8，可按位与输入随机位做AND，或在每拍选择权重/零。精确线性归约时 `平均(W·b)=W·平均(b)`；这说明可把噪声理解为随机输入量化，不证明某一种硬件必然胜出。

双随机把权重幅度也编码成概率；对独立输入/权重位，`E[A AND W]=pA·pW`。权重仍可以二进制存SRAM，只在计算时产生权重流，**不存储全部T拍流**。正负贡献分别计数或采用严格等价的带符号恢复。

历史双随机权重概率为 `|INT8码|/127`，对应事件幅度为127个权重步长；这不是直接拿同一码和0～255整数比较。若新版权重侧也严格采用R8比较器，分母/端点/恢复幅度必须重新定义并单独命名，不能暗中改变后继承旧PPL。

### 4.2 必须分开的归约结构

| 结构 | 空间求和 | 主要影响 |
|---|---|---|
| 精确APC/压缩器 | 统计每拍1的数量，再时间累加 | 对给定比特流无额外近似；保留随机采样噪声 |
| 权重位平面 | 各位分别popcount，最后按2的幂加权 | 可避免每条输入先扩展为多位权重再搭大加法树；需要核对符号、跨位和时间存储 |
| CSA/压缩器时间归约 | 先保留sum/carry或小块计数，延后大进位更新 | 改电路活动，不改变正确结果；节能不能只凭减少更新次数断言 |
| 普通OR2/4/8/16/32/64 | 同组贡献碰撞后只留1 | 独立事件时 `P(OR)=1-∏(1-p)`；共享流须求联合并集概率，一般不等于概率之和；增加T不能消除碰撞偏差 |
| 互斥区域OR | 重编码让每拍最多一个事件，再OR | 需要编码/缩放及量化分析；可由物理随机字驱动，无需固定顺序 |
| MUX缩放求和 | 随机选择一条贡献 | 电路简单但输出被除以组大小，可能增加方差和所需拍数 |

缓存若干拍再更新累加器的RTL已经存在；旧PT中缓存并不总省电。不能将OR64的节省百分比套到OR2/4混合结构，也不能将旧P12/DFF权重核心直接当新版A8/SRAM阵列。

### 4.3 非线性仍是关键边界

曾用 `|g|`幅度流、`sigmoid(g)`概率流和`|u|`幅度流三者AND，恢复乘积尺度 `Sg·Su`。尺度过大时事件太稀少，恢复幅度大，方差显著。

另一版先准确算 `z=SiLU(g)·u`，用更紧的 `Sz`重新编码，再送down矩阵。它改善事件密度，但保留了中间连续估计、sigmoid和逐元素乘法；不能宣传为全部非线性免费或全程纯比特流。固定Sz必须说明是每层、每组还是全局一个常数。

## 5 双侧随机流的现有结果与当前任务

以下Qwen均为全部24个FFN，Attention保持原SDPA，完整WT2 test，context=2048/stride=1024，299077个目标token。

| 固定每64通道Sz、A8共享64路 | T=256 | T=1024 | T=4096 |
|---|---:|---:|---:|
| 固定INT8权重、随机输入 | 31.6484（1 seed） | 14.0534（1 seed） | 12.4535±0.0057（3 seeds） |
| 输入、权重都随机 | 81366.1658（1 seed） | 33.6119（1 seed） | 14.1483±0.0132（3 seeds） |

BF16原版为11.652735。来源：本地 `pbit_shared_rng_ffn_20261015/results/RESULTS_ZH.md`。固定权重使用准确输入联合计数；双侧全量评估的权重残差采用条件高斯压缩近似，**不是完整逐连接精确随机实验**。128-token前缀已有精确条件二项与高斯的差异对照，不能由此直接校正完整PPL。

更早A12固定分组Sz双随机完整结果：T4096为13.948997±0.011665，T1024为42.762909±0.164946，T256为127803.483024±358.103878，也是条件高斯参考。动态Sz可改善质量但增加在线缩放成本；每层仅一个固定Sz效果明显更差。来源：本地 `pbit_sz_dual_ffn_20261014/results/RESULTS_ZH.txt`。

用户当前授权：**先完成本备忘录，再检查/尝试双侧自然随机流的性能影响**。备忘录交付后，已单独建立Issue30并完成下述精确短片段测试；后续完整PPL仍按已有证据决定预算。不要把旧高斯结果包装成新实验；不要依赖挑选seed、预设低差异序列或先重训。

已有可复用精确实现是 `pbit_shared_rng_ffn_20261015/run_shared.py --backend binomial`，条件于共享输入计数，对每连接独立权重位做准确二项抽样，与本阶段IID随机流的精确分布等价，省去展开时间顺序。旧128-token前缀T4096耗20.64秒，高斯0.56秒；原样完整滑窗粗估需20～30 GPU小时/配置，必须先小测和估时，不盲目开几十个全量任务。

### 5.1 备忘录之后实际完成的精确补测

2026-10-18，Issue30/PR31，Slurm2111：47/47输出齐全，包括未改BF16完整参考、BF16短参考和3后端×5长度×3seed的45项短测。模型/tokenizer/完整train-test共9文件及token hash重新核验，完整BF16再次精确复现11.652735047455899。**所有随机结果仅为同一test前128token、127个预测目标，不是完整WT2**；该段BF16为14.329108。

| T | 固定W＋随机输入 | 双随机精确二项 | 双随机Gaussian |
|---|---:|---:|---:|
| 64 | 35642.1 | 3410820.7 | 3081853.5 |
| 128 | 472.925 | 394262.8 | 477122.5 |
| 256 | 40.8736 | 55019.2 | 66118.4 |
| 1024 | 17.3462 | 42.6911 | 43.0987 |
| 4096 | 14.8830 | 17.3134 | 18.4728 |

表为预先固定seed0/1/2的均值，标准差及逐项SHA见结果。当前编码短T退化在精确分布下也存在；不能只归因于Gaussian近似，也不能据此否定其它权重共享/编码/互斥设计。没有新训练、OR、SRR或物理源回放。

公开安全交付分支 `task/30-qwen-dual-iid-public`，目录 `tmp/qwen-dual-iid-public-issue30-20261018/`；原执行SHA `ad14096615054a7ef0a72e43f670863e4a205b11`仅本地和服务器保存，公开源码逐SHA对应。原始校准数据推送被自动审批拒绝后，已改为仅发布代码/汇总/校验索引：两份校准与逐case长JSON留既有服务器个人项目，未绕过拒绝或将旧执行历史推送。PR31于2026-10-19实际合入TLM，merge `d589f152b46d0d4db6f2036af53f967fc5942faa`，Issue30已关闭。完整精确随机WT2尚未补测。

## 5.2 独立范围修正：Issue32 / PR34

2026-10-18，执行源`17c89c3c86f8b1c0aafe42a3eaa1d354c1e539ee`，单独目录`tmp/qwen-dual-range-issue32-20261018`、分支`task/32-qwen-dual-range`；[PR34](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/34)依赖PR31；二者于2026-10-19已实际合入TLM，PR34合并提交`5b71d4e2d00dca0d493576c60849b5ef14ddd17e`；分布/入口补充PR38也已合并`c1555ae6594c863011a70845d88c950a68de732b`，Issue32已关闭。源码和[结果报告](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/task/32-qwen-dual-range/qwen/results/dual_range_20261018/RESULTS_ZH.md)在独立实验目录及qwen/results/dual_range_20261018。Slurm2112/2113完成首轮39输出；2142/2143完成2048token确认10输出，49原件逐SHA收回。原BF16完整WT2重新复现11.652735047455899（299077目标），所有模型/语料/token/冻结源hash及8项kernel/旧实现回归、共享counts和方差测试通过。

输入和权重**原本已有独立尺度**。修正的是范围利用率：A从训练固定包络改为每token/64通道absmax；W从64×64 tile改为每输出行/64输入absmax，从相同旧W8解码值重编码。新概率为8位q/256加独立符号，S=maxabs×256/255；自然IID、A共享64、W逐连接独立、准确计数；准确Attention、无训练、无OR或种子挑选。

| T256三seed、同128token前缀（127计分目标） | PPL均值±总体标准差 |
|---|---:|
| old | 55019.203877±11876.079226 |
| 只改输入 | 20.272866±1.456530 |
| 只改权重 | 426.375111±91.667913 |
| 两者修改 | 15.723897±0.533414 |

同128token BF16为14.329108；both的T64/128/1024分别为30.448111±2.791960、18.925999±1.185136、14.832534±0.313483。gu-only为15.719206±0.880520、down-only为14.734595±0.445133；分支中未采样投影使用相同编码的期望，不能称恢复原BF16。

2048token确认（2047计分目标）：BF16为9.328747；both无采样期望9.365257±0.000000、T128双流12.667931±0.419085、T256双流10.656912±0.014438。这些仍是测试前缀PPL，**不是完整WT2随机PPL**，也不能与11.652735完整参考直接比较。

teacher同输入局部理论T256 NMSE（24层等权）gate10.12%→0.95%、up21.11%→2.26%、down51.50%→1.28%；只改A时down约2.93%、只改W约25.15%。旧down新增W方差39.81%，A共享方差11.04%，均值偏差0.648%；收紧A同时降低两类方差，因此A范围是更有效干预，但W噪声仍重要。输入平均p从gate/up4.93%、down0.761%变为20.40%、16.588%，W约14～16%变为29～30%。这是train前16teacher-token的线性投影理论误差，不能外推为全层因果贡献。

数值改善有硬件成本：在线absmax/概率尺度恢复、权重尺度元数据增加64倍；新W概率阈值8位外加符号，布局尚未定稿，不能默称原signed INT8存储不变。本轮没有新PT/TLM或节能实测。剩余短流误差更偏向SwiGLU前g/u路径，需更广语料/完整PPL再确认。原始长诊断/校准留授权服务器，teacher激活仅临时GPU张量、未持久化。

## 5.3 实际编码分布与裁剪审计（2026-10-19）

用户认为可牺牲罕见大值以改善多数小值精度，并明确授权将缩放合入项目。范围PR31/34和补充[PR38](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/38)均已实际合并；当前项目首页与qwen/README提供入口。合入版本为分组absmax，不主动百分位裁剪；没有把新数值方案直接作为TLM默认或宣称新PPA。

新审计源`622e0efd9d64ea73e27a9a213edb3a238b6ef688`，Slurm2166，前8192train-token、4×2048窗口、24层原BF16 teacher；9模型/语料与冻结文件/token hash通过，原BF16完整PPL11.652735047455899复现，4项分布单测通过。仅统计，不跑随机/裁剪模型PPL，不保存原始激活。原2165在shell启动处失败、Python未执行；重交同不可变快照已记录。原49项结果不变。

旧SwiGLU输出z按元素数加权：q=0约29.537%，1～3约54.156%，4～15约15.438%，16～63约0.837%，64～127约0.028%，128～255约0.002872%。共99.131%落在0～15；高码实际27462个，不能说只有一个极端值。旧平均q2.04156、中位1、90分位5、99分位14、99.9分位40；dynamic64平均q43.57899、零码2.605%。这是8192token计数加权统计，不与此前16token层均值1.949/30.93%混作同一批样本。新q99=255是每64组最大值映射到满幅的结果，不代表大量数值裁剪。

旧Sz乘0.5时只截约0.00283%值，但它们承载约22.384%原平方能量；实际截断SSE/原能量约2.400%，含8位舍入的总编码NMSE约2.594%，旧未缩紧的编码NMSE约0.562%。被截值能量不等于实际损失，平方能量也不等于语义/PPL贡献。标量重构误差不能直接当矩阵输出误差或PPL。

裁剪仍值得独立测试：目标是裁剪偏差＋有限T采样方差，然后用独立PPL验收。可考虑温和百分位或少数极值确定性旁路；不能仅因占比小就删除。阈值由train校准，测试文本不用于选最佳值。本次没有验证裁剪能改善整网。

[报告与入口](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/pbit-tlm-attention-details-20261016/qwen/results/dual_range_20261018/DISTRIBUTION_ZH.md)，新小型总表/索引为DISTRIBUTION_SUMMARY/ARTIFACT_INDEX。旧work32/MANIFEST以45063d8为版本边界，新DISTRIBUTION_MANIFEST单列11文件。Git传输网络失败后经同一jieruiz账号Git Data API上传，4个commit/tree SHA逐个完全相同；没有改执行历史。2026-10-19再查Projects仍缺read:project，Issue/PR已同步，看板待同步。

## 5.4 截断与固定二次幂范围：Issue39 / PR40

2026-10-19用户授权：牺牲少数大值、提高低幅度概率利用率，实际测试PPL；研究离线分组二次幂范围及权重分布。新[Issue39](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/39)/[PR40](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/40)，独立分支task/39-ffn-clipping，目录tmp/qwen-ffn-clipping-issue39-20261019，base c1555ae。不接管Attention成员任务，不修改TLM默认。

主执行6b57b92305cab5dbee2a53c0c65cb297ac976261，Slurm2167/2168：8策略+mean/3seed，512前缀，预注册3策略2048确认，共53替换。补充执行e0cf563daceb4e8528d9b1ca38da58e434907811，Slurm2185/2186，.95/.90温和裁剪和dynamic100恒1端点，共12替换；补充在最早.75无采样失败后注册，属于相同测试文本上的探索，不是独立最终评估。各自原BF16完整WT2再次复现11.652735（299077目标），新10/旧8/共享/方差测试通过；模型/语料/冻结源/token hash重验。主数组先4卡，补充期间降3，补充1卡，总并发4。最初caf4193导出受autocrlf影响，sbatch在作业创建前拒绝DOS换行；LF快照修正另记，未覆盖提交源。

编码：幅度超S时真正p=1，另有普通q/256格点；8bit q最高255本身不表示恒1，须显式饱和旁路/端点码。负数幅度截断后符号仍独立。A组共享64/W逐连接独立，准确计数、无OR/Gaussian/训练/挑选seed。仍先恢复FP32 g/u，准确SiLU(g)×u，再按独立Sz重编码给Wd；不是全比特流非线性。

固定阈值来自前8192train-token、原BF16 teacher、4×2048上下文，每层64通道分组的99.9/99.99绝对值分位；2幂向上取整，W从同一旧W8重新编码。静态激活可能分布漂移，不能保证所有新文本不过界。概率目标不是强行0.5/均匀，而是减小恢复单位下的偏差+采样方差。

硬件：权重尺度可离线，激活固定需校准。每组先计数，按eA+eW−log2T移位后跨组累加；不能将不同尺度的计数直接合成一个总数。Qwen全FFN313,786,368权重，每row64共4,902,912尺度；8bit指数4.676MiB，占原W8容量1.563%，只是容量比例，非总面积/功率。x/z全模型2160个组尺度仅2160字节。专用常数移位可接线，复用PE需指数配置/可选移位/宽累加；BF16转换仍有对齐、舍入、饱和。数字幅度是数值解释，不要求不同逻辑电压。权重不是均匀：旧gate/up/down平均p13.66/15.72/14.64%，row64约29%；旧p≤1/4比例79～85%，但比旧z低码拥挤轻。

原文[SC-CNN2020§4.3](https://pmc.ncbi.nlm.nih.gov/articles/PMC7793640/)直接采用饱和裁剪及2幂尺度，但乘法为确定优化位流，不能继承为自然IID精度；OCP MX支持组尺度/组间对齐，ACIQ与SmoothQuant提供校准/误差折中启发。具体来源和成本说明在PR40的SCALING_HARDWARE_ZH.md。

两批65替换+6基线共71输出全部齐，逐SHA和源代码复查通过。512前缀BF1612.0892，control13.9529±0.4795，.95/.90/.75范围13.7701/14.4005/19.2372；固定99.99分位132.1361，固定PoT A/W446.3353。2048前缀BF169.328747，control10.6569，.75裁剪14.1020，固定PoT A/W333.2295。温和范围改善小、仍需独立全量验证；强裁剪/简单静态分位明显退化。**所有替换分数仍非完整WT2。**

固定99.99分位无采样传播路径layer2的z只截约0.01237%元素，但该层总编码NMSE89.53%；相对该路径未编码z，不是原BF16 teacher，也不是证明全PPL仅由此层造成。少数大值可主导损失，不能只按个数裁剪。

正式结果/实现见[PR40](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/40)，qwen/results/ffn_clipping_20261019/RESULTS_ZH.md和SUMMARY/ARTIFACT_INDEX，交接work/jieruiz/39/。原始校准、长JSON留授权服务器，无新PT/PPA/完整采样WT2。PR待审未合并，Issue39保持open；Projects仍缺read:project待同步。

## 5.5 固定INT8权重＋输入幅度分桶：Issue46 / PR47

2026-10-19用户授权：权重保留固定INT8，只对输入按幅度选择不同二次幂范围，测试自然随机T<=256。新[Issue46](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/46)/[PR47](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/47)，分支task/46-fixedw-multiscale，目录tmp/qwen-fixedw-multiscale-20261019，base c1555ae。与Attention成员PR42-45分开，不修改TLM默认。

全部24FFN，Attention保留原BF16 SDPA。固定相同历史64×64 symmetric INT8解码矩阵，**没有再做权重概率重编码**；不能用此前row64概率再编码的decoded矩阵冒充同一W8。gate/up共用一次x采样，FP32 SiLU(g)×u后z独立编码；输出转BF16。无训练、无OR、无Gaussian、无分层/枚举或种子挑选。

dynamic64为历史每token64路absmax对照；pot1/4/8的顶档S由当前每token/64通道maxabs向上取二次幂，后续档为S/4、S/16等，每元素选择能容纳自己的最小档，不物理重排通道、不主动截断大值。四档需2bit档号，八档需3bit，另外保留幅度q8、符号和恒1端点语义。跨档仍共享同一R8；shared_counts准确模拟自然IID联合计数，不是lane独立二项。先恢复各lane的sign×Si×Ci/T再F.linear，与按档精确归约实数算术等价，尚非有限宽bittrue。**动态顶档与此前失败的静态分位范围不同。**

执行源e6f29b113405df53f2ca32b084d9de0dc9859343。Slurm2234核验9个模型/语料文件及源/token hash，12项新kernel、8项旧range与共享counts测试通过；原BF16完整WT2再次精确复现11.652735047455899，299077目标。2235完成41项512前缀；2276完成预注册22项完整WT2。合计65项计分、无skip/pending，68原件逐bytes/SHA收回，30项执行Git blob复核；本人最终squeue空。服务器来源为既有个人项目，模型revision/语料均未改变。

| 完整WT2，3seed均值±总体标准差 | T64补测 | T128 | T256 |
|---|---:|---:|---:|
| dynamic64 | 14.559275±0.005839 | 12.925563±0.006728 | 12.257885±0.003676 |
| pot4 | 13.038027±0.010666 | 12.309561±0.001471 | 11.989865±0.002580 |
| pot8 | 13.038505±0.012030 | 12.315184±0.003122 | 11.990151±0.004012 |

原BF16完整11.652735；同W8、无A编码、FP32 FFN控制11.681130。四档无采样编码控制11.680940；mean是确定性编码路径，不是非线性随机网络整体的数学期望。四档T128/256相对原BF16 PPL约增加5.64%/2.89%；八档未显示进一步收益。T64此前仅512前缀，因此未进入首批完整主表；用户追问后已补完完整WT2，四档相对BF16增加11.888%，八档仍无明显收益。64次更激进，128次为当前折中候选、256次精度更好；未声明任务性能几乎无损。没有新基础任务或Llama结果。

T64补测执行源a7bae630c62f08165a01192fe4226d9beac34e7c，Slurm2298/2299全部完成，11项新增计分（2BF16＋9完整T64），14服务器原件逐SHA与31源码blob复核。两批模型/文本/token/冻结依赖一致，kernel与测试文件同字节；原BF16完整再次精确复现11.652735。新结果提交a4a15018b9fd7344be916a21c3bf098c929fc5eb已实际发布PR47；正式补充qwen/results/fixedw_multiscale_t64_20261019/，新原件位于同个人项目outputs/a7bae630c62f08165a01192fe4226d9beac34e7c/。首批65项原件与SUMMARY/ARTIFACT_INDEX保持不变，首批RESULTS新增64/128/256联合表。合计76项输出、82服务器原件，需分别用两批manifest核验。

硬件边界：T是每个x/z采样阶段流长度，不是整层或整token周期；幅度档号、多桶计数、符号/端点、跨档对齐与存储需收费。旧W8量化步长并非强制二次幂，故输入PoT不等于全部尺度恢复只有移位。本轮无PT/PPA、物理随机源回放或新TLM能效；GPU参考耗时不能当ASIC周期。W侧随机共享是此前提出的候选，**本轮固定W没有权重随机流，因此没有测试双随机W共享PPL**。

正式结果qwen/results/fixedw_multiscale_20261019/{RESULTS_ZH.md,SUMMARY.json,ARTIFACT_INDEX.json}，实现experiments/qwen_fixedw_multiscale_20261019/，交接work/jieruiz/46/。原件服务器/home/Hongjie_Zeng/projects/pbit-qwen-fixedw-multiscale-20261019-issue46/outputs/e6f29b113405df53f2ca32b084d9de0dc9859343/；Git只发布代码/汇总/索引，不发布权重、文本或校准。PR47已于2026-10-19 15:44:54（北京时间）合入TLM，merge `bef83e54b9da0081c51f393044d2156ce11a34b9`；Issue46验收后已关闭。Projects新查询仍缺read:project，看板待同步。后续优先四档RTL/归约/尺度恢复PPA；T64全量已完成，不重复已验证76项。

## 5.6 多档缩放＋粗细分层：Issue46完整结果（2026-10-19）

接续用户要求同协议比较分层和缩放、档数、粗细分层及真实语言PPL文献。仍为Issue46/PR47、task/46-fixedw-multiscale，未接管Attention Issue48。实现experiments/qwen_multiscale_stratified_20261019，正式总表/图/文献qwen/results/multiscale_stratified_20261019/{COMPARISON_ZH.md,COMPARISON.json,COMPARISON.png,LITERATURE_ZH.md}。

执行db27fa3d7ed8eced13513f0cad10061a3cc59a71，Slurm2308/2309全部完成，本人队列空。67完整配置＋2BF16共69计分、72服务器原件逐bytes/SHA及37执行源blob通过；13新核/12旧multiscale/8range/shared测试通过。新后处理K分组与cfg篡改fixture通过（合成测试，不是PPL），图已视觉检查。模型/文本/token/固定依赖与前两批一致，原BF16完整再次11.652735。结果提交c8ea878c5bf2dc9c37e12a1b4595d8f2fc5c45ed已实际发布。原76输出不覆盖，合计145输出条目、154服务器原件，各批计分协议不同分别保留manifest。

全部24FFN、同固定W8、原Attention、无训练；mean控制不是全网络期望。B为幅度档数，S/S4/S16等；K为均匀门限分层数，层内T/K次有放回，跨层独立、同64路/跨幅度档共享。K1严格原IID；K=T是受控细随机分层；K256完全覆盖无随机。局部恢复方差S²×u(1-u)/(TK)，两机制可叠加，但整网PPL不保证单调。

| 同T64，三seed均值±总体标准差 | IID K1 | 细分层K64 |
|---|---:|---:|
| B1 | 17.800039±0.013904 | 11.861552±0.003298 |
| B2 | 13.324329±0.008113 | 11.703316±0.001176 |
| B3 | 13.064200±0.014960 | 11.692746±0.000593 |
| B4 | 13.038027±0.010666 | 11.693775±0.001432 |
| B6 | 13.036766±0.011718 | 11.694073±0.000768 |
| B8 | 13.038505±0.012030 | 11.693854±0.000628 |

dynamic64仅改细K64为11.768589±0.003298，K128为11.700228±0.000201。单PoT档与dynamic absmax的顶档/端点不同；不要将其混为一行。各档mean约11.680～11.687，支持有限流是主要可改进项，不等于纯权重量化损失。

缩放后粗分层仍有效：T64/B4，K4/16/64分别11.893101±0.003607、11.736863±0.004758、11.693775±0.001432；B2分别12.015205±0.002574、11.773086±0.002320、11.703316±0.001176。K16已接近细覆盖，但同质量可缩短T：B4细T16/32/64/128分别11.900826±0.003825、11.736131±0.000243、11.693775±0.001432、11.683928±0.000383；B2细T16/32为12.048887±0.000542、11.769199±0.001183。

当前建议：B2/T32为简化候选（相对BF16约+1.00%），B4/T32为更低损失候选（+0.716%），B4/T16为激进短流（+2.129%），B4/T64为低损失（+0.352%）。B3～4后增档无明显收益，未宣称B3显著优于4；未测B3的T16/32，未测T16/32同T IID。此前IID“128次折中”不能继续作为分层方案的结论。B4/T64/K16与B4/T32/K32几乎同PPL，优先考察较短T而不只减少K。

细K=T可理解为幅度码低位随机舍入；使用物理随机低位加区间控制，不是自然IID精度已被解决。区间计数器可研究复用现有流计数器；档号/准确跨档归约/移位/符号端点仍收费，W步长未保证PoT。GPU数值参考不是有限宽RTL或ASIC时序；无新PPA/能量面积实测，无基础任务或Llama新评测。

文献：DS-CIM LLaMA六任务未报告PPL；SCOPE小型字符RNN与XNOR-LSTM有真实语言PPL但非预训练LLM直接替换；SCMP公开代码采用Sobol/Owen、局部尺度/敏感INT旁路，归档未获取，仅方法线索。详细primary链接见LITERATURE_ZH。PR47已按用户授权合入TLM（merge `bef83e54b9da0081c51f393044d2156ce11a34b9`），Issue46已关闭；PR29仍待审未合并。Projects新查询缺read:project待同步。原件位于既有个人项目outputs/db27fa3d7ed8eced13513f0cad10061a3cc59a71/，Git仅汇总/索引，无权重/文本/校准原件。

## 5.7 三种短流FFN＋实际筛选/有限Ising/V采样：Issue50（2026-10-19）

用户要求确认§5.6三种较好FFN叠加真实Attention后的质量。新Issue50/PR52草稿（未合并），task/50-joint-ffn-attention，目录tmp/qwen-joint-issue50-20261019；原始base为PR47@5518a0a，PR47已由并行会话合并bef83e54后，PR52已改为集成分支pbit-tlm-attention-details-20261016。复用Attention成员Issue48/PR49的冻结执行源11f1d6ee，只读导入并保留来源/原字节，不接管amlink1219的独立Attention扫描或个人服务器目录。

三FFN固定W8：B2T32K32、B4T32K32、B4T16K16；全24层prefill与decode均替换。每个被计分token的24层Attention实际执行max4 train校准sigmoid/Bernoulli筛块＋固定8块修补→候选准确QK→burn16/spacing4有限hard-onehot CTMC Ising→输出索引直接V gather/平均。PV采样即最后一步，不重复抽一次。筛选不是耦合Ising退火；CTMC是理想硬互斥行为模型，不是物理电路实测。多token prefill Attention保留原SDPA，FFN前缀也替换，未用干净原FFN缓存。

旧完整FFN scorer每次q_len>1会绕过decode Attention补丁，故不能直接拿来测联合。本次建立cached计分器：逐目标单token、分别hook Attention和FFN，核对24层按序调用及目标数；对照匹配batch与目标位置。GPU门禁复现原BF16完整299077目标11.652735，但它只是环境参考；原FFN和B4T32下同BF16 SDPA包装器的计分logits SHA均完全相同。38上游＋10联合＋13FFN测试通过，另2完整计划测试通过。

主执行d61b2861edc91e00495268d39a738edb3599f87f，Slurm2381准备、2382主34项、2412诊断12项均完成。以下**全部仅为同一4096目标后缀**（32段×128、起始context2048、batch8），不是完整WT2；每替换组3seed，PPL算术均值：

| FFN | 原Attention | 筛选＋Ising128＋V采样 | 同路径Ising512 |
|---|---:|---:|---:|
| 原始 | 10.371557 | 11.163005 | 10.980212 |
| B2T32 | 10.476808 | 11.232234 | 11.066401 |
| B4T32 | 10.427377 | 11.197813 | 11.055307 |
| B4T16 | 10.628582 | 11.402422 | 11.201607 |

联合交互以每seed平均NLL计算Ljoint−Lffn−Latn+Lbase，六组均值约−0.0045～+0.00145，未见明显额外放大。主要损失来自Attention；B4T32较稳，但S512时与B2差值小，不能宣布显著优势。准确Softmax＋IID PV128诊断在原FFN下仍为11.094049，B4T32为11.166155，说明不能把误差全归Ising；尚无同协议筛选后准确PV，不能继续把剩余全部归筛选。实际QK候选22.756%，GQA的K候选并集约44.5%，不能混用或直接等于能耗节省。

54项计分原件（8小pilot、34主项、12诊断）＋10准备文件共64原件保留本人服务器/home/Hongjie_Zeng/projects/pbit-qwen-joint-ffn-attention-20261019-issue50/outputs/d61b2861.../。正式报告/逐seed逐段NLL/输入版本/SHA索引为qwen/results/joint_stratified_attention_20261019/。代码experiments/qwen_joint_stratified_attention_20261019/；collect_results.py和summarize_results.py可继续收集。固定公开train校准moment.pt为85917字节，SHA fefbb90c4f38c5f7a6d51a672550bd684ffe3a1415d36dc115a8ca5e05c5db0b，不重上传。

完整cached确认已提交，**尚未收齐**：新冻结源53dd0ff6a04218dc9f2b692464d5b16da284cf17，Slurm2429显存门禁成功（16×2047、32×1023前缀峰值16.23/16.31GiB），Slurm2430运行22项（新cached BF16×1、3FFN单独各3seed、原FFN及3FFN配Ising128各3seed）。batch32、window2048/stride1024、292窗口覆盖299077目标，每个目标实际走24层；固定S128不是逐query固定L/16。此前Slurm2425在实际full计划没有的32×2047-prefix pilot上OOM，未提交full worker，失败快照保留。新显存门禁覆盖实际批形状，没有修改旧执行快照。

完整原件在同本人项目outputs/53dd0ff6.../；已对其45项执行源Git blob与服务器SHA核验。恢复按work/jieruiz/50/HANDOFF.md核实Slurm2430，22项齐后生成FULL_SUMMARY.json并追加结论，不重复提交。当前仅阶段结果完成，Issue50/PR52保持open/draft，PR47已合并；Projects缺read:project，看板待同步。无新PPA/TLM能效结论。

### 5.7.1 固定B4T32、只改变Ising观测次数（同Issue50）

2026-10-19用户要求只用PPL判断次数变化。新源c0fd54446d843f0b21e94bf138c692048e518c86；Slurm2440重新核验模型/语料、49项执行源Git blob和原BF16后缀10.37155678462956，采样计划2测试通过；Slurm2441完成15新项（S32/64/256/1024各3seed＋筛选后准确PV三seed）。旧B4T32 S128/S512和FFN-only不重跑；原FFN六档参考复用成员Issue48/PR49公开summary，publication8dd1b06a、execution11f1d6ee、Slurm2380，未访问其个人服务器目录。

以下为固定32段×128目标=4096目标、batch8的**后缀PPL**均值（各3seed），不是完整WT2。burn16/spacing4、max4固定8块、FFN B4/T32/K32均不变；S为每query/head保留CTMC观测数，时刻16+4k，不是硬件更新拍或ESS。

| S | 原FFN＋相同Attention（成员已发表） | B4T32＋相同Attention |
|---:|---:|---:|
| 32 | 11.996331 | 12.065755 |
| 64 | 11.376921 | 11.514886 |
| 128 | 11.163005 | 11.197813 |
| 256 | 11.024839 | 11.066594 |
| 512 | 10.980212 | 11.055307 |
| 1024 | 10.924655 | 11.006579 |
| 筛选后准确Softmax/PV，不采样 | 10.895520 | 10.970368 |

只看本轮后缀，1024最低；256/512均值差0.011，小于各自seed标准差0.026/0.017，尚不支持明确差异或等价结论。准确PV是候选内取消采样的参考，不是PPL数学下界；不能把所有残差归Ising或把5%当发表通用标准。原FFN与本任务权重/文本/token/目标一致，原始配置/分词器部分元数据字节不同，已披露，不宣称所有输入文件逐字节相同；重叠S128/512均值完全匹配。

新正式成果qwen/results/ising_sample_sweep_20261019/{RESULTS_ZH.md,SUMMARY.json,PPL_CURVE.png/svg/csv,ARTIFACT_INDEX.json,PREPARATION.json,references/}；12公开制品Git blob/摘要字节重现/25项逐段NLL核验通过，图已视觉检查。新16计分原件＋5准备文件=21文件及旧10个对照原件均用SHA索引，留本人同一项目outputs/c0fd5444.../。原源快照不修改，没有新训练、任务基准、PT/PPA/TLM。

经后缀审阅，Slurm2461已提交6项B4T32 S256/S512各3seed完整cached确认（299077目标、2048/1024、batch32），复用53dd已验证实际显存门禁并校验数值内核未变；旧Slurm2430的S128和匹配BF16/FFN-only继续运行，不重复提交。**两组完整联合任务均未收齐**；恢复按work/jieruiz/50/HANDOFF.md核实2430/2461、按同full目标SHA合并对照，不把后缀或启动任务写成完整完成。PR52仍草稿未合并，Issue50保持open，Projects权限待同步。

## 6 随机源、p-bit与相关性

双流误差追加诊断见Issue30公开结果目录 `ERROR_DIAGNOSIS_ZH.md`。已有47项的T4096精确双流x概率层均值5.3492%、z0.8255%；T256/4096最大z裁剪约0.000964%/0.001767%，不支持大面积饱和是当前主因。在同一固定输入/尺度下，独立权重流增加非负条件方差；经SwiGLU和多层传播的主导位置仍待消融。DS-CIM使用加128偏移、128粒度FP8对齐、优化PRNG/seed及SRR，LLM为T256误差pattern注入和六任务准确率，不能等同本项目IID逐连接短测，也不能认为加SRR就会比现有精确计数更准。

三种服务必须分别命名：

- 原始均匀随机字：物理TRNG或本地PRNG，供数字比较器/CDF/地址抽样。
- 可调概率p-bit：根据驱动I输出0/1，典型 `P(1)=sigmoid(2I)`；直接使用器件tanh/ sigmoid响应。
- 耦合p-bit网络：如Ising类别竞争，涉及状态、反馈、更新和相关采样。

任意幅度概率p若直接用tanh器件，需要对应驱动反变换或经过其他编码；把v直接接到tanh不等于得到 `p=|v|/S`。数字随机字比较与物理p-bit一次状态更新不能共用同一成本标签。

已给物理源参数：120.80µW、450MHz、每拍16原始bit。由此 `Ebit=P/(f·16)=16.7778fJ/bit`。这是原始输出预算；没有自动包含比较、分发、网络反馈和读出。固定模块仅使用部分输出时，总功率不一定按用到的bit数线性缩小。

当前随机源层次：根熵源/种子服务→本地子PRNG→邻近算子；可配置重播种周期、每tile/每请求更新和分发。FFN本地A8、64路共享已接入TLM，输入侧概率寄存器副本可以去除，但比较器、必要激活/概率数据和流状态仍存在。权重侧暂按原方案，不能把输入随机数减少64倍说成整机省64倍。

v2具体默认是32位PRNG状态输出8位字，每新输入tile派生子种子、输出波重放同输入流，根按需约每1秒刷新256调理bit；并非每拍都需要物理熵重播种。SHAKE域分离属于软件种子参考，不是已实现的免费硬件SHAKE。Attention消费者保留本地/层次服务；Ising宏内随机成本封装一次，不能重复计费。

共享一个随机数到多个通道会制造相关性；同一乘积的两侧不可随意共用同一个阈值，否则乘积概率可能变成min型而非pA·pW。可以用两路独立物理随机字，或经验证时间独立的新随机字交替供两侧。比较器/区域映射控制相关性，不等于必须使用特定随机序列。

分层/低差异/确定性枚举作为对照单独标注：随机分层是在固定区间覆盖上加抖动，不能称完全IID；256码值范围并不意味着256次IID必然覆盖全部值，更不保证二维乘积的联合频率精确。延长流增加频率分辨率，不消除偏置或系统碰撞误差。

## 7 Attention路线与容易混淆的地方

| 方案 | QK/候选 | 概率或采样 | V阶段 |
|---|---|---|---|
| 原版 | 全部QK | 准确Softmax | 准确PV |
| PV采样 | 仍全部QK | 准确Softmax后类别抽样 | 只读所需V，按重复次数累加/平均 |
| 筛选后准确 | 摘要筛块，再计算候选QK | 候选内准确Softmax | 候选准确PV |
| 筛选加PV | 同上 | 候选内Softmax后采样 | 只读采样V |
| Ising＋V选择 | 仍需score；可先筛选减少维数 | score驱动类别竞争，含预热/更新/有效样本问题 | 读出类别后V选择累加 |
| 随机Q/K投影 | q_proj/k_proj静态权重随机化 | QK动态点积仍准确，后接对应方案 | 按配置 |

max4块筛选：64位置为一块，4个子块均值摘要与q点积，取最大分数，标准化/校准后sigmoid，Bernoulli保留；首块和近块强制保留。**这不是多步Ising退火**。固定预算修复含排序/补齐成本，也不是免费输出固定K。

Ising稠密互斥耦合可在数学上用总激活数广播实现等价局部场；物理时延、异步一致性、广播线、更新吞吐及混合时间仍需设计，不能据此宣称互连代价完全相同或为零。v4把内部细节暂抽象为宏模块，默认理想索引轨迹不验证物理网络平衡。

Qwen GQA每KV头对应7个Q头。各头候选K的并集可能很大，所以“每Q头筛30%”不等于物理K读取30%。V可按实际采样位置去重，仍需按KV组和burst统计；逻辑项数、唯一索引数、物理DRAM字节数分开。Llama7B的MHA没有相同GQA并集结构，但也有burst、重复和布局成本。

PV采样采用比例预算，当前参考为S/L=1/16：2K约128，8K约512；历史固定512保留作历史对照。`counts@V`可以是软件数值模拟，不能据此生成仍读全部V的稀疏硬件事务。采样去重/排序、burst合并、GQA复用与缓存应进入调度。

### 7.1 本地PV v6纠错结果

来源：`architecture_tlm/PV_STREAM_V6_RESULTS_ZH_20261016.txt`、`PV_ENERGY_AND_ISING_AUDIT_ZH_20261016.txt`。v6采用systematic偏移、前缀计数、KV组V并集、广播和最多32个64B请求在途，修正旧逐样本CDF和逐地址DMA排空的串行化；**没有集成筛选或Ising，也不是SANTA CUDA内核原样复刻**。

| DRAMSys情景 | 2K/128采样 | 8K/512采样 |
|---|---:|---:|
| 准确PV阶段→v6 PV阶段 | 3.405→2.756 ms/token | 13.600→10.959 ms/token |
| v6物理V读量/完整V | 34.65% | 34.55% |
| 准确完整Attention→v6 | 7.074→7.036 ms/token | 28.271→28.083 ms/token |

约19%的PV局部加速不等于整个Attention或整机19%加速。第一遍QK/指数、预算和第二遍扫描抵消较多收益；该版新比例预算的质量仍需独立PPL。v6报告标为本地，不能自动称已发布workspace。

## 8 FFN硬件与片上存储

普通调度基准：gate/up可并行或共享引擎分块执行；得到对应g/u后做SiLU和乘积；再供down；残差保留高精度。流水化需要精确的数据依赖、tile就绪和队列容量，不能凭画出流水线就认为达到最优。

权重存储分三种边界：

1. 普通SRAM→读出→计算阵列：按所需带宽分bank/端口，计读能量和必要短暂保持；不默认存在零成本全矩阵并行读。
2. SRAM/计算邻近：增加本地复用、比较器或小阵列，仍要清楚哪部分是库宏、哪部分是标准单元。
3. 定制数字CIM：存储单元或读出路径参与比较/乘法/归约，需要定制电路、寄生和接口验证；普通SRAM宏不能直接套DS-CIM全部峰值。

早期64输入×单输出小核PT，不等于64×64并行阵列；旧权重DFF、P12、T4096、100MHz、特定PVT和活动模式外推存在边界。应比较同工艺、同工作负载、同质量、相近吞吐与存储条件下的确定定点/位串行/随机方案。

不存4096拍所有结果：每拍或每小批更新压缩状态/计数，末尾恢复；所需状态与fan-in、位平面、分组和计数范围有关。缓存B拍可能减少大累加器切换，也增加局部计数器、控制和寄存器活动，必须实测PPA。

### 8.1 已有PPA应保留的负面结果

| 同一批/模式对照 | 约50%活动的能量/帧 | 含义 |
|---|---:|---|
| 37981139精确树→CSA | 25.893→45.430 nJ | 当前CSA映射更费能，面积也增加；不证明所有压缩器均无用 |
| 38015538 G1/B1→G1/B8 | 52.595→58.030 nJ | 当前无ICG缓存实现增加10.33%总能量 |
| 38015538 G2/B1、G4/B1、G8/B1 | 50.322、47.186、45.351 nJ | 普通有损OR，不能当等精度收益 |

它们的电路边界不同，不能跨批次直接排名。详细汇总本地 `sc_architecture_power_comparison_20261014/00_先看这里_架构功耗对比.txt`。

Q10 SwiGLU后处理另有100MHz单通道4级流水、II=1的工艺仿真：TT active约5.565～6.711pJ/结果，SS约4.486～5.352pJ；面积TT 0.00866412mm²、SS 0.00946620mm²。输入范围/活动模式影响能量；这不是布局后或真实模型激活测量，尚未自动接入已发布TLM。来源见第11节。

## 9 总体TLM、内存调度和功耗模型

| 层次 | 当前实现/入口 | 估计范围 |
|---|---|---|
| 系统计算调度 | `architecture_tlm/system_decode.py`、`system_decode_local_shared_v2.py` | 层/tile依赖、算子宏成本、等待、双缓冲；Python LT模型 |
| Attention v3/v4 | `attention_tlm_v3.py`、`screen_ising_tlm_v4.py`、`ising_macro_v4.py` | 稀疏地址、候选、V读取、显式更新或Ising宏参数 |
| 随机源 | `rng_hierarchy.py`、`rng_local_shared_v2.py` | 供给/分发、种子、共享、吞吐与能量；具体后端由配置决定 |
| SRAM | `sram_cacti_calibration_v1.py`、`cacti_memory.py` | 已有宏查库，其它尺寸用校准探索估计；bank/端口限制需调度 |
| 外存 | `architecture_tlm/dramsys/` | 实际DRAMSys SystemC/TLM事务后端；默认Link结果不等于已跑DRAMSys |
| DRAM功耗 | DRAMPower + memory spec/电流参数/电源策略 | ACT/PRE/RD/WR/刷新、后台、低功耗与接口；输入profile必须核验 |
| 映射探索 | `mapping_decode.py`、ZigZag相关脚本 | 受限定资源/映射空间搜索；不是全架构全局最优证明 |

SRAM已有55nm工艺SS/TT资料，CACTI采用多配置校准与独立宏验证；面积不应只按最小宏颗数机械放大。已有宏参数优先直接使用，未见尺寸给拟合误差；写能量等不确定项保留区间。库本体不得上传。

校准v1为A～F六种几何拟合、H独立验证、SS/TT分别；H验证面积误差约15%、内部读能量约9.3%、内部写能量64%～73%，因此不能称全指标校准到10%。F=4096×128宏64KiB、面积0.31216331mm²，SS最小周期约11ns；当前探索先取80MHz SRAM与100MHz计算核，CDC/读出实现未闭合。

Qwen本地v5探索起点为1MiB统一16bank、1RW、16B交织及16GB/s互连上限；有462个Link初筛点和后续详细情景，不是最终最优SRAM规模。Llama独立TLM使用8MiB等不同配置，不能机械复用1MiB结论。

DRAMPower不是无条件正确的常数表：与具体DRAM电压/IDD、VPP、接口及低功耗状态定义有关。历史PV读取减少而DRAM能量上升曾涉及VPP参数问题；修订profile与旧trace重新计价必须保留版本，不能静默重写旧结论。DRAM低功耗收益还取决于可进入空闲的持续时间、进入/唤醒和再激活。

Issue5已引入Micron厂家完整core电流限值新情景。旧统计重计价后，PV core能量仍比准确Attention高约0.566/2.340mJ/token（2K/8K），碎片化空闲减少长SREF区间仍可能增能。此前置零VPP仅是因果诊断，不能当最终校准。新Llama TLM显式使用新profile；I/O/PHY仍有未标定部分。

系统比较输出至少包括时间/token、J/token、平均功率、面积分解、SRAM/DRAM字节、采样/RNG/计算/等待占比。`E=P·t`；低功率但更慢不等于低能量。GPU平均功率、GPU J/token、ASIC估计J/token及算术节省比例分开报告。

尚未证明全部调度最优：片上bank仲裁、多DMA/回压、队列容量、NoC/时钟/CTS、真实源相关、Ising混合和prefill/decode分别建模仍有缺口。不能把未标定项置零来宣称整机千倍。

## 10 质量和硬件结果的证据口径

| 结果 | 数值/含义 | 来源与边界 |
|---|---|---|
| Qwen BF16完整WT2 | 11.652735 | `results/base_bf16/`；必须保持模型/tokenizer/语料/window/stride一致 |
| 原FFN＋PV采样 | 11.717755±0.002673 | 3 seeds，完整WT2；历史采样预算见原配置，不能与新比例预算自动视同 |
| Qwen A8共享64固定W | T4096 12.4535±0.0057 | 第5节；准确输入联合计数，准确Attention |
| Qwen A8共享64双随机W | T4096 14.1483±0.0132 | 第5节；权重残差Gaussian参考，非完整精确分布验证 |
| Llama2 BF16完整WT2 | 2K 4.979503；4K 4.895831 | `llama2/results/`及Issue14；不能与Qwen数字比较质量 |
| Llama2固定W8+A8，无采样 | 5.038305 | Issue19已合并阶段；准确SiLU，原Attention |
| Llama2分层采样128/64 | 5.308904±0.001642 / 6.758371±0.008464 | Issue19阶段，三种子；不是纯IID |
| Llama2 IID256 | 6.256753±0.005911 | Issue19阶段，三种子；其余配置以最新结果为准 |

完整WT2按目标token总NLL合并后取exp；不能平均窗口PPL。历史后缀指标是2K的32段×128目标、8K的16段×128目标等，须看各自protocol。固定前缀/探针、合成trace、RTL功能、DC/PT、器件测量各用原名称。

代码、模型revision、tokenizer、train/test文本、配置、种子、精度、采样、共享和环境均需版本和SHA256。WikiText parquet空行恢复为一个空格加LF，直接普通newline join可能破坏历史语料hash。长轨迹、权重、数据和原始PT产物留约定共享存储，Git提交索引及manifest。

Qwen正式test raw SHA256为 `173c87a53759e0201f33e0ccf978e510c2042d7f2cb78229d9a50d79b9e7dd08`，旧完整输入token hash为 `8d41d21825bb0e103dc63337727daf4b51c631cacec5937f014b119ae209081e`。本地 `pbit_llm/data/wikitext-2/wiki.test.raw`只274432 bytes、SHA `d2eaaf4cc05caaa66707285cb34c0c8aa944de4843f9f2f40fed4c6aabb1b332`，**不符合正式完整语料，不能直接拿它复现上述PPL**。本次未改写它。

### 10.1 Qwen3.5和Llama TLM的独立边界

Qwen3.5完整2K WT2原版15.661098；动态随机FFN＋PV为15.923481；再加18层DeltaNet out/z/QKV投影联合为16.124398（3 seeds），相对原版约+2.958%。固定投影替换仍保留卷积、门/状态更新、归一化等；状态每token只递推一次，不能在每个随机采样拍重复提交。已有25份投影PPL（其中4份8K），没有8K全部联合或完整DeltaNet TLM。模型revision `2fc06364715b967f1860aea9cf38778875588b17`。

该DeltaNet每层16头×128×128的FP32状态约1MiB，18层共18MiB/序列。固定投影占所列DeltaNet MAC约92.84%，但不能据此忽略状态存储/读写；其状态路径没有普通Softmax/PV可直接套用。

LLaMA-1当前标准82项TLM，Llama2为116项，涵盖Link/DRAMSys和多上下文；算法联合质量需另看对应实验。Llama2当前2K筛选PV在同SC FFN情景下整机能量约降2.16%，但相对数字W8 TLM仍约高219%，不是GPU能耗比较。它使用少量真实decode QK捕获，不是全语料筛选质量验证；Ising仍有IID oracle边界。

### 10.2 新器件与随机架构质量指标核查 Issue51

2026-10-19，独立文献任务Issue51修正此前“PPL增幅5%以内较好”的解释：它只能是本项目自定工程预算，不是DAC或体系结构会议统一门槛。报告与14项原文表值复算在[质量指标报告](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/task/51-emerging-quality/architecture_tlm/EMERGING_LLM_QUALITY_METRICS_ZH_20261019.md)及同目录EVIDENCE JSON；用户master_report目录有正文副本。

- MICRO2025 Kelle Table2：Llama2-7B WT2 FP165.47→5.74（+4.94%）；13B4.88→5.62（+15.16%）；7B PG1910.51→12.59（+19.79%）。这是W8A16/KV淘汰/eDRAM retention等整套方案损失，不是单独器件误差，也不是发表容忍线。
- DATE2026 DS-CIM：LLaMA7B FP8六任务平均66.0%，DS-CIM1/2为62.6%/58.8%，即损失3.4/7.2个百分点，不能称PPL上涨3.4%/7.2%；质量表使用T256，不与短流宏峰值混配。
- DAC2025 UniCAIM用LongChat问答F1；DAC2026 CQ-CiM用检索指标且LLM保持FP16；DATE2026光学PCM SCARLET用下一token准确率而非PPL。指标不同来自应用/验证范围，不证明新器件可以自动忽略生成质量。
- 新器件另需验证噪声、漂移、故障与校准，但局部NMSE/ENOB不能代替完整模型。我们保留BF16→匹配确定性量化→有限随机/器件路径三层参考，并报告逐任务、FFN/Attention/联合与质量匹配能量/时延曲线。
- VQT-CiM、HEIRS、DBC的可核质量表全文本轮仍缺，不引用二手精度或所谓5%阈值。报告没有新模型/PPL/RTL/TLM/PPA/服务器实验，不改变Issue46/48/50。


补充入口：[论文与任务指标对照](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/task/51-paper-task-map/architecture_tlm/LLM_PAPER_TASK_METRIC_MAP_ZH_20261019.md)，含11篇论文总表、任务解释、GLUE/AFM协议与未明确口径；用户副本在pbit_llm_master_report_20261012/LLM_PAPER_TASK_METRIC_MAP_ZH_20261019.md。原报告PR53已合并856105b，原备忘录补丁PR54已合并e0abc39；任务对照PR56已实际合并`fdceb386d9abe993f494ec09945ef8da35863bb1`；备忘录补丁PR57已合入任务28分支`d3861072ff88dbc4e66f2a7844eed4f8ec97245b`，随PR29交付。无新模型或硬件实验。

## 11 重要文件与成果位置

正式仓库内相对路径以实际任务分支为准；未合并PR的文件不要去旧main找。下列本地路径均相对 `C:/Users/86134/Documents/a_P_BIT/`。

| 主题 | 稳定入口 |
|---|---|
| 本备忘录 | 本地根 `PROJECT_MEMORY_ZH.md`；仓库根同名文件；AGENTS有必读提示 |
| 当前TLM总索引 | 本地 `tmp/project-memory-issue28-20261018/architecture_tlm/WORKSPACE_LATEST_ZH.md`；仓库路径 `architecture_tlm/WORKSPACE_LATEST_ZH.md`，工作区集成分支；混合根同名路径不存在 |
| TLM需求/全局资料索引 | `pbit_llm_master_report_20261012/TLM_REQUIREMENTS_AND_FILE_INDEX_ZH_20261014.md` |
| 旧总报告/Word | `pbit_llm_master_report_20261012/PBIT_LLM_MASTER_REPORT_ZH.md`、`Qwen概率计算方案与能效估算总报告.docx`；日期较旧，需合看本备忘录 |
| P-DNN算法设计 | 仓库 `experiments/pdnn_ffn/P_DNN_FFN_DESIGN_ZH.md` |
| 双随机固定Sz | `pbit_sz_dual_ffn_20261014/README_ZH.md`、`results/RESULTS_ZH.txt` |
| A8共享64双流/固定W | `pbit_shared_rng_ffn_20261015/README_ZH.md`、`results/RESULTS_ZH.md` |
| 新精确双随机短测 | `tmp/qwen-dual-iid-public-issue30-20261018/qwen/results/dual_iid_exact_20261018/ANALYSIS_ZH.md`；Issue30/PR31，47项齐全；原始输入/逐case结果用ARTIFACT_INDEX和CALIBRATION_ARTIFACTS索引 |
| 新短流RTL/能量 | `tmp/qwen-short-stream-issue22-20261018/`；Issue22/PR25，未合并，尚无新PT或Qwen短流PPL |
| 小核心旧PT | `sc_weighted_rtl_20261011/`、`tmp/37962470/`；核对PVT、活动与排除项 |
| 分组OR＋缓存PT | `sc_grouped_or_cache_20261013/results_38015538/结果检查与功耗总结.txt` |
| SRAM权重存储版本 | `sc_weight_storage_or4_20261014.zip`；归档不作为原始工艺库公开 |
| SwiGLU后处理PT | `tmp/ffn-epilogue-ppa-20261017/architecture_tlm/results/ffn_epilogue_ppa100_38100634/RESULTS_ZH.txt` |
| 数制转换RTL | `format_conversion_rtl_20261016/README_ZH.txt`；功能验证与工艺表征分开 |
| SRAM实测/库资料摘要 | `architecture_tlm/SRAM_PT_CHARACTERIZATION_ANSWERS_ZH_20261016.txt`、`SRAM_CACTI_EXISTING_RESULTS_SS_TT_ZH_20261016.txt`及校准报告 |
| 文献清单 | `pbit_llm_master_report_20261012/PBIT_LLM_RECOMMENDED_READING_ZH_20261018.md`；Issue23/PR24 |
| 17篇文献总结 | `pbit_llm_master_report_20261012/PBIT_LLM_READING_SYNTHESIS_ZH_20261018.md`；仓库Issue26/PR27；用户补充PDF后17项主文均已读 |
| Qwen3.5实验总入口 | `qwen35_publish_20261013/experiments/qwen35_20261013/README_ZH.md`，独立历史发布包 |
| 物理随机矩阵新文献 | `tmp/physical_rng_matmul_20261018/agent_a/NOTES_ZH.md`、`agent_b/notes.md`；尚未并入17篇原报告 |
| 远程登录材料 | 原有本机SSH配置/远程说明保持本地；备忘录不复制认证内容，恢复时使用原路径与任务handoff |

## 12 远端任务与交接索引

### 12.1 2026-10-19 待审PR审核与实际合并回执

用户授权按最新GitHub内容审核并合并。下表为Issue55本批实际回执；后面的旧索引保留为历史快照，不能据其“待审”文字撤销已发生的合并。PR47由此前单独审核合并。

| PR | 实际目标分支 | 合并提交 |
|---|---|---|
| #2 | `main` | `35db82089ea6b76f5fcf76458c37d8ee59d4c7c9` |
| #4 | `pbit-tlm-attention-details-20261016` | `7bf80c97b7a77050660e46f6b3a12d03039b4725` |
| #6 | `pbit-tlm-attention-details-20261016` | `92234f3ffc1d91a301e2da8a635ed54e29c408ac` |
| #8 | `pbit-tlm-attention-details-20261016` | `6e94bf15cb1a3523274f80a26f36e75604e3c8f8` |
| #10 | `pbit-tlm-attention-details-20261016` | `fe9238ebb2b4e19d9ffa03e5b75eaa210cdab48e` |
| #11 | `task/7-ffn-cim-scheduling` | `89c5725064bfa1827e28c6566e3899dbc5cb1f9e` |
| #24 | `pbit-tlm-attention-details-20261016` | `2ede802c3725cceca50eb3bccfdb33653c3fcde5` |
| #25 | `pbit-tlm-attention-details-20261016` | `c0ca336657757967e9c0512da17453e1f3181586` |
| #27 | `pbit-tlm-attention-details-20261016` | `1ec98aee2f28bd4f21f48bf6d31c95787e430e9b` |
| #40 | `pbit-tlm-attention-details-20261016` | `e4798f70cb57a864cbbfeb20b83674e1dadc1c4b` |
| #41 | `pbit-tlm-attention-details-20261016` | `82229d54750d65b925f72050f0d8478bc2013c90` |
| #42 | `pbit-tlm-attention-details-20261016` | `ed0c7a4e8e9546ec89895135efff36aa8a00d568` |
| #43 | `pbit-tlm-attention-details-20261016` | `202eac13d17d88cf049330a620bec844b4c4037d` |
| #44 | `pbit-tlm-attention-details-20261016` | `46c12e5f6c1c07751272871abb360c35735e8d59` |
| #45 | `task/36-digital-attention-reference` | `1b0af7604037ce8a772063bd9583ce9e1f96f0e5` |
| #53 | `pbit-tlm-attention-details-20261016` | `856105beaefaee307ba1a9b1972aa61d8f82ba59` |
| #54 | `task/28-project-memory` | `e0abc39fb4fb83510fabb5c6ef22dcc8e3c39a6b` |
| #56 | `pbit-tlm-attention-details-20261016` | `fdceb386d9abe993f494ec09945ef8da35863bb1` |
| #57 | `task/28-project-memory` | `d3861072ff88dbc4e66f2a7844eed4f8ec97245b` |

PR29科学正文已审核；源head为`d3861072ff88dbc4e66f2a7844eed4f8ec97245b`，刷新至集成基线`fdceb386d9abe993f494ec09945ef8da35863bb1`后交付。PR29实际合并回执及本批完整报告见[Issue55](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/55)。#11随#8、#45随#44的内容已进入集成；#54与#57随PR29交付，不能仅凭子分支合并声称已进入集成。#2的实际目标仍为main，其余正式科研集成位于TLM分支。

#49（`8dd1b06aa465b3bdaaed60ae321c5362983ae169`）与#52（最后补审资料为`e3c5e957c3769b5fc6867b42a52facace647a83b`）保留draft：完整确认/质量验收未完成，不替作者标为ready，不启动重复作业。后续恢复须重新读取实时head及Slurm。

Issue7（实际TT/SS DC/VCS/PT）、Issue22（短流硬件/质量后续）、Issue37（最终质量与硬件验收）、Issue28（持续记忆维护）继续开放；48/50随草稿工作继续。其他本批有限交付的Issue按实际验收回执处理。仓库合并权限可用；Projects看板的read:project仍待同步，不把看板授权范围与仓库写权限混为一谈。

本轮独立审核未启动新GPU/服务器/许可EDA实验。硬件TLM的13项测试、4组数值重放和84源/结果blob保留通过；最终科学集成`e4798f70cb57a864cbbfeb20b83674e1dadc1c4b`的102项CPU测试为101通过/1个Windows符号链接权限跳过，另1协议fixture通过，43/44/45/40汇总复现。后续文献/备忘录交付须核对科学blob未变。

### 12.2 早期远端状态快照（原文保留）

2026-10-18通过GitHub API核实，登录 `jieruiz`；有仓库admin/push权限。目标仍按项目审查流程用PR交付，不把权限等同于所有PR已批准。

| Issue / PR | 核实时状态 | 接续范围 |
|---|---|---|
| 1 / 2 | open / 未合并 | 工作区治理；保留原实验复现规则 |
| 3 / 4 | open / 未合并 | 架构可用性与调度审计 |
| 5 / 6 | open / 未合并 | DRAMPower参数、DS-CIM权重实现 |
| 7 / 8、11 | open / 未合并 | FFN调度、SwiGLU RTL及PPA |
| 9 / 10 | open / 未合并 | 筛选K读取并集与burst放大 |
| 12 / 13 | closed / 已合并07d0338 | LLaMA-1当前TLM |
| 14 / 15 | closed / 已合并7a50636 | Llama2 BF16基线与116项TLM |
| 16 / 17、18 | closed / 已合并 | qwen/llama1/llama2三目录 |
| 19 / 20、21 | Issue仍open；阶段PR已合并40ea9f1、3553996 | Llama2全32FFN精度分解；剩余作业不因阶段合并而完成 |
| 22 / 25 | open / 未合并 | Qwen短流A8共享64 RTL与条件能量 |
| 23 / 24 | open / 未合并 | 论文推荐清单 |
| 26 / 27 | open / 未合并 | 17篇原文总结；当前报告SHA为41d5118da9d0b259e1ee54453362251ed020e5f2e06baa6a7179bf07844c7970 |
| 28 / 29 | open / 已推送待审、未合并 | 本备忘录、恢复入口和状态索引 |
| 30 / 31 | closed / 已合并d589f152 | 精确短流参考47输出，完整精确随机WT2未做 |
| 32 / 34、38 | closed / 已合并5b71d4e、c1555ae | 范围49输出＋真实分布/项目入口，完整随机/裁剪WT2未做 |
| 39 / 40 | 实验完成，PR待审未合并 | 裁剪/固定PoT范围65替换；独立目录tmp/qwen-ffn-clipping-issue39-20261019 |
| 46 / 47 | closed / 已合并bef83e54 | 固定W8多档＋分层；145输出/154原件，含67新完整配置，目录tmp/qwen-fixedw-multiscale-20261019 |
| 50 / 52 | 34后缀主项＋12诊断＋15次数扫描完成；完整2430/2461运行，PR草稿未合并 | 三种FFN联合及固定B4T32的S32..1024 PPL；见§5.7/5.7.1和tmp/qwen-joint-issue50-20261019 |
| 51 / 53、56 | 原报告PR53已合并856105b；任务对照PR56待审未合并 | 质量报告与论文任务/指标对照；补充目录tmp/paper-task-map-issue51-20261019；原备忘录PR54已合并e0abc39 |
| 33 / 待核验 | open，负责人amlink1219 | Attention价值核查与实验计划；与FFN Issue32分开，不接管他人状态 |

Issue19此前交接记录的Slurm数组为2084，8/9等子项尚在运行或排队；这只是此前STATUS快照，不是本次查询实时队列。继续前必须查当前squeue与原manifest，不取消/重交已有作业。精确入口：`tmp/llama2-ffn-precision-issue19-20261018/work/jieruiz/19/HANDOFF.md`及该目录个人STATUS。

Issue30开始前另查本人squeue为空；这说明旧作业当时不在队列，不代表Issue19剩余结果已经收回/核验/合并。其余结果仍需原任务collector及manifest确认。

个人进度统一在每个任务checkout的 `progress/jieruiz/STATUS.md`，辅助资料在 `work/jieruiz/<Issue>/`。同一人多个任务checkout可能保留不同时间的STATUS，必须结合远端提交与本节导航，不能把最后读到的一份当全项目唯一最新。

## 13 已纠正的认识与不得重复的错误

- “随机计算必须用特殊PRNG序列”不成立。自然随机可以正确计算，特殊覆盖主要影响短流方差。
- “有精确并行计数就不可能省面积/能量”不成立；已有物理TRNG＋AND＋精确计数研究，但其任务、精度和基线不同。
- “随机流长度256就有8位准确度”不成立：输出网格分辨率和估计误差不同；独立随机频数存在方差。
- “OR计数天然等于加法”不成立；普通OR有碰撞偏差，互斥重映射是另一编码。
- “PV稀疏只减少乘法，KV可以仍全读”不符合本项目稀疏数据流目标；真实索引gather/去重/突发必须实现。
- “操作少了整机一定更省电”不成立；后台时间、DRAM电源profile、布局放大和重复收费要核查。
- “Ising参考模拟时间可直接当芯片周期”不成立；有效独立样本、更新/混合和物理采样频率需标定。
- “普通SRAM＋寄存器就是定制CIM”不成立；读端口、保持、比较与局部计算边界必须画清。
- “层数、模型和评估协议差不多可以直接比较”不成立；Qwen与Llama、20/24/32替换、后缀与全量、动态与固定尺度都需明确。

已有直接物理随机证据：APL2021 SOT-TRNG ANN采用输入/权重随机流、AND与并行计数；256拍45nm综合结果有面积/低功率及能量收益，1024拍能量优势消失；基线为FP32，非INT8强基线，器件rawbit实测而全ANN是仿真。DATE2017 VC-MTJ点积/FIR报告模型级能量收益；SFQ2024有低温矩阵实物功能。不要把这些倍率直接套到Qwen。

## 14 后续维护与恢复流程

1. 进入本项目时，先读AGENTS和本文件第0、1、12节，再读当前任务Issue/PR及HANDOFF；核对实际Git根、分支、diff、remote、GitHub身份和远端最新SHA。
2. 根据主题读第3～10节及原证据，不重复把曾失败/已完成的实验当新任务。发现资料冲突，以原manifest、准确版本和最新验证为准，记录替代关系，不覆盖旧成果。
3. 每次有重要结果、方案改变、任务提交/合并或阻塞，更新本文件对应章节与版本记录，并维护STATUS；保留时间、协议、证据链接和SHA。
4. 正式仓库根文件是版本化交付；本地 `a_P_BIT/PROJECT_MEMORY_ZH.md`为同字节阅读副本。发布后校验两者与Git blob一致，避免两份独立编辑漂移。
5. AGENTS入口能让在本项目目录工作的后续Codex按规则重新读取；这不是模型对所有新会话的永久内在记忆。若新会话不在此工作区或没有文件访问，用户需提供工作区或此文件路径。
6. 凭据、SSH内容、token、工艺库、受限论文PDF不进入备忘录或公开Git；只保存安全路径/来源及必要摘要。

## 15 版本记录

- 2026-10-18，Issue28：建立覆盖历史对话的首版主题备忘录，核实workspace身份/分支/任务状态，加入双随机既有结果、物理随机适用条件与后续精确验证缺口。文档任务没有产生新PPL、RTL/PT、训练或TLM仿真结果。
- 2026-10-18，Issue30/PR31：首版备忘录交付后完成47项精确短流风险检查，补充第5.1节和结果索引；该模型测试属于独立任务，不混称Issue28进行了模型实验。

- 2026-10-18，Issue32/PR34：独立A/W范围对照、逐投影理论诊断及128/2048token确认共49输出完成；自然IID低T明显改善，保留动态范围成本及前缀协议边界。

- 2026-10-19，用户授权合并：PR31/34/38均已合入TLM，Issue30/32已关闭；补充8192train-token真实直方图、极值能量与裁剪口径，保留未跑裁剪PPL/未测PPA边界。

- 2026-10-19，PR47独立审核与用户授权合并：25项核测试、145计分/154原件、98次执行blob和60次发布blob检查通过；合并提交`bef83e54b9da0081c51f393044d2156ce11a34b9`，两个父提交及与审核head同树均核实，Issue46于15:46:38（北京时间）按验收完成关闭。[审核记录](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/47#pullrequestreview-5568295057)及[合并回执](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/46#issuecomment-6262300688)已在线。GitHub集成403不等于仓库账号无权限；本机jieruiz已核实admin/push并成功合并。Projects仍缺read:project。没有新GPU推理或PPA，K>1仍为受控分层；PR29继续待审，不随PR47合并。
