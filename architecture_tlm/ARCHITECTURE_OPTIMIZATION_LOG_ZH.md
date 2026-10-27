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

## O14（2026-10-25）：有限双本地权重bank与供数/计算分离

Issue186，分支task/186-local-pipeline，独立目录tmp/ffn-local-pipeline-issue186-20261025；main基线d83eeb1f，原PR190已合并。本轮13项CPU Slurm3074 completed，执行6f73ef65；3完整36层＋10单层诊断，旧case逐数复现407.142620ms；44项合同/回归通过。

新目录[ffn_local_pipeline_20261025](ffn_local_pipeline_20261025/README_ZH.md)。下一权重/系数预取到第二本地bank，同输出窗口内装载覆盖计算/恢复；跨窗口保留SRAM优先次序；SC阵列、计数和恢复仍单套。不改主默认；增加32KiB权重＋32B系数及选择端口，不当免费CIM。W8/B4/GU64/NL64/R8、100MHz、8MiB64bank64GBs、HBM时序不变；128另列。

完整decode407.143→315.236ms（少22.57%），bypass307.049（少24.58%）；FFN268.576→176.680→168.488ms。单层双bank4.966ms，SRAM翻倍再少3.5%，恢复/累加4倍少11.6%，阵列翻倍少20.5%，全K驻留少6.5%，NL128增19.6%。权重有效复用B1仍1，64是随机事件；原共享流量未变，bypass少5.015GiB/token，SRAM内部动态25.532→13.131mJ；整机PPA未知，HBM能量禁用。主瓶颈从串行装载转向采样/恢复，不能再把全部延迟称带宽限制。完整结果、时间线、SHA及成熟模拟器对照见新目录；真实GU数值/PPL/物理bank时序未验收。发布与PR状态见work/jieruiz/186/PIPELINE_PUBLICATION.json；未授权自动合并，Projects待权限。

## O15（2026-10-26）：500MHz资源档位与保留状态时钟门控

用户授权先保持原算子拍数/II，扫描计算与SRAM并行，加入成熟时钟门控。12完整36层CPU Slurm3124（执行64e0cf8a）完成，110+32测试/SHA/动作与物理流量守恒。307.049ms旧锚→仅核心500MHz157.595→扩SRAM76.750→同时扩计算NL64=63.134ms；NL128三seed64.411，门控64.526（+0.178%）。数字参考110.012→110.157ms。
门控排空后idle8拍关，请求1拍恢复，内存/随机源保持；SRAM80MHz和HBM时序不跟核心加速。32SC、2048MAC/拍、512bank/512GBs、有限本地双bank256KiB，输出并行和后处理同步×4；不是同面积对照。旧计算预算来源与未实现吞吐详见新目录CYCLES_AND_UNCERTAINTY_ZH.md。
新100MHz计数PPA按正确M1输出粒度回填，B7/M8×256约209.803mm²；已计价面积小计279.637mm²。500MHz条件门控80%情景小计27.34→8.41W，1.761→0.543J/token，未测ICG/500MHz/B7活动；完整物理PPA保持null。旧100MHz/NL64预算约0.476J不能被隐去，提速不保证每token省能。主候选仍screen_pv，未新测Ising。
证据architecture_tlm/clock500_resource_20261026/RESULTS_ZH.md及COMPARISON/PPA_ANCHORS；功耗原件/台账SHA、CPU封存与验证见work/jieruiz/186/CLOCK500_*。下一步优化计数面积、实现500MHz流水线/门控，补HBM与本地存储成本。

## O16（2026-10-27）：固定资源下提前发起下一DMA

Issue186/PR192；[最终报告](scheduling_v2_20261027/FINAL_RESULTS_ZH.md)。Qwen3-4B后训练形状、36层/B1/2K含lm_head，500MHz目标、32SC/2048MAC、8MiB512GBs、GU64/NL128/HBM/screen_pv固定，不门控。两轮执行410fa5af/5ba79477、Slurm3156/3163共11项completed/SHA核验，134软件测试通过；没有模型载荷/PPL或新电路PPA。

先测试prefill、就绪日历和SC跨窗口：只少约0.14%；下一DMA依然偏晚，42541次prefill中提前就绪数0。随后把普通矩阵DMA提到shared fill释放响应槽之后，SC DMA提到program释放响应槽之后/context准备之前。复用原1响应槽/2shared槽/2本地bank，不扩阵列或数据存储。

组合三seed平均64.411267→57.445385ms/token，少10.81%；seed0 FFN25.4916→25.2070ms，普通投影/lm_head29.8444→23.1709ms。主收益属于普通部分供数，不能归为随机乘法本身10.8%提升。同seed动作/采样/帧顺序/物理字节/数据状态相同；控制PPA和完整能量待校准。

负面结果和第一轮未删除。剩余：单macro DMA及批间排空、SRAM整描述符占用、SC恢复串行、旧数字L/II；下一步数字基线同样优化后再做公平比较。Git只留小汇总和manifest，原件在个人服务器；两个输入包唯一归档和恢复SHA见SCHEDULE_PACKAGE_ARCHIVE。上传与PR状态查work/jieruiz/186/SCHEDULE_V2_PUBLICATION.json。

## O17 既有电路价格回填和随机版能耗重算（2026-10-27）

沿Issue186/PR192，对O16封存动作重新计价，不改调度、不启动新TLM/PPL/EDA。主入口[ppa_recalibration_20261027/RESULTS_ZH.md](ppa_recalibration_20261027/RESULTS_ZH.md)。采用新三级合并计数/真实X8 ICG、单MAC/FP32加、既有PRNG/共享64/CIM前端和SRAM库表。按物理输出通道、实际动作和状态计，去除旧七桶复制/重复归约收费，保留公共恢复代理。

三seed57.4454ms/token：已覆盖片上新计数CE12.7864W，计数真实ICG/数字CE10.0280W，数字门控90%空闲动态情景2.5162W（0.14454J/token）；数字工作时钟/漏电保留。旧64pJ/B+50mW外存仅粗预算另6.1661W，总候选8.6823W非HBM/整片已测。共享/局部/响应SRAM与PRNG已计，B7和500MHz仍外推。关键待补：计算/门控集成500MHz、CIM并行外围和互连、匹配HBM能量；Ising当前不启用。

6份completed输入SHA、4份结果×3情景全表重建、8会计守卫通过。源价格及SHA见ANCHORS.json；统计RESULTS.json/MODULES.csv。新数字价格揭示CE-only大阵列idle占比，不能将旧2pJ动作代理与新全寿命功耗直接比较。没有新增电路run，统一台账05为派生索引。
