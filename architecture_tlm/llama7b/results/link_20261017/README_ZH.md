# 已完成的 Link 结构对照

本目录保存 Slurm1878 完成的60项结构对照均值/标准差，以及原始成果的服务器位置和SHA。后端是简化Link；输出目录名称中的Staggered只是统一命名，Link没有执行DRAM低功耗状态机。

这些时间、K/V读取与阵列数敏感性可用于检查数据流；外存能量沿用未校准的64pJ/byte与50mW背景，不能替代DRAMSys的主能耗结果。完整闭环结果另存 `../current/`。CPU仿真墙钟与模拟芯片ms/token分开。

`ARTIFACT_INDEX.json` 的expected_full_results=82是整项任务的计划，不表示本目录已有82项或DRAM已经完成。本目录严格只有60项Link，模拟输入来自单公开WT2窗口的真实BF16 QK，不证明随机FFN联合质量或新PPL。
