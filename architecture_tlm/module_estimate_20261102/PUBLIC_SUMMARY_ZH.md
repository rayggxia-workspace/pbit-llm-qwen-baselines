# 选定LPDDR5X的统一能量预算

2026-11-03，按用户“能耗优先、只选一款”的要求，后续研究预算选定 **LPDDR5X-8533、16GiB、128bit（8个x16通道），136.528GB/s，访问主值4pJ/bit＝32pJ/Byte**。具体新时序后端仍待接入，旧DDR4封存结果不改；本页早先的多候选属于当时调查。

同5.412434944GB/token，外存预算173.198mJ/token；沿旧53.668ms窗口约3.227W，加已有片上后200.010mJ/token。6.6pJ/bit敏感性为285.777mJ外存，8pJ工程情景为346.396mJ。均不是新器件实测或新的TPOT；不得把更换外存的收益归于概率算法，数字基线和概率版使用相同外存规则。

文献核对：[IKS，ASPLOS2025](https://arxiv.org/html/2412.15246v1#S6.SS1)采用LPDDR5X，正文给出8533Mb/s/pin能力，方法段列LPDDR访问4pJ/bit并说明缩放至16nm；本项目不继承其逻辑技术缩放。[CXL-PNM，HPCA2024](https://snu.elsevierpure.com/en/publications/an-lpddr-based-cxl-pnm-platform-for-tco-efficient-inference-of-tr/)采用512GB/1.1TB/s LPDDR5X；[Kelle，MICRO2025](https://arxiv.org/html/2510.16040v1#S8)使用16GB/64GB/s LPDDR4与CACTI7；[Edge-LLM，DAC2024](https://www.haoranyou.com/publications/pdf/2024DAC_EdgeLLM.pdf)使用8GB LPDDR4。[LLMET预印本表2](https://arxiv.org/html/2607.26491v1#S3)把LPDDR5建模为6.6pJ/bit（非LPDDR5X实测），用于敏感性。[HSA正式比较](https://arxiv.org/html/2507.09010v1#S5.SS2)是DDR5 51.2GB/s、32pJ/Byte，不能混为引言的Jetson LPDDR5参考。

4pJ也有Micron LPDDR5X官方简报索引支持，但完整背景/刷新、PHY/控制器边界尚未拆分，标未知而非0；不再叠加旧DDR4那份背景能量。无新LPDDR/EDA/PPL运行。完整本地报告、预算JSON及原件索引继续留本地；PR226仍待审未合并。

---

# LPDDR候选和实际模型核查

2026-11-03，接续Issue225。完成公开源码与参数文件静态核查，未运行新内存仿真、未改变默认。

优先器件方向为16GiB／128bit LPDDR5X-8533（峰值136.528GB/s），例如两颗Micron MT62F1G64D4EK-023家族x64器件；优先现有后端路线为16GiB／256bit LPDDR4X-4266（136.512GB/s），例如八颗MT53E512M32D1ZW-046家族x32器件。具体revision/等级/供货及PHY需确认，不作采购承诺。LPDDR5-6400／128bit仅102.4GB/s，余量不足；256bit则204.8GB/s，可作为原生开源时序预设备选。

实际取回并按Git blob、SHA-256核对13份公开源码/配置/许可文件：
- DRAMSys有8/16Gb x16 LPDDR4-4266时序配置，但所读两份4266配置功耗全零；不能直接用它们报告能耗。3200配置非零但DQ1.1V，不是已匹配的4266 LPDDR4X功率表。
- Ramulator2.1公开LPDDR5时序/控制器，当前所读预设只有5500/6400；没有现成8533/9600预设，不只改rate就当LPDDR5X。
- DRAMPower当前公开源码已明确包含LPDDR5核心和接口功耗实现。它的公开测试JSON有channel=0等测试数值，不能当实际器件参数；仍需对应IDD/电压/I/O表。
- Micron TN-53-07（LPDDR4X）及TN-62-05（LPDDR5）功耗计算器存在，但为受限访问，当前未取得。

接入要按32B/64B实际突发拆分并保持相同在途字节窗口；例如256×64B变为512×32B才同为16KiB，避免请求数固定导致人为限流。新通道/bank映射、WCK/CK、背景与低功耗状态仍须配对回放。上述是资源可得性与静态检查，不是完整后端已部署或LPDDR性能/能量结果。

来源：[Micron LPDDR4目录](https://in.micron.com/products/memory/lpddr-components/lpddr4/part-catalog)、[Micron LPDDR5X目录](https://in.micron.com/products/memory/dram-components/lpddr5x/part-catalog)、[DRAMSys](https://github.com/tukl-msd/DRAMSys)、[Ramulator LPDDR5](https://github.com/CMU-SAFARI/ramulator2/blob/1bb52ceed30cc607a2d328589815eaea976c0224/python/ramulator/dram/lpddr5.py)、[DRAMPower编译清单](https://github.com/tukl-msd/DRAMPower/blob/a2068bc58411ff36abb2f6aab74b1a5fbe98e93d/src/DRAMPower/CMakeLists.txt)、[Micron功耗工具](https://www.micron.com/sales-support/design-tools/dram-power-calculator)。完整研究和取回原件仍仅本地，PR226不自动合并。

---

# 外存能耗复核：论文口径与低功耗候选

2026-11-03，Issue225补充。仅复核既有三seed封存结果并重计价，没有新DRAM/RTL/PPL仿真，不改默认或旧结果。

当前实际读写合计5.412434944GB/token，原执行窗口53.668ms/token，已覆盖片上26.812mJ/token不变。

| 情景 | 外存mJ/token | 同窗口外存平均W | 加已有片上后mJ/token |
|---|---:|---:|---:|
| 64GiB双rank DDR4命令＋状态模型 | 796.726 | 14.845 | 823.538 |
| FIGNA/MBA同口径3.9pJ/bit | 168.868 | 3.147 | 195.680 |
| LPDDR5X代表参数4pJ/bit | 173.198 | 3.227 | 200.010 |

后两行是相同流量的器件/系数情景，不能称新增概率算法节能或实际LPDDR回放，不自动改变带宽与时延，也不当作已包含全部PHY/控制器的板卡功耗。

用户提供的MBA原文第5页采用HBM **1.5TB/s、3.9pJ/bit**；其中256GB/s是每个本地eDRAM缓冲的带宽。FIGNA为HBM2 256GB/s、3.9pJ/bit。MBA参考[38]《Fine-Grained DRAM》将约3.9pJ/bit分为激活、内部搬运和I/O；不是裸阵列价格。两篇评估段未逐项披露本项目这样的rank背景/刷新状态模型，不能直接混称同一计价边界。

当前DDR4为8通道、128颗器件、64GiB、NoPowerDown。背景与刷新346.056mJ/token，占43.43%；即使理想全部去掉仍有命令450.670mJ。全部分配地址落在rank0，未用rank仍待机/刷新。当前IDD/IPP表还使PowerDown状态功率高于普通待机，须核实后才能评估省电；不能静默改电流或直接宣布开关后的收益。

建议保留原详细结果，另列统一3.9pJ/bit公平对照；候选先检查同8通道单rank32GiB与有效PowerDown参数，再探索16GiB/128bit LPDDR5X-8533（理论136.53GB/s）。128bit LPDDR5-6400仅102.4GB/s，离当前平均100.85GB/s太近。高速PHY与功率边界仍待确认，候选尚未运行。完整报告与原件索引仅本地保留，PR226仍待审未合并。

来源：[MBA官方题录](https://63dac.conference-program.com/presentation/?id=RESEARCH509&sess=sess318)、[FIGNA](https://doi.org/10.1109/HPCA57654.2024.00064)、[Fine-Grained DRAM](https://niladrish.org/pubs/micro17.pdf)、[Micron技术简报](https://sg.micron.com/content/dam/micron/global/public/documents/products/product-flyer/lpddr5x-camm2-technical-brief.pdf)。Micron官方索引列4pJ/bit，但直接PDF下载被站点拒绝，边界未完整核实；不把自刷新低功率当工作功率。

---

# 完整回放更新：2.5 MiB SRAM＋12核公共FFN

2026-11-03，Issue225。已完成6项单层配对及3个seed的36层＋lm_head完整事件回放；27项预检、结果封存校验、容量和队列排空检查通过。完整源码快照、输入及原始记录由项目方本地维护，此页只更新公开汇总。

配置：Qwen3-4B形状，B1 decode、2K上下文、100MHz、8通道DDR4；K64/M128/T64准确归约，无OR；GU与Wd顺序共用12核，32个权重槽共256KiB。152KiB宽状态实际读写，非重复预留。

| 指标 | 新方案三seed均值 |
|---|---:|
| 时间 | 53.668 ms/token，18.63 token/s |
| 已计片上面积 | 61.492 mm² |
| 已计片上能量 | 26.812 mJ/token |
| 外部DRAM核心能量 | 796.726 mJ/token |
| 已计系统能量 | 823.538 mJ/token |
| 已计片上／系统平均功率 | 0.500／15.345 W |

| 执行阶段 | ms/token |
|---|---:|
| QKV投影 | 10.744 |
| Attention及结果汇集 | 3.874 |
| O投影 | 6.871 |
| FFN Wg/Wu | 16.280 |
| FFN非线性＋Wd | 8.288 |
| lm_head | 7.417 |
| 其余（含embedding） | 0.193 |

| 物理资源 | 面积mm² | 能量mJ/token |
|---|---:|---:|
| FFN公共核 | 15.601 | 8.251 |
| 跨K端口＋状态返回保持代理 | 0.209 | 0.137 |
| FFN本地随机服务代理 | 0.123 | 0.065 |
| 共享数字MAC | 12.607 | 8.055 |
| Attention QK／筛选／采样／V通路 | 13.001 | 1.660 |
| 共享2.5MiB SRAM | 17.224 | 7.234 |
| DMA数据保持及其他代理 | 2.726 | 1.411 |

与历史8MiB／公共16核固定轨迹预算相比，已计面积104.623→61.492mm²，片上29.323→26.812mJ/token，含DDR1188.447→823.538mJ/token。历史66.992ms轨迹与新版不是单纯容量消融；最近旧8MiB完整执行的同seed时间57.72879→53.66395ms，降低7.04%，仍包含FFN组织和排布变化。

单独隔离容量：同一新完整轨迹按8MiB计价，SRAM面积55.118→17.224mm²、漏电0.852→0.266mJ/token，动态读写仍为6.967mJ/token；全片已计能量27.398→26.812mJ/token。这个8MiB数是同轨迹计价对照，非另做完整8MiB新核回放。缩容主要省面积；整体DDR收益还来自权重排布和执行调度。

面积为已覆盖宏／标准单元之和，项目原始面积单次乘0.81。能量采用实际访问／活动计数与已有PPA锚点，部分保持、格式及向量成本仍是代理；不含完整CIM外围、全局布线／CTS、DDR PHY/IO和控制器。没有新EDA、PPL或硅片实测；不能称完整芯片PPA。三seed时间SD约0.0043ms仅为轨迹变化，不代表模型准确度。

---

以下保留历史阶段记录；其中“未接入／待完成”只对应当时版本。

# 概率LLM公共后端与Attention：条件面积/能量汇总

2026-11-02，Issue225。此页仅公开汇总；完整复算和内部证据留在本地。本次没有新EDA、GPU、DRAMSys或完整TLM运行。

主情景：Qwen3-4B形状、B1/2K，55nm等效、100MHz、8通道DDR4、8MiB SRAM；FFN总16个M128公共核，普通数字MAC1024路，Attention QK另配512路。

| 已覆盖模块 | 面积mm² | 能量mJ/token |
|---|---:|---:|
| FFN公共核及外部随机服务代理 | 20.965 | 4.227–8.967 |
| 普通数字MAC：QKV/O/lm_head | 12.607 | 8.351 |
| Attention QK、筛选、采样和V通路 | 13.001 | 1.937 |
| 全片8MiB SRAM | 55.118 | 8.053 |
| 已价保持、跨K及格式等代理 | 2.932 | 1.677 |
| **已覆盖片上合计** | **104.623** | **24.245–28.985** |

以旧完整回放的66.99185ms作为固定观察窗口，片上平均0.362–0.433W；这是能量除以同一参考时长，**不是新版TPOT预测**。面积是单元/宏与代理合计，未含完整布局、时钟树及IO/PHY。

FFN按同M128宽度比较，从GU16＋Wd16两池32核变成总16核阶段复用；核逻辑面积约39.244→20.801mm²，约少47%。相对旧GU16＋Wd256×M8约47.575mm²，下降约56%，但后一比较同时包含Wd加宽与组织改进。

每token仍完成218880个GU帧和109440个宽Wd帧，工作量没有减半。能量两情景分别采用旧分模式组件代理和新公共核首个混合功耗窗口；新公共核完整PPA尚未验收。**该区间不是置信区间或保证上下界，不能据此宣布动态能量已减半。**

Attention采用候选128、每头64样本的流式地址/V累加交接。其随机源/LUT/比较器在完整采样器锚点内，V控制/ADD/部分和另计；共享SRAM只计一次。删除旧返回FIFO SRAM读写，并给跨K宽状态补读写动作；这些是数据流重计数，尚未真实重放新联合调度。

| 资源情景 | 已覆盖面积mm² | 片上能量mJ/token | 同一参考窗口平均W |
|---|---:|---:|---:|
| A12：紧凑公共池12核 | 99.38 | 23.75–28.49 | 0.355–0.425 |
| A16：紧凑公共池16核 | 104.62 | 24.25–28.99 | 0.362–0.433 |
| B20：保留更多资源的流水切片外推 | 110.08 | 24.74–29.46 | 0.369–0.440 |
| B24：保留更多资源的流水切片外推 | 115.36 | 25.23–29.95 | 0.377–0.447 |

上述不是同吞吐已验证对照。B24的面积不能与A16的面积混用，流水是否提速还需要真实供数和状态bank调度。

现有旧完整DDR核心参考约1159.12mJ/token，命令727.16mJ、后台/刷新等431.97mJ；同窗口平均约17.30W。若只拼接该固定参考和新片上价，约1.183–1.188J/token、17.66–17.74W。**此为交叉版本固定轨迹预算，不是新整机结果**；没有把旧按字节外存代理与当前DDR命令模型直接比较。

关键未闭合项：公共核最终分模式/idle价格；新公共池、Attention V控制和有限DMA入口的统一bank/DDR调度；随机服务接口与数值相关性；存储节点接口增量、DMA路由及PHY。尚无该新组合的模型质量或物理签核结论。

## SRAM容量检查补充

当前8MiB的原声明保留量约2.16MiB，加公共池152KiB宽状态后约2.30MiB。八项静态分配检查显示：保留512个bank、全部权重双缓冲、八组Attention缓存及256KiB激活区，重排后4MiB可放下；将全层常驻归一化权重改为32KiB按层双缓冲后，2MiB也可放下。2MiB方案仍保留旧32KiB FIFO占位，Attention侧bank已满，余量较小。

| SRAM容量 | 同宏价55等效SRAM面积mm² | 其余已价模块不变的合计mm² | 同动作参考SRAM平均mW |
|---|---:|---:|---:|
| 8MiB | 55.12 | 104.62 | 120.21 |
| 4MiB | 27.56 | 77.06 | 112.27 |
| 2MiB | 13.78 | 63.28 | 108.30 |

表中沿用既有4KiB宏单价、面积raw×0.81一次、同动作与参考窗口；未估新增外部选路差异。容量缩小不自动减少动态读写。旧封存轨迹有实际FIFO读写，新直达方案尚须联合回放；不能把旧FIFO视为已删除。当前不改默认，不声称新TPOT已验证。建议先回放4MiB布局，再验证2MiB按层装载和bank竞争；结论限于当前B1/2K配置。

## 2026-11-03：4MiB单层真实访存对照完成

CPU Slurm＋DRAMSys已完成3布局×3seed共9项单层；新解压快照本地、服务器均20项机制/布局检查通过。保留512bank及全部原工作缓冲、24KiB有限直达入口，仅改变SRAM深度与norm/state的bank布局。

| seed | 8MiB原布局ms | 8MiB重排ms | 4MiB相同重排ms |
|---|---:|---:|---:|
| 17 | 1.392620 | 1.406500 | 1.406500 |
| 503 | 1.385600 | 1.381960 | 1.381960 |
| 1009 | 1.381960 | 1.391620 | 1.391620 |

同布局8/4逐phase周期、bank计数、数学工作、外存地址/字节指纹和DDR核心能量完全一致。相对旧布局平均慢0.478%，属于重排影响，不能写成相对旧默认完全无变化。SRAM读写次数和动态能量按同宏价保持，宏面积及漏电约减半；实际外围布线未重新表征。

完整36层＋lm_head配对已在运行（3893），尚无封存TPOT；未由单层乘36外推。原3851在浮点能量严格相等的检查处退出，实际差异小于4e-15mJ；改为精确整数读写动作验收，旧快照/失败保留，9项健康单层未重跑。完整运行仍使用既有GU16/NL256服务合同，新公共FFN只预留152KiB状态容量，不能当作其新状态流量已接入。默认配置尚未更改，完整内部证据留本地。

## 2026-11-03：2.5／3MiB banked池候选已完成单层对照

参考[Gemmini](https://github.com/ucb-bar/gemmini#architecture)与[ONNXim](https://github.com/PSAL-POSTECH/ONNXim#hardware-configuration)将操作数/累加存储按用途分别配置的原则，新增主计算/状态侧与Attention侧的banked池；容量和具体映射为本项目提出，并非它们已验证的配置。保持512个16B/1RW端口，宏深度以既有4KiB宏拼接。

|容量|主计算侧|Attention侧|完整声明后的余量|同宏价55等效SRAM面积|
|---|---:|---:|---:|---:|
|2.5MiB|1.5MiB|1MiB|201KiB|17.224mm²|
|3MiB|2MiB|1MiB|713KiB|20.669mm²|
|4MiB同映射对照|2MiB|2MiB|1737KiB|27.559mm²|

本地/远端26项机制与布局检查通过。实际CPU Slurm＋DRAMSys完成3容量×3seed共9项单层；对应seed的三容量周期全部相同：17为138327拍、503为138560拍、1009为139808拍（100MHz）。逐phase、数学动作、bank计数、外存字节/地址指纹和DDR核心能量严格配对通过，无新权重换出/缓存缩水。动态SRAM动作不变，宏面积/漏电随拼接宏数量变化，bank wrapper及物理布线未新校准。

预检3898/单层3899已完成，完整36层＋lm_head三容量3900已通过门禁并运行，0/3封存；既有3893保持不动。新公共FFN仍只预留152KiB状态，未接其真实读写，不能据本轮确认其状态带宽充分。当前默认不改，无PPL/新EDA或完整芯片PPA结论，完整内部资料留本地。
