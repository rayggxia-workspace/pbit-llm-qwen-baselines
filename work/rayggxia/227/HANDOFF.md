# Issue227共享调度交接（2026-11-01）

负责人rayggxia；正式仓库rayggxia-workspace/pbit-llm-qwen-baselines；分支task/227-shared-memory；目标main@7d42c7d30fa9c729c899ba7f815332dd6ed5671a。独立目录tmp/shared-memory-issue227-20261101，本地Git起点7874891；API发布只把本任务明确增量接到最新远端main，不强推不改其他成员分支。

先读architecture_tlm/shared_memory_20261101/REPORT_ZH.md、results/RESULTS.json、本EXECUTION_INDEX及本人STATUS，再查Issue227/关联PR，不重复提交已有作业。

已实现unified_v6共享请求/完成后端、全局64credits、8KiB返回FIFO、512个128bit单端口bank逐拍服务与逐bank容量检查、target双缓冲/直接填充、有限源写回保持、跨阶段预取和元数据访问。入口python -m architecture_tlm --shared-memory；原默认行为保留。16项机制检查通过。无新EDA/训练/PPL。

Slurm3638/3639小探针、3640原型、3641–3646 v2、3647/3648/3649 v3单层全部已有封存结果；确切源码/配置/输入/结果SHA见索引。旧电流负ACT实验保留作历史和时序消融。v3使用官方Micron同型号mempowerspec，默认不走PowerDown；8ch/2rank64GiB，PHY/VDDQ未知。配对v2只改电流时刻/SRAM完全一致，54.758627→49.957182mJ。v3异步直接填充5.459883ms/0.431708mJ SRAM/49.802673mJ DRAM；串行屏障8.834193ms/0.485296mJ/69.530172mJ，额外staging6.444903ms/0.638161mJ/57.642898mJ。均一层含embedding无lm_head、seed17，不叫整机结果。

**健康运行中3650**：/home/Hongjie_Zeng/projects/pbit-shared-memory-20261101-issue227/wholeofficial_v3_15da73345c7a，36层＋lm_head；源码归档SHA15da73345c7a991bc359ba92d3fdfb8e7389f6bfd0b2a5562b18a754c71739cb；官方配置SHA03fb3c30f2784f16a1f301d8f6bac3cba87b32101e41666c451896211ff9f147；输入SHA586be3c7d401a20ea06c578615a3de008e8308c83d72d64ed1618c52df178604。单CPU/8GiB、无GPU、6h上限，预计约2–3h；不得改冻结source。3场景按layer%3重用代表性地址事件，不是新36层数值capture。

本机原始证据project_archives/shared_memory227_20261101；包含source tar和逐phase结果/日志/原字节SHA。收集器work/rayggxia/227/deploy.py留本机，已有lab-server-ai授权，先status --phase all，确认完成再collect --phase wholeofficial_v3。不以sacct不可用/控制器记录过期推断失败；只用RESULT、完成日志、源码哈希确认，未封存保持运行/未知。

下一步：3650完成后，核对status=completed、36层GU/NL帧数218880/1751040、lm_head argmax151936、全局排空/物理容量/字节数，封存原件并运行build_report.py，更新同一PR/Issue/STATUS和MEMORY增量。若失败留失败原件，另建冻结修复执行，不改旧source、不重跑健康任务。不将一个seed或代表性流量当完整质量验收；需要随机敏感性时再明确补seed503/1009。

原默认TLM、Issue186/225及其他成员冻结原件保持。两个本地module_handoff包未公开；本任务仅引用已公开PPA标量，不上传原包、私有fixture、工艺库、凭据、大trace。Projects连接器无写接口，待维护者同步；根长期备忘录维护任务Issue28需合并本MEMORY_UPDATE，不用本地混合union覆盖远端正式根文件。

当前完整芯片能耗/面积仍不闭合：本轮只验证存储事件及能量，不将新的DDR核心能量与旧片上预算直接拼加，不将100MHz核周期当已过500MHz STA，不为定制CIM外围/随机源/互联/跨K/转换未知项填0。
