# Issue16交接

更新 2026-10-18T12:58:30+08:00，负责人@jieruiz；task/16-model-folders，base 7a506365cce42fd257f2645aa589b624e7d77116，独立目录C:/Users/86134/Documents/a_P_BIT/tmp/model-folders-issue16-20261018。

已完成本地三个模型目录、代码/配置/基线/结果索引和运行分派；路径/参数透传/不可变SHA验证已通过，代码和索引已推送；PR #17待审、未合并。原Llama2 PR15已合并、Issue14已关闭，merge见MERGE_ACCEPTANCE.md。

正式新增范围qwen/、llama1/、llama2/、scripts/model_workspace.py；根README只添加模型入口，个人STATUS及work/jieruiz/16为交付资料。没有移动历史源或结果；本次无Slurm/训练作业。接续先读Issue16、PR #17与STATUS，再按VALIDATION.md实际记录验证，不能把本地完成写为已上传。Projects仍缺read:project待同步。

模型/数据/硬件/采样配置与既有成果相同，路径与原字节SHA见各project.json及旧EXECUTION_MANIFEST/ARTIFACT索引。本任务属于目录/入口调整，不产生新的模型质量或芯片性能数字。新源码/资料SHA见manifest.json；最终提交见PR头/Issue评论，避免manifest自引用。

实际交付PR：https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/17。目录代码已推送、原Llama2 PR15已合并；二者状态分开。Issue16等待目录PR验收，不自动关闭。最终交付提交见Issue16评论和PR头。
