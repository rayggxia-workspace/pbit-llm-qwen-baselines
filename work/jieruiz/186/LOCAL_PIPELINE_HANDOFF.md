# Issue186 本地权重双bank续作（2026-10-25）

负责人jieruiz；task/186-local-pipeline；base main d83eeb1fc6b89a3dff51b5b62bf79acf665c7166；目录tmp/ffn-local-pipeline-issue186-20261025。原PR190已合并，新PR发布回执见work/jieruiz/186/PIPELINE_PUBLICATION.json；此刻本地完成，待发布，不自动合并。

13/13 CPU Slurm3074 completed，3完整36层＋10单层，执行6f73ef65，SHA/工作量/流量守恒通过；44项相关测试通过。407.143→315.236→307.049ms/token（原/双bank/再bypass）；FFN 268.576→176.680→168.488ms；旧结果逐数复现。新目录architecture_tlm/ffn_local_pipeline_20261025，记录本O14。没有新PPL/RTL/PT或完整物理PPA；SRAM已知内部动态不能当整机能量；HBM能耗未知。原件远端pipeline_6f73ef65，健康完成任务不重跑。Projects缺read:project待同步。下一步审核有限双bank接口与计数结果/恢复流水，不混淆硬件扩容和调度。

---

运行入口：python -m architecture_tlm.ffn_local_pipeline_20261025.run_case；源与配置冻结清单PIPELINE_SOURCE_6f73ef65.json；提交回执PIPELINE_SUBMISSION.json；采集collect_local_pipeline.py仅接收completed并校验原件SHA；分析python -m architecture_tlm.ffn_local_pipeline_20261025.analyze。所有结果MANIFEST/EXECUTION已放新目录results。后补receiver guard不改变有效配置时序，冻结源码未动。独立测试test_pipeline.py验证了bank所有权、完整回包容量、边界顺序、动作守恒、慢端口回压和排空。

交付仅新文件夹及相关记录；不改统一v6源码或默认入口；不移动删除其他成员文件。大原件/DRAMSys日志保留个人服务器，tar本地可在发布核验后清理。没有正在运行的本任务job。下一执行者先核最新main/PR再工作。
