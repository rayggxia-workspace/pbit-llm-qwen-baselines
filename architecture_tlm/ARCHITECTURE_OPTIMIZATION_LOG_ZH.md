# 概率计算架构优化记录本

维护入口：Issue186 / PR190；负责人jieruiz；建立于2026-10-25。这是论文准备的**机制与证据索引**。具体电路结果仍只登记在 `digital_circuit_simulation_registry/`，不在这里另造功耗台账。历史记录不因新方案出现而删除。

## 当前可以说到什么程度

当前统一执行器为 `unified_v6`，共同调度基线为PR190，依赖PR183。它有完整decode图、有限tile生命周期、真实DRAMSys以及SRAM容量/端口模型；部分算子和新增接口仍采用有界延迟宏。结果是**带假设的架构级时延/活动估计**。既不是全芯片周期精确RTL，也不是全部已有PPA。没有通过匹配模型质量验证的新映射，不能继承旧PPL。

上一轮试验是“跨输入块的部分和本地驻留＋128阵列组织”。入口：[详细结果](unified_v6/FFN_LOCALITY_ZH.md)、[13项完整对照](unified_v6/results/locality_20261025/COMPARISON.csv)。默认路径保留原实现，候选通过配置显式启用。

最新增量为O13：[资源与调度16项消融](unified_v6/RESOURCE_SCHEDULING_ABLATION_ZH.md)。O12：[LLMCompass独立时延核对](unified_v6/LLMCOMPASS_COMPARISON_ZH.md)。O11的[HBM整机结果](unified_v6/HBM_RESULTS_ZH.md)保留。新比较不修改现有TLM默认，也不把原生GEMV的解析分支称为周期精确整机。

## 已有改进总览

