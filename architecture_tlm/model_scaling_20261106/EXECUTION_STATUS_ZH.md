# 三模型硬件评估：材料已齐，24项原生单层验证通过

**2026-11-08更新：** 数组38625522的24项单层pilot已全部完成；RESULT、WORK_GATE和SEAL逐SHA复核通过。原始JSON归档`project_archives/cross245_20261108/SEALED_PILOTS.tar.gz`，219990B，SHA-256 `6e0198f2460989ef40ba24ca9a6969b4581d6b6b36dd1b9bd3c918e19a0f86e2`。这是事务/工作量门禁，未改变下方“整机结果尚未完成”的边界。数组已自然结束，不重交。

已另生成可重算的`COMPONENT_BUDGET.json`，给出经过全尺寸工作量检查的权重流量下界和已标定计算核能量，便于先判断量级：

|模型|W8/概率：只读矩阵权重的时间下界|BF16：同一下界|W8/概率：只读矩阵权重能量，4pJ/bit|
|---|---:|---:|---:|
|Qwen3-4B|39.24ms|58.95ms|171.36mJ|
|Llama-3.2-3B-Instruct|31.59ms|47.08ms|137.96mJ|
|DeepSeek-LLM-7B-Chat|65.39ms|95.13ms|285.55mJ|

上表是136.4606GB/s下、包含lm_head矩阵的**数学下界/单项预算**，不是实测或TLM总时间/总能量；不含KV、norm、元数据、SRAM、PHY及等待等成本。SC和W8外存权重字节相同，不能把这部分节省都归因于随机运算。100MHz FFN内部增量能量（不含存储/转换/驻留）分别约0.90/0.71/1.36mJ，来自有效SS100核标定；BF16 FFN对应约17.80/13.99/26.85mJ。它们不能当FFN子系统总能耗或整机节能倍率。250MHz SC有效价仍为空，失败STA数据未填入。

以下保留11月7日的执行背景和具体限制；其“运行中/首项完成”是历史时点。

2026-11-07，Issue245 / PR247，负责人 rayggxia。目标仍是同一套100/250MHz芯片运行Qwen3-4B、Llama-3.2-3B-Instruct、DeepSeek-LLM-7B-Chat，比较概率与等面积数字方案。此次开始真正执行CPU事务回放；没有下载大权重、启动GPU或训练。

## 所需材料能否取得

