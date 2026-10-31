## 2026-10-31 Issue204：非线性到Wd集成PPA已交付

负责人rayggxia，PR219/base task/206-group64-scale，科学结果提交36426f4ed48cce32cd3bd06bcf95ee62aa4accb7，open待审未合并。工作目录tmp/matrix-t32-issue204-20261028；本地历史分支task/204-bf16-baseline不整支推送，远端为task/204-gu-unified-code。

用户确认从已编码g/u开始。N64/M8/T32，SS1.08V125℃100MHz，34拍/340ns输出8点积；64完整Sigmoid LUT、192比较器及三流AND共用前端实际驱动8列固定Wd。raw面积仅乘.81一次。8/9位等价weighted归约436.6733/479.8533pJ/帧、.110074043/.118259255mm²；OR4/signed9为458.7733/467.9533pJ、.083171610/.087664291mm²。逐拍加权树后每列一个signed19累加器，与位平面exact的激励和oracle字节一致，不是输入先计数。

8配置/48PT全部完成，RTL及门级各11496逐拍PASS，100%映射叶单元活动覆盖；Slurm38475207/38475302/38475377/38475382均COMPLETED/0:0，无本轮遗留作业，不重交。68返回原件及1720归档成员SHA验证；两冻结源包不改。小源码ZIP SHA d99d30965a036efb1d3fc097a3cb61cbe4c188b73559eed15010a9e7b6bfe30d。15发布文件blob逐一远端核验。

报告/小汇总/源码索引：architecture_tlm/nonlinear_wd_integrated_20261031/results/。统一run nonlinear-wd-integrated-204-20261031，任务71/根镜像103/本PR47各自check/render PASS，保留旧record；未上传全局路径或归档CSV。源/原件归档project_archives/nonlinear_wd204_20261031；本地PUBLICATION.json、TRANSFER_VERIFICATION.json、REGISTRY_CHECK.json及LOCAL_RECOVERY.json可恢复。72生成fixture和54审核helper文件逐SHA归档后回收，本地PR目录保留。

weighted setup只15.3ps/1.8ps、hold30.1ps，功耗ramp告警保留，未物理签核。OR4与signed9饱和是近似；四档尺度和活动为合成，未做模型质量/PPL。GU/写前编码/SRAM/真实随机源与广播/跨K/BF16恢复/CTS/SDF/SPEF不在本轮。两共享LFSR旧价格24.8769pJ/帧仅条件代理，不当集成实测。下一步：审阅本PR，按真实活动验证近似质量并闭合实际外围/物理时序，不自动启动昂贵模型或新EDA。Projects写能力受既有工具限制，待维护者同步。Issue204保持open。

---

## Issue204：g/u单份9位与总8位码试验（2026-10-30）

负责人rayggxia；新交付分支task/204-gu-unified-code，依赖PR207@104a2e49，PR base为task/206-group64-scale。原独立目录tmp/matrix-t32-issue204-20261028/task/204-bf16-baseline只作本地执行，不推送其预算宽历史。

本轮模型小测已完成：同后训练Qwen3-4B/准确SDPA、8固定片段共1024目标、全36FFN及前缀；BF1613.566049、原17.921546±.266163、单g数值码raw9=17.511391±.246922、raw8=17.882045±.286634。直接复用裁剪幅值码的另一族严重失败，原件及原因保留。没有新训练/尺度拟合/完整WT2/RTL/PPA或默认变更。

26CPU通过2CUDA跳过、GPU28通过；86冻结依赖源、模型/语料/尺度/计分位置/118原件SHA及两归档逐成员核验，旧BF16/三seed严格重放。3502/3503/3504及3507/3508/3509完成，最终队列为空；3499测试参考dtype失败及未执行依赖撤销有恢复记录。正式experiments/gu_unified_codec_20261030/results/REPORT_ZH.md；交接work/rayggxia/204/unified_gu/HANDOFF.md。仅本轮小型代码/结果增量交付，科学交付934ab21a、PR219 open待审，23文件Git树和5个关键文件读回一致；回执见work/rayggxia/204/unified_gu/PUBLICATION.json。未合并、不关闭Issue。项目看板无已知写工具，待维护者同步。

下一步为两种格式的编码/解码、LUT、SRAM接口模块PPA及完整WT2确认；本轮不自动追加执行。下方原公开状态保留。

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
