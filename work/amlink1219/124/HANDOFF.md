# Issue124 恢复吞吐/数据流消费实验交接

负责人 amlink1219；唯一目标 rayggxia-workspace/pbit-llm-qwen-baselines。
分支 task/124-recovery-dataflow；独立目录 workspace_projects/rd124；基于集成 46804fb3a1c50b29a19a7d0a3da6bb8f8b59af7d。

范围是短多波投影消费实验；复用 Issue116 周期内核、PR120 供数、PR122 恢复数值/资源合同，不接管 Issue123 的完整 FFN 接合或 STA/PPA。原 Issue117/PR119 保持。

入口 architecture_tlm/ffn_dataflow_optimization/PROTOCOL_ZH.md。先冻结输入、源与8配置，再对每配置执行三seed和SC/W8；源改变另开输出目录。全部为本机CPU，无GPU/Slurm任务，不含完整FFN/PPL/物理PPA。

依赖见 DEPENDENCIES.json 和 DEPENDENCY_VERIFICATION.json：13份精确Git源原字节已核。缓存位于本机项目根 outputs/asic_recovery_dataflow_20261023/dependencies。冻结的 Issue116 提交 6a569409 尚不能从GitHub解析（实测HTTP422，见 DEPENDENCY_REMOTE_STATUS.json）；在该提交公开前，新机器不能仅凭GitHub重建本轮依赖。该限制不影响已归档结果核验，不能把此任务称为已独立可复现的完整集成。

进度和最终发布回执将在结果归档后追加。不得重放运行覆盖既有目录，不修改 cycle23 工作副本。
