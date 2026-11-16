# EVA 和 M-ANT 的 Qwen3-4B 单步 decode 快速估算

共同条件为冻结的后训练 Qwen3-4B、batch 1、2,048 个上下文位置、36 层、一个输出 token、250 MHz、LPDDR 峰值 136.4606 GB/s 和 4 pJ/bit。采用项目封存 W8 Dense 的完整 BF16 词表头，包含 151,936 个词表输出及选择，占 6.31 ms、0.778 GB 外存流量和 2.60 mJ 片上能量。外部两种时延分别对应 80% 有效带宽下逐算子的搬运与计算重叠及串行。模型单独保留 65% 和 90% 结果。 [上一版 BitMoD/Tender 快估](QUICK_BENCHMARK_ZH.md)

| 方案 | ms/output token | 外存 GB/token | 外存 mJ/token | 片上面积证据 |
|---|---:|---:|---:|---|
| 本项目 P-bit，原生 TLM | 51.13 | 5.41 | 173.2 | 6.48 mm²，封存计价子系统 |
| 本项目 W8 + K 筛选，原生 TLM | 85.45 | 5.42 | 173.4 | 6.40 mm²，封存计价子系统 |
| EVA W2 | 50.7–61.8 | 2.00 | 63.9 | 1.414 mm²，原报 28 nm／500 MHz |
| EVA W3 | 67.0–82.3 | 2.45 | 78.5 | 同一阵列 |
| EVA W4 | 83.3–102.8 | 2.91 | 93.1 | 同一阵列 |
| M-ANT W4A8KV4，tile 每 4 拍 | 37.1–56.0 | 2.85 | 91.1 | 4.587 mm²，原报 28 nm 模块小计 |
| M-ANT W4A8KV4，tile 每 8 拍 | 66.6–85.6 | 2.85 | 91.1 | 同一阵列 |

EVA 的线性层采用作者 32×8 FP16 阵列、4×32 输入归约和 8 维码本。保留首块的码本与激活加载、片上码本点积与归约重叠、索引传输、K 分块中间量重读写。在 252 个线性项上，以作者原始 FC 函数逐项核对计算周期、外存读写字节和重叠公式，覆盖 W2/W3/W4 共 756 项。整步另用共同 BF16 GQA 的 256 路数字估算、向量操作和全词表 head。原作者指标中的 native DDR4 功耗和 500 MHz PPA 未直接移到 LPDDR 结果。 [EVA 原文 §VI](https://arxiv.org/html/2605.24144#S6) · [作者 FC 函数](https://github.com/dbw6/Eva/blob/main/simulator/methods/vqarray.py#L60-L208) · [原报面积构成](https://github.com/dbw6/Eva/blob/main/simulator/configs/hardware.yaml)

M-ANT 使用论文的 weight-stationary W4A8 64×32 逻辑 tile，QK/PV 假设共用 A8×KV4 路径并在一个 KV tile 上复用四个查询。每 64 个元素按 16-bit scale 和 8-bit 系数估算元数据。tile 发射间隔 II=4/8 拍对应约 **70/35 GB/s** 的片上权重服务能力，是调度情景。作者没有公布 Qwen batch 1 的实际发射间隔或 SRAM 供给，所以 JSON 另保留 II=2/16 的敏感性。暂按 KV 全部为量化后表示，动态 V 的 INT8 窗口和周期性再打包没有展开。Table IV 的 4.587 mm² 是 PE、RQU、512 KB 缓冲、向量和累加模块相加。 [M-ANT §IV–VII](https://arxiv.org/html/2502.18755v1#S6)

平台对齐的是模型形状、计算频率和外存价格。两套外部模型采用各自低位宽，Qwen3-4B 的实际量化质量、共同工艺库下的 STA、全片面积与片上能量仍待确认。JSON 的已计能量小计只含外存和共享词表头，适合查账；正文表使用明确可复算的外存能量。

## EdgeCIM 和 CELLA 的原有工作点

| 论文 | 工作点 | 指标边界 |
|---|---|---|
| EdgeCIM，IEEE TCAD 2026 | Qwen3-4B INT4/INT8，B1、128 输入＋128 生成，65 nm、LPDDR5X 273 GB/s。 | Fig. 12 有本模型数据；正文 139.3 token/s 对应 Llama-3.2-3B INT4。136.5 GB/s 的 1.45× 时延变化是论文带宽实验结果，未移用到 Qwen3-4B B1/2K。 [原文 §V](https://arxiv.org/html/2604.11512v2#S5) |
| CELLA，VLSI 2025 | 28 nm，原报 **31.32 token/s**，倒数 **31.93 ms/output token**。 | 1.78 ms 是另报的 prefill 响应。公开摘要未披露该速度点对应的外存带宽及能量。 [CELLA 论文](https://doi.org/10.23919/VLSITechnologyandCir65189.2025.11075101) |

项目既有 EdgeCIM 式数字 Gate/Up 同预算对照可保留为单层消融。相同 Qwen3-4B、B1/2K 和 28HPC+/250 MHz 解析外存条件下，P-CIM 与替换数字 GU 分别为 **1.095 与 1.124 ms/层**，含外存估计 **4.466 与 4.468 mJ/层**。此运行只替换 Gate/Up，保留概率 Down，数据边界为单个 decoder layer。

## 复算

```powershell
python architecture_tlm/benchmark_inventory_20261029/aligned_qwen4b_20261116/estimate_eva_mant.py --summary <frozen-SUMMARY.json> --out EVA_MANT_ESTIMATE.json
```

在 Windows CPU、Python 3.8.1 运行七种情景，估算器本体不到 0.1 秒。复算记录在 [EVA_MANT_ESTIMATE.json](EVA_MANT_ESTIMATE.json)，含模型 revision、封存文件和作者源 Git blob 校验值。该实验使用形状与参数流量，未读取模型权重或语料，语料哈希、种子及 PPL 不适用。 [封存摘要和模型尺寸来源](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/tree/01a2fb1d13018d381e012630ea1be442e85bdd26/architecture_tlm/process_28nm)
