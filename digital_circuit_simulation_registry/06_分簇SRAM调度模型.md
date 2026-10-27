# 分slice共享SRAM端口/链路模型（2026-10-27）

沿原Issue186/PR192，仅替换主TLM可选memory_factory；不是新的一套LLM实现，也没有新电路PT。结构和参考见[本机说明](C:/Users/86134/Documents/a_P_BIT/tmp/ffn-local-pipeline-issue186-20261025/architecture_tlm/sliced_sram_20261027/README_ZH.md)，[实际对照](C:/Users/86134/Documents/a_P_BIT/tmp/ffn-local-pipeline-issue186-20261025/architecture_tlm/sliced_sram_20261027/RESULTS_ZH.md)。

4×128个80MHz单端口bank、4×128GB/s共享读写链路与具体DMA/矩阵/向量端点；原8MiB/512GB/s保持。beat有限双credit，额外16KiB FIFO明确未价。45验证通过，同bank/链路冲突、缓冲在途、原物理字节和工作量已检查。SRAM宏原校准仍用，待补的是FIFO/仲裁/互连/CDC实现，不把它们称已测。

旧global/分slice描述符/beat-cycle_end六项一层Qwen3-4B＋完整词表实际DRAMSys已封存；写入接受返credit策略3178两项也已completed，8/8封存核验；SC/BF16较旧集中模型慢约1.13%/1.20%，无本任务运行作业。不是完整36层时间。当前功耗2.52W仍对应旧调度，不能自动套给新NoC。Ising输出sink未拆beat，配置明确不支持该新后端。

正式来源[任务分支](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/tree/task/186-local-pipeline/architecture_tlm/sliced_sram_20261027)，未合并。此为TLM条件模型索引，不新增数字电路run，台账已有PRNG/SRAM证据不变。
