# Qwen2.5-0.5B Base

本目录是该模型的独立工作入口。模型标识 `Qwen/Qwen2.5-0.5B`；[project.json](project.json)固定代码、配置、结果映射与SHA，路径相对仓库根。

| 内容 | 位置 |
|---|---|
| 代码与TLM | [tlm/](tlm/README.md) |
| 配置与模型身份 | [configs/](configs/README.md) |
| 基线与协议 | [baselines/](baselines/README.md) |
| 已有结果与SHA | [results/](results/README.md) |

已有证据与限制：

- 原始BF16基线、任务分数、历史随机FFN实验见所列结果。
- 当前目标分支中的Qwen Attention入口为v3/v4历史实现，默认合成输入、固定样本512；不要混称Llama分支的比例PV/有限bank标准。
- Qwen3.5等其他分支成果不因本次整理而自动合入。

```sh
python qwen/run.py info
python qwen/run.py check
python qwen/run.py --dry-run tlm --help
python qwen/run.py tlm --help
```

`--dry-run`只列出命令；不加载模型、不仿真。动作后参数原样传入，路径以调用者当前目录为准；脚本本身按绝对位置定位。任意工作目录均可用该run.py的绝对路径。GPU评测/捕获继续使用原Slurm脚本，不在登录节点直接运行。新输出应显式传`--output`，不要覆盖历史结果。

历史实现和已签SHA成果保留原路径、原字节，运行入口直接调用原脚本；没有复制一套可分叉的模型实现。共享SRAM、DRAM、随机源与通用算子继续共用，未因本次整理改变采样协议或质量结论。[返回项目首页](../README.md)。
