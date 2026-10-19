# 实际使用的是哪个模型

已有 `llama7b/` 是 `huggyllama/llama-7b` 转换的 **LLaMA-1 7B**；本目录是 **Llama 2 7B Base**，官方身份 `meta-llama/Llama-2-7b-hf`。不使用 Chat 或量化发布版本。

| 项目 | LLaMA-1 7B | 本次 Llama 2 7B |
|---|---:|---:|
| 层数 | 32 | 32 |
| 隐藏维度 / FFN中间维度 | 4096 / 11008 | 相同 |
| Q头 / KV头 | 32 / 32 | 相同，仍为MHA |
| 每头维度 / 词表 | 128 / 32000 | 相同 |
| 参数量 | 6,738,415,616 | 相同 |
| FFN / Attention投影 / 词表嵌入与读出参数 | 4,328,521,728 / 2,147,483,648 / 262,144,000 | 相同；另有266,240个norm参数 |
| FFN / 归一化 / 位置编码 | SwiGLU / RMSNorm / RoPE | 相同 |
| RMSNorm epsilon | 1e-6 | **1e-5** |
| 原生上下文 | 2048 | **4096** |
| RoPE theta | 10000 | 10000，无RoPE缩放 |
| embedding与lm_head | 独立 | 独立 |
| 权重与训练结果 | LLaMA-1 | **不同，必须重新运行** |

因此，“主要矩阵形状一样”是正确的，但不能只替换模型名称。已有有限SRAM、DRAMSys、随机FFN和稀疏Attention引擎可直接复用；筛选率、V去重率、保留mass和PPL依赖新权重，必须使用真实Llama2基线与新轨迹。

来源：[Llama 2原论文Table1及A.2.1](https://arxiv.org/abs/2307.09288)、[2023官方推理代码](https://github.com/meta-llama/llama/blob/llama_v2/llama/model.py)。具体数值以本次核验的 `configs/model_identity.json` 和下载的官方同字节config为准，不用其他版本的默认配置覆盖checkpoint。

本次用户授权使用镜像。上游revision为 `01c7f73d771dfac7d292323805ebc428287df4f9`；传输来自ModelScope `shakechen/Llama-2-7b-hf` @`e61a2c602c83286a3ffbadaa29c20ad1160a8c4e`。2份safetensors及tokenizer.model的SHA-256与上游LFS记录相同；其余小文件Git blob也全部与上游相同。11个实际下载文件的大小、SHA和匹配结果均保存，不将“镜像同名”作为核验依据。

分词器SentencePiece模型与LLaMA-1相同，配置文件仍分别核验。此次捕获使用同一原始WT2字节、`add_special_tokens=False`、起始token201979；前2048个token IDs的SHA为 `5c208664955a0c5e4d2fb19d1a018559bf02eccd36d6aafb2a77b0e5d8cabca8`，与旧LLaMA-1捕获完全一致。4K继续延长同一窗口；不把旧LLaMA-1外推到4K。

本次完整WT2滑窗PPL仅评价未修改的BF16 Llama2；真实QK捕获只提供TLM地址工作负载。二者都不证明随机FFN、筛选或Ising替换后的联合模型质量。硬件能耗/时间/面积属于参数化TLM情景，不能当作GPU或芯片实测。
