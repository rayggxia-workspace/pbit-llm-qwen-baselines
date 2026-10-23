# ASIC 资源计划首轮优化（Issue117）

根据 Issue112 的资源计划，在已集成 `46804fb3a1c50b29a19a7d0a3da6bb8f8b59af7d` 上新增独立分析与搜索入口。沿用真实有限随机服务、原 Link 窗口排空后端和 SRAM 描述符调度。没有修改 unified_v6、历史默认或 52＋40 项原件；Issue116 的周期级后端由原任务继续。

本目录已完成 P0 资源/缺项账本、条件下界及 **208项完整decode TLM执行**：128项共同候选粗筛、64项预声明代表点补充、16项vector128跟进。五个代表点均覆盖四方法、2K/8K和seed0/1/2；没有剩余运行或待补case。完整结果见 [RESULTS_ZH.md](RESULTS_ZH.md)，机器汇总和独立验收见 [SUMMARY.json](results/analysis_20261023/SUMMARY.json) 与 [VALIDATION.json](results/analysis_20261023/VALIDATION.json)。

当前映射只扩2/4/8MiB容量没有时延收益；同1MiB重新分块带来小幅改善。vector128下SC筛选/PV的三seed均值，在8K比同配置W8数字准确路径快 **7.543849%**，在2K仍慢 **4.166733%**。这说明恢复资源和上下文长度会改变条件时延比较，不能宣布SC普遍更优。完整ASIC面积、J/token和面积锚点A0仍为null，不能做完整同总面积排名。

## 工具与比较边界

- `ledger.py`：输入必须与已执行结果的 config/model 完全一致；区分逻辑容量、整组宏的物理容量、SRAM 内部区域、未落实的 SC 局部状态及接口。宏面积、随机端点面积只是局部锚点。
- `lower_bounds()`：物理字节带宽界、原 Link 最少窗口界、已知完整 descriptor/window 服务时间、固定资源 busy 分开；跨资源取 max。busy、等待和墙钟不相加，固定 busy 的界不适用于改变服务合同后的架构。
- `search.py`：16 个共同候选，BF16准确、W8数字准确、SC准确、SC筛选/PV均可执行；2K/8K、batch1、B4/T32/K32、核心100MHz、SRAM80MHz。限制物理宏容量、bank带宽、Arena区域、SC权重slot及配置字段。
- `ReceiptDecode` 只观察现有 `route`/`sample_row` 返回值，保存全部 query 候选绝对 token ID 和抽样绝对 token ID 的摘要，不改变执行。相同 seed 不保证不同资源配置下的随机输出相同；结果同时记录源输出与地址摘要。
- `summarize.py`：核验旧档 manifest，并仅汇总有完整 manifest/receipt 的新执行；保存账本、条件下界、公平候选集、最短条件时间及三seed统计。速度最优仅指本轮有界候选，不能称全局最优。

所有结果属于合成事务 TLM。FFN 数值张量未做模型推理；没有新 PPL、质量验收、STA、布局布线或 DRAMSys/DRAMPower。W8仅替换FFN权重，其他投影/lm_head仍为BF16。旧40项的集成随机源采用q/256响应，不继承理想源完整模型质量。

## 候选与阶段

同硬件映射候选 `mapped_1m` 在1MiB、原16bank/16GB/s/512MAC/64vector/8SC下，将两个权重slot各增至256KiB并将Attention tile设为256。容量only 2/4/8MiB保留原映射，检查额外容量是否实际有收益。其他候选调整缓冲、32/64bank与匹配fabric、DRAM带宽/在途窗口、数字和SC并行度，额外物理接口/互连成本未标定，不能算免费扩容。

第一阶段完成全部16候选 × 4方法 × 2上下文、seed0粗筛，共128项。第二阶段按预声明选取baseline_1m、mapped_1m、balanced_2m和wide_4m，补seed1/2共64项，seed0复用粗筛。第三阶段由vector_128的8K正向时延结果触发，补四方法、两上下文的seed1/2共16项；选择记录见任务目录的CONFIRMATION_SELECTION.json和CONFIRMATION_EXTENSION.json。三seed只检查TLM随机地址/时间稳定性；第三阶段明确为看过seed0后的跟进，不是盲测质量证明。

