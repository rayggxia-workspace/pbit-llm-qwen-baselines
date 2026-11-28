# FP24指数范围与0.5B验证交接

2026-11-27，负责人rayggxia，Issue225/PR266，分支task/225-cim-bank32-20261124，工作目录tmp/cim-bank32-tlm-issue225-20261124。验收已完成，PR待审未合并，广义Issue225不关闭。

执行源码00e025c4671aa61751d6585b5ab874b13e93e3af；只读FP24依赖d81f77f179e1e8220afed3b7ecfe9bd5510ce555，原动态尺度冻结源0d1e85176fd52205669148296c585a06c47bc369。scan_v1/62266旧快照保留，正式复核scan_v2/62268与small_v1/62267均COMPLETED/0:0，5/87秒。两个新任务内各6项单测通过。

报告experiments/fp_state_exponent_20261127/REPORT_ZH.md及RESULTS.json/sha。4B写回指数GU−18..7、Wd−18..12；0.5B为−17..3、−17..10。E6/M15写回状态与E8/M15同值且无上下溢；E5/M15有少量下溢。22位为存储候选，不改64位默认、RTL/TLM或PPA；物理宏打包不一定省容量。

0.5B固定Qwen/Qwen2.5-0.5B-Instruct、revision7ae557604adf67be50417f59c2c2f167def9a775，原缓存Base未使用。官方LFS SHA与7文件核验，模型在/lustre/home/lgzhang/zhj/fp-state-range225-20261127/assets/qwen05。完整原BF16 WT2 PPL12.8361204065（292窗/299077目标）；局部随机FFN回放为W8/16/32、组64PoT+S/S2，3上下文×24层×GU/Wd=144样本，GU14/Wd76个K64全链。144轨迹SHA、GPU整数参考、模型文件、完整基线账本和不改变原生logits检查通过。不是0.5B采样模型PPL，也不是已训练的0.5B T64。

服务器个人根/lustre/home/lgzhang/zhj/fp-state-range225-20261127，small_v1/outputs和scan_v2/outputs只读。本目录对应version/original保存原JSON/源码包/日志/作业脚本，COLLECTION_CHECKS.json保存各SHA；没有复制大权重/NPZ。Slurm提交原命令见各SUBMISSION.json，job.sh见original。可用原任务个人venv/python复查，依赖目录/t64-fp24-state225-20261127/run_v1/code及/t64-narrow-state225-20261127/run_v2保持冻结。

整数FP24→P8与当前参考逐项一致；raw-g sigmoid地址也已独立核对。但现有模型用P8重建g，4B/0.5B有3.78%/3.54%的g最终阈值与raw-g不同，不能静默切换。下一步可将FP24/22真正接入模型前向验证PPL，并综合共享浮点转换/加法器；本轮不提交这类新任务。

本地根/Issue28工作目录的PROJECT_MEMORY同字节同步；远端Issue28仍按原维护流程待同步。Projects未操作。发布回执见PUBLICATION.json；没有回执的状态不能写成已推送。
