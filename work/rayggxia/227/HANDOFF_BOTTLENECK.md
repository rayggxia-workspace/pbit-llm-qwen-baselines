## 2026-11-01 Issue227完整结果与审计已推送

科学提交05b9f6ef01f567c6cbdaf97d11083665cfecc168，18文件内容及Git blob远端回读一致；PR228和Issue227已更新，仍open/draft未合并。完整66.991850ms、11审计/28检查及下一步见HANDOFF_BOTTLENECK；本轮无运行中任务。回执BOTTLENECK_PUBLICATION.json，Projects待维护者同步。

# Issue227完整回放与等待审计交接

负责人rayggxia；分支task/227-shared-memory，PR228/main。复用tmp/shared-memory-issue227-20261101。Git origin仍指历史个人库，禁止向其发布；workspace才是目标。远端PR228父提交3aebd7419fc78ea55775538529f5d381445ec49a，本地历史落后远端API提交，不能force-push。准确交付提交/回读见BOTTLENECK_PUBLICATION.json。

本轮可检查成果：architecture_tlm/shared_memory_20261101/bottleneck_audit/REPORT_ZH.md、RESULTS/FULL_VERIFIED/VALIDATION/RAW_RESULT_INDEX/EXECUTION_INDEX/OLD_FULL_MATCHED.json和LAYER_TIMES.csv。新增观测器unified_v6/shared_audit.py，不改原调度事件；audit_decode.py为有界资源对照；test_shared_audit.py三项加旧25项通过。完整3673为66.991850ms，507相位/36层/帧/样本/词表/5,354,946,560B权重/排空/100MHz检查通过。旧同100MHz3653为222.636130ms，旧混合3650完整224.796237ms单独保留，不混称全同钟比较。

数组3688全部11个RESULT完成；每任务冻结快照内28测试OK。squeue已空；本次sacct输出为空，未虚构账单退出码。原件project_archives/shared_memory227_20261101/bottleneck_audit/results/<case>/RESULT.json；完整原件见RAW_RESULT_INDEX，私有原输入不公开。远端root及执行源码/配置/bridge/input/result SHA、命令均在EXECUTION_INDEX和SUBMISSION。原始文件不改字节；未改提交后的远端快照。

复核命令：python -B architecture_tlm/shared_memory_20261101/bottleneck_audit/build_report.py --archive <project_archives/shared_memory227_20261101> --task <checkout>；随后运行test_shared_audit及原四个test_shared_*模块。build_report会核对9个匹配配置工作量与地址，并将原始结果重建为汇总；OLD_FULL_MATCHED/EXECUTION_INDEX是额外身份索引。

主要发现：数字2048MAC加倍无收益；NL160更均衡；直接返回省一次FIFO写读获较大收益；加全局credit/总fabric不解决主要问题。各自为单层消融，不可叠加成整机成绩。等待状态是驱动阻塞，SRAM读取可与算术重叠，不能把380µs operand区间说成380µs纯空闲；并行核时间不加成墙钟。sampler_V_pipeline标签包含初期直接DMA等待，不能全叫Ising时间。

下一步可执行：有限bypass＋NL160＋按片区码复用组合，3场景及完整回放；流式数字operand/提前补货；GU核/下游tile流水；QK与筛选宏分别消融。当前未提交新实验，不需要重新跑健康/已封存作业。完整RNG服务与500MHz/256GB/s迁移仍未实际接入此后端，不能据此继承旧预测/全芯片PPA/PPL。无新EDA，勿新增假PPA台账run。PR待审不合并/不关闭Issue；Projects写接口不支持待维护者同步。正式根记忆通过MEMORY_UPDATE_BOTTLENECK窄增量交Issue28。
