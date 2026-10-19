# Llama-2-7B Base 的 BF16 基线

任务 Issue #14；与 LLaMA-1 7B、Qwen 结果分开。此目录提供完整 WikiText-2 raw 测试集 PPL 与简单 greedy 生成检查。它不修改 FFN/Attention，不是随机计算模型质量评测，也不测 GPU 功耗。

只接受 `meta-llama/Llama-2-7b-hf` Base 的固定 revision 和经 SHA-256 核验的本地模型。镜像下载可以作为传输渠道，但必须由身份清单记录来源与官方文件哈希对应关系；没有正式权重时只能交付脚本，不生成替代结果。

## 评测协议

完整读取原始 `wiki.test.raw`，要求 SHA-256 为 `173c87a53759e0201f33e0ccf978e510c2042d7f2cb78229d9a50d79b9e7dd08`。不改空白，不切片，不新增 BOS/EOS；tokenizer 使用 `add_special_tokens=False`。若从 Salesforce/WikiText parquet 重建，空行必须恢复成一个空格与 LF（`" \n"`），逐行拼接而不插入额外分隔符；哈希不匹配直接停止。

分别计算窗口 2048、4096，stride 均为 512 的完整滑窗 PPL。共有 N 个 token 时，计分位置必须恰好为 `1..N-1`：

- 第一个窗口 `[0, W)` 给真实 target `1..W-1` 计分。位置 0 没有真实的前置 token，不能计分。
- 下一窗口从 512 开始，重叠段只作上下文，新到达的 512 个 target 才计分；最后不足 512 的部分按实际 token 数计分。
- 窗口输入位置 i 的 logits 预测位置 i+1。每个窗口保存 `begin/end/score_start/logits_start/count`，结束后强制检查 target 总数为 N−1。
- 每个窗口重新从 position 0 开始；RoPE 不延伸至 4096 之外。2048 和 4096 的上下文长度不同，因此不应混为同一指标。

不使用模型返回的平均 loss 乘以输入长度。先对被计分 token 的 BF16 logits 转为 FP32，计算逐 token cross entropy，再转 FP64 求和；最终 `PPL = exp(总NLL / (N−1))`。首窗口 2047/4095 个 target 和后续 512 个 target 因而得到正确权重。

环境固定 Transformers **4.45.2**、BF16 权重及激活、SDPA、batch=1、seed=0、TF32 关闭、PyTorch deterministic algorithms 开启。SDPA 可用后端及 torch/CUDA/GPU 名称写入环境记录；更换 GPU/后端仍可能改变最后几位数值，不是逐位跨平台保证。

## 输入与 Slurm 提交

先将代码提交并复制到不可变执行快照，日志父目录必须预先创建。所有 GPU 工作通过 Slurm 执行，不在登录节点直接调用脚本：

```bash
sbatch --chdir="$SNAPSHOT" --output="$RUN/logs/ppl-%j.log" \
  --export=ALL,SOURCE_COMMIT="$SHA",MODEL_PATH="$MODEL",DATA_PATH="$DATA",IDENTITY_MANIFEST="$IDENTITY",OUTPUT_ROOT="$RUN/new-baseline-output" \
  baselines/llama2_7b/evaluate.sbatch
```

默认请求 gpu5090 分区的 1 张 GPU、4 核 CPU、40 GiB 主存、6 小时；正式运行耗时以作业结果为准。权重 BF16 大约 13.5 GB，4096 上下文仍需激活和临时 logits 缓冲，因此推荐单张 32 GB 卡。代码设置 `use_cache=False` 评测 PPL，不累计跨窗口 KV。

`$IDENTITY` 为 JSON，要求：

```json
{
  "repository": "meta-llama/Llama-2-7b-hf",
  "revision": "<40位官方HF提交SHA>",
  "files": {"config.json": {"sha256": "<64位SHA256>", "bytes": 0}},
  "model_shape": {
    "model_type": "llama", "hidden_size": 4096, "intermediate_size": 11008,
    "num_hidden_layers": 32, "num_attention_heads": 32,
    "num_key_value_heads": 32, "max_position_embeddings": 4096,
    "vocab_size": 32000, "rms_norm_eps": 0.00001,
    "rope_theta": 10000, "tie_word_embeddings": false
  }
}
```

示意中的 `files` 不能直接运行：须列出 config、tokenizer.json、tokenizer.model、tokenizer_config.json、实际存在的 special_tokens_map/generation_config/added_tokens，以及全部所用权重和分片 index。脚本禁止未校验的额外加载元数据、路径越界、缺少分片、RoPE scaling 或配置不匹配。支持完整 safetensors 或完整 bin 权重，优先 safetensors；加载全程 `local_files_only=True`、不执行 remote code。模型目录须为个人目录中的实体文件或目录内链接；跨目录 HF cache symlink 应先物化。

输出目录必须不存在。`SOURCE_COMMIT` 写入准确 40 位 Git SHA，源代码目录中的逐文件 SHA 也随输出保存。代码不下载模型，不处理登录/token，不覆盖输出，不将语料全文写入成果。

## 输出和检查

- `protocol.json`、`identity.json`、`source.json`、`command.json`、`environment.json`：精确配置、模型/源码/语料身份、命令和环境。
- `tokenization.json`：token 数、N−1 target 数、little-endian int64 token IDs SHA-256。
- `windows_2048.jsonl`、`windows_4096.jsonl`：每窗口计分范围、NLL、累计 token 数和进度；部分作业也可以检查已实际完成的窗口，但不能当作完整 PPL。
- `ppl_2048.json`、`ppl_4096.json`：完整 PPL、总 NLL、实际计分 token 数、经过 warmup 后的 wall time、显存 allocated/reserved 峰值。
- `greedy_smoke.json`：两个公开英文提示的 greedy 输出，仅验证基本生成，不是正确率基准。
- `summary.json` 与 `ARTIFACT_MANIFEST.json`：只有全部成功才写 completed；最终 SHA 清单不包含自身。

时间包含每窗口传输、前向、CE、同步及日志；它不是纯 kernel 时间。显存峰值包含模型驻留。没有测量功率，不能把此 GPU 结果当作 TLM 的 ASIC 能耗实测。

本地纯 CPU 协议检查（无需 torch）可运行：

```bash
python -m unittest discover -s baselines/llama2_7b -p 'test_*.py' -v
```

检查包括 N−1 target 唯一覆盖、短尾窗口、移位标签对齐、无 BOS 的首 token 边界、独立 tiny causal scorer 的 NLL 对照、模型文件篡改、缺失权重分片及越界路径拒绝。临时文件显式放在个人 checkout 的 `.test_tmp/` 中，不使用共享临时目录。这些检查不能代替正式模型 GPU 运行。
