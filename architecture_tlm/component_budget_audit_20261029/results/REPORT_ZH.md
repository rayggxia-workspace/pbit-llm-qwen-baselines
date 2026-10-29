# 原整机TLM功耗 面积与时间分项审计

Issue210；主线基线 `787489192ebfcdb61ad72edde406818f450aa3dc`；科学锚点PR192@`91f68416acad0e8306b920b1b8ac779f3d24ad98`。不修改原模型、调度或电路结果。

## 一眼看结果

本报告对应后训练Qwen3-4B形状、36层、batch1、2K上下文、单个decode token、500MHz目标、32个64×64随机阵列、2048 MAC/拍、GU64/NL128、8MiB SRAM与HBM时序。Attention为筛选＋准确Softmax＋PV系统采样，**不是Ising**。不含prefill，不加载真实模型权重，不继承PPL。

三seed平均时间 **57.445385ms/token**；已计价片上能量 **144.544740mJ/token**、平均 **2.516212W**；已计价面积原值 **192.738839mm²**、按0.81折算 **156.118460mm²**。完整物理总值仍未知。

外存旧粗预算另外为 **354.211677mJ/token、6.166060W**；加总 **498.756417mJ/token、8.682271W**。这是64pJ/B＋50mW情景，不能称HBM实测。

| 片上类别 | mJ/token | 平均W | 片上能耗占比 | 55nm面积mm² | 已价面积占比 |
|---|---|---|---|---|---|
| FFN计数与恢复 | 50.1866 | 0.873641 | 34.720% | 63.128107 | 40.436% |
| 共享普通数字MAC | 69.5320 | 1.210401 | 48.104% | 34.046190 | 21.808% |
| PV累加器 | 0.7798 | 0.013575 | 0.540% | 0.464022 | 0.297% |
| 所有片上SRAM和缓冲 | 21.3040 | 0.370857 | 14.739% | 58.186425 | 37.271% |
| FFN随机前端和NL端点 | 1.5568 | 0.027101 | 1.077% | 0.159536 | 0.102% |
| Attention随机端点 | 1.1632 | 0.020249 | 0.805% | 0.125269 | 0.080% |
| sigmoid与其余向量代理 | 0.0223 | 0.000388 | 0.015% | 0.008911 | 0.006% |

功率一律用同一三seed平均TPOT换算，故功率占比等于能量占比。不能把局部工作期间活动功率除整机平均功率来算占比。面积按共享硬件计一次，不按36层重复复制。

## 原始预算的三个门控情景

| 情景 | 片上W | 片上mJ/token | 含旧外存代理W |
|---|---|---|---|
| new_counter_CE | 12.786397 | 734.519483 | 18.952458 |
| counter_real_ICG | 10.028005 | 576.062614 | 16.194066 |
| counter_ICG_plus_digital_gate_candidate | 2.516212 | 144.544740 | 8.682272 |

2.516W这一列已经采用数字单元减少90%空闲动态的假设。原封存时序没有重新加入数字门控唤醒延迟；它是保持原时间的能耗敏感性，不是新门控整机执行。

## 每个物理计价模块

| 模块 | mJ/token | 平均W | 片上占比 | raw面积mm² | 55nm面积mm² |
|---|---|---|---|---|---|
| FFN权重门控 符号 档位对齐 合并计数 | 48.158121 | 0.838328807 | 33.31710% | 76.30387331 | 61.80613738 |
| FFN公共系数与数值恢复代理 | 1.812209 | 0.031546650 | 1.25374% | 1.37857536 | 1.11664604 |
| 共享数字MAC阵列 QKV Wo QK 筛选 lm_head | 69.531976 | 1.210401435 | 48.10412% | 42.03233280 | 34.04618957 |
| PV选择后的向量累加器 | 0.779826 | 0.013575085 | 0.53950% | 0.57286656 | 0.46402191 |
| FFN跨tile宽部分和活动代理 | 0.216305 | 0.003765404 | 0.14965% | 0.25348608 | 0.20532372 |
| 共享SRAM 8MiB | 5.190836 | 0.090361243 | 3.59116% | 68.04730276 | 55.11831523 |
| FFN本地驻留权重SRAM 双bank | 2.375166 | 0.041346508 | 1.64320% | 2.12647821 | 1.72244735 |
| 数字本地权重与激活缓冲 | 5.683186 | 0.098931979 | 3.93178% | 0.59807200 | 0.48443832 |
| DMA响应缓冲 数字与FFN共同使用 | 8.054833 | 0.140217240 | 5.57255% | 1.06323911 | 0.86122368 |
| FFN入口共享随机源 比较器与分发 | 0.007618 | 0.000132616 | 0.00527% | 0.00364176 | 0.00294983 |
| FFN非线性10个Bivium比较端点 | 1.549196 | 0.026968153 | 1.07178% | 0.19331640 | 0.15658628 |
| Attention原有8个Bivium端点 | 1.163188 | 0.020248593 | 0.80473% | 0.15465312 | 0.12526903 |
| FFN及筛选器sigmoid查表 | 0.001090 | 0.000018980 | 0.00075% | 0.01100160 | 0.00891130 |
| 其余向量与非线性旧单价代理 | 0.021188 | 0.000368845 | 0.01466% | 未独立价 | 未独立价 |

