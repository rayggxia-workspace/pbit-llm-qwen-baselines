# 同64路并行INT8对照

[正式报告](results/REPORT_ZH.md)、[核验汇总](results/FINAL_SUMMARY.json)、[输入追溯](INPUT_REFERENCE.json)、[执行manifest](EXECUTION_MANIFEST.json)。

64并行乘法+平衡树，固定N64精确22位和、32/22位结果寄存。两top/三seed最终24PT窗口，v1保持违例另24窗口保留。功能与对应门级均984有效输出。源码是base158e4898+冻结ZIP，不伪造执行提交；无真实模型/PPL。

在新目录重建RTL/bench及激励：`python architecture_tlm/int8_parallel64_20261028/prepare.py`；prepare会重写RTL/bench/fixtures，不在冻结快照内运行。实际EDA命令及哈希见work/rayggxia/204/int8_parallel64/RUN_LEDGER.json，需已授权服务器与相同私有库绑定。不要在冻结快照继续改写/提交。
