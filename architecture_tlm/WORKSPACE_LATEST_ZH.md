# 工作区最新 TLM 文件索引（2026-10-16）

发布目标：rayggxia-workspace/pbit-llm-qwen-baselines。
这是现有实现的发布快照；本次对话提出的“原生 p-bit 直接驱动筛选”及“耦合预算筛选器”尚未实现，不能当作本版功能。

| 模块 | 设计与范围 | 实现 | 已保存结果 |
|---|---|---|---|
| Attention v3：准确、PV采样、Ising、筛选后准确、筛选后PV采样 | [详细说明](ATTENTION_TLM_V3_ZH.txt) | [事务调度](attention_tlm_v3.py)、[概率参考](attention_reference_v3.py)、[入口](run_attention_v3.py) | [2K/8K结果](results/attention_v3_verified_20261015/RESULTS_ZH.txt) |
| 筛选＋紧凑候选＋Ising宏模块＋V累加 v4 | [接口与边界](SCREEN_ISING_TLM_V4_ZH.txt) | [事务模型](screen_ising_tlm_v4.py)、[Ising宏](ising_macro_v4.py) | [固定/可变候选结果](results/screen_ising_v4_20261016/RESULTS_ZH.txt) |
| 多层随机源 | [设计](RNG_HIERARCHY_V1_ZH.txt) | [随机源层次](rng_hierarchy.py) | [结果目录](results/rng_hierarchy_v1/) |
| FFN本地8位随机数、64路共享 | [设计](LOCAL_SHARED_V2_ZH.txt) | [本地随机源](rng_local_shared_v2.py)、[整机调度](system_decode_local_shared_v2.py) | [18组结果](results/local_shared_v2/RESULTS_ZH.md) |
| 外存和访存调度 | [映射说明](MAPPING_OPTIMIZATION_ZH.md) | [DRAMSys](dramsys/)、[映射](mapping_decode.py) | [调度对比](results/mapping_20261015/RESULTS_ZH.md) |
| SRAM校准 v1（A～F拟合、H独立验证） | [校准报告](SRAM_CACTI_CALIBRATION_V1_RESULTS_ZH_20261016.txt)、[使用与复现](SRAM_CALIBRATION_PUBLICATION_ZH_20261016.txt) | [校准/查表接口](sram_cacti_calibration_v1.py) | [数值、系数和误差](results/sram_calibration_v1_20261016/) |
| 时序与内存调度审计 | [当前实现及下一步](MEMORY_SCHEDULING_NEXT_STEPS_ZH_20261016.txt) | DRAMSys / ZigZag / 本地事务调度的分工 | 片上bank调度是后续计划，未在本次实现 |
| SRAM参数与格式转换 | [SRAM模型](SRAM_FLEXIBLE_MODEL_ZH_20261016.txt)、[转换核算](FORMAT_CONVERSION_AUDIT_ZH_20261016.txt) | [CACTI适配](cacti_memory.py) | [CACTI结果](results/cacti_memory_20261016/) |

## 筛选和随机源的准确含义

v3/v4的max4筛选仍然是摘要评分、归一化、sigmoid和独立Bernoulli判决，没有块间Ising退火。v4可选固定预算修复是显式计费的排序/补齐，也不是耦合筛选。

v3对串行随机扫描Ising显式核算更新；v4将Ising内部随机源、状态、抑制反馈及读出包在宏级参数中，避免重复计费。v4默认用理想IID索引产生地址轨迹，不验证真实p-bit网络混合时间。Attention其他随机服务继续使用层次随机源；不只有FFN本地PRNG。

## 复现与限制

Python 3.10+；基本检查使用标准库。完整依赖和DRAMSys构建见README。旧版本的variants/local_shared_a8_64保留为历史快照；当前Attention使用目录根部的共享实现。

```sh
python architecture_tlm/checks/test_attention_v3.py
python architecture_tlm/checks/test_screen_ising_v4.py
python architecture_tlm/audit_attention_v3.py architecture_tlm/results/attention_v3_verified_20261015
python architecture_tlm/audit_screen_ising_v4.py architecture_tlm/results/screen_ising_v4_20261016
```

已保存Attention结果采用合成输入，不是新Qwen PPL或芯片实测；多个硬件成本参数未标定。此前DRAMSys结果继续保留，新增Attention默认仍为Link后端，只有指定--bridge才使用DRAMSys。公开的压缩事务轨迹仅是合成地址/事件，不包含文本、KV内容或模型权重。工艺库本体、工具安装、远程凭据和编译缓存不在发布包中。

部分结果中的机器绝对路径替换为相对引用，数值未变；发布清单记录源文件与发布文件SHA256。原始源码保持不变，当前模块源码哈希由审计核验。

发布检查：[验证记录](PUBLICATION_VALIDATION_20261016.md)。历史DRAMSys结果保留对应历史源码；没有将旧结果标注为新版重跑。

补充：[数制转换与累加 RTL](../format_conversion_rtl_20261016/README_ZH.txt)，包含已有功能验证记录，尚无工艺库 DC/PT 面积功耗结果。

SRAM校准补充：已有宏直接查库值；其他尺寸是带验证误差的探索估计。写能量尚有较大误差。未自动修改现有整机配置或重写历史Attention结果。工艺库本体不在发布包中。


## 2026-10-22 Unified complete-decode TLM v6

[Issue96 implementation, operator contracts and limits](unified_v6/README_ZH.md). Fixed W8 / B4 / T32 / K32, current parallel sampler options and same-resource digital controls share a bounded resource/memory model. Local RNG interface has no random-stream SRAM. This is an optional new entry; it does not rewrite historical defaults, results or claim full physical PPA.


## 2026-10-22 周期/访存假设审计与非随机数字RTL（Issue107）

[完整周期/存储报告](digital_ppa_v1/CYCLES_MEMORY_AND_RTL_ZH.md)、[RTL模块索引](digital_ppa_v1/README_ZH.md)、[55nm PPA任务](digital_ppa_v1/PPA_TASK_ZH.md)。只读52冻结情景列出核等效周期，区分库/宏约束、时序代理和未展开接口；含64值B4编码、恢复、连续算术、累加、非线性候选、控制和存储外围。66功能组/12870输出及63活动预检通过，源码23e8d65，29输入blob逐字节相同。没有新TLM数值、模型PPL、DC/PT/STA、真实DRAMSys；新RTL尚未回填原TLM。随机源/随机矩阵阵列不在本包，PR105可视化仍独立待审。
