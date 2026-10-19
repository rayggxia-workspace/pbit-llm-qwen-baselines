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

2026-10-18新增：[固定权重短流能量估算与RTL表征](energy/short_stream_20261018/REPORT_ZH.md)（Issue22）。比较4096/256/128/64拍；只有旧成本代理下的TLM敏感性和RTL功能验证，不代表Qwen短流PPL或新PT实测。

```sh
python qwen/run.py info
python qwen/run.py check
python qwen/run.py --dry-run tlm --help
python qwen/run.py tlm --help
```

`--dry-run`只列出命令；不加载模型、不仿真。动作后参数原样传入，路径以调用者当前目录为准；脚本本身按绝对位置定位。任意工作目录均可用该run.py的绝对路径。GPU评测/捕获继续使用原Slurm脚本，不在登录节点直接运行。新输出应显式传`--output`，不要覆盖历史结果。

历史实现和已签SHA成果保留原路径、原字节，运行入口直接调用原脚本；没有复制一套可分叉的模型实现。共享SRAM、DRAM、随机源与通用算子继续共用，未因本次整理改变采样协议或质量结论。[返回项目首页](../README.md)。

## 已合入的随机FFN范围缩放

2026-10-19，精确双随机参考PR31及独立范围缩放PR34已合入`pbit-tlm-attention-details-20261016`（范围合并提交5b71d4e）。

- [实现与运行说明](../experiments/qwen_dual_range_20261018/README_ZH.md)：A按当前token每64通道缩放，W按每输出行每64输入缩放；准确Attention、自然IID、无训练。
- [49项结果与限制](results/dual_range_20261018/RESULTS_ZH.md)：128/2048token前缀PPL及mean/fixed/分支对照；不能冒称完整随机WT2或硬件节能实测。
- [分布与裁剪诊断](results/dual_range_20261018/DISTRIBUTION_ZH.md)：teacher真实编码直方图和标量裁剪误差，不是裁剪模型PPL。

这是一项可选实验实现，没有改变原BF16基线或TLM默认配置。历史执行源17c89c3和校验原件保持不变。


## 固定INT8权重、输入多尺度短流（2026-10-19）

[完整WT2与三种子结果](results/fixedw_multiscale_20261019/RESULTS_ZH.md)：全部24FFN保留同一固定W8，输入4/8档二次幂编码，T128/256完整滑窗；原BF16 Attention不变。4档T128约12.31、T256约11.99，原BF1611.652735。已[补完T64完整WT2三种子](results/fixedw_multiscale_t64_20261019/RESULTS_ZH.md)：4档13.0380±0.0107、8档13.0385±0.0120，较BF16增加约11.89%；单档pot1仍只有512前缀。没有新PPA或修改TLM默认。


## 多档缩放＋随机分层：完整WT2短流（2026-10-19）

[联合结果与图](results/multiscale_stratified_20261019/COMPARISON_ZH.md)：固定同一W8、全24FFN、Attention原版；新增67配置＋2BF16参考均收齐。四档细分层T16/32/64为11.900826/11.736131/11.693775（各3seed），BF1611.652735；两档T32为11.769199。3～4档后无明显额外收益，缩放后粗K4/16也有效；K>1是受控随机分层，不能冒称自然IID。只给数值精度，无新PPA/整机能耗结论。
## FFN裁剪与固定二次幂尺度（2026-10-19）

见[Issue39前缀PPL与证据边界](results/ffn_clipping_20261019/RESULTS_ZH.md)。八项主策略及端点/温和裁剪补充共65项替换对照已完成，Attention保持原BF16；完整WT2仅重跑原BF16基线，不能把替换前缀分数称为完整PPL。固定范围的质量与电路开销分别记录，没有修改TLM默认。
