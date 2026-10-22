# ASIC 资源计划首轮优化（Issue117）

根据 Issue112 的资源计划，在已集成 `46804fb3a1c50b29a19a7d0a3da6bb8f8b59af7d` 上新增独立分析与搜索入口。沿用真实有限随机服务、原 Link 窗口排空后端和 SRAM 描述符调度。没有修改 unified_v6、历史默认或 52＋40 项原件；Issue116 的周期级后端由原任务继续。

本目录交付 P0 资源/缺项账本、条件下界及首轮共享候选搜索工具。完整 ASIC 面积、J/token 和面积锚点 A0 仍为 null，不能做完整同总面积排名。

## 工具与比较边界

- `ledger.py`：输入必须与已执行结果的 config/model 完全一致；区分逻辑容量、整组宏的物理容量、SRAM 内部区域、未落实的 SC 局部状态及接口。宏面积、随机端点面积只是局部锚点。
- `lower_bounds()`：物理字节带宽界、原 Link 最少窗口界、已知完整 descriptor/window 服务时间、固定资源 busy 分开；跨资源取 max。busy、等待和墙钟不相加，固定 busy 的界不适用于改变服务合同后的架构。
- `search.py`：16 个共同候选，BF16准确、W8数字准确、SC准确、SC筛选/PV均可执行；2K/8K、batch1、B4/T32/K32、核心100MHz、SRAM80MHz。限制物理宏容量、bank带宽、Arena区域、SC权重slot及配置字段。
- `ReceiptDecode` 只观察现有 `route`/`sample_row` 返回值，保存全部 query 候选绝对 token ID 和抽样绝对 token ID 的摘要，不改变执行。相同 seed 不保证不同资源配置下的随机输出相同；结果同时记录源输出与地址摘要。
- `summarize.py`：核验旧档 manifest，并仅汇总有完整 manifest/receipt 的新执行；保存账本、条件下界、公平候选集、最短条件时间及三seed统计。速度最优仅指本轮有界候选，不能称全局最优。

所有结果属于合成事务 TLM。FFN 数值张量未做模型推理；没有新 PPL、质量验收、STA、布局布线或 DRAMSys/DRAMPower。W8仅替换FFN权重，其他投影/lm_head仍为BF16。旧40项的集成随机源采用q/256响应，不继承理想源完整模型质量。

## 候选与阶段

同硬件映射候选 `mapped_1m` 在1MiB、原16bank/16GB/s/512MAC/64vector/8SC下，将两个权重slot各增至256KiB并将Attention tile设为256。容量only 2/4/8MiB保留原映射，检查额外容量是否实际有收益。其他候选调整缓冲、32/64bank与匹配fabric、DRAM带宽/在途窗口、数字和SC并行度，额外物理接口/互连成本未标定，不能算免费扩容。

第一阶段：全部16候选 × 4方法 × 2上下文，seed0粗筛，128项。第二阶段：基线、同硬件映射及粗筛代表点采用0/1/2三seed；同一候选对四种方法均开放。三seed只检查TLM随机地址/时间稳定性，不是模型质量证明。

权重chunk增大主要改变普通矩阵行分组；SC仍按64×64、有限engine波次供数，不能假定所有方法获得同等收益。vector128是通用向量资源加倍的配置假设，不是已实现的专用恢复器。当前增容没有新跨token驻留/KV缓存策略；该部分仍待后续实现。

## 复现

先提交执行代码，所有输出使用新目录；模型/数据/分词器字段不适用，因为没有运行模型或文本语料。

```sh
python -m unittest architecture_tlm.resource_optimization_v1.test_ledger architecture_tlm.resource_optimization_v1.test_search
python -m architecture_tlm.resource_optimization_v1.summarize p0 --output NEW_P0
python -m architecture_tlm.resource_optimization_v1.search --candidates all --methods bf16_exact w8_exact sc_exact sc_screen_pv --contexts 2048 8192 --seeds 0 --max-cases 128 --output NEW_COARSE
python -m architecture_tlm.resource_optimization_v1.summarize search --inputs NEW_COARSE --output NEW_ANALYSIS
```

`--resume` 仅接受原 manifest、执行提交及逐文件 SHA 一致的目录。输出文件和回执不可覆盖。最终执行版本、结果数量、独立审阅及发布状态见结果报告和 `work/amlink1219/117/`。
