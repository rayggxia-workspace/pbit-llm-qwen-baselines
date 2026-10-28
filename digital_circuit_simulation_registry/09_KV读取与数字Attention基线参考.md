# KV读取与经典数字Attention基线参考（2026-10-28）

Issue198 / 草稿PR199；文献、现有代码审计及旧轨迹地址推导。本次无新物理仿真/模型/DRAMSys运行，不新增台账run，不改已有功耗系数。这里的字节数和下界没有对应的新PPA，不能填成实测能耗或周期。

## 先锁定这些条件

1. K/V的独立布局、行/页尺寸、位宽、对齐和实际burst粒度。
2. GQA各头候选/采样地址的并集，以及有限缓冲下是否重复取同一burst。
3. SRAM驻留、KV追加、页表/SG描述符、读写/广播和回压；摘要cold-build与warm维护分别收费。
4. 相同后训练模型质量所需的S；旧单头S128不等于真实GQA或同质量S512。

## 全量KV扫描的形状账

沿当前TLM的后训练Qwen3-4B形状：36层、32Q/8KV头、d128、BF16，L包含当前token。没有跨token片存命中时，每层有效数据为`2×L×8×128×2B`，不含传输放大/页表/追加。

| 上下文 | 每层KV | 36层合计/生成token |
|---:|---:|---:|
| 512 | 2MiB | 72MiB |
| 2048 | 8MiB | 288MiB |
| 8192 | 32MiB | 1152MiB |

2K时，仅按29.851GB/s和256GB/s分别除字节，裸传输下界约10.117ms与1.180ms；512 MAC/拍、100MHz理想QK+PV下界约11.796ms。只是资源假设下的算术下界，不能相加，不能当实测周期或总Attention时延；FP32 PV/Softmax/片存/控制另计。KV也不自动超过整机稠密权重流量。

## 已核实的布局风险

同一旧2K/d128、每头S128轨迹、三个seed的P0，连续行V读取32KiB；映射为vLLM v0.18.0文档的一种V通道交错页ABI，按page16、64B传输粒度及理想burst合并算为456KiB。P4则约23.75KiB变为125.333KiB。不是实测GPU数据，不代表所有vLLM后端；是同轨迹地址几何敏感性，也没有满足同质量GQA比较。

## 数字对手应采用的结构

完整稠密QK、分块在线Softmax/PV、GQA组内KV一次加载共享、有限双缓冲；不物化完整概率矩阵。长KV可研究split-KV加partial-output/LSE合并，但必须计并行资源/合并缓冲。再用相同筛选集合的候选数字精确P1、优化数字CDF采样P2隔离Ising采样收益；KV量化另作为需重新验证质量和反量化成本的数字候选。

## 证据入口

- [完整调研与可验收步骤](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/task/198-attention-compare/architecture_tlm/attention_compare_20261027/KV_DIGITAL_BASELINE_ZH_20261028.md)。准确发布SHA看Issue198及work/rayggxia/198/KV_BASELINE_PUBLICATION.json。
- [地址审计JSON](references/kv_baseline_20261028/KV_READ_AUDIT.json)：100个核验、18旧单头案例/输入SHA、shape与纯解析GQA示例。
- [逐seed布局CSV](references/kv_baseline_20261028/SINGLE_HEAD_LAYOUT_REPLAY.csv)。本目录两份数据从正式attention_compare结果同字节同步，不独立修改。
- [FlashAttention](https://arxiv.org/abs/2205.14135v2)、[Flash-Decoding作者说明](https://princeton-nlp.github.io/flash-decoding/)、[FlashInfer v1，GQA fusion](https://arxiv.org/html/2501.01005v1)、[FlashInfer布局文档](https://docs.flashinfer.ai/tutorials/kv_layout.html)、[锁定的vLLM ABI](https://github.com/vllm-project/vllm/blob/bcf2be96120005e9aea171927f85055a6a5c0cf6/docs/design/paged_attention.md)。不将GPU数据直接套为55nm ASIC周期/面积。

下一步先完成真实2K、一个KV组4个Q头的D0/P1/P2/P4共同字节/周期/质量表，再扩展完整8KV组36层；本次尚未启动后续服务器实验。
