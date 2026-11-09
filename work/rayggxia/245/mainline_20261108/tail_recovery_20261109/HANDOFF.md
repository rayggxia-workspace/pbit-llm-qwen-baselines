## 2026-11-09：55nm三模型TLM已封存28/36，漏接三尾项已补交

北京时间11:47实核，Qwen12/12、Llama12/12、DeepSeek4/12，全部计入项有全层+head、VALIDATION及SEAL逐SHA；原历史失败6项与当前待做分开。剩8项：24/27/30/31及32/33/34运行，35由健康worker3随后执行。Qwen100概率约54.216ms，250约50.428ms；本批动态数制访存成本较225独立批略不同，不能混seed。

发现原恢复只补24/25/26而漏其后32/33/34。三项从未启动、原worker0/1/2失败及无输出目录已核实；新CPU数组38638359三项已RUNNING且无Traceback，沿原冻结driver/manifest，不改算法/硬件/价格，不重跑健康case。旧等待汇总38634118已核名/状态后取消，改38638371等待所有活跃任务；首汇总依赖含已被控制器回收的完成job而拒绝，依durable receipt仅补汇总，没有重复tail。

按已有DeepSeek约7h/项及数字工作量估计全批再8–12h CPU墙钟，非保证。当前不是36项最终结果，不宣布PR合并。正式RUN_STATUS_20261109.json和STATUS_20261109_ZH.md；恢复tail_status_20261109.py与repair_status.py两者结合，不能只读旧聚合ID。Issue245/PR247发布以tail_recovery_20261109/PUBLICATION.json为准，Projects待维护者同步。

恢复不得重跑tail_submit/tail_finish；只读两个status脚本。全部36项封存后执行新的aggregate入口并下载校验，更新本任务PR，不自动合并。未运行中的源/状态不能当实验结果。
