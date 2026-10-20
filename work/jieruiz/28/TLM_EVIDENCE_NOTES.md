# 全项目备忘录辅助核对：TLM、Attention、存储与随机源

核对日期：2026-10-18。只读核对现存源码、报告和索引；没有启动新作业、修改正式仓库或确认远程队列。本文是主备忘录的素材，不代替对应 Issue/PR/状态中的最新发布状态。

## 1. 入口及版本边界

- 本地混合资料目录：`C:/Users/86134/Documents/a_P_BIT`，不是正式 Git 根。
- 正式 workspace 仓库：`rayggxia-workspace/pbit-llm-qwen-baselines`。不能误向历史个人仓库 `jieruiz/pbit-llm-qwen-baselines` 推送。
- 已发布 TLM 总入口：任务分支 `pbit-tlm-attention-details-20261016` 的 `architecture_tlm/WORKSPACE_LATEST_ZH.md`。本次从主代理下载到 `tmp/project-memory-20261018/remote/pbit-tlm-attention-details-20261016/architecture_tlm/WORKSPACE_LATEST_ZH.md` 的快照读取。
- 这个索引正文仍为 10 月 16 日，覆盖 Attention v3/v4、本地共享随机源、SRAM v1 等；它不能代表之后所有本地优化已经发布。特别是本地 Qwen v5/v6 PV 与后来 Llama 独立适配必须分别看实际文件和发布记录。
- 模型顶层导航的已整理 checkout：`tmp/model-folders-issue16-20261018/`，其中 `qwen/`、`llama1/`、`llama2/` 只是导航和统一运行入口；正式实现仍在共享 `architecture_tlm/` 及各历史路径，避免复制多份实现。该 checkout 的 `project.json` 记录锚点 SHA 和原路径。
- 当前状态和合并情况由主代理核对远端，不应把一个本地 checkout 的旧 STATUS 当成全仓库当前状态。

## 2. TLM到底模拟什么

- 计算调度主要是 Python 的宏级/事务级模型；外存后端已真实接入 SystemC/TLM-2.0 DRAMSys 与 DRAMPower。不是全部模块都已实现为 SystemC，更不是逐周期 RTL 全芯片仿真。
- 算子动作数、数据依赖、SRAM 容量/端口服务、有限 DMA/在途队列、阶段时间和能量账本可以核对；部分服务时间、互连、PRNG、数字向量核和 SC 核仍为未完整标定参数。
- 基本模型是 batch=1 decode，硬件算子在各层复用；不会按24/32层复制整套算子面积。模型权重、KV和中间数据按各层更新/搬运。
- GPU模型质量、算法参考、合成 TLM输入、真实BF16 QK捕获、PT/库数据和芯片实测是不同证据。TLM 的 `ms/token` 不是模拟器 CPU `wall_seconds`；ASIC BF16 TLM 行不是 GPU 能耗。
- 整体仍未证明全局最优，也不能宣称相对 GPU 已有可信节能倍率。

## 3. Attention各路线及不能混称之处

正式 v3：`architecture_tlm/attention_tlm_v3.py` / `ATTENTION_TLM_V3_ZH.txt` / `run_attention_v3.py`：准确、准确QK/Softmax后PV采样、Ising、筛选后准确、筛选后PV。

正式 v4：`screen_ising_tlm_v4.py` / `ising_macro_v4.py` / `SCREEN_ISING_TLM_V4_ZH.txt`：摘要筛选→紧凑候选→Ising宏→V选择累加；支持固定/可变候选和预算修复。

- 现有 max4 筛选器是摘要评分、归一化、sigmoid和独立Bernoulli判决，**没有块间耦合Ising退火**。显式排序/补齐的预算修复也不是已经实现的耦合筛选器。
- v3 显式计随机扫描 Ising 更新；v4 将状态、随机源、抑制反馈、预热、采样及读出封装为宏。**v4默认地址来自理想IID分类参考，不是实际p-bit网络输出**；100 ns有效样本间隔是未标定假设，不能当真实混合后独立样本率。
- 未来真正需要测：配置/建立、预热、非法态概率、目标分布误差、自相关和ESS、样本间隔、读出、背压与并行实例数。
- “筛选后维度较小”有利于Ising接口，但固定槽padding、候选大小分布和重配置仍需计费。

## 4. PV v6与历史错误纠正（关键长期记忆）

本地正式来源：

- `C:/Users/86134/Documents/a_P_BIT/architecture_tlm/PV_STREAM_V6_RESULTS_ZH_20261016.txt`
- `.../PV_ENERGY_AND_ISING_AUDIT_ZH_20261016.txt`
- `.../pv_stream_v6.py`、`scatter_memory_v6.py`、`configs/pv_stream_v6.json`

