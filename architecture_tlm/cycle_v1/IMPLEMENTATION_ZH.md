# TLM 周期深化实施结果 · Issue116

**当前目标状态：paused。** 用户提前暂停，后续只做既有证据收尾与交接，不自动继续。最终A–G分类、未提交清单、作业终态与恢复条件见[暂停报告](../../work/amlink1219/116/PAUSE_REPORT_ZH.md)。下列实验来源和指标保持原边界。

2026-10-23。本轮交付了可运行、可复核的 **FFN tile / Attention query 周期后端、共享KV的GQA分组、缩小版单层闭环、原生随机服务、v6配置桥和交互轨迹**。真实片段矩阵和真实context64 GQA已经执行，独立审查已完成。**原方案A–G尚未全部完成：真实全维单层、完整Qwen/Llama、多token与2K/8K GQA、在线DRAM命令后端与物理PPA仍有明确缺口。**

起点为集成分支 `pbit-tlm-attention-details-20261016@46804fb3a1c50b29a19a7d0a3da6bb8f8b59af7d`，正式任务分支 `task/116-cycle-execution`。计划原件SHA-256为 `b6425a140c404c347c1e458a073cea2da0eb3a2aeb645a4ff579348f2b887b13`。旧 `unified_v6`、`random_service` 和历史结果没有改动；43项旧回归通过。

[逐条需求映射](../../work/amlink1219/116/PLAN_COVERAGE_ZH.md)另按原方案章节核对格式schema、物理供给、筛选、采样指标、关键路径、DRAM/互连和最终停止条件，列出下一项可检查验收；阶段表中的“原型完成”不替代这些横向要求。

## 实际达成范围

| 原阶段 | 本轮状态 | 可检查证据 |
|---|---|---|
| A 冻结参考 | 完成当前任务基线、源码/配置/输入散列及旧模式回归 | `work/amlink1219/116/START.json`、`release_validation_v2/RESULT.json`、各运行source manifest |
| B 框架试验 | ONNXim固定官方提交已构建，2官方小例和4自定义Operation场景通过；PyTorchSim只固定版本、未构建 | [ONNXim试验](external/onnxim/README_ZH.md)；采用自有严格参考核继续p-bit数值/时序建模，暂不整机迁移 |
| C 最小周期核 | 已完成所列FFN/query原型：真实字节、有限容量/端口、在线反馈、cycle/event全轨迹相等 | [代码与运行入口](README.md)、[FFN契约](FFN_CONTRACT.md)、68真实片段+8synthetic用例执行/审查回执 |
| D RTL对照 | 有限流水/FIFO/mailbox协议9组252握手逐ps相等；PR122算术适配兼容复验通过 | [RTL报告](RTL_CONTRACT_ZH.md)、`work/amlink1219/116/pr122_compat/REPORT_ZH.md`；未把协议RTL扩大为完整数据通路/STA |
| E 单层闭环 | 缩小单头层7成功场景+2容量拒绝通过；另完成真实7query/1KVhead GQA分组，真实全维整层尚未完成 | `results/reduced_layer_20261023/SUITE.json`、[GQA回执](results/gqa_real_20261023/README.md)；分组输入已投影/RoPE，不是完整层 |
| F 全模型 | 未完成新后端的完整24层Qwen/32层Llama与2K/8K多seed执行 | [具体接口缺口与验收](FULL_MODEL_TODO_ZH.md)；禁止把tile时间乘层数充当实测 |
| G 校准优化 | 交付动作计费边界及8个条件参数敏感性案例；完整PPA/同质量同资源排名未完成 | [动作台账边界](ACTION_COST_BOUNDARY_ZH.md)、`results/ffn_sensitivity_20261022/`；未知保持null |

## 真实输入和执行矩阵

Qwen2.5-0.5B固定模型 revision `060db6499f32faf8b98477b0a26969ef7d8b9987`，模型/配置/语料/token哈希保留于fixture manifest。在本人5090 allocation内抓取层0、12、23的实际输入。FFN保留完整896输入维，裁剪为70 intermediate、16 down输出；W8 scale从原完整64×64 tile量化得到后再裁剪。Attention为head0、2048长度KV中的确定候选，Q/K的FP32 RoPE用于本轮声明的数值边界，不声称与原BF16 Attention逐bit相同。候选是显式固定输入，未把筛选器的计算省略后仍计作完成。

