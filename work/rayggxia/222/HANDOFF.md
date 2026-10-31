# Issue222交接

负责人rayggxia；task/222-sparq-sampling-budget，目标rayggxia-workspace/pbit-llm-qwen-baselines，远端base main@7d42c7d30fa9c729c899ba7f815332dd6ed5671a；独立本地tmp/sparq-sampling-budget-issue222-20261031。

用户授权先测试SparQ后较低S及K128是否过少，再更新训练方案。复用Issue198冻结依赖，新增P8接口和采样预算探针，旧源只读。正式代码experiments/sparq_budget_probe_20261031。CPU编译/静态检查不是GPU门禁，GPU结果只有status=completed且SHA通过才可汇总。

远端个人目录、精确源SHA与Slurm ID见私有提交回执；不重交健康任务。首先preflight，之后afterok三seed short；原BF16每seed新跑。主短流512目标，不作为完整WT2；未知真实模型结论和PPA不填。

恢复先核Issue222/相关PR、队列、SOURCE/SUBMISSION/COLLECTION，保留执行快照，失败修复新建源版本。不得修改原Issue198/PR199或Issue220训练清单，入选S/K之后再有版本地提出范围更新。
