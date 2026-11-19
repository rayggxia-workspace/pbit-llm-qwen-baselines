# Issue259交接

负责人rayggxia；分支task/259-w8-dense-original，目标main；基线206bf81f18ea88c4c625ce8d32edd18a58edd1cd。
独立稀疏目录：C:/Users/86134/Documents/a_P_BIT/tmp/w8-dense-original-issue259-20261118。

范围：原始后训练Qwen3-4B的FFN W8-only、稠密BF16 Attention完整WT2 PPL。不是训练后确定性模型；不改变P8/概率实现、TLM或论文。

已完成：读取最新远端README/AGENTS、本人STATUS及W8相关Issue，核实连接器登录rayggxia；现有8.742652使用训练后权重，缺少本项original控制。服务器已连接，Slurm在/opt/slurm/21.08.8/bin，检查时本人队列无运行任务、八张5090空闲。

已实现并验证：固定tile64 PoT W8量化、CPU独立标量/既有初始化比对、GPU与CPU数值门禁、原评测器完整BF16与W8连续执行、108权重SHA、所有36层覆盖及NLL/目标位置核验。

实际作业：CPU5896通过；GPU5897 COMPLETED/0:0，1卡4CPU48GiB，时长1分54秒。不可变执行目录为/home/Hongjie_Zeng/projects/pbit-w8-dense-original-issue259-20261118/run_d20328393f5f；执行本地代码提交47b9dfc10ebecdb021659ca994ccbbbe32c22c96，准确执行runner SHA为b3a645d9b38c13dd6ff6e44bad22ae17ca51b36389980bfbc50617e6f8c709db；交付含同字节runner及后加结果/收集脚本，不把后加元数据称为执行前已存在。

完整结果：BF16=11.537160373065971，W8 original dense=11.483210645174708，相对-0.467617%。CPU/GPU门禁、292窗/299077目标连续覆盖、36层各597062前传token、108矩阵、封存SHA及NLL核验通过。原始源码和结果已逐SHA收进project_archives/w8_dense_original259_20261118/d20328393f5f-results.zip，准确SHA见RESULTS.json。该目录可恢复，不重跑昂贵历史实验。

成果位置：experiments/w8_dense_original_20261118。大模型及原始语料只读取服务器既有授权路径；结果原件保留本人新项目目录，Git不复制模型。

本地评测与归档已完成；发布与PR状态见PUBLICATION.json（尚无该文件时不能声称已上传）。下一步核对PR文件和源码字节、同步Issue阶段；不自动合并。Projects待同步。

## 2026-11-19 UTC：补齐三组统一cached数字对照

用户要求确认BF16/W8/W8＋K筛选的PPL，缺项提交。旧向量化BF16/W8结果已完成并保留；缺的是原始W8＋SparQ K128准确Softmax/PV。为与筛选路径采用相同计分器，新批同时补cached BF16/W8控制，不重写旧结果。

新源码experiments/w8_dense_original_20261118/screen/，执行本地提交071e36e61823cd0aea8c2708dfc740bc8d841b38，screen_runner SHA f9d07d8974894bcb2322b0216b7fe7a6acf1c43247242c26b135de08bff9b821；后加collect仅为收集脚本，未改冻结runner。

服务器/home/Hongjie_Zeng/projects/pbit-w8-dense-original-issue259-20261118/screen_be7740802af7。CPU5898通过5个原筛选器与计分测试及原W8量化预检；GPU5899通过原生/包装SDPA逐位一致、真实W8筛选16query×36层和禁止随机调用门禁，重跑BF16向量化锚点仍为11.537160373065971。数组5900_0/1/2于01:15UTC核为RUNNING，分别BF16_dense/W8_dense/W8_SparQ128_exactPV；当前尚无完整cached PPL。

配置原始Qwen3-4B，FFN仅W8权重量化；r32、总K128含最近32、四Q共享候选；候选FP32准确QK/Softmax/完整PV，BF16接口，无采样/训练后权重覆盖。2048窗/1024步长、292窗299077唯一目标，未计分前缀原生，计分位置36层全部单token执行，batch_windows32。三GPU独立任务、每项4CPU48GiB/6h时限，非预计耗时，未设置人工并行上限。

恢复命令：python experiments/w8_dense_original_20261118/screen/ops.py status。只在三份COMPLETE均封存后运行同入口collect，验证SHA/连续位置/NLL/36层覆盖并归档。缺失、运行中、失败分开，不填部分PPL，不重交健康任务；修复另建执行目录，原快照保持不可变。结果依旧交付同一PR260，Issue259保持开放，Projects待同步。
