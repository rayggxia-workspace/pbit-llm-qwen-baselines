# 单次后台延续与补测交接

正式质量作业2878已经在服务器运行，固定源8d60abe4e7c5；完整WT2 PPL已核验并上传，三任务尚在执行。此包是本机编排程序的审阅快照，不是可在任意目录直接执行的新模型入口。

实际本机入口是DAC工作区`outputs/sparq23/watch_quality.py`，运行状态写同目录`WATCH_QUALITY_STATE.json`，独占启动记录`WATCH_QUALITY_LOCK.json`。单次监控最多13小时，每45秒只读查调度、每180秒下载已完成JSON。完整PPL、每个完整任务与终态触发独立校验/分支提交/PR更新。未通过验证、Git工作树/HEAD被外部修改、源码散列变化或发布失败均停止并保留恢复状态，不猜测结果，不自动重放状态变更。

仅当2878为COMPLETED且完整质量已独立核验，才调用`measurement_continuation.py`；先核三台本人GPU队列，独占锁和排他submit intent防重复，然后最多提交一个单GPU补测。固定补测源a430ca231792，13文件导出、tar和脚本SHA均已核；暂存到本人`/home/Weican_Chen/projects/sparq-qwen3-issue157/measurement-source-a430ca231792`，本交接创建时尚未提交。补测结果使用全新identity/目录，原质量数值源不变。没有任何SparQ RTL/STA物理PPA结果。

补测首个终态立即保存，下载后验证源/父身份/envelope/54trial/功率积分和报告散列，再上传独立结果。GPU功率采样可用性以实际报告为准，null不会补造；没有隔离的ASIC能量归因。

本机需保持后台Python进程存活才能继续自动归档/补测；本机断连不代表远端2878停止。恢复先检查本机PID、lock、WATCH状态、Slurm及所有提交意图/回执，不能直接删锁重跑。已有sbatch intent而无job回执时先查本人队列和scheduler identity，不能再次提交。后台不发送新的成员通知，不自动合并PR，不恢复116/123。

本包15项报告器、12项补测CLI、12项benchmark辅助、3项watch、4+3项归档/发布描述测试已通过，并经过独立审查；完整CPU原生模型门禁51项在2877通过。正式模型质量与物理PPA仍按对应结果独立判断。
