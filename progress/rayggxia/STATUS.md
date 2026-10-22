# rayggxia 当前任务

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
