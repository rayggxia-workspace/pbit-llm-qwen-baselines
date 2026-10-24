面向远程Agent提供可执行的Qwen/Qwen3-4B非Base训练交接：固定源码与模型revision、依赖PR160复用、待实现模块、先导验证、Slurm组织及结果回传模板。新增INT4/INT6，与INT8各执行原完整一套，其余设置保持。

主扫描为48随机配置+9控制=57项（每位宽19项，A计划114亿有效训练token）。每项实验36层gate/up/down统一Wb，输入仍A8/共享64；三份BF16为配对重复，不作三种量化结构或三seed。B阶段每位宽最多18、合计54；C/D同样按各位宽原预算。

入口：qwen3/training/sc_qat_20261023/REMOTE_AGENT_START_HERE_ZH.md，附REMOTE_ENV/RUN_RESULT模板、SCAN_MANIFEST与原设计依据。PR147/153只读oracle；PR160已有非Base准备，恢复先检查现有任务。

验证：57项唯一任务ID/码界/跨位宽非权重设置一致、JSON与Python语法、未就绪启动拒绝、独立审阅通过。G2独立120步短课程覆盖目标采样及尺度冻结。无本任务训练器、H200/Slurm作业、新PPL/PPA。关联Issue159；通过本PR交付设计，不自动合并。
