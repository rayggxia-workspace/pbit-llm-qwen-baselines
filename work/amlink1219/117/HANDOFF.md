# Issue117 ASIC资源优化交接

负责人amlink1219，正式目标rayggxia-workspace/pbit-llm-qwen-baselines。独立工作目录workspace_projects/ar117，分支task/117-asic-resource-optimization，base集成46804fb。PR base pbit-tlm-attention-details-20261016。

执行源44dbbbdbc2720963b2b24bf03cdf7582a2d97075。首批P0已完成：92旧/新封存情景、145payload逐SHA审计与资源/下界分析；28新机制测试、43原v6测试通过；完整BF16/2K及SC筛选PV/8K smoke复现234.36001/202.83611ms。模型、tokenizer、语料不适用：未做LLM数值推理。

正式入口architecture_tlm/resource_optimization_v1/README_ZH.md和P0_RESULTS_ZH.md；机器证据results/p0_20261023。新增搜索16候选×4方法×2上下文seed0共128项，四个独立输出shard，源码/配置manifest已冻结；此交接版本写入时仍在执行，不是完成声明。

本机执行无Slurm/GPU任务。全量新结果写入results/coarse_20261023/shard_0..3；CLI --resume只接受原执行提交、manifest、源SHA及case回执。必须先核已有receipt和执行进程，不重复启动同一case。后续若任务分支HEAD已经有文档/结果提交，要在执行44dbbbd的最小独立工作树恢复，不能仅放宽版本检查。

待做：128项完成后生成summary、按共同候选选择三seed代表点、独立审阅、登记TLM估计及结果/图表、更新PR与本交接。全部面积/能量/A0仍null，不做完整同面积排名；新KV驻留、恢复RTL和Issue116后端未实现，保持独立范围。

发布状态见work/amlink1219/117/PUBLICATION.json及Issue117；首批成果准备通过任务PR交付，不自动合并或关闭Issue。Projects权限单独核实，不将仓库push权限当作看板权限。
