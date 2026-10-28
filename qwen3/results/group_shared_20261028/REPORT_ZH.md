# 每64元素共享尺度：运行阶段

2026-10-28T13:49:22+08:00；Issue206，负责人jieruiz。模型后训练Qwen/Qwen3-4B，依赖PR202@fbd67c39c57562d7d7947867493ed8227574f93b。

28项CPU/CUDA检查通过，pilot3210封存5项完成，源62blob/原字节SHA/36层覆盖核验通过。正式Slurm3211_[0-3]运行；尚未收齐完整三seed，暂不给共享尺度质量建议。

主协议为context2048、8x128=1024目标后缀，非完整WT2。固定W GU64与双随机GU256分别比较六种尺度方式：原逐元素、仅x groupmax、仅g/u groupmax、全部groupmax、全部trim1/64、全部trim4/64。g/u各自一套预冻结四档PoT；不在线重估S，不同token独立选档。原真实g sigmoid/P8、NL128/Wd固定W8/准确SDPA不改；共享指档号，并未改变随机源共享关系。

四次新BF16一致13.566049，固定W原路径首seed15.551865与PR202一致。每配置三seed；最终40主输出/37唯一，pilot5项独立保留。32目标pilot用于运行/吞吐，不和主PPL混算。按pilot和当前控制吞吐，固定W预计约20分钟，双随机三分片预计约60～90分钟；不是ASIC延迟。

选档可由三档超限标志OR/小计数完成；允许1/4项截断需计数判断，是有损对照。尺度值只在原四个PoT中选，不使用组最大值作为新S，也不进行排序。共享组内可以先归约再统一移位，减少逐元素档号及对齐；本轮没有新RTL/PT/PPA，不把潜在节省当实测。

运行源码qwen3/group_shared；SOURCE/SUBMISSION/ARTIFACT_AUDIT和恢复见work/jieruiz/206。科学执行4d6883b24ad27d9fa96feb84592696c374cfd808冻结，不修改、不重交健康任务。GU恢复仍上游FP32oracle，非全链路bittrue；用户0.81面积规则不涉及本次PPL。Projects缺read:project待同步。
