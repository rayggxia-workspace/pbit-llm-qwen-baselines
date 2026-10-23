用TRAIN离线固定四档代替每token/64路动态absmax，检查FFN能否省去在线范围归约。选出的四档是S、S/4、S/16、S/64；S按层、信号及64通道组固定，推理不扩档。

已完成Qwen2.5-0.5B全24层FFN、原准确attention的21项完整WT2，采样各三seed：BF16 11.652735；动态32 11.736131；固定32 11.851810；固定64 11.736412。只固定x32 11.746519，主要差距在z。固定64接近动态32，但采样翻倍，不能仅据此声称能耗下降。

验证：同轮BF16和模型/语料/源码SHA门槛；12项TRAIN候选及4项独立holdout；37份评分记录原字节/配置/尺度/24层全部输入覆盖验证，0缺失0无效；17新内核+13stratified+12multiscale测试。Slurm2840/2841/2842，执行49bc6bd冻结。较大原件只在服务器/本地压缩归档，83成员SHA与恢复索引齐全，Git保留必要表/汇总。

报告qwen/results/static_multiscale_20261023/REPORT_ZH.md；任务Issue #150。无新RTL/PPA/TLM或联合随机attention验证；不自动合并。Projects缺read:project，待维护者同步看板。
