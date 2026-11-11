# 28nm、250MHz 完整 TLM 结果

北京时间 2026-11-11 11:03:50 复核。新增 15 项全部通过，Qwen 数字 3/3，Llama 6/6，DeepSeek 6/6。最后两项 DeepSeek 概率 seed17 与 BF16 稠密分别于 02:05:57、03:10:26 完成。15 项 Slurm 均为 COMPLETED/0:0，冻结源码、配置、封存原件 SHA-256、完整层覆盖、原生后端、完整 lm_head 配置及能量加和通过。表中 Qwen 概率三 seed 为此前独立完成的参照。

同一 28nm TT 0.9V 25°C、250MHz、B1、2048 上下文、832KiB SRAM、LPDDR 和 DMA 口径。片上数字方案面积约 6.37–6.45mm²，概率版 6.48mm²。外存能量按 4pJ/bit 估计。6.6、8pJ/bit 及逐 seed 原始结果见 SUMMARY.json 和封存账本。

|模型|方案|含 lm_head 时间 ms/token|片上 mJ/token|含外存 mJ/token|覆盖面积 mm²|
|---|---|---:|---:|---:|---:|
|Qwen3-4B|概率版（3 seed 均值）|51.133|15.268|188.432|6.480|
|Qwen3-4B|BF16 稠密|111.120|32.092|299.199|6.450|
|Qwen3-4B|W8 稠密|94.999|22.905|203.966|6.370|
|Qwen3-4B|W8＋SparQ、准确 PV|85.450|19.808|193.167|6.399|
|Llama-3.2-3B-Instruct|概率版（3 seed 均值）|43.929|12.414|151.771|6.480|
|Llama-3.2-3B-Instruct|BF16 稠密|86.103|25.064|238.200|6.450|
|Llama-3.2-3B-Instruct|W8 稠密|74.136|17.874|163.381|6.370|
|Llama-3.2-3B-Instruct|W8＋SparQ、准确 PV|66.688|15.771|155.288|6.399|
|DeepSeek-LLM-7B-Chat|概率版（3 seed 均值）|98.985|26.527|317.782|6.480|
|DeepSeek-LLM-7B-Chat|BF16 稠密|207.008|53.777|501.426|6.450|
|DeepSeek-LLM-7B-Chat|W8 稠密|180.594|39.796|357.620|6.370|
|DeepSeek-LLM-7B-Chat|W8＋SparQ、准确 PV|149.438|33.435|325.590|6.399|

DeepSeek 概率版相对 W8＋SparQ、准确 PV 加速 1.51×，片上能量降低 20.7%，含外存能量降低 2.4%。概率版面积高 1.26%。三 seed 时延范围为 98.966508–99.006260ms/token。

## 不含 lm_head 的同次执行前缀

时间和能量取到 final_norm，使用同一常驻硬件面积。

|模型|方案|时间 ms/token|片上 mJ/token|含外存 mJ/token|
|---|---|---:|---:|---:|
|Qwen3-4B|概率版（3 seed 均值）|43.594|12.623|160.897|
|Qwen3-4B|BF16 稠密|102.533|29.402|271.615|
|Qwen3-4B|W8 稠密|88.689|20.307|176.474|
|Qwen3-4B|W8＋SparQ、准确 PV|79.140|17.209|165.675|
|Llama-3.2-3B-Instruct|概率版（3 seed 均值）|34.838|9.664|123.807|
|Llama-3.2-3B-Instruct|BF16 稠密|77.405|22.339|210.259|
|Llama-3.2-3B-Instruct|W8 稠密|66.378|15.178|135.469|
|Llama-3.2-3B-Instruct|W8＋SparQ、准确 PV|58.930|13.074|127.375|
|DeepSeek-LLM-7B-Chat|概率版（3 seed 均值）|88.924|23.580|287.994|
|DeepSeek-LLM-7B-Chat|BF16 稠密|197.756|50.876|471.681|
|DeepSeek-LLM-7B-Chat|W8 稠密|171.373|36.880|327.861|
|DeepSeek-LLM-7B-Chat|W8＋SparQ、准确 PV|140.215|30.519|295.831|

[逐项核验及原件 SHA](SUMMARY.json) · [Slurm 与封存核验回执](../../../work/rayggxia/225/tlm_status_20261111/RECHECK_REMOTE_20261111.json)

本表采用代表性事务的条件 TLM 估计。共享资源、gross 与 idle 沿冻结账本计费。W8 数字对照采用既有混合数制。各项未计价边界见 SUMMARY.json 中的 unpriced 字段。
