# Issue182 可继续执行的交接

负责人jieruiz；更新时间2026-10-25T04:15:19.874160+00:00。目标rayggxia-workspace/pbit-llm-qwen-baselines；task/182-memory-hierarchy，PR183→main5273e5d9。本任务实现、验证及报告完成，通过PR待审；不自动合并、不提前关闭Issue。Projects因缺read:project待同步。

## 实现与结果入口

- 保持unified_v6和python -m architecture_tlm统一入口；memory_profiles.py、ffn_latest.py、core.py、model.py与run.py完成标准DRAM、SRAM重排、显式DMA响应缓存、跨输出波和输入组预取。
- 阅读architecture_tlm/unified_v6/MEMORY_HIERARCHY_ZH.md及RESULTS_MEMORY_ZH.md；22个完整36层结果的EXECUTION/MANIFEST/派生RESULT_SUMMARY在results/memory_20261025，19份DRAMSys完整RESULT原件留远端，analysis_memory.py与build_memory_report.py可重建摘要/报告。
- 8/16/32/64跨组结果516.97928/468.98478/462.11397/438.47604ms/token；不是芯片实测或PPL。W8数字参考只改变权重格式，仍512MAC/拍宏，非最优INT8ASIC。
- 93tests日志UNITTEST_cross_group.txt；独立18案例AUDIT_cross_group.jsonl。源码manifest四版本、实际Linux环境/argv、Slurm脚本和归档SHA在本目录，打包本机环境不能冒充执行环境。

## 冻结执行和远端原件

个人远端根/home/Hongjie_Zeng/projects/pbit-memory-issue182-20261025/，通过已有lab-server-ai配置。仅CPU Slurm，无GPU。
- 本地Link三case：0855eab497659964a594c91c5358b4729f4e5476。
- 首轮DRAMSys 11case：7e44b6a4d49d7ba4237c84a105f9a56338fc7f35，Slurm2913，execution_7e44b6a4；collector2922。
- PV/rejection补充seed1/2四case：fe3fc20fe0dfd9b580d5ed7adfe914bd55ad22c0，Slurm2925，execution_fe3fc20f；51个TLM模块与首轮相同，只runner加seed参数。
- 跨组预取4case：baf0aab1c20712d666bea40716d5cffde3df6e24，Slurm2931，execution_baf0aab1；collector2935。它与首轮是不同执行版本，不能混表后不标SHA。
- 2910启动失败保留；2911八microbenchmark、2912两tiny、2930两新tiny通过。Slurm accounting未启用，完成根据封存status、退出/突发守恒、文件SHA和source未变核验。
- 大dram.requests.jsonl.gz和bridge日志留远端，各run MANIFEST和remote_*的RAW_REMOTE_INDEX提供绝对位置/SHA。Git只保留小结果与索引，不公开模型、工艺库、凭据。

## 复现与验收

1. 恢复前核对Issue182/PR183、本人STATUS/本交接和远端main，不重跑已完成实验，不改执行快照。
2. 设置PBIT_DRAMSYS_BRIDGE，执行python -m architecture_tlm --memory-profile balanced_ddr4。缺bridge明确报错；legacy仅用于重现旧Link，不冒充真实DRAMSys。
3. 使用本目录run_memory_cases.py和各source manifest/远端完整argv复现确切case；跨组开关、数字chunk65536、seed与模型形状必须相同。
4. 先审计接口64GB/s、local receiver1024B/corecycle、单波response缓存的带宽/面积/功耗；本轮只有SRAM宏内部表征，不能把同8MiB解释成同总存储、同面积。
5. DRAMPower能量保留负ACT：ACT_*记录实际6.3.1源码及代数复算。它是上限参数组合的未校准分项，非物理负能量；不影响时序。需要后续一致电流模型/实测校准，不静默截零。
6. 现有数值/随机服务合同保留，但调度会改变随机序列推进；没有模型质量验证，不继承旧PPL。

发布通过PR183；以GitHub远端HEAD和发布回执确认已推送，未合并。任务目录保留最小待审副本，执行包已经有远端冻结原件；后续回收须按工作区生命周期规则核对ignored/未提交文件，不删除唯一证据。
