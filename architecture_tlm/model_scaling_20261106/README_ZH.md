# 三模型硬件评估入口

当前工作先看[实际执行状态与材料来源](EXECUTION_STATUS_ZH.md)：24项原生LPDDR完整尺寸单层pilot已全部封存并通过事务守恒检查，尚非24项整模型PPA。另有可重算的COMPONENT_BUDGET.json（权重流下界/已标定核增量能量，不是整机总量）。固定100/250MHz两版芯片，不下载大权重或做准确率基线。试接与主线调度的差异有明确清单，不能把pilot直接乘层数。

下方为保留的旧解析预算，不能作为当前小SRAM/短采样/六核或三核配置的结果。

先读[初步报告](REPORT_ZH.md)。这是解析预算适配器，不是新的完整TLM入口。代码和校准可独立离线重算；新模型尚无原生TLM/PPL。

运行：`python -B architecture_tlm/model_scaling_20261106/estimate.py`；检查：`python -B -m unittest architecture_tlm.model_scaling_20261106.test_estimate -v`。