以上14行能量和已价面积分别闭合到原结果。CSV另含面积占比与“含外存代理”分母下的占比。未独立计价不等于面积为零；不能据小计排除缺项。

## 时间占比与可重叠忙时

| 串行阶段 | ms/token | 总时间占比 |
|---|---|---|
| FFN含输出转换与残差 | 25.209667 | 43.885% |
| QKV与O投影 | 16.356659 | 28.473% |
| Attention核心 | 8.952024 | 15.584% |
| lm_head与argmax | 6.815673 | 11.865% |
| 其余归一化 RoPE 残差和显式存储 | 0.111362 | 0.194% |

这一张阶段表可以相加得到整token时间；它包含供数、排队与存储等待。下一张是实际预约的服务忙时，跨行存在重叠，**不可相加成TPOT，也不是减少该项就能同比减少的关键路径时间**。

| 模块服务或资源 | 忙时ms | 相对TPOT | 说明 |
|---|---|---|---|
| 外存DMA总资源 | 39.802997 | 69.288% | resource busy time |
| 共享SRAM fabric | 15.286006 | 26.610% | resource busy time |
| 普通数字MAC总资源 | 1.576103 | 2.744% | resource busy time |
| FFN入口编码 | 0.008640 | 0.015% | sum of named stage reservations; may overlap other rows |
| FFN GU采样与计数 | 2.131200 | 3.710% | sum of named stage reservations; may overlap other rows |
| FFN非线性编码与查表 | 0.120384 | 0.210% | sum of named stage reservations; may overlap other rows |
| FFN AND直连Wd采样与计数 | 5.800320 | 10.097% | sum of named stage reservations; may overlap other rows |
| FFN权重与系数编程 | 6.617088 | 11.519% | sum of named stage reservations; may overlap other rows |
| FFN旧恢复宏 | 3.309696 | 5.761% | sum of named stage reservations; may overlap other rows |
| FFN宽部分和更新 | 0.708192 | 1.233% | sum of named stage reservations; may overlap other rows |
| 数制转换 数字矩阵输出及FFN输出 | 0.071568 | 0.125% | sum of named stage reservations; may overlap other rows |
| Attention QKV投影算术 | 0.626688 | 1.091% | sum of named stage reservations; may overlap other rows |
| Attention O投影算术 | 0.414720 | 0.722% | sum of named stage reservations; may overlap other rows |
| RoPE算术 | 0.017280 | 0.030% | sum of named stage reservations; may overlap other rows |
| 摘要筛选算术 | 0.195840 | 0.341% | sum of named stage reservations; may overlap other rows |
| 筛选摘要存取 | 0.296837 | 0.517% | sum of named stage reservations; may overlap other rows |
| K读入与片存搬运 | 4.401483 | 7.662% | sum of named stage reservations; may overlap other rows |
| QK打分与缩放 | 0.103055 | 0.179% | sum of named stage reservations; may overlap other rows |
| 准确Softmax含输入输出SRAM | 0.223488 | 0.389% | sum of named stage reservations; may overlap other rows |
| PV采样选址与GQA合并 | 0.181525 | 0.316% | sum of named stage reservations; may overlap other rows |
| V外存读取 片存装载与广播 | 1.800340 | 3.134% | sum of named stage reservations; may overlap other rows |
| V选择累加与平均 | 0.596304 | 1.038% | sum of named stage reservations; may overlap other rows |
| Attention随机服务真实响应 | 0.008640 | 0.015% | sum of named stage reservations; may overlap other rows |
| lm_head算术与argmax | 0.455812 | 0.793% | sum of named stage reservations; may overlap other rows |

原时间模型仍保留旧分桶归约与系数恢复宏，而能量后处理已经换用合并计数器并排除重复的七桶能量。因此旧恢复忙时不能再用于追加一套七桶面积或能量；这是下一轮集成需要对齐的边界。

## 用户关心的功能逐项对应

