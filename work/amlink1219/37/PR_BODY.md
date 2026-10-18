此前Attention保存结果混合了core/全模型范围、两token均值/首冷token和不同内存资源，无法据此判断QK概率筛选＋Ising对完整Attention的收益。本变更增加同边界条件事务模型：QKV/RoPE/KV追加/core/Wo，明确投影权重stream、GQA并集、有限DMA、真实SRAM峰值、宏服务和功率/能量分账。

Slurm2164 CPU作业COMPLETED/0:0，23源SHA通过，9/9快照测试、32/32全24层场景完成；归档及40文件SHA回收通过，后处理三份汇总逐字节复现。2K默认S512比D0条件延迟高69.34%、代理能量高10.17%；S32有小幅成本改善，S128有能量/延迟tradeoff，给出约17.27ns宏输出预算。新增报告区分SRAM库值与未标定逻辑/DRAM/Ising参数，完整物理PPA和PPL保持null。

没有GPU/PPL/RTL/DC/PT；8K仅6.25%候选、理想IID地址、不同candidate的screen_exact诊断和未集成PV-v6均明确。代码、配置、原始小型结果、源/成果SHA及接续步骤齐全；不含PDK、论文PDF、模型权重或数据集。

Refs #37；依赖Issue36的本地数字参考提交d3c6514，实际事务执行源7f1cc0d。当前文案为待发布草稿，不自动关闭Issue或合并。目标base pbit-tlm-attention-details-20261016。
