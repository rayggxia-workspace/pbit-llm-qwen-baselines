# Issue22 可继续执行的交接

2026-10-18T18:30:38+08:00，@jieruiz；本地/分支/base见个人STATUS。

1. 只在独立checkout C:/Users/86134/Documents/a_P_BIT/tmp/qwen-short-stream-issue22-20261018工作；RTL子代理有独立checkout tmp/qwen-short-stream-rtl-issue22-20261018，不在旧Issue7工艺包改动。目标workspace，origin个人历史仓库不能推。
2. 正式估算脚本qwen/energy/short_stream_20261018/estimate_energy.py提交62a34e7。命令：python该脚本 --output qwen/energy/short_stream_20261018/results_v1；必须新目录，先提交准确LF脚本。现4组数据与ARTIFACT_MANIFEST保留，不覆盖。只改samples，完整模型和输出源hash随JSON。
3. 独立核算辅助归档在a_P_BIT/tmp/issue22_energy_audit_out，17项SHA manifest；本任务ENERGY_VALIDATION.json给其manifest SHA及4组交叉相等结果。未复制第二套正式大数据，正式结果只有results_v1。
4. 历史Qwen在pbit_shared_rng_ffn_20261015。HISTORICAL_QWEN_AUDIT.json核旧源码与原结果hash；A8=q/256+sign，固定W±127，准确SiLU再Sz。没有新Qwen短流PPL，本地小raw不是完整WT2，后续须先在服务器核模型/原文/IDs+重跑BF16。此次无新增Slurm。
5. 当前RTL已经实际功能/活动验证，合入后核最终SHA与验证记录一致。原始VCD/vvp保留子代理本地且不进Git，生成脚本和小型验证JSON/日志随交付。源/前端可共享，不把单列含源top整套乘64；外部SRAM/seed保持仍需计费。
6. ppa目录是DC/PT模板而非运行结果。100MHz相同SS条件；同27bit累加器比较IID/strat/enum，再测短流缩位。需要用户工艺环境返回hierarchy power、area、timing、coverage、窗口和网表/VCD/SHA；保持配置/seed装载与计算能量分开。
7. 发现Windows core.autocrlf使3个旧锚点工作字节变化，已恢复为Git blob，新增窄-text；工作文件和旧manifest SHA现吻合，源语义不改。不要为过检查改hash。
8. 本阶段交付应为任务分支/PR，未获本次新RTL的合并指令，不把PR待审写成已合并。更新Issue22验收/STATUS，Projects缺read:project待同步。Issue19不关闭。
