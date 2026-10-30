# Issue212 发布回执

- PR：https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/214；待审、未合并。
- 负责人：rayggxia。正式测量Slurm3399已完成，3389预检、3398门禁已通过，无运行中测量任务，不重跑。
- 科学交付：4a214468f9d508e34de881045f1ee489186c459e；冻结执行源码：20d46ec7f04021e90bba42312681ad4f7bbe81ee。
- 报告：results/gpu_decode_energy_20261029/REPORT_ZH.md；明细：MODULES.csv、WHOLE.csv；原字节校验索引：raw/ARTIFACT_MANIFEST.json。
- 2K原生decode25.720ms/token、5.931J/token；CUDA Graph固定forward10.531ms、3.928J。8K分别25.756ms/8.438J与16.774ms/7.823J。两种执行边界分开，模块隔离回放能量不可相加。
- 8项CPU检查、logits逐位一致、36层覆盖、模型/输入/源码及封存产物SHA均通过。未做PPL/训练/EDA，不把条件TLM预算当芯片实测。
- 完整历史STATUS/交接的后续同步被自动审批拒绝，本回执仅包含本任务公开成果；本地状态已更新，以本回执和Issue212最新回复确认远端发布阶段。
- 本连接器无Projects操作接口，看板未同步；Issue212保持open，等待PR评审。