| 功能 | 原预算状态 | 时间或费用对应 | 说明 |
|---|---|---|---|
| FFN入口随机源与64比较器 | 合并计价 | FFN_shared64_input_frontend；忙时2.131200ms | 原价含LFSR、比较器及分发；不能凭纯比较器价格强行减拆。GU服务时间与计数器重叠。 |
| FFN非线性随机源与192路比较 | 合并计价 | FFN_nonlinear_10_local_PRNG_endpoints；忙时5.800320ms | 每端点20比较器，200路容量覆盖192路；含随机与比较不再叠加三路比较费用。与Wd采样重叠。 |
| FFN输入与g/u定点编码 | 有动作和时间，独立PPA缺失 | 独立能量未知；忙时0.052416ms | x 92160值，g/u 700416值；不能因已计比较器就认为编码也收费。 |
| 真正g的signed8编码 | 有时间，独立PPA缺失 | 独立能量未知；忙时0.021888ms | 350208值；真实g驱动sigmoid，不等于分档后的概率码直接入sigmoid。 |
| FP32或宽定点转BF16 | 有时间，独立PPA缺失 | 独立能量未知；忙时0.071568ms | 数字矩阵313344值，FFN最终92160值；原表未为这两类转换独立定价。 |
| 三路AND本体与符号指数恢复 | 部分并入计算核，未独立闭合 | counter及restore已含部分门控；额外AND控制缺独立PPA | 179306496次两输入AND仅为动作；不能把整个非线性视为只付sigmoid LUT的能量。 |
| RoPE与RMSNorm | 旧向量非线性代理 | other_vector_and_nonlinear_proxy；忙时0.017280ms | RoPE、范数、指数与倒数没有完整同工艺阵列PPA。 |
| 筛选器 | 摘要点积加概率保留与固定预算修整 | MAC增量+Attention随机端+旧向量代理；忙时0.195840ms | 不是耦合Ising退火；candidate_compact等控制未独立定价。 |
| Ising Softmax | 本锚点未启用 | 独立能量未知 | screen_pv实际执行准确Softmax；不能从原2.516W拆出Ising，也不能把未启用理解为物理电路零成本。 |
| V读取 | 字节与时间已记录，HBM能量仅粗预算 | 外存64pJ/B代理+共享SRAM；忙时1.800340ms | GQA去重后真实物理读取，不能按每头样本数重复读或把面积重复分摊。 |

### FFN随机源与比较器

GU入口是一个共享64路前端，原价同时包含本地LFSR、64比较器和分发。NL按10个Bivium完整端点收费，200个原生比较通道覆盖192路消费。两个合并价格无法从旧整机账本精确拆出PRNG与比较器各自占比；已测纯比较器价格只能作为独立优化参考，不能强行相减产生“实测分项”。本锚点固定W8，不包含新双随机W侧SNG。

非线性g/u编码、真实g驱动、sigmoid查表、三路比较/AND和Wd计数构成一条路径。不能把LUT一行的微小能量当作整个随机SwiGLU能量。FFN计数核含权重门控、符号、档位对齐、归约和时间累计，不再追加同功能门费。

### QKV O投影 QK与lm_head

| 功能 | MAC次数 | 仅有效计算增量mJ | 面积与背景 |
|---|---|---|---|
| QKV投影 | 566,231,040 | 2.791708 | 共享MAC，背景另列 |
| O投影 | 377,487,360 | 1.861139 | 共享MAC，背景另列 |
| lm_head | 388,956,160 | 1.917684 | 共享MAC，背景另列 |
| 候选QK点积 | 75,497,472 | 0.372228 | 共享MAC，背景另列 |
| Q与K摘要点积 | 18,874,368 | 0.093057 | 共享MAC，背景另列 |

五项精确合计到原记录的1,427,046,400次MAC。共享MAC有效增量仅 **7.035814mJ**，其余背景动态和漏电 **62.496162mJ**；背景动态也包含工作期间基底。实际MAC利用率约 **2.426%**。面积不能分别给QKV、O和lm_head各加一套。

### 筛选 Softmax和V读取

筛选流程是16token子摘要读取/平均、Q与摘要点积、max4归一化和sigmoid保留、固定候选预算修整。它不是真正耦合p-bit网络退火。本锚点之后准确Softmax，再用系统采样偏移、CDF计数、重复次数保持与GQA地址并集读取V。

准确Softmax的exp/倒数等仍是旧向量/非线性动作代理，完整物理PPA没有闭环。Ising在该整机结果中未启用，原2.516W和57.445ms不能提供Ising占比。Issue198的新阈值/RNG/拒绝控制只能独立列增量，不能和这组原时序直接拼成已验证新整机。