真实矩阵为3层 ×（4组B/T/K × 3seed + exact一次 + PV/winner/rejection各3seed）=66例，另加层12的winner/rejection N512/S512两例，共68例；另有8例synthetic smoke。全部使用默认native随机协议、host_order恢复、cycle与event双模式，**68/68 + 8/8通过**。真实完整矩阵并不等于完整模型。

| 配置 / 边界 | 案例数 | 条件完成时间 |
|---|---:|---:|
| FFN B4/T32/K32，896→70→16 | 9 | 165.725 µs |
| FFN B2/T32/K32，同尺寸 | 9 | 124.775 µs |
| FFN B4/T16/K16，同尺寸 | 9 | 140.125 µs |
| FFN B4/T64/K64，同尺寸 | 9 | 216.925 µs |
| exact Attention，128候选、64维 | 3 | 8.0125 µs |
| systematic PV，N128/S32 | 9 | 10.3125–11.175 µs |
| winner，N128/S32 | 9 | 30.2125–38.9625 µs |
| rejection，N128/S32 | 9 | 30.2125–50.325 µs |
| winner，N512/S512，层12/seed0 | 1 | 322.7625 µs |
| rejection，N512/S512，同输入 | 1 | 320.500 µs |

这些是新后端在明示资源假设下的算子时间，不是TPOT、硬件实测或同质量算法排名。N512的两个样例各保留512样本，但实际只访问2个独立V行；winner保持与重复样本仍保留multiplicity。源帧、80个物理lane/64个逻辑lane、padding、提议与拒绝分别记账，不把一次完整多波源访问称作一拍。

主索引为 [矩阵SUMMARY](results/matrix_20261023/SUMMARY.json) 和 [归档位置](results/matrix_20261023/ARCHIVE_INDEX.json)。`CASE_SUMMARIES.json.gz` 包含76个完整summary；两份原制品manifest列出全部SHA，选择性保留代表trace和HTML。完整原件在本人服务器和本机归档，未上传模型权重或原始私有fixture。

交互检查台：

- [真实FFN B4/T32/K32](results/matrix_20261023/qwen_layer12_ffn_B4T32K32_seed0/timeline.html)
- [真实exact Attention](results/matrix_20261023/qwen_layer12_exact_N128_S32_seed0/timeline.html)
- [缩小版整层](results/reduced_layer_20261023/exact/timeline.html)

检查台脚本已用最小DOM执行过滤、点击详情、范围拒绝和重置检查；本轮未宣称浏览器布局逐像素验收。时间条显示实际接受至完成区间；等待原因、时钟、地址和依赖可点开查看。latest-dependency回溯不是涵盖所有资源/信用因果的完整关键路径证明。

## 正确性证据与修复

最终81项实现测试、43项旧回归通过（release_validation_v2）；独立代理71项测试通过，其中基础54项覆盖手推时序、32随机DAG、32随机字节内存、Q256边界、精确有理数FP32舍入oracle、有限预取与乱序返回反例，新增17项GQA检查包含32组随机稀疏head图。层0/12/23真实FFN片段的gate/up/z/projected/output与独立标量oracle逐bit一致；它们冻结实际native门限，独立数学实现不导入生产encoder/restore。

最终矩阵独立离线验收：302制品、源archive内64文件；34份完整trace共403,583事件、98,340操作，重算动作、old-state额度、窗口/bank/完成端、资源统计；从私有fixture独立重建4,597项真实read payload hash。42份未保存完整trace的案例只称回执级验收，不把它们写成独立逐操作复验；全76例也没有冒称全矩阵独立数学证明。详见 [独立审查](audit/REVIEW_ZH.md) 和 `audit/results/matrix_v5_offline_review_final.json`。

首轮真实矩阵2775为62通过、6失败，暴露了有序V累加与无序预取的信用死锁。后来V读占满缓冲，使更早需要的V无法发出。修复为按消费顺序限制有限lookahead窗口，窗内仍允许真实乱序返回；[1,2,10]且仅1slot的独立最小反例通过。最终2776全部通过。旧失败SUMMARY/6个FAILURE保留在 `work/amlink1219/116/first_matrix_failed/`，没有覆盖失败历史。

