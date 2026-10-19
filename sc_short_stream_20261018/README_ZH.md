# Qwen短流采样与精确累加：仿真包入口

这是Issue22的A8共享64、固定W8随机矩阵实验包。没有新的工艺功耗或Qwen短流PPL结果。

1. [先看能量估算](../qwen/energy/short_stream_20261018/REPORT_ZH.md)：128拍单列窗口约1.656nJ是沿用旧功率的估计，整Qwen旧TLM情景约56.7mJ/token，非实测。
2. [RTL接口和模式](RTL_USAGE_ZH.md)：`rtl/sc_ss_sampler.sv`是门限/随机源；`rtl/sc_ss_exact.sv`是精确矩阵归约和时间累加；`rtl/sc_ss_fixed_tops.sv`给定型模块。
3. [交给DC/PT的任务](ppa/README_ZH.md)：同100MHz/SS条件，分开source/frontend/body、存储与广播；先同27位累加器比较，再测22/21位。
4. [本地实际验证](results/VALIDATION_ZH.md)：36配置252帧、202496有效样本，7组活动窗口，全部通过；并非PPA。

Linux安装好Icarus和Python后，在本目录运行：

```sh
python3 sim/run_sim.py --seeds 0x13579bdf
python3 sim/run_sim.py --power --presets iid4096 iid128 strat128 strat64 enum256 --rng 1 --cases 1 --seeds 0x13579bdf --out results/power_local
python3 sim/prepare_active_vcd.py results/power_local
```

可单独选择`--sampler-only`来表征共享前端。完整三种子/多分布命令见接口说明。Windows可显式传入Icarus路径，工具和工艺库不在包内。

下载zip后，这个RTL目录可以独立运行。整机能量脚本依赖仓库`architecture_tlm/`，要复算整机请使用GitHub任务分支完整checkout；zip只附小型报告/结果，不复制整套仓库或受限库。

权重、概率和输入符号由上游保持稳定，不是硬编码常量，也不意味着SRAM/保持/配置零成本。xorshift32是本地可综合源候选；具体序列尚未做Qwen质量验证。旧IID4096的PPL不能直接配到分层128的新能耗上。