这轮是准确QK→指数/块统计→systematic前缀整数计数→按KV组合并V位置→有限队列DMA→V广播/累加。**没有运行Ising，也没有接入筛选；不能说已得到“筛选＋v6 PV”的结果。**

采样按原上下文约1/16：2K=128、4K=256、8K=512。它是探索起点，不是已经由PPL证明的质量定律。全局每头一个systematic偏移，Qwen24层共336随机字/token；论文 SANTA 的 prop CUDA 使用最大余数块预算和块偏移，本版不是其原内核复刻。

修正了旧逐样本CDF阻塞查找和逐地址DMA排空：前缀扫描/组内V并集/显式广播/最多32个64B事务在途。旧速度差是可避免的控制和访存串行化，不能归因于采样算法天然慢。

| 真实DRAMSys情景时间 | 2K/128 | 8K/512 |
|---|---:|---:|
| 准确PV阶段 ms/token | 3.405 | 13.600 |
| 新PV阶段 ms/token | 2.756 | 10.959 |
| PV局部时间下降 | 19.1% | 19.4% |
| 新V物理读取/完整V | 34.65% | 34.55% |
| 准确完整Attention ms/token | 7.074 | 28.271 |
| 旧同比例采样Attention ms/token | 19.499 | 85.896 |
| 新完整Attention ms/token | 7.036 | 28.083 |

完整核收益很小，因为第一遍QK/指数、预算和第二遍扫描抵消大部分PV局部收益。FFN T4096仍主导整机时间。不能把19%说成整个Attention或整机加速。

有限RF/Buffer、ALU、广播和服务依赖已经显式计费，但32KiB数字核内部存储、每向量微操作一拍、互连/CDC等仍需PPA/时序标定。旧报告末尾“本轮未上传GitHub”及Issue3引用边界说明：本地v6不能自动宣称已经在workspace发布。

## 5. GQA导致K读取与QK算术节省不同

来源：`tmp/screen-k-traffic-issue9-20261017/architecture_tlm/SCREEN_K_TRAFFIC_ANALYSIS_ZH_20261017.md`，Issue9/PR10。

- Qwen2.5有14Q/2KV，每7Q共享KV。逐Q头候选并集决定物理K读取，原来已经做组内去重，不能再把去重说成待实现。
- 历史合成高斯logits场景，QK保留27.58%/28.62%，有效K并集却81.65%/89.65%；旧Link256又放大到96.42%/98.86%。这不是所有真实Qwen数据必然值。
- max4四个FP32摘要/64token相对BF16 K约12.5%流量。8K有效K+摘要可能已超过完整K读取。
- PV发生在候选QK算完之后，只降低V，不能回头降低K。
- 共享随机阈值在当前饱和概率下仅将K期望覆盖约降低1.4个百分点，不能指望单靠共享解决。更值得研究每KV组共同预算/共同核心候选、摘要压缩和真实head overlap，均需质量验证。
- LLaMA-1 7B、Llama2 7B都是32Q/32KV MHA，没有这类7头并集放大；不能对MHA先取所有头token全局并集再要求每头全读。
- 老LLaMA后缀筛选PPL与新标准TLM不是同一协议：旧为32×128后缀、单块均值，当前为max4、完整地址路径。旧Ising软件还gather全部候选V后加权，非零V地址不等于实际物理读取。

## 6. 随机源：保留分层，FFN输入已8位共享64

来源：`architecture_tlm/RNG_HIERARCHY_V1_ZH.txt`、`LOCAL_SHARED_V2_ZH.txt`、`rng_hierarchy.py`、`rng_local_shared_v2.py`。

- 分层：物理熵/调理→根种子及扩展/分发→共享PRNG→消费者本地叶。数字模型中的SHAKE域分离是可复现种子参考，不是声称真实硬件免费SHAKE。
- FFN输入：本地32bit PRNG状态，输出8bit随机字R∈[0,255]；阈值q∈[0,255]，P(bit=1)=q/256。**“8位随机字”不是“8位LFSR状态”。** 64个通道共享R，但保留各自阈值/符号。
- 输入前端在输出波间恢复checkpoint重放同一输入流；不存4096拍随机数组。每新64输入tile默认数字派生子种子；默认根每1秒按需刷新256调理bit，冷启动/派生/恢复/分发/预热均计费。
- 权重侧仍原方案，双随机时有本地Bivium核及比较选择；输入/权重必须分域，不能同一R比较后AND冒充独立乘积。v2没有把权重源删掉。
- Attention其他消费者仍可由层次服务/本地叶供应随机字；Ising宏内部源已封装，避免重复收费。PRNG不需要随机流SRAM，不代表CDF/索引/概率阈值/Ising状态都可删除。
- 原用户测得物理随机源120.80μW、16bit、450MHz，即每rawbit16.7778fJ；物理模块固定功率、调理、分发与相关性另算，不能按使用bit比例免费削减已开启模块功耗。
- 关键限制：实际RTL/物理源相关性与理想IID参考PPL未贯通；长期PRNG更新和物理熵补种成本不是同一个量；不能用巨大候选bit量声称需要同等物理熵带宽。

