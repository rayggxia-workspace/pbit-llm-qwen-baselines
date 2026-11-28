# Prefill核数预算交接

负责人rayggxia，Issue225/PR266，task/225-cim-bank32-20261124；复用tmp/cim-bank32-tlm-issue225-20261124，不另建checkout。当前为本地已完成，上传状态以PUBLICATION.json为准。

用户问以本项目P-CIM使Qwen3-4B prefill进入1–2秒需要多少核。固定2K、28nm/250MHz、GU16/Wd32，范围仅资源选型，不替换decode默认。正式文档/可复算程序architecture_tlm/process_28nm/prefill_core_sizing_20261127。复用已封存CIM配置/ALIGNMENT及250MHz BINDINGS的公开参数，原字节SHA与最小提取字段在SOURCE_INPUTS，未复制工艺库/大型依赖。

python -B architecture_tlm/process_28nm/prefill_core_sizing_20261127/estimate.py
可用 --source-root C:/Users/86134/Documents/a_P_BIT核验现有三个原件；最小两文件快照与本地RESULT字节相同，独立MAC和因果pair核验PASS，VERIFICATION记录。无需模型权重/数据；seed/PPL不适用，没有远端/EDA任务。

纯FFN62.7573核秒；完整2s候选96核配16384 FMA等为1.80s，1s候选192核配32768 FMA等为.943s。这些含建议的128/256行权重复用、独立状态行流水、扩大SRAM/向量/encoder和100GB/s有效DRAM；不是已实现性能。当前阻塞state_worker若不改，约2.46/1.27s。默认两state32口理论至少5.38s，数字QKV/O当前256lane约32.09s，旧资源无论只加多少CIM都达不到1–2s。

下一步：先2K/96核配套候选的代表性prefill分块，验证每次权重装载服务128行、状态owner/读更新写流水、有界结果槽与回压、数字GEMM广播复用和物理bank调度；再决定是否做原生全36层TLM。不能把最短服务时间写成已测TTFT，不能将FP24/22数制预支为既有PPL或PPA。PR未合并，Issue225广义任务不关闭，Projects未操作，Issue28远端待原维护流程同步。
