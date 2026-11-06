# 两模型固定芯片概率预算

先读[初步报告](REPORT_ZH.md)。这是解析预算适配器，不是新的完整TLM入口。代码和校准可独立离线重算；新模型尚无原生TLM/PPL。

运行：`python -B architecture_tlm/model_scaling_20261106/estimate.py`；检查：`python -B -m unittest architecture_tlm.model_scaling_20261106.test_estimate -v`。