## 7. SRAM：库直接查表＋CACTI探索，不是凭小宏硬乘

主要来源：`architecture_tlm/SRAM_CACTI_CALIBRATION_V1_RESULTS_ZH_20261016.txt`、`sram_cacti_calibration_v1.py`、`SRAM_PLACEMENT_V5_RESULTS_ZH_20261016.txt`。

- 55nm工艺库14点：A～F六几何拟合，H独立验证，SS/TT分别；56厂商文件已hash核对。已知合法宏优先直接查库，未知尺寸CACTI加输出校正并标误差。
- H=4096×144验证：面积误差15.02%，内部读能量约9.3%，内部写能量64%～73%，漏电约11%～12%但交叉验证38%～41%。不能说CACTI全指标均已校准到10%。
- F=4096×128=64KiB，面积0.31216331mm²；16实例1MiB面积4.99461296mm²是实例相加，不是预测更大单宏。
- SS F最小读/写周期10.9192/11.0613ns；当前先用80MHz宏时钟、100MHz计算核，跨域接口仍需真实实现。不能按F宏连续100MHz访问。
- 读写次数×事件能量＋状态功率积分；库内部能量不含所有外部负载、保持、wrapper、CTS/互连。
- 当前Qwen起点1MiB统一16bank SRAM，16B交织，1RW、80MHz，计算100MHz，共享互连上限16GB/s。231候选×2上下文=462 Link初筛，最后12DRAMSys+4Link情景；并非全架构全局最优。
- 1MiB是Qwen batch1 decode 2K/8K、T4096情景建议；不能直接迁移Llama、大batch、32K或Qwen3.5 DeltaNet状态。
- 权重驻留接口未闭合：普通128bit SRAM口不能免费变成64×64×8bit同时稳定输出。可用装载后静态tile保持或定制CIM，必须计端口、装载、保持、扇出和面积。缩到T128/256后装载更容易成为瓶颈。

## 8. DRAMSys/DRAMPower及纠正

来源：`tmp/dram-dscim-issue-5-20261017/architecture_tlm/DRAM_POWER_AND_DS_CIM_WEIGHT_REVIEW_ZH_20261017.md`、`dram_power_profile.py`、`results/dram_power_review_20261017/`。

- DRAMSys5.6.0提交9f15aaf1fe6f05ff16a2e521a20a96f3bfe29d52；DRAMPower6.3.1；DRAMUtils1.16.0。命令/状态模型可用，不需我们晶体管级仿真DRAM。
- 历史示例VPP-PD电流与VDD值重复，导致低功耗态反而更贵；接口参数也是未标定代理。引擎账本闭合并不保证输入器件参数正确。
- 10/16置零VPP-PD是因果诊断，不是校准，更不能把诊断的-3.078mJ当真实节能。
- 10/17已按Micron Rev.M/2020、dieRev.A厂家手册引入完整core电流限值新情景、预检查及13测试；不改历史默认，也未认证完整timing/I/O。
- 旧4份完整统计用新电流重计价后，PV核心能量仍比准确多约0.566/2.340mJ/token（2K/8K），说明碎片化调度减少长SREF区间仍有真实影响；不是新控制器仿真，不能拼未校准interface成“新真实整机能效”。
- 后续Llama模型TLM已显式用新Micron限值情景，仍应区别core有来源与I/O/PHY未完成校准。

## 9. 模型当前证据状态

### Qwen2.5-0.5B

24层、hidden896、FFN4864、14Q/2KV、head64。算法历史丰富；TLM v3/v4有合成输入，v5/v6有真实DRAMSys但不是新PPL。同一批最新真实位流、v6 systematic规则、筛选与Ising尚未形成一个完整质量/PPA闭环。FFN分析、短流PPL和现存作业由其他备忘录模块核对。

### LLaMA-1 7B

入口：`tmp/model-folders-issue16-20261018/architecture_tlm/llama7b/README_ZH.md` 和 `results/current/RESULTS_ZH.md`。

