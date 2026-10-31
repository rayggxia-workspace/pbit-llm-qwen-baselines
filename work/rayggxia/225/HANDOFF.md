# Issue225：新模块整机初估交接

owner rayggxia，task/225-module-estimate，目标main@7d42c7d30fa9c729c899ba7f815332dd6ed5671a。独立本地目录tmp/module-estimate-issue225-20261031，最小稀疏checkout复用7874891对象；API发布以远端main为父，不强推本地不同历史。

用户要求先估两份module_handoff对整机时间/功耗的影响；新增architecture_tlm/module_estimate_20261031，包含INPUTS、estimate.py、REPORT、VALIDATION和JSON/CSV。13来源SHA及三原摘要核验、账目和时间资源不变量通过。256个NL核＋8KV组约51.67–53.71ms、74.22–77.62mJ片上（含旧FFN组合RNG预算预留）；串行或缩核会更慢，见报告。无完整TLM/DRAMSys/EDA/训练/PPL，未改原源码/冻结结果/主线默认。

只发布本任务新估算和小型来源标量，不复制两个未公开交接包、不上传宽历史/工艺/IP/凭据。旧FMA整机HBM与局部DDR4参考作为宏条件区分；DDR4全模型TPOT与完整系统PPA保持null。k128/F4/burn0硬件候选不能继承训练k256或旧理想PPL。Projects无工具接口待维护者同步。

下一步：按新模块工作单位做unified_v6适配和固定配置共享后端重放；优先验证8组端口/竞争、NL外部保持/纯RNG/待机，不重跑已有RTL/PPL。本人STATUS维护在本地同名入口，本任务公开状态以Issue225及本交接/发布回执为准；不重传受限宽历史。PR/发布后状态见PUBLICATION.json。
