# Qwen3-4B 单步 decode 快速 benchmark

共同任务为冻结的 Qwen3-4B 后训练版、batch 1、2,048 个上下文位置、36 层、一个输出 token、全词表 BF16 head。外部两种架构按 250 MHz 和 LPDDR 标称 136.46 GB/s 计算。表里的两个时延端点分别对应算子内完全重叠和完全串行，均以 80% 有效带宽为例。项目内四行来自封存的原生 LPDDR TLM，只有外部行用本轮快速模型。 [项目封存结果](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/01a2fb1d13018d381e012630ea1be442e85bdd26/architecture_tlm/process_28nm/results_20261111/REPORT_ZH.md)

| 方案 | 证据及设定 | ms/token | 外存 GB/token | 外存 mJ/token | 片上 mJ/token | 含外存 mJ/token | 片上 mm² |
|---|---|---:|---:|---:|---:|---:|---:|
| 本项目 P-bit | 封存 TLM | 51.13 | 5.41 | 173.2 | 15.27 | 188.43 总计 | 6.48 子系统 |
| 本项目 W8 + K 筛选 | 封存 TLM | 85.45 | 5.42 | 173.4 | 19.81 | 193.17 总计 | 6.40 子系统 |
| 本项目 W8 Dense | 封存 TLM | 95.00 | 5.66 | 181.1 | 22.91 | 203.97 总计 | 6.37 子系统 |
| 本项目 BF16 Dense | 封存 TLM | 111.12 | 8.35 | 267.1 | 32.09 | 299.20 总计 | 6.45 子系统 |
| BitMoD W6 | 作者 64×16 阵列周期 + 解析估计 | 187–214 | 3.68 | 117.8 | 45 小计 | 163 小计 | 3.8–4.6 阵列＋SRAM |
| BitMoD W3 | 作者 64×16 阵列周期 + 解析估计 | 130–144 | 2.32 | 74.2 | 31 小计 | 106 小计 | 3.8–4.6 阵列＋SRAM |
| Tender W4 | 原文 64×64 output-stationary，B1 映射估计 | 248–268 | 2.95 | 94.5 | — | — | 3.98 原报，28 nm、1 GHz |

BitMoD 作者模拟器的阵列周期在本轮重新执行。原 64×16 网格的全矩阵合计复现 49,495,296 和 33,783,296 周期。整步估算替换为项目已有的 BF16 head 阶段，以保留 151,936 个词表输出和选择，统一计入约 6.31 ms、0.778 GB 外存传输和 2.60 mJ 片上能量。Tender 依据论文的 output-stationary 数据流，B1 占一个输入行，每拍推进至多 64 路输出的内积。QK/PV 采用共同 256 路 BF16 数字路径的估算。两家均补上共同的向量操作周期估计。 [BitMoD 作者代码](https://github.com/abdelfattah-lab/BitMoD-HPCA-25/tree/e445a5f31100a5057b4c5c4373da223ce95f1c3b/bitmod_sim) · [Tender §IV、§V](https://arxiv.org/html/2406.12930v1#S5)

## 结论对映射有多敏感

同样 1,024 个 PE，BitMoD 作者代码改用 **256×4** 网格后，W6 是 **54–80 ms/token**，W3 是 **39–53 ms/token**。W3 的外存能量仍约 74 mJ/token。这个情景需要更宽的权重 SRAM 供给，权重端口的名义读位宽是原排列的四倍。面积、布线、端口能否达到尚未核实。原 64×16 与这个情景都说明计算利用率足以改变排序。

## 计价口径

- BitMoD 的 W6/W3 按作者包括分组开销的 6.0625/3.0625 bit 和 KV8。Tender 示例为 W4 加每 128 权重暂计 16-bit 元数据和 BF16 KV。矩阵权重、完整 GQA KV、head 各计一次传输，片上保留算子间中间量，另计单 token KV 更新和小参数。外存能量以 4 pJ/bit 计价。65%、80%、90% 有效带宽数字见 JSON，80% 为计算情景。外部总线排队、突发细节与量化后 Qwen3-4B 质量未验证。
- BitMoD 片上小计含作者 PE 活动模型、借用项目 28 nm SRAM 读写价、共同 BF16 head，控制、互连、向量单元与其余常驻功耗未计。面积小计用原论文 16 个 PE tile 和项目 28 nm 4–8 KiB SRAM 宏代价估算作者两个 512 KiB 缓冲的面积，端口和外围适配另需证据。Tender 面积直接引用原文 Table V。两篇均无本轮完整同库 STA 或整机 PPA。 [BitMoD Table X](https://arxiv.org/html/2411.11745v1#S5.SS3) · [Tender Table V](https://arxiv.org/html/2406.12930v1#S5.SS3)

## 复算

在仓库根运行以下命令。BitMoD 作者输入提交、模型 revision 与参考文件 SHA-256 记录在 [QUICK_BENCHMARK.json](QUICK_BENCHMARK.json)。封存摘要与模型索引取自 [项目证据提交](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/tree/01a2fb1d13018d381e012630ea1be442e85bdd26/architecture_tlm/process_28nm)。Windows CPU 上 Python 3.8.1、PyTorch 2.4.1 CPU、NumPy 1.24.4 的两次重跑各约 3 秒，JSON 原字节一致。此实验使用形状和流量，未加载权重或语料，因此 PPL、语料哈希与训练种子不适用。

```powershell
python architecture_tlm/benchmark_inventory_20261029/aligned_qwen4b_20261116/quick_benchmark.py --artifact <author-checkout> --summary <frozen-SUMMARY.json> --out QUICK_BENCHMARK.json
```
