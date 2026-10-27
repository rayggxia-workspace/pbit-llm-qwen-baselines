## 2026-10-27：Issue159七组单因素训练交接（rayggxia）

用户确认：B0=W8/tile64-PoT/T32；W6/W10只改位宽；S1/S3只改共享粒度；T16/T64只改采样，共七组，不做27种组合。三种共享方式都冻结二次幂尺度。定义文件qwen3/training/seven_case_ffn_20261027/REMOTE_AGENT_PLAN_ZH.md及CASES.json；PoT量化、冻结指数、S1/S3离线映射和W10参考一并提供。

分支task/159-seven-case-pot64-plan；依赖PR178@216f2b9939e9984f140290c98edb05db3aad5c0f，目标PR base task/177-trainable-and-ffn。范围仅新计划/参考组件，不接管jieruiz原任务或主线程存储调度。七组全模型IID训练器仍需远端Agent接入；原参考输入64/joint32和FFN-only不当作已完成的七组runner。

实际验证：七组单因素/13文件引用检查；52项CPU组件测试48通过4CUDA跳过；没有提交GPU/Slurm、没有新4B PPL/训练或RTL/PPA。任务发布及逐文件回读以work/rayggxia/159/PLAN_PUBLICATION.json为准；创建PR不等于合并。Projects待有权限的界面/维护者同步，未在本侧同步本机根长期备忘录镜像。

下一步：执行Agent核对最新Issue159/177和运行快照，在独立执行分支补全共同T与全模型CE/KL接入、整数数值边界、2步GPU门禁及吞吐预算，再按七组清单运行；保留当前健康作业和冻结源码。不得复用旧PPL冒充新PoT权重。

---

# rayggxia 当前任务

## Issue112 资源预算与片上存储探索计划

- 更新时间：2026-10-22；负责人：rayggxia（本轮连接器已核实）。
- 分支：task/112-resource-budget-plan；PR base：pbit-tlm-attention-details-20261016@eb317e4f6fb1b0d8844887401f3275f128ef8a83。
- 工作目录：C:/Users/86134/Documents/a_P_BIT/tmp/resource-budget-issue112-20261022，独立最小稀疏worktree。
- 阶段：中文实施计划已上传PR114，ready/open待审、未合并；来源提交18c2a62f4a6cee4cf2a7df62594510a35073639d，4份来源文件远端回读一致。最终回执见work/rayggxia/112/PUBLICATION.json及Issue112，不自动合并/关闭。
- 成果：architecture_tlm/resource_budget_plan_20261022/PLAN_ZH.md；本机pbit_llm_master_report_20261012/PBIT_LLM_ASIC_RESOURCE_PLAN_ZH_20261022.md为同字节阅读副本。
- 验证：12个固定Git文件链接解析、四份封存结果数值、FFN/KV容量/带宽下界、UTF-8/LF和阅读副本SHA通过；记录work/rayggxia/112/VALIDATION.json。
- 边界：仅计划/文档核算，无新PPL/GPU/Slurm/TLM/RTL/EDA/DRAMSys；2/4MiB非最优结论，完整物理PPA保持null。
- 待同步：当前连接器未提供Projects操作；唯一备忘录维护源的入口追加由其维护流程处理，拟文见HANDOFF，不覆盖其他工作树增量。
- 下一步：PR审阅；后续从资源账本、条件下界和恢复/供数流水开始执行。本任务未接管95/96/104/107/110。

以下保留此前状态的历史快照；Issue98/PR100及Issue95/PR97已进入本任务集成基线，不将旧“待审”文字作为当前状态。

更新时间：2026-10-22；本会话 GitHub 连接器实际账号 rayggxia。

## Issue98：benchmark / LLM质量 / PPA统一调研

- 分支：task/98-benchmark-protocol；PR base：pbit-tlm-attention-details-20261016@83e15289434af50fc09c35e699d8b39965389d98。
- 工作目录：C:/Users/86134/Documents/a_P_BIT/tmp/benchmark-protocol-issue98-20261022，最小稀疏 worktree。
- 阶段：研究文档、16篇结构化对照与协议已上传；PR100开放待审未合并，源提交618b85ac59e4823497dc8ae7083aefc75247b7f4，9份来源文件已远端读回一致。最终发布状态见work/rayggxia/98/PUBLICATION.json；不关闭Issue。
- 验证：work/rayggxia/98/verify.py，33项文档/数据一致性、来源制品hash、Git内链接及例子复算通过；不是33项模型或PPA测试。
- 成果：architecture_tlm/benchmark_protocol_20261022/README_ZH.md、PAPERS.json/.csv、PROTOCOL_PROPOSAL.json。
- 未运行：模型、训练、GPU、Slurm、TLM、EDA；协议/质量门槛是提议，未知物理成本仍null。
- 待同步：Projects权限/写入未核实；长期备忘录唯一维护目录已有其他任务未提交增量，不覆盖。待合并/维护时追加本研究入口，拟追加文字在HANDOFF。
- 下一步：PR100评审验收；质量预算与协议评审后再决定新实验。接口实现仍由Issue95/96负责。

## 并行既有任务保留

Issue95随机源模型/RTL已由本账号发布PR97，开放待审未合并；其工作目录、进度及实际验证以 task/95-rng-service-rtl 的 work/rayggxia/95/HANDOFF.md / PUBLICATION.json为准。本分支没有修改其源码、默认配置、冻结结果或工作目录，也未接管Issue96等成员任务。

## 2026-10-22 Issue95 架构图续作

PR97已合并（上文旧状态为历史）；当前新增离线架构核对图，源码/数值模型/RTL未改。task/95-rng-architecture-view基于eb317e4f，目标pbit-tlm-attention-details-20261016。12场景372沿由原模型导出；11模块交互及1440/768/390宽度浏览器检查通过，无JS错误。文件architecture_tlm/random_service/architecture-view.html；恢复work/rayggxia/95/VISUALIZATION_HANDOFF.md。已注明PR103小接口与38322118后续布局前PPA边界。待文档PR评审与用户核对，不代表整机已全部换源；Projects同步未核实。本节不改变Issue98记录。

可视化交付PR：https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/113，开放待审、未合并；源提交bc8561813c110b62829287661c1303c65a2d14b0。远端HTML已读回与本地逐字符一致。