## 存储容量与外存粗预算

| 物理存储 | 容量KiB |
|---|---|
| 共享SRAM | 8192.0 |
| FFN权重双bank | 256.0 |
| 数字本地operand与激活 | 72.0 |
| DMA响应缓冲 | 128.0 |

共享SRAM配置8MiB，原表显式地址空间保留峰值为715,008B（约0.682MiB）；这不包含上表单独计价的本地和响应缓冲。缩小容量可能同时影响bank数与带宽，不能免费保留原供数能力。FFN权重只按编程写入和保持计，未按每个采样拍重新收取完整普通SRAM读费；CIM全并行读出外围仍缺价。

| 外存事务 | 物理MiB/token | 旧64pJ/B代理mJ |
|---|---|---|
| embedding_physical_bytes | 0.0049 | 0.00033 |
| norm_weights_physical_bytes | 0.3740 | 0.02510 |
| weights_physical_bytes | 5106.8750 | 342.71658 |
| KV_append_physical_bytes | 0.1406 | 0.00944 |
| summary_update_physical_bytes | 0.2812 | 0.01887 |
| summary_read_physical_bytes | 18.0000 | 1.20796 |
| K_selected_physical_bytes | 82.7917 | 5.55605 |
| V_sparse_union_physical_bytes | 24.1775 | 1.62252 |
| ffn_fixed_scale_table_physical_bytes | 0.0483 | 0.00324 |
| weight_scales_physical_bytes | 2.6719 | 0.17931 |

上述外存动作之和另加50mW×TPOT=2.872269mJ，闭合到旧外存代理354.211677mJ。weights行同时含普通投影和FFN权重；FFN权重约2.505GiB，普通矩阵权重约2.482GiB。HBM控制器、PHY和封装面积没有计入片上面积表。

## 优化时优先看什么

1. 能量先看共享MAC背景、FFN计数器和外存模型；先确认数字门控、500MHz及HBM单价，避免优化一个已被低估的小项却忽略主项。
2. 面积先看计数器和共享SRAM；以原位宽/并行度/吞吐为对照，不能把新OR4或双随机小核无条件替代旧多档精确计数。
3. 时间先看供数和FFN全阶段：普通MAC实际忙时远小于投影阶段总时间，单纯增加MAC未必减少等待；DMA、SRAM与计算忙时不可直接相加。
4. 编码和格式转换虽然不是旧表大项，但其中部分没有独立价格，应先补齐再谈占比；随机源与比较器拆价也需要匹配集成边界。

## 未闭合项与复算入口

- 数字门控90%空闲动态消除是情景，不是实测2048路门控阵列。
- 100MHz电路动态能量/参考拍固定，向500MHz外推；未证明500MHz完整STA。
- B7计数按B4位数比例，宽部分和和旧恢复为代理；并非完整集成测量。
- 定制CIM全并行读出、广播、mux、端口、CTS和控制未闭合。
- 外存采用HBM时序，但64pJ/B+50mW来自旧粗预算，不是有效HBM DRAMPower表征。
- 部分数制转换和控制有时间/动作而未独立定价，已计价小计不等于完整芯片总能耗或面积。

`BREAKDOWN.json`保存完整数值；`MODULES.csv`是物理模块能量/面积表，`PHASES.csv`是可相加的阶段时间，`SERVICE_BUSY.csv`是不可相加的资源忙时。`FUNCTIONAL_MAC.csv`、`DRAM_TRAFFIC.csv`、`ACCOUNTING_GAPS.csv`分别对应功能增量、外存和缺项。

复算：`python derive.py --repo <本任务checkout> --out <新目录>`。六个completed摘要原字节SHA及其manifest、配置引用、定价代码和anchors均已核对；raw结果SHA仅核对封存引用一致，未重新下载大轨迹或门级原件。四配置×三情景逐字典复算一致。文件证据见`SOURCE_MANIFEST.json`。模型/语料SHA不适用，因为没有执行数值模型。

当前主线仍为PR190共同调度默认；本报告采用PR192扩容候选的已有预算，不能把其资源、门控或HBM假设说成默认。后续本地端口优化仅有单层＋词表结果，不冒称已经重跑36层新PPA。

[原预算](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/91f68416acad0e8306b920b1b8ac779f3d24ad98/architecture_tlm/ppa_recalibration_20261027/RESULTS_ZH.md) · [原调度](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/91f68416acad0e8306b920b1b8ac779f3d24ad98/architecture_tlm/scheduling_v2_20261027/FINAL_RESULTS_ZH.md) · [Issue210](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/210)