其他已修正事项包括：完成端不能堵塞后同沿无限排空、事件跳步必须保留CDC/bank局部解锁的stall变化、FFN输入/权重/partial必须消费实际字节、原位平面必须保持输入符号与二补码权重、PV CDF与归一化不能在回调内免费完成、tiny编码不能倒数中间溢出、restore必须展开有限lane和scratch。恢复的host_order与rtl_fused0_order保留显式差异，次正规反例0x2/0x3已独立核验；新增profile不代表全FFN bit-true RTL。

## 共享KV的真实GQA分组

[GQA接口与容量契约](GQA_GROUP_ZH.md)把7个query head和一个KV head接入同一Kernel。K候选union每行只从DRAM读取一次，所有QK消费者完成后才归还行信用；V在各head采样完成后经有限lane扫描/压缩形成union，保持每个head自己的权重、重复次数和分母。cache读口、操作数响应、metadata、score状态都有明确有限额度和释放事件。独审发现并修复了免费host union和无界操作数暂存两个P1；最终无未修复P0/P1。

Slurm2781用9秒GPU分配捕获Qwen层12、query head0–6/KV head0、64token、D64的实际输入。私有fixture SHA为 `ee5722b38a1acb94daf4d09e49651c9a4610dbc9a9b0ac444b29bb1ef2280080`，BF16投影后采用明确的FP32 RoPE边界。新fixture的下载被自动审批拒绝，故全部实际张量、输出和完整轨迹保留本人服务器；回传仅白名单配置、计数、时间、误差、哈希及终态，未绕过导出限制。

Slurm2782在2CPU/8GiB、隐藏GPU的分配内运行2分57秒，COMPLETED/0:0。生产源固定 `f94c9db566b45a1c2f8db0fa8749366dde7f7450`，独审4文件固定 `9f1122e04f272f34d3ca48e3314677721b49f8d5`；74个执行源文件逐项散列核验。5个S32 CLI配置均通过双模式：

| 配置 | 条件完成时间 | 操作数 | K/V实际union行数 |
|---|---:|---:|---:|
| exact | 41.94 µs | 2,116 | 64 / 64 |
| systematic PV | 52.10 µs | 2,354 | 64 / 49 |
| winner | 55.16 µs | 3,423 | 64 / 40 |
| corrected rejection | 66.47 µs | 4,483 | 64 / 42 |
| exact，K/V/operand/window均缩至1 | 97.00 µs | 2,116 | 64 / 64 |

默认K/V/operand slot各2、memory window4。约束收紧后7个exact输出hash保持一致。每组K的DRAM读为16,384B，query各自的cache读取与MAC仍收费；不能据此声称完整Attention节能7倍。生产高精度weighted-V参考的exact最大绝对误差为1.1920928955078125e-7。

独立服务器审查另用6个S16配置、12次cycle/event执行，**42个case/head、2,688个输出值全部逐bit相等**；12,776操作、70,185事件、636项实际共享行返回字节检查通过，全部信用归还。该算术结论以实际观察到的native采样轨迹为条件，未证明IID、分布质量或PPL。公开回执、源archive与root整合副本由独审再次核验，见 [GQA结果](results/gqa_real_20261023/README.md) 和 [最终审查](audit/REVIEW_ZH.md)。旧Attention四个真实样例的完整双模式payload与冻结v5保持相等。

另有4模式7head合成回执及显式event-only标志检查，保存在 `work/amlink1219/116/gqa_validation/`。原核N64→N128的有界event-only规模探针为4.97→21.78秒，显示全表调度明显超线性；[原核2K评估](../../work/amlink1219/116/gqa_scaling/ASSESSMENT_ZH.md)的约93分钟仅是风险外推，没有原核2K结果。

