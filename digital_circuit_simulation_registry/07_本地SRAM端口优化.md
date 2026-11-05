# SRAM本地端口优化：TLM索引

Issue186/PR192，非新电路PPA，不新增数字run。使用已校准55nm SS E宏256×128：read最小周期3.468ns，250MHz仅通过周期筛查，未新验证wrapper STA。8MiB/2048宏cell面积68.0473mm²不变，外围宽接口、driver/mux、响应缓冲读口、gearbox/CDC/CTS未价，不能填0。

取消无依据全局512GB/s封顶，改为4个本地共享读写通路各512GB/s，由bank/消费者定宽；真实单端口bank/有限credit/20ns CDC/原DRAMSys保留。额外16KiB payload FIFO与旧分slice对照相同，不藏入8MiB。独立端点和2048宏显式映射作为匹配消融保留，无免费多端口bitcell。

58软件检查，12新项封存＋2旧基线逐SHA核验。单Qwen3-4B形状层＋全词表、seed0/2K，SC8.322292→6.816810ms、数字FFN8.936880→7.172958ms；不是36层TPOT。只升频/窄DMA/宏暴露等负面和无收益对照完整保留，等宽后独立拓扑未进一步加速。

正式成果：[源码与结构](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/tree/task/186-local-pipeline/architecture_tlm/local_ports_20261027)，[本机结果](C:/Users/86134/Documents/a_P_BIT/tmp/ffn-local-pipeline-issue186-20261025/architecture_tlm/local_ports_20261027/RESULTS_ZH.md)。可恢复原件/封存/源/归档/回执见同任务work/jieruiz/186/LOCAL_PORTS_*；冻结快照未改，PR待审未合并。现有PRNG/SRAM/计算模块run仍在原records中。