|材料|本次核验结果|用于什么|
|---|---|---|
|Qwen3-4B配置|已有锁定revision的本地配置；[官方配置](https://huggingface.co/Qwen/Qwen3-4B/blob/main/config.json)可访问|层数、矩阵尺寸、头数、词表、绑定输出权重|
|Llama-3.2-3B-Instruct结构|HF原始config的匿名请求曾401；已用[Meta官方SKU](https://github.com/meta-llama/llama-models/blob/main/models/sku_list.py)及原有身份记录交叉核验，保留“结构派生配置”来源|本阶段只需结构，无须申请或下载权重|
|DeepSeek-LLM-7B-Chat配置|已有锁定revision的本地配置；[官方配置](https://huggingface.co/deepseek-ai/deepseek-llm-7b-chat/blob/main/config.json)可访问|MHA的32个KV头、矩阵和词表尺寸|
|数字FFN与Attention|发现并接用了11月7日两个模块的新交接，而非重做算术价格|FMA16/C4、W8整数GU、有限bank读写、非线性和确定性Attention|
|SRAM / LPDDR|已有校准动作价格、4KiB宏和原生Ramulator动态库|真实bank端口、有限DMA、队列、FRFCFS/刷新时序|
|采样输入|本地生成合成BF16 Q/K及active-head SparQ候选；复用有SHA的ab_both/P8参考采样轨迹|参考事务驱动；不是新模型真实文本分布|

模型config和身份入口仍在`evidence/`。没有重复下载几十GB权重。私有模块执行源码只进入本地/EDA冻结快照；Git发布本任务胶合代码、配置/来源索引和小型回执。

## 实际完成的工作

1. 已有可执行跨模型试接入口`execution.py`，复用现有SharedMemory/BeatSRAM和原生LPDDR后端，数字FFN绑定交付的生成器接口；所有主要矩阵按完整尺寸搬权重和分块执行。
2. 分离有效Q头与物理四Q槽。Llama为3/4有效槽；DeepSeek为1/4有效槽，32个KV组复用八个片上组、分四波执行。空槽的物理执行成本暂保留，候选计算只使用有效头；这是明确的初始映射，不宣称已优化为任意头数电路。
3. 数字FFN尺度表按真实64×64块数配置；DeepSeek33024B向上预留36KiB，未继续使用20/32KiB常数。SC的g/u尺度移到权重元数据之后，避免重叠；GU输出状态保持96KiB及原有分批所有权。
4. 前端bank按对象连续轮转，避免各对象独立向上取整造成虚假的bank溢出。250版本的960KiB物理深度检查通过；删除的DMA SRAM没有重新加回，16KiB返回寄存器仍另计。
5. 四项测试通过，包含24个物理布局/完整面积配额检查、12套FFN全形状分包工作量、三seed参考采样地址覆盖及头数/波数检查。另已实际执行Llama250 SC FFN和DeepSeek250 W8 FFN的本地完整尺寸回放；它们是解析外存下的模块检查，不作整机PPA。

## 已提交的远程任务

- Slurm数组 **38625522_[0-23]**，分区v6_384；每项1CPU、10GiB、2小时上限，最多同时2项，0GPU。
- 三模型×两频率×SC+Ising/BF16dense/W8dense/W8screen，共24个**完整尺寸单层pilot**；本轮暂不计lm_head。
- 原生外存配置SHA：`1afdaa1b1e144b838537798ac476e9d98eff9ae1c853e63d30fe8875b4713b07`；其模型时钟为0.938ns，从PROFILES.json读取，与片上4/10ns分开；是LPDDR5派生8533条件模型，不是厂商签核的LPDDR5X模型。
- 冻结执行manifest SHA：`bc8cbd87244c239d88774c71a860a939b41b880536e52fbe2dbdba68e7e9f529`。精确执行目录、提交UTC、动态库及配置SHA见本任务SUBMISSION.json。
- 首个Qwen100 SC单层已完成，权重读取127139840B与公式一致，原生后端与片上队列排空，WORK_GATE=PASS。其余任务的实时状态以STATUS.json和服务器为准；不把正在运行写成已完成。

## 当前还不能作为最终三模型结果的原因

这批是适配门禁，**不是原主线配置已完整移植、不是24个整模型结果，也不能把pilot时间直接乘以层数**。本次没有替换100/250默认：

- 试接的投影供数及PV生产/消费目前较串行，尚须恢复主线已经验证的预取与重叠，然后用Qwen主线结果作回归锚点。不能据此宣布数字基线或概率方案变慢。
- 试接Attention沿新数字模块的r32入口；250概率主线为r16，后续必须对齐。固定四Q槽有明确额外工作，后续报告须区分有效和填充MAC，不把额外工作解释为模型需要。
- 数字面积配额采用八Attention槽及合法FMA16切片；这是预算内合法点，不是已经穷举2/4/8并发等所有最优点。
- Norm/RoPE/残差先保留显式延迟宏；最终整机还须补齐原主线的实际读写、价格及输入/输出生命周期。此次没有输出一个遗漏这些项的“总能量”。
- 250MHz新短T核PPA仍未验收；不采用时序失败结果当有效功耗或面积。当前250总面积仍是有标注的旧TT参考配额。

这些是接口/调度的剩余工作，不是缺少模型权重或需要再跑准确率。下一步先收齐封存pilot并检查各矩阵字节数、帧数、候选/样本、bank深度与队列守恒；对齐上述主线项后再提交28/30/36层含head的整机任务，分别报告含/不含lm_head时间，以及逐模块能量、平均功率、面积和未标定项。最终随机情景仍按三seed报告，本轮单seed只是结构门禁。

恢复命令：`python -B work/rayggxia/245/execute_20261107/ops.py status`。本机使用Codex附带Python；系统Python3.8.1与现有SSH依赖不兼容。不得重新执行prepare产生重复作业，也不得改写已提交快照。没有新增数字电路综合/PT，不能登记为新实测PPA。
