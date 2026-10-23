# Qwen3 Base 双模型基线（Issue136）

本目录是 Qwen3-1.7B-Base 与 Qwen3-4B-Base 的独立入口；不是 Qwen3.5，也不是带 thinking/chat 模板的指令模型。

本阶段只建立未修改模型的 BF16 完整 WikiText-2 test 基线。FFN、QK-Norm、GQA、RoPE、Softmax/PV 全部使用 Transformers 原始实现；没有随机计算、校准或训练。后续 FFN/PV/QK/Ising 方案不能提前继承本结果。

| 项目 | 1.7B-Base | 4B-Base |
|---|---:|---:|
| layers | 28 | 36 |
| hidden / FFN intermediate | 2048 / 6144 | 2560 / 9728 |
| Q heads / KV heads | 16 / 8 | 32 / 8 |
| head_dim | 128 | 128 |
| Q 内部宽度 | 2048 | 4096 |

固定 revision、原始语料 SHA 与协议在 [config.json](baselines/config.json)。权重使用 `https://hf-mirror.com`，下载后核对镜像返回的固定 revision、LFS SHA256/非LFS Git blob SHA1，并记录实际文件 SHA256。镜像哈希核对是传输完整性证据，不是第三方签名认证。

## 评测协议

- 完整 `wiki.test.raw`，UTF-8 原字节解码，`add_special_tokens=False`，无 chat template、BOS 或截断。
- window 2048、stride 1024、batch 1、seed 0、无 KV cache；所有位置 1..N-1 恰好计分一次。
- 原始 BF16 参数，原生 SDPA；RoPE 频率保留 FP32，不做整模型 dtype blanket 转换。Cross-entropy FP32，逐窗口 NLL 求和后除以总目标数再取 exp。
- 训练语料只做 SHA 校验，不参与训练；不同分词器/模型的原始 PPL 不能解释为随机替换收益。
- 此为无采样的原始数值基线，一个固定 seed；后续随机方案按规则至少三个独立 seed。
- 源码、配置、模型/分词器、token 序列、数据、环境、Slurm、命令和结果均记录。GPU 耗时只含评测，不含下载/模型加载；不是芯片硬件性能。

## 执行

服务器个人项目目录：`/home/Hongjie_Zeng/projects/pbit-qwen3-baseline-20261023-issue136`。
独立 venv 复用现有 PyTorch 2.7.1+cu128，安装 Transformers 4.51.3 / tokenizers 0.21.4；不升级原 `pbit_llm` 环境。

1. 提交源码后运行 `python qwen3/baselines/package.py --output <new-tar.gz>`，从 Git blob 生成只读快照与源码 SHA 清单；上传/验证包 SHA，解压到新的快照目录，不覆盖已提交作业的源码。
2. CPU Slurm：`sbatch --output=<ROOT>/logs/prepare-%j.log <SRC>/prepare.sbatch <ROOT> <SRC>`。先覆盖测试、原生 tiny Qwen3 GQA/QK-Norm/save-reload，再下载两个模型并校验配置/权重/语料。
3. CPU 作业成功后，GPU Slurm：`sbatch --output=<ROOT>/logs/evaluate-%A_%a.log <SRC>/evaluate.sbatch <ROOT> <SRC>`。数组0/1各一张GPU；每个模型开始前重新核对源码、模型和语料SHA。
4. 结果在 `<ROOT>/results/`，模型清单在 `<ROOT>/prepared/`，日志在 `<ROOT>/logs/`。仅小型结果/manifest归档Git，不上传权重/数据。

实时阶段、作业号与限制见 [HANDOFF](../work/jieruiz/136/HANDOFF.md)。