| ID | 问题与具体改进 | 已有实现／证据入口 | 可用于论文的结论和边界 |
|---|---|---|---|
| O01 | FFN长随机流：固定W8、四档幅度、门限分层；GU与非线性/Wd分别明确采样数 | [FFN当前合同](unified_v6/FFN_CURRENT_ZH.md)、`ffn_latest.py:defaults/validate`；历史算法PR47/PR147及长期备忘录 | 当前TLM为x T64/K64，非线性默认T64/联合32格；不是所有历史方案都一样。旧FP32 SiLU算法的PPL不自动适用于当前定点宏 |
| O02 | 避免在非线性之后重新物化连续z：P8的g、sigmoid(g)、u三路比较并AND，直接驱动固定Wd | 同上；`ffn_latest.py:nonlinear/down` | z随机流不放SRAM；保留每64路编码、状态和最终计数。GU系数恢复/舍入编译器尚未完整数值闭环 |
| O03 | 每拍更新宽累加器：缓存若干拍再汇总；OR分组为另一个可选近似 | 台账`records/sc-38015538.json`；同批精确树/CSA对照`sc-37981139.json` | 这是**采样时间维度**的计数优化；既有无ICG缓存版本增加能量的负结果保留。旧64输入单输出、DFF权重、布局前PT不直接当64×64阵列PPA。与O09可叠加但不可重复扣能耗 |
| O04 | SRAM采用工艺表征校准；DRAM采用标准配置及真实控制器执行 | [存储层次](unified_v6/MEMORY_HIERARCHY_ZH.md)、`sram_cacti_calibration_v1.py`、DRAM配置PROVENANCE | 校准SRAM动态/漏电、DRAM core有边界。CDC、fabric、DMA和DRAM PHY未完整计入；负ACT诊断值保留，不截成乐观结果 |
| O05 | 采样后的V应减少实际读取：比例预算、GQA并集、索引整理和物理突发 | `unified_v6/model.py`、`test_scatter_gather.py`、[45项结果](unified_v6/MATURE_SCHEDULING_ZH.md) | 不能只按逐头保留率缩放KV字节；K和V分别计量；本轮FFN局部驻留实验保持准确Attention以隔离变量 |
| O06 | 随机源本地供给/共享64、检查点重放，避免存完整随机流 | `unified_v6/rng_integrated.py`、`random_service/`及Issue95最新独立分支 | 区分实际端点执行与有限带宽宏。三路非线性独立随机供给本来就是新宏；O09又增加多检查点银行，尚未接入真实端点实现 |
| O07 | 改善权重供数：64bank/64GB/s、标准双通道DDR4、本地权重驻留、跨组DMA预取 | PR183；[MEMORY_HIERARCHY_ZH](unified_v6/MEMORY_HIERARCHY_ZH.md) | 64GB/s与本地1024B/拍接收仍是接口合同，未做完整布线。一次采样帧内复用权重，不是每拍重读DRAM |
| O08 | 数字与SC使用共同有限tile调度；修复W8每K64系数恢复；SG减少描述符屏障 | PR190原45项，执行`bab9721d/6b0df70b`；[调研与实装](unified_v6/SCHEDULER_RESEARCH_ZH.md) | 有真实DRAM联调和原生ONNXim小probe；不是完整Qwen已经移植到ONNXim。同Attention下W8数字仍快于原SC，负面结果保留 |
| O09 | 多个K64块在本地累加，R8/R16/全K后再写共享SRAM | 首轮`b1df81d2`；修正跨窗口预取后`829559dce8f3d97c38768dc4d8df9b32b2ccf200`；`ffn_locality.py`；[结果](unified_v6/FFN_LOCALITY_ZH.md) | 部分和流量显著减少；增加本地累加、输入码窗口、随机检查点与端口。保持每K64恢复和累加次序。首轮丢失窗口边界预取的负面结果保留，面积仍为容量/结构代理 |
| O10 | 128×128用四个64×64象限构成，保持K64算法，比较同计算单元和同阵列数量 | 同O09；2×128对8×64、8×128对8×64；源供给1组/2组分开 | 不能把4倍计算单元称为同面积；不把尺寸128当成T128；时序需计源供给、尾波、恢复带宽和权重搬运 |
| O11 | 将DDR4换为HBM2，区分64B旧入口、256B入口与1ns流水响应，保持核心/SRAM/采样不变 | 执行e7505ee4/43b7b1ff；[25项完整结果](unified_v6/HBM_RESULTS_ZH.md)、[合同](unified_v6/HBM_TIMING_ZH.md) | BF16 599.340→402.629ms，W8 426.364→333.664，SC R8 503.639→438.038，SC筛选PV474.154→407.167。HBM无有效功耗参数；FFN主体几乎不变，KV单通道热点保留，不称最优HBM实现 |
| O12 | 采用公开LLMCompass，区分主流硬件资源与当前小配置；核查GEMV省略的片上搬运和保守串行调度 | 执行3b06f295、Slurm3052；[报告](unified_v6/LLMCOMPASS_COMPARISON_ZH.md)、results/llmcompass_20261025/final | A100服务4.162ms（旧launch代理20.989）；小配置178.006ms、补共享SRAM限制350.977ms，当前TLM402.629ms。名义资源匹配，不是同拓扑；QK/PV/Softmax实现也不同，差额不能当纯调度收益。无新GPU/PPA/PPL |
| O13 | 分离早期小资源默认和具体调度损失：MAC512/8192/32768、共享SRAM64/256/512/1024GBs；同资源下一shared fill覆盖当前MAC | 执行b01058f7，Slurm3057/3058；[16项报告](unified_v6/RESOURCE_SCHEDULING_ABLATION_ZH.md)、results/resources_20261025 | 旧F402.629→379.372ms；同E512/64为400.439→377.666；8192/512为125.505，8192/1024为107.639；计算扩大4倍仅124.807。主要资源瓶颈为共享接口；仅一项预填充不是全局最优，更宽供数/互连PPA未签核；无新PPL/RTL/PT |

O01—O08为本次核对的已有机制索引，**不是本次重新完成全部算法/RTL/PT验证**。缺少匹配的当前质量记录时保持待验证，具体历史版本和失败记录以PROJECT_MEMORY与各manifest为准。

每项的具体Git版本、文件路径、字节长度及SHA-256见[证据索引](ARCHITECTURE_OPTIMIZATION_EVIDENCE.json)。历史电路记录核对的是`6966739a`原字节，不把本轮TLM提交当作旧PT执行代码。

## 本轮采用的文献思路

