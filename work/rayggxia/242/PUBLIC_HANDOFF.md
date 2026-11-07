## 2026-11-05 22:00：完整WT2单seed已提交

用户授权只申请一个完整任务观察效果。Slurm4652已核RUNNING：联合版本/seed101、292窗/299077目标、batch8；1×5090/4CPU/48GiB，12h时限。原21文件数值快照未改，新driver仅冷启动N1检查和每128调用只读计时；GPU N1/S64门禁PASS，本地及服务器完整计划292窗/39组/40005单token调用一致。

预计启动后4–8小时，待实际进度校准；尚无完整PPL。不展开其他seed/对照，不重复提交。恢复full_ops.py status→读FULL_SINGLE_STATUS及封存，不修改已提交source/driver。根服务器项目中full_single_afd284c33749；具体路径/命令/资源/SHA在FULL_SINGLE_SUBMISSION、FULL_SINGLE_MANIFEST。驱动SHA afd284c33749e7dbff8377ba41cdf38413c128326f24a55087e636252c8a2346。此前“无运行作业”仅针对后缀批次。PR243未合并，Projects待同步。

---

# Issue242：联合快速PPL已完成

负责人rayggxia，分支task/242-t64-strat32-joint，PR243，未合并。Slurm4643七项全部封存完成，本任务没有运行作业。CPU4641六项，GPU4642 P8字节帧独立oracle、32token前缀no-op逐位等价及36层覆盖通过；源码包56df7b93d4f4fa4296f1dc3c052b93194082f1667dc60967dab439ba580a2521，gate a50b3f090d5d307079baa6906ba5101968ea626ada75202ddc048408aed30b2a。

结果：原BF16 13.580351，T64训练权重分层T32 FFN-only 13.372338±0.224580，联合概率Attention 14.297115±0.520343。都是相同1024个WT2后缀目标，三部署seed101/102/103；±为样本标准差。联合比FFN-only+6.9156%，比原BF16+5.2779%。不是完整WT2，不能与旧10.698直接相减，不是多训练seed置信区间或PPA。

正式入口：experiments/joint_t64_strat32_20261105/README_ZH.md与results/REPORT_ZH.md、RESULTS.json。最终JSON保留模型export/non_ffn/36FFN文件、语料/token/目标位置、源码配置和35原件SHA；原件大权重不发布。可按公开合同重新构建输入并评测；私有原件位置及执行脚本恢复见本人工作区同Issue的完整HANDOFF和归档索引，不重复提交已完成任务。

数值合同：QK signed12/F4 RNE饱和→max差→U8/F4饱和地址→floor-P8 LUT→各候选独立IID R8；SparQ r32/k128/recent32、赢家保持S64/burn0/slot0。前缀Attention准确、FFN前缀及计分均T32；全部计分token经过36层采样。SparQ仍FP32行为参考，未验整Attention RTL位真，未测GF64联合PPL。

没有新训练或自动合并；下一步若需要更强结论，再用相同checkpoint做完整WT2匹配确认。Issue/PR保持开放待审，Projects待维护者同步。
