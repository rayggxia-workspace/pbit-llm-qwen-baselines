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
