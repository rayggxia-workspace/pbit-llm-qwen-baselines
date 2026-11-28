# 给x也增加逐元素1bit：16/32单因素评测

Issue225/PR266，负责人rayggxia。保持训练100M的T64/W8、g/u组64基准+S/S2、真实幅度sigmoid P8 LUT、16层共享R8输入分层、4×2×4后级联合采样与AND直连整数Wd，只改变x：每64项动态ceilPoT基准S，每元素一位选择S或S/2。尺度下限2^-6、x上限512；小档低于下限时禁用。没有新增训练或改变Attention。

x采用与已验证g/u同一个half.encode，恢复指数随元素送入原GU整数对齐后累加；不能先把不同尺度计数混加。关闭新x标志必须与旧动态64编码及模型logits逐位一致。新的XOnebitOverride仅替换dynamic.encode这一入口，旧g/u、权重和数值归约源码不改；退出时恢复所有函数。

评测：单部署seed101；完整PIQA1838/ARC-C1172（25分片、2完整组，全题干答案36层FFN，无模板/截断）；新候选与原四档各一份完整WT2（292窗299077目标、2048/1024），另在相同8窗9215目标上比较原四档、x原四档+g/uS2、x纯共享+g/uS2、新x/g/u均基准+S2。完整与子集分开报告。

CPU Slurm先跑原14项及新5项编码/位宽/题覆盖测试。GPU门禁重做完整BF16、权重/数据/harness身份核对、关闭x标志的logits逐位一致、新候选重复一致和原S2任务逐答案分数回放。通过后PPL作业和一张任务worker并行，最多两张A6000。旧完整任务对照只读复用，不重复运行。收集器同时检查PPL和完整任务，未齐写incomplete。

执行快照提交后冻结；源码/配置/模型/数据SHA与Slurm命令记入work/rayggxia/225/x_onebit_20261127/HANDOFF.md及SUBMISSION.json。正式入口runner.py --settings SETTINGS --phase cpu/gate/ppl/worker，collect.py ROOT。当前没有新GPU结果，不改变RTL/PPA/TLM默认或自动合并PR。
