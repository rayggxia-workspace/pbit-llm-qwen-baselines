# Issue16启动核实

时间 2026-10-18T12:58:30+08:00；负责人@jieruiz。仓库rayggxia-workspace/pbit-llm-qwen-baselines；分支task/16-model-folders，base pbit-tlm-attention-details-20261016 @7a506365cce42fd257f2645aa589b624e7d77116，工作目录C:/Users/86134/Documents/a_P_BIT/tmp/model-folders-issue16-20261018。

已读远端README、协作AGENTS blob9e9d2cc409ddcb636e97a38b7f97052c33344db8、状态索引、全部open Issue/PR和个人状态/交接。无目录整理重叠任务，其他待审任务工作树保持只读。

本次使用三个模型入口目录与薄运行分派，共享实现保持原路径。原因是原实验SHA和不可变执行输入约束；直接搬迁会破坏原始命令/manifest。目录配置列明路径和证据版本，避免用一个模型结果冒充另一个模型。未改权重/数据/硬件或采样协议，不需要重测GPU PPL。
