# 随机版固定资源调度探索

**最终入口：[FINAL_RESULTS_ZH.md](FINAL_RESULTS_ZH.md)**。两轮11项完整36层TLM已完成；组合三seed64.4113→57.4454ms/token，时间少10.81%。参数、字节、缓冲、分项效果和未展开调度均在该文档。代码/结果归Issue186/PR192，尚未合并。

# 固定资源随机版：调度消融

Issue186/PR192；Qwen3-4B后训练形状、36层、B1/2K，含lm_head。采用上一轮500MHz、32个64×64随机阵列、GU64/NL128、8MiB/512bank/512GB/s SRAM与同一标准HBM时序。Attention仍为筛选＋准确Softmax＋PV采样。

本轮只改三项：资源日历利用已暴露任务间的空隙；SC另一权重/系数bank跨输出或输入窗口提前装载；普通BF16 QKV/O/lm_head启用既有共享预填充。复用现有两槽、两本地bank和单套计算/恢复资源；保持逻辑K64顺序、每级采样、工作量、字节与本地数据容量。主消融均不开门控，避免把门控协议变化混进调度；本轮未改计数器/普通数字L/II参数。

MATRIX共7项：原调度、三个单因素、组合seed0/1/2。源提交后冻结，通过CPU Slurm执行，存储使用真实DRAMSys。运行源与结果manifest保存准确SHA，完整结果待完成后追加。资源日历是对有限预取任务的宏级仲裁，不新增无限乱序队列；外存仍是原来的单macro actor、批间排空，没有宣称已实现跨描述符并发。

验证：python -B -m unittest architecture_tlm.scheduling_v2_20261027.test_scheduling architecture_tlm.ffn_local_pipeline_20261025.test_pipeline -v。完整调度验证后才报告整机时间；小形状link不是HBM结果。时间变短引起的idle/background动作变化单列，算术和物理访存应保持一致。

area/power缺项沿原边界，完整芯片PPA仍未知；若动作不变，动态能量不会因软件仿真更快自动同比下降。随机重播种若取决于墙钟可能改变epoch，不继承逐bit或PPL等价。后续数字基线会采用相同可行的预取政策，本次先看随机模型的变化。

首轮7项已完成，见RESULTS_ZH.md：三个开关组合仅约0.14%均值收益。第二轮MATRIX_EARLY_DMA.json把下一请求前移到当前响应缓冲释放边界，单因素＋组合三seed已提交；结果将在RESULTS_EARLY_DMA_ZH.md记录。两轮执行快照独立，不覆盖旧结果。
