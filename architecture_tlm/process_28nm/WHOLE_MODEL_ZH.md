> **2026-11-09：250MHz已接新零余量FFN/FMA、PV参考与平台宏，面积预算6.4803mm²。** 六个小回放与六项检查通过；完整token46.02ms为条件外推。500MHz保持6.5929mm²预算。见[250MHz最新报告](250MHz/UPDATED_TLM_20261109_ZH.md)。

> **2026-11-09更新：28nm250/500MHz默认832KiB/178个混合宏。** 前端106共享端口＋Attention72端口；条件面积预算6.566340/6.592880mm²。见[混合宏验证](SRAM_MIXED34_VALIDATION_20261109_ZH.md)。55nm保持。

> 2026-11-09：宿主已独立完成832KiB两频小配对，见[验证结果](SRAM832_VALIDATION_20261109_ZH.md)。此前默认960KiB，现已接受832KiB；[需其它模块确认的清单](../module_handoff/SRAM_REDUCTION_COORDINATION_ZH_20261109.md)。

> 用户2026-11-09决定：取消统一15%面积预留；当前250/500MHz中心7.139/7.165mm²。SRAM已默认832KiB，两频小配对已完成。见[面积和SRAM审查](AREA_SRAM_REVIEW_20261109_ZH.md)。

> 2026-11-09更新：真实28nm SRAM宏已接入250/500配置。见[SRAM接入结果](SRAM_INTAKE_20261109_ZH.md)。下方此前SRAM未表征/跨工艺估值均为历史状态，其它模块限制仍保留。

# 28nm整机TLM运行入口

2026-11-09，Issue225 / PR249，rayggxia。`run_whole.py`现在可以运行完整decode流程：embedding→各层Norm/QKV/RoPE→SparQ/QK→S12前端/Ising/PV→O/残差→随机GU→跨K/尺度转换→随机非线性-Wd→残差→最终Norm/lm_head。当前支持Qwen3-4B B1/2K、K128/S64，250/500MHz分开，不改55nm默认。

## 执行模型沿用什么，实际改了什么

- 复用既有不可变快照的bank级16B/1RW SRAM、region/地址检查、有限16KiB返回保持、DMA信用、bank仲裁、双缓冲、预取、GQA共享、输出回压和部分和状态。重新执行事件，不按旧总时间乘比例。
- FFN使用28nm实测18/34拍；250MHz初始3核，500MHz初始2核。两结果信用/核、32权重槽、两state32端口保持。最终g/u使用一个1KiB宽值暂存信用、两64元素尺度组、16codec流水；暂存忙时阻塞上游。输出转换也使用同一个codec资源阶段。GU/Wd两模式共享一份核面积；SNG/GF64/sigmoid/AND/计数不再另计。
- 当前A前端每头只从SRAM读512B，内部保存S12，执行整数max-gap。每层32查询=16384B分数读取。32拍前端输出/后端加载属于同一握手，不在时间上双计。
- 新gap采样器暂用已测平均query周期的向上取整宏，扣去共享32拍后，按固定S64的有限地址流驱动V。地址来自既有封存参考，不是新Qwen概率或p-bit统计实验。**这不是逐query真实28nm采样器轨迹**，参数到齐后可替换，不回退成S64=64总周期。
- 筛选价卡的单位已对齐：norm是四头一组，feature选择是每个Q头一次（每KV组4次），token选择是每KV组一次。四头共享候选/V缓存，外存V字节按真实miss计；相同地址允许重复消费，但不重复DMA读。

## 目前显式保留的假设

`250MHz/WHOLE_CONFIG.json`与`500MHz/WHOLE_CONFIG.json`是可调宏入口。初始同一片上时钟4/2ns，SRAM每bank1RW、178混合宏/832KiB、访问延迟1拍；S0宏TT时序已确认，bank互连沿有限执行模型。`--sram-latency-cycles 2`改变返回延迟，bank仍每核心拍接受一次操作，不等价于把bank时钟减半。