- **GEO: Generation and Execution Optimized Stochastic Computing Accelerator for Neural Networks**，2021，§III-C/D。讨论本地寄存器、跨pass部分和、近存储向量累加与流水线；它也指出强行输出驻留可能增加操作数流量。因此这里采用可调的局部驻留窗口，而不是预设全输出驻留一定最优。[原文](https://nanocad.ee.ucla.edu/wp-content/papercite-data/pdf/c112.pdf)
- **SASCHA—Sparsity-Aware Stochastic Computing Hardware Architecture for Neural Network Acceleration**，TCAD 2022，§V。采用near-memory vector unit和局部merger处理部分和，说明“先局部合并、再写存储”是已有方向。本轮没有实现其稀疏异步调度，也不套其加速比例。[原文](https://nanocad.ee.ucla.edu/wp-content/papercite-data/pdf/j72.pdf)
- **DS-CIM: Digital Stochastic Computing-In-Memory Featuring Accurate OR-Accumulation via Sample Region Remapping for Edge AI Models**，2026，§III-D。每四拍缓存后更新累加器，属于O03，不等于O09。其OR/双随机/重映射、CMR复制和本项目的固定W8/精确归约不同，不迁移其能效或面积倍率。[原文](https://arxiv.org/html/2601.06724v1#S3.SS4)
- **Gemmini** 的scratchpad/accumulator与输出驻留提供成熟的确定性对照组织；累加存储可以是RF或专用SRAM，并非必须复用通用激活SRAM。[官方设计](https://github.com/ucb-bar/gemmini#scratchpad-and-accumulator)

## 每次改进的登记模板

新增记录必须保留下列字段，优先填同一个表或链接同一任务报告，不能只留下“更快/更省”。

1. **问题与机制**：具体消除哪一种读取、更新、等待或重复计算。
2. **对照和范围**：模型形状/版本、prefill或decode、batch、上下文；改变的硬件资源，保持不变的算法/时钟/存储。
3. **版本**：Issue/PR、执行代码commit、配置及SHA、数据/模型SHA或“不涉及真实模型载荷”的理由。
4. **结果**：时间/周期、实际字节和动作、局部容量/总容量；哪些面积/能量为空，是否满足质量约束。
5. **证据等级**：解析、合成TLM、行为数值、RTL功能、综合/STA/PT、后布局、实测分别写。各级不得互相替代。
6. **代价和负面结果**：额外状态/端口/重放、尾波、频率风险、未省下的流量，失败配置不删除。
7. **状态和下一步**：本地/已推送/待审/已合并，未完成的验证和准确可恢复路径。

## 论文写作时的消融顺序

先固定模型、质量和资源，比较数字W8、原SC和只改变驻留窗口的SC；再单独展示增加阵列规模与随机供给的资源曲线。最后才组合Attention优化，避免把Attention节省、硬件扩容和FFN调度混为单个算法收益。绝对面积和整机能耗需补对应模块表征；只有字节下降时只能报告流量或已知宏内部动态能量下降。


## 2026-10-28 Issue198：完整采样反馈/仲裁服务器电路评估

沿用PR199，8固定控制top同SS100约束DC/VCS/PT，116回放230400拍、66功耗窗口，额外8top时序审计。G16融合折算面积0.035969mm²，较G16两级小14.2%；全1吞吐压力每输出17.17pJ，低21.8%，非独立有效样本/完整Attention。所有hold为负、PWR-981保留；最短路径rst_n，禁用弧仅p/C、无loop-breaking或用户false/multicycle。按需/预取拒绝控制微收益2%–3%未计额外公平位。原面积×0.81另列，不缩功耗/时序。入口attention_compare_20261027/control_v2/eda_20261028/RESULTS_ZH.md，统一run attention-control-198-eda-20261028。无模型/PPL/布线；下一步IO/reset合同/hold/标注。


## 2026-10-28 SparQ＋Ising完整WT2三seed完成（Issue198 / PR199）

负责人rayggxia；task/198-attention-compare，原独立checkout继续复用，PR待审未合并。GPU Slurm3270_[0-2]完整结果均已收齐，独立SHA/回执、299077目标恰好各一次、36层计分覆盖及每头160更新/128保留采样审计通过。执行源a7108f8cba2c72ad319114af34557f4cec2b793d；短流源d9b64717641ae8f7efeaa2e9375a1b01a30361d0。模型Qwen/Qwen3-4B后训练revision1cfa9a7208912126459214e8b04321603b3df60c，权重/tokenizer/原始train-test/token SHA在provenance中核验。原BF16 FFN/投影/归一化不改，dense prefill、全36层单query Attention替换；无chat模板、无BOS，window2048/stride1024、batch32。

完整PPL：BF16 11.538153；纯SparQ 10.797926；SparQ＋winner S128 11.177429±0.006594（三seed样本标准差），相对BF16 -3.126%，相对纯SparQ +3.515%。固定r32/k128/local32、burn32/spacing1，赢家地址直接V读出；理想FP32 sigmoid/Philox行为参考，不是器件或q/256实测。完整结果不同于1024目标初筛，短流S32退化/S512≈IID128的负结果保留。

完整平均每KV组唯一V 54.594行。理想标量读取、候选K维度复用、4Q完整去重下，K+V逻辑元素需求为dense的17.41%、纯SparQ的87.91%；不是实测DRAM字节或速度。SparQ第一阶段全N近似softmax和top-k仍存在，只替换候选上的第二阶段softmax/PV。当前说明质量可行但未证明同质量完整硬件PPA胜出；完整缓存、布局、仲裁、累加及有限相关采样成本待补，不继承旧控制RTL为整机PPA。无新数字电路台账run。

正式源码及报告：experiments/sparq_ising_20261028/results/REPORT_ZH.md、SUMMARY.json。准确SOURCE/SUBMISSION/COLLECTION见work/rayggxia/198/QUALITY_*；原始结果保留本人GPU目录/home/Hongjie_Zeng/projects/attention-sparq-ising-issue198-20261028和本地project_archives/attention_compare_issue198_20261027/quality。report_quality.py可按封存原件重建。下一步以纯SparQ为硬件主要对手，在匹配质量下接有限KV读出和控制费用；未自动启动额外全量扫参、未合并PR或关闭Issue，Projects权限待维护者同步。发布以QUALITY_PUBLICATION.json和远端实际head为准。


## 2026-10-28：128节点控制EDA已完成，按能量与时间联合选型

负责人rayggxia；Issue198 / task/198-attention-compare / 草稿PR199，base main，执行源父提交5f4f5bde及CONTROL128_SOURCE.json精确SHA。工作目录tmp/attention-compare-issue198-20261027复用，未新建重复checkout。

用户明确不能为了面积牺牲功耗和时间。8个top重新DC；本机168回放106227拍，服务器336个RTL/门级回放212454拍通过；56个PT窗口、8top额外时序审计完成。G16融合、binary winner、10位计数、弹性流水主候选：原面积0.014409360mm²×0.81=55nm折算0.011671582mm²；稀疏p=1/32三seed、S128/B0全query平均0.922946nJ、161.667拍/1.61667μs、570.833μW，7.210516pJ/输出。串行2.246279nJ/415.667拍且面积更大，排除；G32能量仅低0.83%、面积高10.79%且setup余量更小，保留备选。提前保持dense有收益但setup仅0.052158ns，暂不主选；公平随机源本体仍未计。

全1压力首帧至首输出3拍、稳定II1、完整query133拍，不能视为独立有效样本。S64/256/512、burn32功能/周期已测，没测相应能量；不由硬件结果决定模型必须burn0。候选局部7位index不等于KV物理地址；不包含概率驱动/随机源/token映射/V读取/累加，也没有给其附加串行调度。

SS1.08V125°C100MHz、IO delay0/slew.1ns/load.02pF/setup uncertainty2ns/hold.1ns；无SDF/SPEF/CTS/毛刺完整建模。全部整体hold负；主候选−0.056977ns来自cfg_ready→configured，内部reg-reg setup/hold为+2.801410/+0.134473ns。仅SS内部通过，不是全接口/FF hold/物理签核。PWR-981虽100% net/cell标注仍保留；禁用弧p/C/c、无loop-breaking/user false/multicycle。不缩放功率/时序。时钟持续空闲445.9μW，未实现/假扣ICG。

正式结果architecture_tlm/attention_compare_20261027/control128_20261028/RESULTS_ZH.md及RESULTS/COMPARISON/TIMING_AUDIT.json。本机原报告2426成员、额外时序96成员SHA核验，完整大包仅授权EDA远端；恢复索引work/rayggxia/198/CONTROL128_ARCHIVE.json，私有原件project_archives/attention_compare_issue198_20261027/control128_20261028。统一台账新增attention-control128-198-eda-20261028；84→85条增量check/render通过，旧记录不变。仅schema check不冒称对全台账原件重哈希，本轮新原件核验单列。

DC38444217/38444227，replay/PT38444238/38444263，timing38444334，collection38444378；无本轮GPU/PPL。首次依赖提交在创建job前拒绝，已有作业完成后重提，原失败回执保留。当前本地实现/测试/归档/台账完成；准确分支上传SHA和回读见CONTROL128_PUBLICATION.json。PR199待审、未合并，Issue保持开放，Projects沿既有限制待同步。下一步修接口hold和标注，再结合真实候选激励及外部接口成本，不启动未经要求的昂贵模型重跑。

---
