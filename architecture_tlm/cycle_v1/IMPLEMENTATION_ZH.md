# TLM 周期深化实施结果 · Issue116

2026-10-23。本轮交付了可运行、可复核的 **FFN tile / Attention query 周期后端、缩小版单层闭环、原生随机服务、v6配置桥和交互轨迹**。真实片段矩阵已经执行，独立审查已完成。**原方案A–G尚未全部完成：真实全维单层、完整Qwen/Llama、多token/GQA、在线DRAM命令后端与物理PPA仍有明确缺口。**

起点为集成分支 `pbit-tlm-attention-details-20261016@46804fb3a1c50b29a19a7d0a3da6bb8f8b59af7d`，正式任务分支 `task/116-cycle-execution`。计划原件SHA-256为 `b6425a140c404c347c1e458a073cea2da0eb3a2aeb645a4ff579348f2b887b13`。旧 `unified_v6`、`random_service` 和历史结果没有改动；43项旧回归通过。

## 实际达成范围

| 原阶段 | 本轮状态 | 可检查证据 |
|---|---|---|
| A 冻结参考 | 完成当前任务基线、源码/配置/输入散列及旧模式回归 | `work/amlink1219/116/START.json`、`release_validation_v1/RESULT.json`、各运行source manifest |
| B 框架试验 | ONNXim固定官方提交已构建，2官方小例和4自定义Operation场景通过；PyTorchSim只固定版本、未构建 | [ONNXim试验](external/onnxim/README_ZH.md)；采用自有严格参考核继续p-bit数值/时序建模，暂不整机迁移 |
| C 最小周期核 | 已完成所列FFN/query原型：真实字节、有限容量/端口、在线反馈、cycle/event全轨迹相等 | [代码与运行入口](README.md)、[FFN契约](FFN_CONTRACT.md)、68真实片段+8synthetic用例执行/审查回执 |
| D RTL对照 | 有限流水/FIFO/mailbox协议9组252握手逐ps相等；PR122算术适配兼容复验通过 | [RTL报告](RTL_CONTRACT_ZH.md)、`work/amlink1219/116/pr122_compat/REPORT_ZH.md`；未把协议RTL扩大为完整数据通路/STA |
| E 单层闭环 | 缩小单头层7成功场景+2容量拒绝通过；真实全维/GQA层尚未完成 | `results/reduced_layer_20261023/SUITE.json`；真实Qwen数据仅算子片段 |
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

71项实现测试、43项旧回归通过。独立代理的54项测试包括手推时序、32随机DAG、32随机字节内存、Q256边界、精确有理数FP32舍入oracle、有限预取与乱序返回反例。层0/12/23真实FFN片段的gate/up/z/projected/output与独立标量oracle逐bit一致；它们冻结实际native门限，独立数学实现不导入生产encoder/restore。

最终矩阵独立离线验收：302制品、源archive内64文件；34份完整trace共403,583事件、98,340操作，重算动作、old-state额度、窗口/bank/完成端、资源统计；从私有fixture独立重建4,597项真实read payload hash。42份未保存完整trace的案例只称回执级验收，不把它们写成独立逐操作复验；全76例也没有冒称全矩阵独立数学证明。详见 [独立审查](audit/REVIEW_ZH.md) 和 `audit/results/matrix_v5_offline_review_final.json`。

首轮真实矩阵2775为62通过、6失败，暴露了有序V累加与无序预取的信用死锁。后来V读占满缓冲，使更早需要的V无法发出。修复为按消费顺序限制有限lookahead窗口，窗内仍允许真实乱序返回；[1,2,10]且仅1slot的独立最小反例通过。最终2776全部通过。旧失败SUMMARY/6个FAILURE保留在 `work/amlink1219/116/first_matrix_failed/`，没有覆盖失败历史。

其他已修正事项包括：完成端不能堵塞后同沿无限排空、事件跳步必须保留CDC/bank局部解锁的stall变化、FFN输入/权重/partial必须消费实际字节、原位平面必须保持输入符号与二补码权重、PV CDF与归一化不能在回调内免费完成、tiny编码不能倒数中间溢出、restore必须展开有限lane和scratch。恢复的host_order与rtl_fused0_order保留显式差异，次正规反例0x2/0x3已独立核验；新增profile不代表全FFN bit-true RTL。

## 旧TLM与并行项目的关系

[v6适配入口](V6_ADAPTER_ZH.md)实际运行旧算子方法与新算子，5例配置/shape桥通过，47制品与完整trace另行核验。它明确区分旧BF16 fused路径与新FP32显式路径、旧Link与新banked descriptor服务、宏恢复与分级恢复；`speedup=null`。没有将独立边界的耗时差包装成性能增益。

本轮核对到PR119资源优化、PR120供数/整数状态、PR122编码恢复和PR125完整FFN接合均待审。未合并或改写这些业务代码。对固定PR122 `8007d98f15676ad316180ee18b5d1b29aa00af95`，在当前核心上新跑28软件测试、12场景/1536完整恢复，16份JSON与其原冻结结果相等；其27组RTL/6861输出仅引用原回执，未计作本任务重跑。中央台账的独立record需合并后重建，不能互相覆盖catalog。

[PR125](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/125)在本轮核对时为 `a9c0031d4b4f45697f6b52144948d6ac084df2f4`：其回执已记录真实896→4864→896完整FFN单token fixture（Slurm2777），以及T16/T32/T64编码恢复45场景、11667输出、180 reset flush（2778）。这些是并行任务的证据，没有计入Issue116新跑数量；完整FFN接合仍在进行。实际STA/PPA按该任务安排交由jieruiz执行，当前EDA仍not_run。本次正式发布周期后端供其继续接合，不重复抓取完整权重或接管其运行。

## 资源、归档和剩余风险

5090主服务器仍可用，没有切换4090。GPU只用于2759真实fixture抓取，14秒成功；构建、RTL、矩阵均为Slurm CPU分配并隐藏GPU。最终矩阵2776申请8CPU/20GB，7分56秒，COMPLETED/0:0；ONNXim2772、协议RTL2764均完成。依赖构建的失败及恢复、启动脚本错误均保存，不算作测试成功。

主任务个人根为 `/home/Weican_Chen/projects/tlm-cycle-issue116-20261023`。完整矩阵归档SHA-256：`82319f0d95054149e7d3dbeba5248648d461fe91539107aaa85e83fd44429ee5`。实际执行源archive SHA-256：`f6c596f3d772dee19bea1d85badb25fe0088aefaaae70ab959555b68daf96cbf`。快照按真实执行字节散列，Windows换行与Git规范化不能静默替代；结果文件明确保留原始字节。

32KiB权重额度是DMA到restore期间单份逻辑所有权；它没有证明32KiB staging与额外32KiB阵列保持都已存在。全阵列静态驻留和宽供数需后续RTL/布局证明。全局地址空间容量、共享全模型随机网络、真实DRAM/NoC、完整格式映射和全模型质量也未闭合。完整896→4864→896 FFN估计3192tiles、418waves、210432 operations；局部fanout探针120秒超时，不能承诺把裁剪片段扩成整层即可在十几分钟完成。全部性能数字、未知项和下一步门禁分别保留，不为满足时间限制跳过这些问题。