共享数字池初始256FMA、4上下文、II1、4拍反馈/尾部；500MHz的新数字实现仍待最终绑定。PV初始每头2ADD、7拍反馈，输出归一化/格式宏16拍。Norm/RoPE/残差及部分控制保留原命名周期数。上述未确认项目分别标宏，不冒称已通过28nm STA；FFN零setupunc与Attention10%period的表征标签保留。

SRAM读写能量、漏电/面积未绑定时保持null，实际读写和等待仍执行并计数。可在WHOLE_CONFIG填宏价；不能把缺项当免费，不能暗套55nm或0.81。`whole_pricing.py`只报告已有依据的组件小计、外存4/6.6/8pJ情景与未计项目，整机总面积/总能量保持null。外存仍独立：本机回放为原136.4606GB/s、30ns解析后端；Linux可选原封存Ramulator/LPDDR后端，不能随核心倍频而提升DRAM带宽。

## 运行方式

依赖既有共享执行资料，并在每次运行前验证其manifest。当前本机位置：

- `tmp/cross-model245-20261106/work/rayggxia/245/mainline_20261108/revision2/snapshot`：既有host/fixture快照3a7dd5e0679e，manifest982f9303785c364ed7c7ac5384927f0a12f98388433708306878e5f14fbae925。
- `project_archives/ffn_sram_batch204_20261106/runtime`、`project_archives/sram1216_225_20261106/dependencies`：既有冻结运行环境；入口会逐源码/依赖SHA核对。
- 当前28nm价卡：本目录各频率BINDINGS.json；不得在已提交运行中改写它们。正式验证通过独立小型执行快照冻结源码/绑定/宏配置，恢复入口见work/rayggxia/225/process28_whole_20261109/EXECUTION.json。

从仓库根运行完整250MHz36层＋实际完整词表的命令模板：

```powershell
python -X utf8 -B architecture_tlm/process_28nm/run_whole.py `
 --snapshot <既有host快照> --runtime <冻结runtime> --dependencies <冻结依赖> `
 --bindings architecture_tlm/process_28nm/250MHz/BINDINGS.json --cores 3 `
 --layers 36 --head --out <新的结果目录>
```

500MHz改用500MHz绑定、cores2。省略`--head`可运行主体；结果总会同时列实际包括的head阶段时间和扣除该阶段的时间。**这里是运行入口，不表示已经完成36层新仿真。** `--head-probe-rows 384`仅供快速集成检查，输出有明确字段；不能当成151936词表耗时。实际完整词表全部tile、字节和128行尾块会在结构预检中检查。

`--backend native`仅在既有Linux native桥及库可用时使用。默认analytic不是LPDDR逐命令回放，不把本轮解析结果当成新的原生LPDDR测量。

## 验证范围和已发现的问题

正式三个冻结门禁：250MHz两层＋384词条输出头（含128行尾块），500MHz完整单层，以及500MHz SRAM延迟2拍的同工作量敏感性。`verify_whole.py`核SEAL/SHA、源与配置、采样/FFN/转换工作量、V miss/字节、有限信用、未知成本状态及周期。完整151936词表只有tile/字节结构检查；完整36层未在本轮执行。结果见WHOLE_VALIDATION.json。

开发试跑发现两层截断仍按36层预取Norm，最终Norm会等待未执行tag释放。现已仅对截断＋head测试绑定真实执行深度，完整36层语义保持；失败过程保留，两个本地阻塞探针已终止，没有取消服务器健康任务。一次tile预检将MAC数误当BF16字节数也已拆开修正，失败v2未计有效结果。正式消费只认不可变v3及其封存，不用未冻结开发回执充数。

本轮没有新增RTL/PT/工艺仿真或模型/PPL，没有为缺项虚构芯片面积与功耗。补测只改价卡时可重计价；latency/II/端口/状态变化时更新宏和回放。发布看work/rayggxia/225/process28_whole_20261109/PUBLICATION，PR未合并，Projects待维护者同步。
