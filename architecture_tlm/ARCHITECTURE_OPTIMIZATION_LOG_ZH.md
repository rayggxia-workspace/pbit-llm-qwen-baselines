# 概率计算架构优化记录本

维护入口：Issue186 / PR190；负责人jieruiz；建立于2026-10-25。这是论文准备的**机制与证据索引**。具体电路结果仍只登记在 `digital_circuit_simulation_registry/`，不在这里另造功耗台账。历史记录不因新方案出现而删除。

## 当前可以说到什么程度

当前统一执行器为 `unified_v6`，共同调度基线为PR190，依赖PR183。它有完整decode图、有限tile生命周期、真实DRAMSys以及SRAM容量/端口模型；部分算子和新增接口仍采用有界延迟宏。结果是**带假设的架构级时延/活动估计**。既不是全芯片周期精确RTL，也不是全部已有PPA。没有通过匹配模型质量验证的新映射，不能继承旧PPL。

最新试验是“跨输入块的部分和本地驻留＋128阵列组织”。入口：[详细结果](unified_v6/FFN_LOCALITY_ZH.md)、[13项完整对照](unified_v6/results/locality_20261025/COMPARISON.csv)。默认路径保留原实现，候选通过配置显式启用。

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
