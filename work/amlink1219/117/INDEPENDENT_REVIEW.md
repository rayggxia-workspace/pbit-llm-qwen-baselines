# Issue117 独立审阅记录

日期：2026-10-23（Asia/Shanghai）。审阅者：本任务独立审阅子代理。结论：**当前证据与声明范围内未发现阻断交付的问题。** 此记录不代表PR已经合并，也不代表物理ASIC或模型质量验收。

## 实际执行的检查

- 阅读用户提供的ASIC资源计划，以及新模块 `ledger.py`、`search.py`、`summarize.py`、`verify.py`、`report.py`、`plot.py` 与新增机制测试源码；对照原始 `unified_v6` 的SRAM、DRAM、SC计数/恢复、随机服务和调度实现。
- 独立读取十份执行清单。粗筛执行 `44dbbbdbc2720963b2b24bf03cdf7582a2d97075`、首轮补充 `315862412e15695c3fa21e6c573d9e5f3547e70d`、vector128跟进 `b1b4d183678e25f24b7b37c273fcb3f61c37483b`；全部数值/调度源集合SHA-256为 `cc1568efcd6cc8d192235271b16a7f20f216abb8395b99ca48d7bda3cbc5fb80`。
- 对最终SUMMARY的208行逐一回读case和receipt，独立计算原case文件SHA-256，核对SUMMARY/receipt散列、候选/方法/上下文/seed标识及TPOT，全部一致。
- 从SUMMARY原始行独立重算全部128个聚合组的均值与样本标准差，与聚合表一致；检查容差为绝对误差1e-10。
- 对六个旧结果目录的145个manifest payload独立核对文件长度与SHA-256，全部一致。它们对应52个旧情景与40个已集成随机服务情景；没有改写原件。
- 阅读最终 `VALIDATION.json` 的208项PASS结果，并审阅验收器关于完整键集合、336个query唯一覆盖、计数、相位/资源/容量守恒、24容量对照、七个基线锚点和执行源一致性的实现。未另行重跑该验收器、单元测试或TLM仿真。
- 目视检查三张PNG。SRAM面积散点和下界图范围标注明确；latency图的标题/图例遮挡问题修复后再次目视确认，标题、图例、坐标与三seed说明均可读。

## 核验后的关键解释

- vector128的8K SC筛选/PV三seed时间为173.92807、173.90432、173.89007 ms，均值173.907486667 ms；同配置W8为188.09726 ms，条件时延降低7.543849%。2K SC筛选/PV均值169.934753333 ms，相对同配置W8的163.13726 ms仍慢4.166733%。
- 六个vector128 SC筛选/PV情景的完整候选和采样地址摘要均与同seed基线一致。此证据只支持本次合成事务路径配对；不能证明真实LLM有限精度张量结果或PPL相同。
- vector128是整个共享向量资源扩展；恢复代理服务减少27.57888 ms，但其他向量阶段与调度也会改变。最终报告已删除“整机收益必小于该恢复服务减少量”的错误解释。
- 额外16项vector128执行明确标注为seed0粗筛正向结果触发的跟进；没有包装成预声明盲测或质量验收。其余四个代表点的64项补充保持原预声明范围。
- 仅扩容量的24个负对照不支持“新驻留/KV缓存也无收益”；额外bank、向量、SC和外存资源仍有未标定成本。完整面积、能量和A0保持null，SRAM宏面积散点不作为完整ASIC Pareto前沿。

## 已反馈并关闭的问题

1. 修正封存Llama目录名称，使用四个实际存在的Llama结果目录。
2. 为随机路径提供完整候选/采样地址摘要，区别于含idle时间等字段的source activity摘要；加严最终完整case集合及计数检查。
3. 修正共享向量扩展的收益解释；保留8K正向与2K负向结果。
4. 修正latency图标题与图例重叠，并重新目视核验。

## 本次审阅绑定的制品

以下路径相对 `architecture_tlm/resource_optimization_v1/`。

| 制品 | SHA-256 |
|---|---|
| `results/analysis_20261023/SUMMARY.json` | `5a13597bd01fa38cad2827419958e8b3e50a69ad417f8d8b0d82d96b477a3da2` |
| `results/analysis_20261023/VALIDATION.json` | `84a4b65d736ddabb577d8112db2b0b8caf7c20f80a4da620303cd44c109e179f` |
| `RESULTS_ZH.md` | `972a0d6a1de1d4fd6de1023f867d3390dd084d451201bafcf72de094b4f53a13` |
| `figures/latency.png` | `1249ea733e5b67280abd2882539ab6d8a1cfad59cb5a7e08bcba8de303d59782` |
| `figures/partial_area.png` | `6f13cd2eb4391d3872aec26cbd0fb7270fd54f2208e81cc8202ba02453f8b325` |
| `figures/bounds.png` | `c2832bbd8b080e2bcc9035111ed5ee559c469d9cfadfd3316ab9817319adcdec` |

审阅没有重新进行网络项目状态核验、GitHub写入、模型推理、PPL、RTL/EDA/STA、真实DRAMSys或芯片测试。远端权限、发布回执、最新并行任务状态及最终后处理制品manifest由主代理负责。