权重chunk增大主要改变普通矩阵行分组；SC仍按64×64、有限engine波次供数，不能假定所有方法获得同等收益。vector128是通用向量资源加倍的配置假设，不是已实现的专用恢复器。当前增容没有新跨token驻留/KV缓存策略；该部分仍待后续实现。

## 执行版本、验证与协作

粗筛执行提交为`44dbbbdbc2720963b2b24bf03cdf7582a2d97075`，首批补充为`315862412e15695c3fa21e6c573d9e5f3547e70d`，vector128跟进为`b1b4d183678e25f24b7b37c273fcb3f61c37483b`。十份EXECUTION清单的数值/调度源集合SHA-256全部为`cc1568efcd6cc8d192235271b16a7f20f216abb8395b99ca48d7bda3cbc5fb80`；提交差异是文档/结果或后处理更新，不是运行时模型变更。

71项机制/单元测试通过（28新增＋43原v6），旧52＋40情景的145payload SHA保持一致；verify.py独立验收208项完整键集合、源/配置/receipt散列、336query覆盖、相位/资源/容量守恒、24容量only配对及7个新基线锚点。数值与图表属于部分宏标定的条件估计，已按`CALIBRATED_ESTIMATE`登记到`digital_circuit_simulation_registry/records/asic-resource-117-20261023.json`；schema check/render及8项台账测试通过。历史指定阅读镜像路径在本机不存在，未同步；workspace正式版本随本PR交付。

成果通过[PR119](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/119)整理最终交付，待审、未合并；精确远端head及阶段见`work/amlink1219/117/PUBLICATION.json`。Projects缺`read:project`，看板同步待补。并行[PR120 / Issue118](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/120)的FFN供数/局部状态合同尚待审、未纳入本轮；后续对接其接口及Issue116周期后端，不重复其实现。

## 复现与独立核验

在仓库根目录执行以下命令。汇总和验收仅读取已保存结果，无需重跑208项；`NEW_ANALYSIS`必须是不存在的新目录，保留原件。模型/数据/分词器字段不适用，因为没有运行模型或文本语料。

```sh
python -X utf8 -m unittest architecture_tlm.resource_optimization_v1.test_ledger architecture_tlm.resource_optimization_v1.test_search architecture_tlm.unified_v6.test_model architecture_tlm.unified_v6.test_rng_integrated architecture_tlm.unified_v6.test_rng_interface
python -X utf8 -m architecture_tlm.resource_optimization_v1.summarize search --inputs architecture_tlm/resource_optimization_v1/results/coarse_20261023 architecture_tlm/resource_optimization_v1/results/confirmation_20261023 architecture_tlm/resource_optimization_v1/results/vector_confirmation_20261023 --output NEW_ANALYSIS
python -X utf8 -m architecture_tlm.resource_optimization_v1.verify --inputs architecture_tlm/resource_optimization_v1/results/coarse_20261023 architecture_tlm/resource_optimization_v1/results/confirmation_20261023 architecture_tlm/resource_optimization_v1/results/vector_confirmation_20261023 --expected 208 --output NEW_ANALYSIS/VALIDATION.json
```

如需另行复跑，先提交执行代码，并为每个阶段使用全新输出目录；下面是完整208项矩阵的顺序入口。新执行会记录当前提交，不能冒充上述冻结原件。

```sh
python -m architecture_tlm.resource_optimization_v1.summarize p0 --output NEW_P0
python -m architecture_tlm.resource_optimization_v1.search --candidates all --methods bf16_exact w8_exact sc_exact sc_screen_pv --contexts 2048 8192 --seeds 0 --max-cases 128 --output NEW_COARSE
python -m architecture_tlm.resource_optimization_v1.search --candidates baseline_1m mapped_1m balanced_2m wide_4m --methods bf16_exact w8_exact sc_exact sc_screen_pv --contexts 2048 8192 --seeds 1 2 --max-cases 64 --output NEW_CONFIRMATION
python -m architecture_tlm.resource_optimization_v1.search --candidates vector_128 --methods bf16_exact w8_exact sc_exact sc_screen_pv --contexts 2048 8192 --seeds 1 2 --max-cases 16 --output NEW_VECTOR_CONFIRMATION
```

`--resume`仅接受原manifest、执行提交及逐文件SHA一致的目录。输出文件和回执不可覆盖。本轮无待恢复运行；后续工作优先落实恢复latency/II、SC供数/保持与局部计数物理归属，再比较真实驻留和持续在途DRAM调度。