- 32层、4096hidden、11008FFN、32Q/32KV MHA；82/82 TLM=60Link+18Staggered+4NoPowerDown；512/1024/2048真实BF16 QK捕获，观察前后输出逐位相同。
- 8×64×64 SC阵列、100MHz、W8/A8共享64、T4096；8MiB校准SS SRAM、16lane；2通道2rank16GiB DDR4；PV按L/16=32/64/128。
- 新标准TLM没有新联合PPL。2K筛选后PV实际K36.96%、V1.67%、摘要65MiB/token；相同SCFFN下能量降低2.16%，相对BF16/数字W8 TLM仍更慢更费电。不是GPU基线。

### Llama2 7B Base

入口：同checkout `architecture_tlm/llama2_7b/RESULTS_INDEX_ZH.md`、`results/current/RESULTS_ZH.md`、`baselines/llama2_7b/results/bf16_wt2_20261017/RESULTS_ZH.md`。

- 模型revision01c7f73d771dfac7d292323805ebc428287df4f9，逐文件SHA固定；官方镜像只作下载通道，非绕过模型身份核验。
- 完整WT2 BF16 PPL 2K4.9795028452/4K4.8958312205，stride512、335686预测token、不加BOS/EOS；实际RTX5090。这是质量实测，未测GPU功耗。
- 116/116 TLM=72Link+36Staggered+8NoPowerDown，4种上下文512…4096，PV32/64/128/256。与Llama1共用冻结MHA运行时；硬件同上。
- 2K筛选后PV物理K37.16%、V1.41%、摘要65MiB/token；4K分别33.52%/1.15%、摘要129MiB/token。2K SC筛选PV比同SC准确Attention整机能量-2.16%，比数字W8 TLM约+219%；当前长采样尚未获得硬件优势。
- TLM只取每上下文一个真实decode查询，不能代表全语料筛选质量。Ising仍IID oracle。后来Issue19的数值短流评估需从其独立任务读取，不能用旧README“没有新随机PPL”覆盖后来的已完成结果。

### Qwen3.5-0.8B

独立本地发布包：`C:/Users/86134/Documents/a_P_BIT/qwen35_publish_20261013/experiments/qwen35_20261013/README_ZH.md`，不是上述三个模型TLM导航已经自动集成的一部分；该包Git远端仍历史个人仓库，workspace当前发布状态由主代理另核。

- revision2fc06364715b967f1860aea9cf38778875588b17；24层FFN、18DeltaNet、6完整门控Attention。后训练权重、tokenizer不同，绝对PPL不能和Qwen2.5比较。
- 完整WT2滑窗2K/stride1024/297192预测token：原15.661098；仅PV51215.744119；动态随机FFN15.840404；动态FFN+PV15.923481；再加18层DeltaNetout/z/QKV投影16.124398（三种子，较原+2.958%）。
- DeltaNet solo out/z/QKV随机化15.857678±0.002626，INT8无采样15.839524；8K solo14.645752±0.003248，原14.408686。未测8K联合，没有超长状态稳定性证明。
- DeltaNet固定投影优先替换，alpha/beta、状态更新、卷积、Q/K归一化、gatedRMSNorm均保留；每token状态只提交一次，不能4096采样周期重复做4096次递推。
- 固定投影占DeltaNet所列MAC约92.84%；状态核心小但18层FP32状态18MiB/序列，不能从MAC少推断存储能量小。当前没有为Qwen3.5建立对应完整新TLM及状态布局优化。

## 10. 不能丢失的未完成事项

1. 数值参考、真实有限精度位流、trace、TLM和PT成本目前没有统一为同一实现；部分报告参数是代理。
2. 当前筛选是概率门控，不是已完成p-bit耦合退火；Ising宏没有真实混合时间/ESS/PPA。
3. 共享物理/伪随机源必须核验输入与权重联合独立性、时间自相关、输出波重放语义；32bit状态/8bit比较不能混称。
4. FFN短流降低计算时间后，要重新比较SRAM装载、局部保持、非线性、Wd调度；不能沿用T4096瓶颈结论。
5. bank/DMA有宏约束但非逐字队列全周期验证；SC权重供给、互连、RF、CDC、CTS和转换器PPA仍缺部分关键数据。
6. DRAMcore有厂家限值输入不等于整DRAM/PHY都已校准；已有SRAM宏内能量不等于wrapper总能量。
7. 限定搜索用过ZigZag3.8.5/LOMA，产生54合法映射；未运行Stream、ZigZag-LLM或Timeloop/Accelergy全系统优化，不能宣称达到最优。
8. 所有新服务都应报告局部算子、完整Attention、整机三层收益，公平比较同精度/质量的数字ASIC，另列GPU实测。

本次核对源文件散列见同目录 `SOURCE_HASHES.json`。没有更改这些源文件。
