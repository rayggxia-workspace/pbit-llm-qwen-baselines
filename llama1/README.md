# LLaMA-1 7B

本目录是该模型的独立工作入口。模型标识 `huggyllama/llama-7b`；[project.json](project.json)固定代码、配置、结果映射与SHA，路径相对仓库根。

| 内容 | 位置 |
|---|---|
| 代码与TLM | [tlm/](tlm/README.md) |
| 配置与模型身份 | [configs/](configs/README.md) |
| 基线与协议 | [baselines/](baselines/README.md) |
| 已有结果与SHA | [results/](results/README.md) |

已有证据与限制：

- 当前标准TLM共82项：60 Link＋18 Staggered＋4 NoPowerDown。
- 三个上下文512/1024/2048的真实BF16 QK捕获逐bit验证。
- 本次标准随机FFN/比例PV/max4/Ising没有新的联合PPL；BF16 TLM不是GPU实测基线。

```sh
python llama1/run.py info
python llama1/run.py check
python llama1/run.py --dry-run tlm --help
python llama1/run.py tlm --help
```

`--dry-run`只列出命令；不加载模型、不仿真。动作后参数原样传入，路径以调用者当前目录为准；脚本本身按绝对位置定位。任意工作目录均可用该run.py的绝对路径。GPU评测/捕获继续使用原Slurm脚本，不在登录节点直接运行。新输出应显式传`--output`，不要覆盖历史结果。

历史实现和已签SHA成果保留原路径、原字节，运行入口直接调用原脚本；没有复制一套可分叉的模型实现。共享SRAM、DRAM、随机源与通用算子继续共用，未因本次整理改变采样协议或质量结论。[返回项目首页](../README.md)。


## Unified TLM v6 (Issue96)

[Complete decode model and boundaries](../architecture_tlm/unified_v6/README_ZH.md). Optional `python llama1/run.py tlm-unified --context 2048 --output /absolute/new_directory`; legacy commands are unchanged. Local RNG is an interface with zero random-stream SRAM; physical PPA and new combined PPL remain unverified.