随后对PR125固定公开d944081a的ActiveMemory候选做了独立兼容审查：47个GQA图原核/候选×cycle/event共188执行和动态hazard另4执行全payload/state相等，另20个core方法在候选上通过；[范围说明](audit/results/active_memory_d944081/REVIEW_ZH.md)保留私有接口依赖风险。合成N64/128/256候选约0.995/3.668/14.692秒，原核同形状结果散列一致，仍近二次；这是模拟器CPU成本，默认Kernel未替换。用户暂停时，新的本机2K合成候选刚完成建图即被终止，没有执行、数值或轨迹通过结论；暂停原件在`work/amlink1219/116/active_gqa_2k_paused/`。

## 旧TLM与并行项目的关系

[v6适配入口](V6_ADAPTER_ZH.md)实际运行旧算子方法与新算子，5例配置/shape桥通过，47制品与完整trace另行核验。它明确区分旧BF16 fused路径与新FP32显式路径、旧Link与新banked descriptor服务、宏恢复与分级恢复；`speedup=null`。没有将独立边界的耗时差包装成性能增益。

本轮核对到PR119资源优化、PR120供数/整数状态、PR122编码恢复和PR125完整FFN接合均待审。未合并或改写这些业务代码。对固定PR122 `8007d98f15676ad316180ee18b5d1b29aa00af95`，在当前核心上新跑28软件测试、12场景/1536完整恢复，16份JSON与其原冻结结果相等；其27组RTL/6861输出仅引用原回执，未计作本任务重跑。中央台账的独立record需合并后重建，不能互相覆盖catalog。

[PR125](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/125)最新在2026-10-22 19:31 UTC核到 `d944081a22dc346a3a50d505633e5d15c857ba78`，base已调整为本任务分支，公开完整FFN接合和活动内存调度优化；它仍待审未合并。其回执记录真实896→4864→896完整FFN单token fixture（Slurm2777），T16/T32/T64编码恢复45场景、11667输出、180 reset flush（2778），以及28软件测试/120次独立随机复核。完整形状作业2783仍在运行，尚无完整形状通过结论。这些是并行任务的证据，没有计入Issue116新跑数量。实际STA/PPA按该任务安排交由jieruiz执行，当前EDA仍not_run。本次正式发布周期后端供其接合，不重复抓取完整权重或接管其运行；任何在GQA上采用该优化的结论必须另附固定来源和等价性验证。

**暂停时补充终态：** 2783已由scontrol核实为CANCELLED/0:15，运行24分20秒；上述“仍在运行”仅为19:31核查快照。Issue116没有取消该并行作业，也不将取消计为完整FFN验证成功。

## 资源、归档和剩余风险

5090主服务器仍可用，没有切换4090。GPU仅用于2759与2781的真实fixture抓取，分别14秒和9秒成功；构建、RTL、矩阵及GQA验证均为Slurm CPU分配并隐藏GPU。最终矩阵2776申请8CPU/20GB，7分56秒，COMPLETED/0:0；ONNXim2772、协议RTL2764与GQA2782均完成。依赖构建的失败及恢复、启动脚本错误均保存，不算作测试成功。

主任务个人根为 `/home/Weican_Chen/projects/tlm-cycle-issue116-20261023`。完整矩阵归档SHA-256：`82319f0d95054149e7d3dbeba5248648d461fe91539107aaa85e83fd44429ee5`。实际执行源archive SHA-256：`f6c596f3d772dee19bea1d85badb25fe0088aefaaae70ab959555b68daf96cbf`。快照按真实执行字节散列，Windows换行与Git规范化不能静默替代；结果文件明确保留原始字节。

32KiB权重额度是DMA到restore期间单份逻辑所有权；它没有证明32KiB staging与额外32KiB阵列保持都已存在。全阵列静态驻留和宽供数需后续RTL/布局证明。全局地址空间容量、共享全模型随机网络、真实DRAM/NoC、完整格式映射和全模型质量也未闭合。完整896→4864→896 FFN估计3192tiles、418waves、210432 operations；局部fanout探针120秒超时，不能承诺把裁剪片段扩成整层即可在十几分钟完成。在线Ramulator接合仍需异步descriptor/返回信用、写可见性及不同callback语义的独立门禁，见 `work/amlink1219/116/RAMULATOR_ONLINE_FEASIBILITY_ZH.md`；当前banked模型未伪装成DRAM命令后端。全部性能数字、未知项和下一步门禁分别保留，不为满足时间限制跳过这些问题。
