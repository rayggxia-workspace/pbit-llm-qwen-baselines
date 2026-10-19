# Llama 2 7B Base：完整 WT2 BF16 基线

Slurm **1961** 已实际完成；使用一张RTX5090、Transformers4.45.2、BF16 SDPA。模型为 `meta-llama/Llama-2-7b-hf`，官方revision `01c7f73d771dfac7d292323805ebc428287df4f9`。用户授权的ModelScope镜像文件已逐一与官方记录核验，不是Chat或量化版。

| 完整测试协议 | PPL | 计分token数 | GPU评测耗时 |
|---|---:|---:|---:|
| window=2048，stride=512 | **4.979503** | 335,686 | 114.98秒 |
| window=4096，stride=512 | **4.895831** | 335,686 | 239.90秒 |

这里是完整 `wiki.test.raw` 滑窗计分，不是固定文本后缀PPL。原始测试语料分成335,687个token，不额外添加BOS/EOS；除第一个无前文token外，每个target恰好计分一次。新窗口只计新增target，保留最后短尾。logits/target移位与分母均有检查：FP32逐token交叉熵、FP64累加，然后取平均NLL的指数。

这些耗时是整段PPL评测所花的时间，不是单token解码延迟，也没有测GPU能量。2K/4K窗口的评测协议与使用BOS、不同stride或非重叠分块的论文可能不同，不能只用模型名称直接比较PPL。

两个短提示的greedy生成检查完成；这只是运行基本检查，不是问答能力评测。`greedy_smoke.json`保留实际输出。此次未运行HellaSwag/PIQA等任务，也未评价随机FFN、稀疏Attention或Ising替换后的联合模型质量。

复现信息：

- 源码提交：`9ee1ab47d0317430212364e75adb78abec9797fb`，不可变服务器快照 `baseline_9ee1ab47d031/`；完整命令见 `command.json`。
- 语料SHA-256：`173c87a53759e0201f33e0ccf978e510c2042d7f2cb78229d9a50d79b9e7dd08`。
- 全部token IDs的SHA-256：`d47afcd2762c6a3e70f50c5b7de0e4ccad565d812aee21772b7cd276b7b8626c`（little-endian int64）。
- 模型/分词器大小及SHA：`identity.json`；环境：`environment.json`；协议：`protocol.json`；原始摘要：`summary.json`。
- `windows_2048.jsonl`与`windows_4096.jsonl`逐窗口保存target区间、NLL及累计计数，可独立核对覆盖和总NLL。
- 原始12个成果文件均按 `ARTIFACT_MANIFEST.json`逐字节核验，原文件没有换行改写；本中文说明及.gitattributes是另加的发布文件。

服务器原始位置：`/home/Hongjie_Zeng/projects/pbit-llama2-7b-20261017-issue14/outputs/bf16_baseline/`。模型权重、原始语料、长QK轨迹不在Git中。TLM与硬件情景结果在独立的 `architecture_tlm/llama2_7b/` 目录。
