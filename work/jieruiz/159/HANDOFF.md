## Issue159远程执行交接v2：INT4/INT6/INT8（2026-10-23）

用户要求面向远程Agent，并增加INT4/INT6，其他设置不变、工作3倍。正式入口qwen3/training/sc_qat_20261023/REMOTE_AGENT_START_HERE_ZH.md，附环境/逐seed结果JSON模板。每项实验36层gate/up/down统一Wb，三套各19项=57计划（48随机+9控制，A总114亿有效token）；BF16三个是配对重复，不是三位宽结构或三训练seed。输入仍A8、共享64、原尺度/采样/优化器设置保持，跨位宽清单一致性通过。

补明确源码/依赖、待实现模块、独立120步G2课程、checkpoint随机重放、位宽/容器区别、Slurm及回传门槛。PR160已有非Base准备，revision1cfa9a7208912126459214e8b04321603b3df60c；依赖读取head98954637，22:45交接的2869/2870状态不当实时队列，恢复先查避免重复。本任务无新训练器/GPU/Slurm/PPL；v2清单/模板/启动拒绝与独立审阅通过。继续同PR161，实际发布见work/jieruiz/159/remote_agent_v2/PUBLICATION.json；不合并不关闭，Projects待权限。

## Issue159 实际发布：2026-10-23

Qwen/Qwen3-4B非Base训练设计已推送PR161，科学提交6991c97f9d54c1d9ea17ee2ce87f44d08b6677f4；远端设计文件原字节核验通过，Issue159已同步。PR待审未合并，无GPU训练/新PPL；后续执行需模型revision/数据/训练器/H200环境。19项是计划配置，不是已运行结果。work/jieruiz/159/FINAL_RECEIPT.json为回执；Projects待权限同步。

# Issue159 交接

负责人jieruiz；task/159-qwen3-sc-qat-plan；base pbit-tlm-attention-details-20261016@2f23344948cfd43e9ab7061f77ea6d3f4a2c2527。
独立稀疏目录tmp/qwen3-qat-plan-issue159-20261023。正式文件qwen3/training/sc_qat_20261023/TRAINING_PLAN_ZH.md、SCAN_MANIFEST.json、scan.py。

用户最后确认Qwen/Qwen3-4B非Base。教师/学生均相同模型，36层W8随机FFN全模型训练；D/F/L/H四尺度策略、T8/16/32/64共16组加3控制。B/d与IID分阶段扫描。PR147和153只作历史机制证据。

已完成方案与19计划配置校验、语法解析、launch-ready拒绝守卫及独立审阅。没有训练器实现、模型下载、H200训练/评测、RTL/PPA/TLM改动或Slurm任务。

下一步：确认模型revision及权重/模板SHA、H200个人Slurm环境、许可数据与manifest；实现可训练FFN/校准/蒸馏/导出，先完成逐拍oracle、梯度与随机重放，再重测非Base基线和profile。不能把null revision或设计清单直接用于启动，不重复PR147旧Base实验。

实际上传状态以PUBLICATION.json与FINAL_RECEIPT.json为准。当前准备任务PR，不自动合并/关闭Issue。Projects既有read:project权限缺口待同步，不等于Git仓库无写权限。原始大权重/数据均不进入本PR。
