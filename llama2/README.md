# Llama 2 7B Base

本目录是该模型的独立工作入口。模型标识 `meta-llama/Llama-2-7b-hf`；[project.json](project.json)固定代码、配置、结果映射与SHA，路径相对仓库根。

| 内容 | 位置 |
|---|---|
| 代码与TLM | [tlm/](tlm/README.md) |
| 配置与模型身份 | [configs/](configs/README.md) |
| 基线与协议 | [baselines/](baselines/README.md) |
| 已有结果与SHA | [results/](results/README.md) |

已有证据与限制：

- 原BF16完整WT2滑窗PPL：2K4.9795028452 / 4K4.8958312205，stride512，无额外BOS/EOS。
- 当前标准TLM共116项：72 Link＋36 Staggered＋8 NoPowerDown；原生4K。
- 上述PPL不属于随机替换联合模型；TLM不是GPU或芯片能效实测。

```sh
python llama2/run.py info
python llama2/run.py check
python llama2/run.py --dry-run tlm --help
python llama2/run.py tlm --help
```

`--dry-run`只列出命令；不加载模型、不仿真。动作后参数原样传入，路径以调用者当前目录为准；脚本本身按绝对位置定位。任意工作目录均可用该run.py的绝对路径。GPU评测/捕获继续使用原Slurm脚本，不在登录节点直接运行。新输出应显式传`--output`，不要覆盖历史结果。

历史实现和已签SHA成果保留原路径、原字节，运行入口直接调用原脚本；没有复制一套可分叉的模型实现。共享SRAM、DRAM、随机源与通用算子继续共用，未因本次整理改变采样协议或质量结论。[返回项目首页](../README.md)。
