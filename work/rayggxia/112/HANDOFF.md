# Issue112 资源预算计划交接

2026-10-22；负责人为连接器实际登录账号rayggxia。正式仓库rayggxia-workspace/pbit-llm-qwen-baselines，基线及PR base为pbit-tlm-attention-details-20261016@eb317e4f6fb1b0d8844887401f3275f128ef8a83。

分支task/112-resource-budget-plan；最小稀疏worktree为C:/Users/86134/Documents/a_P_BIT/tmp/resource-budget-issue112-20261022。只检出本任务文档、个人STATUS/辅助目录及cone默认根文件，没有复制模型、环境、波形或历史大轨迹。

正式成果：architecture_tlm/resource_budget_plan_20261022/PLAN_ZH.md。便捷阅读副本：C:/Users/86134/Documents/a_P_BIT/pbit_llm_master_report_20261012/PBIT_LLM_ASIC_RESOURCE_PLAN_ZH_20261022.md，只作同字节阅读，不独立编辑。

内容：当前资源与Qwen工作集、同资源/同总面积对照、P0至P4实施任务、1/2/4/8MiB与带宽/计算/恢复/随机服务联合搜索、TLM七项改造、条件下界、输出指标、12个固定Git文件入口及三篇主要论文。2/4MiB只是搜索候选；完整PPA仍未知，具体质量预算待用户确定。计划不自动授权或启动后续作业。

实际验证：文档UTF-8/LF、9个主体章节；12个固定Git链接逐一在相应提交对象中解析；只读四份封存Qwen结果验证TPOT、SRAM/权重字节、面积/null语义，复算FFN/KV容量和带宽下界；阅读副本字节相同。记录及SHA见VALIDATION.json。首次校验在全部来源断言通过后，因旧Python不支持Path.write_text(newline=)而未写出元数据；改用write_bytes后完整重验通过，计划内容未改。

本次没有模型/训练/PPL/GPU/Slurm、新TLM扫点、RTL/EDA/STA或DRAMSys运行。模型、tokenizer、语料revision及新实验种子/精度不适用；旧结果沿固定执行版本与原manifest索引，未继承成新实验。外部文献按正文/表格定位，未打包用户PDF或工艺库。

发布以同目录PUBLICATION.json及Issue112最新回执为准；PR待审不等于合并，Issue不自动关闭。当前连接器未提供Projects看板操作，本轮未同步看板；不把历史read:project不足当成本轮新权限测试。

长期备忘录只有task/28-project-memory的唯一维护源；本任务不在独立分支建立第二份编辑版本，也不写入其他任务未提交工作树。待维护者按当前流程追加以下入口：

> 2026-10-22 Issue112：资源预算与存储DSE计划入口architecture_tlm/resource_budget_plan_20261022/PLAN_ZH.md；建议Qwen先搜索1/2/4/8MiB并联合带宽、恢复、引擎和有限随机服务，数字与p-bit分别进行同资源/同面积优化。附工作集、条件下界、P0-P4验收及固定证据链接。只有规划文档/来源核算，没有新模型/TLM/EDA结果；2/4MiB非最优结论，质量预算与整机PPA未闭合。发布状态以Issue112/PR为准。

下一步：先审核计划，再按P0资源账本和P1数据流落实范围继续；执行前重新检查Issue95/96/104/107/110和PR103/105/109/111。不要重复启动已完成实验，不把待审RTL自动合入TLM。

本次无额外helper需要清理。PR待审保留此最小目录；合并后核对refs、未跟踪/ignored和本机阅读副本SHA，再按项目生命周期规则归档恢复索引并回收本工作树。

实际发布：PR114 ready/open未合并；远端来源提交18c2a62f4a6cee4cf2a7df62594510a35073639d，本地来源a945acfc908b1c65e1127fd0dcb3ad5560fbf921，二者同树56a1c2b5a90aad5add7cac86c6ec18eb5975acfd，4文件远端回读一致。Git push连接失败/取消后使用GitHub对象API上传，不能把本地SHA写成远端SHA；后续恢复先fetch核实远端，保留本地历史，不强推覆盖。元数据提交不修改正式计划与阅读副本。
