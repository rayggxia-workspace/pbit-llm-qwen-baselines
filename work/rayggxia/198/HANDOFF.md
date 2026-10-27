已发布：草稿PR199（https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/199），科学提交5fad0fc32f5284560c38c03f4fe28657f936f553；7关键文件远端逐字回读、完整Git tree和本地相同SHA导入通过。Issue198评论6443236705；待审未合并，广泛验收仍开放。PUBLICATION.json为准确回执。

# Issue198交接

2026-10-27，rayggxia。用户指定两份Attention资料后，本轮完成第一阶段可运行代码与功能仿真。任务更广泛的验收保持open；准确发布状态见PUBLICATION.json，不能用本文件的本地完成冒充已合并。

仓库rayggxia-workspace/pbit-llm-qwen-baselines；task/198-attention-compare；main base d83eeb1fc6b89a3dff51b5b62bf79acf665c7166；独立最小worktree C:/Users/86134/Documents/a_P_BIT/tmp/attention-compare-issue198-20261027。原GitHub CLI网络getaddrinfo失败，使用认证rayggxia连接器发布；未改变历史origin/他人分支。

正式代码architecture_tlm/attention_compare_20261027：core.py、schedule.py、run.py、quality.py、test_core.py；rtl/attention_rejection_control.sv、nr_singleton_tree.sv、tb_rejection.sv及validate_rtl.py。P3/P4复用main已合PR88三个模块，未复制改写随机算法；源SHA在INPUTS和执行SOURCE。数字参考输入BF16存储、算术FP64数学oracle，未冒称逐位BF16 MAC。

已验证6机制测试、108合成案例、72项预算探索；RTL9例22500拍通过，N16/64/512，seed17/503/1009，配置/输出/公平位等待、reset、cap、m24上限均覆盖。Icarus10.1在Windows沙箱内启动WinError623，沙箱外自动审批后短验证成功。rtl_v2打印格式失败、旧快照和负结果均归档；最终RTL为rtl_v4，未跑综合/STA/PT。cap失败会在输出若干地址后报告failed，下游必须丢弃整query部分和，不得用部分输出充成功。

原始输入为固定normal QKV，未加载真实模型/文本/tokenizer；不适用模型SHA/BF16 PPL复现门禁，不能引用旧Base证据作新模型。L512/2048/8192、d64/128，S=L/16，筛选8块。单一输入/三seed均值过解析IID128 MSE阈值仅探索；P3/P4须S512，117264/22181条件拍，对D033586；没有能量/面积胜出结论。

重跑命令见正式README，必须新输出目录。正式Python为C:/Users/86134/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe（3.12.14，NumPy2.3.5）；Icarus位于C:/Users/86134/Documents/a_P_BIT/sc_weight_storage_or4_20261014/tools/iverilog/bin，ivl-lib为同级../lib/ivl。CLI命令与环境见CONFIG/VALIDATION。

RAW_ARCHIVE.json是5.31MB原始ZIP及399成员逐SHA，包含逐case事件/地址/结果、全部bit轨迹与编译日志、历史失败；.vvp可重建不归档。Git保留小型FINAL汇总/配置/SOURCE/manifest与QUALITY/RTL VALIDATION。读取manifest中的某个case原件时，从ZIP的results/sweep_final/对应成员取出并核对SHA。输入与外部资料保持原位置，不上传用户PDF/工艺库/模型。

统一台账同PR仅新增attention-rejection-198-20261027；main缺全套工具，work/rayggxia/198/registry_check用根现有78记录增量合成79并check/render；READING_SYNC记录根镜像原记录未改的核验。本人Issue28记忆维护副本和根镜像原有历史差异，分别追加同段，旧字节保留，preimage在归档。尚未执行远端Projects同步。

下一步按优先级：

1. 将新RTL真实捕获→树→校正/反馈→配置完成→输出的边沿时序接到PR88或可替换适配器；源配置/稳定等待外供，不能删sink检查绕过PR192未实现映射。
2. 用后训练真实QKV建立同输入数学/逐位参考与质量曲线；若新增模型比较，核对model revision、权重/tokenizer、train/test SHA并同轮重跑未变BF16。旧78 Base仅诊断引用。
3. 实现赢家完整count/无偏按秩仲裁RTL；补共享V有限表/缓存/返回/累加；D1固定ITA commit/许可后移植或建立明确INT8合同。
4. 沿统一unified_v6接口补GQA集合复用和真实memory后端，报告固定资源与质量/吞吐匹配；Link宏条件模型不是新整机版本。
5. 若用户要PPA，先N512代表控制与公共算术STA/PT，不重测已有源本体；按相同PVT/负载/活动绑定计价。未知完整成本留null。

无本任务运行中GPU/Slurm/许可EDA或自动化。保留最小待审目录；恢复优先复用，不新建全量副本，不清理其他成员。PR待审不关闭Issue。
