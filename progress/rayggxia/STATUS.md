# Issue141 Qwen新采样器联合PPL（2026-10-23）

负责人rayggxia，任务分支task/141-qwen-sampler-ppl，PR143 draft/open未合并；base6966739，独立tmp/qwen-sampler-ppl-issue141-20261023，不修改Issue138训练目录，不恢复116/123。执行7a286ec140de6846006c96456275377fd22b4943已推送；正式结果qwen/results/parallel_sampler_ppl_20261023。

2802仅缺历史两校准资产而失败；新快照按原SHA补齐，2803已完成SHA门禁、原BF16完整299077目标11.652735047455899、12组GPU轨迹/分布＋仲裁/cap检查、6项8目标pilot。10个sidecar与identity本机回读通过。2804_[0-15]%2后缀4096目标运行；2805_[0-15]%2完整299077目标依赖afterok:2804，已提交未完成。每协议16配置，随机配置3seed；精确参数看正式README/PLAN。理想软件随机，不把结果继承给物理RNG或q256。

服务器/home/Hongjie_Zeng/projects/pbit-qwen-sampler-ppl-20261023-issue141；快照snapshots/7a286ec140de6846006c96456275377fd22b4943，输出outputs/同SHA；源码不改。回执work/rayggxia/141/remote/workers-submission.json。下一步只读squeue/sacct及已完成JSON，核对sidecar和每层覆盖，分别汇总后缀/完整。不要重交健康作业；不因pilot排序，不把pending写成完成。失败作业修复另冻执行源，保留旧原件。看板权限本轮未核，待同步；PR附加UI因侧会话thread not found失败，GitHub PR已实际创建。

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

## 2026-10-23 Issue141后缀16项已核验，完整WT2已启动

2804已全部完成；16唯一配置SHA/identity/config/24层4096目标与NLL回算通过。后缀三seed均值：BF16 10.3715568、FFN-only10.4273772、筛选准确PV10.9703677、旧CTMC128 11.1978127、新校正拒绝128 11.1645223、赢家1024 11.0437051。赢家用了8倍更新预算，不能称同成本优势；以上非完整WT2。完整2805已自动启动，按最多2GPU运行，未收齐，不重交。原件project_archives/qwen_sampler_ppl_issue141_20261023/suffix及服务器对应outputs/7a286ec.../suffix；汇总qwen/results/parallel_sampler_ppl_20261023/SUFFIX_SUMMARY.json，恢复work/rayggxia/141/HANDOFF.md。Git直连回执推送超时后API发布90548ac（与本地b5ef627完全同树）；新后缀增量以PR143实时head为准。执行7a286ec源码未改。