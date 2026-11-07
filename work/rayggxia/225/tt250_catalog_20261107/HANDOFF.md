# 250MHz隔离目录交接

2026-11-07，负责人rayggxia，Issue225/PR248、task/225-norm-stream-20261106、同工作目录。用户明确要求250MHz与100MHz隔离，250结果尚不完整，可先不给完整TLM。

正式目录architecture_tlm/sram1216_20261106/250MHz/，仅README、MODULE_CATALOG、ASSEMBLY_STATUS、validate_catalog、VALIDATION。没有完整模型运行入口；整机time/energy/power/die_area均null。没有选定320/640路普通池、FFN核数、SRAM时钟和QK映射，不把候选资源当已定配置。

已索引204的TT1.2V25℃250MHz八模块：GF64、C20/T64完整M128、非线性64、后端M128、state32、数字CIM、Gemmini OS/WS。8/8原始归档大小及整包SHA本轮复核，沿用来源3119成员SHA验收记录；不是重新执行3119成员仿真。全文整核与分解组件不重复相加，DOT64与向量单位区分。raw面积单次x.81为55等效，不缩放功耗/时延。

198的九旧Attention模块仅元数据索引：18项17正常退出，FMA64/250超时缺seed1009回压/两idle窗；自动归档也超时且无完整SHA，不能晋级完整价格。新PV4/QK共享包装TT250、末端归约单价/II、真实供数、SRAM/DMA与其他算子250参数均明确未绑定。既有数据“未绑定”不能冒称“从未仿真”，后续先盘点再请求补测。

11项目录/PVT/单位/缺项检查通过；原100MHz宿主、sampling_latency、attention_candidate三个历史manifest合计32成果文件逐SHA不变。未修改100默认或执行源、198/204原件及作业；无新EDA/GPU/PPL/RTL/PT。数字电路统一台账不新增重复仿真run。

关于新Attention未作100MHz正式默认：PV4门级X和真实QK供数尚未闭合；优先候选combined32可以显式做TLM研究，41.46是条件预算，52.62为已有参考。不是要求所有无关电路完成才研究，不把未通过的后端当通过。

恢复：读最新Issue225/PR248、STATUS、本交接；运行build_catalog.py刷新只读证据索引，再运行250MHz/validate_catalog.py。若来源发生更新，新增版本/记录来源SHA，不改已提交实验；不自动提交缺窗或重跑原17项。用户要求资料完整后再做独立250MHz调度/TLM，不把100结果直接除2.5、功率乘2.5，不让外存带宽随片上时钟增长。

ROOT阅读镜像同字节，SOURCE_MANIFEST/ISOLATION_VALIDATION绑定此次小型索引与不变的旧成果；原始大报告仍在既有project_archives。公开状态见PUBLICATION.json，PR待审不合并；Projects无写接口待维护者同步。
