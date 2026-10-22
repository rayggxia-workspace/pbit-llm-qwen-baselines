# Issue124 恢复吞吐/数据流消费实验交接

负责人 amlink1219；唯一目标 rayggxia-workspace/pbit-llm-qwen-baselines。
分支 task/124-recovery-dataflow；独立目录 workspace_projects/rd124；基于集成 46804fb3a1c50b29a19a7d0a3da6bb8f8b59af7d。

范围是短多波投影消费实验；复用 Issue116 周期内核、PR120 供数、PR122 恢复数值/资源合同，不接管 Issue123 的完整 FFN 接合或 STA/PPA。原 Issue117/PR119 保持。

入口 architecture_tlm/ffn_dataflow_optimization/PROTOCOL_ZH.md。先冻结输入、源与8配置，再对每配置执行三seed和SC/W8；源改变另开输出目录。全部为本机CPU，无GPU/Slurm任务，不含完整FFN/PPL/物理PPA。

依赖见 DEPENDENCIES.json 和 DEPENDENCY_VERIFICATION.json：13份精确Git源原字节已核。缓存位于本机项目根 outputs/asic_recovery_dataflow_20261023/dependencies。冻结的 Issue116 提交 6a569409 尚不能从GitHub解析（实测HTTP422，见 DEPENDENCY_REMOTE_STATUS.json）；在该提交公开前，新机器不能仅凭GitHub重建本轮依赖。该限制不影响已归档结果核验，不能把此任务称为已独立可复现的完整集成。

进度和最终发布回执将在结果归档后追加。不得重放运行覆盖既有目录，不修改 cycle23 工作副本。

## 本轮结果与后续入口

48例已完成，四分片returncode均0；执行提交54a9968bbbc3219573bd00e71f37133c8292b302。20项数值/数据流测试、8项登记守卫通过；VALIDATION覆盖48例/24对/3fixtures/467520操作，15类篡改拒绝。主报告、表和图见模块README及results/analysis；完整gzip保留原始数据，不是摘要替代。

SC基线221.3625µs，read128_only206.35µs，pipeline2为205.75µs；后者同配W8完全相同。新增局部状态/接口必须物理计费，完整面积、能量、PPL仍null。部分和3584笔×37.5ns加排他供数和信用返还边沿是当前限制；II4敏感性未触发额外时延。下一步与Issue123协调完整接合，并研究部分和合并访问/合法重叠，W8共享改进。

截至发布前PR125已开放（a9c0031d），负责完整FFN与实际EDA交接；不改变本轮冻结依赖。Issue116未公开的6a569409是新机器复现限制，保留本机缓存/提交，不提前发布其代码。无GPU/Slurm任务，四本地CPU批次均已结束。暂保留本任务最小工作目录和验证依赖缓存供评审，旧ar117/cycle23未改动。

正式独立审计命令：

```sh
python -m architecture_tlm.ffn_dataflow_optimization.verify_results --dependencies /owned/dependency_cache --fixtures architecture_tlm/ffn_dataflow_optimization/results/fixtures --runs architecture_tlm/ffn_dataflow_optimization/results/shard0 architecture_tlm/ffn_dataflow_optimization/results/shard1 architecture_tlm/ffn_dataflow_optimization/results/shard2 architecture_tlm/ffn_dataflow_optimization/results/shard3 --expected-grid main48 --output /owned/new/validation.json
```

本分支台账36条564行不含其他未合并分支的新增记录；合并时须取并集再render，不能以总表覆盖PR119/120/122/125。Projects实时缺read:project；当前机器无C:/Users/86134/Documents/a_P_BIT/digital_circuit_simulation_registry镜像路径，未创建异账号目录。实际GitHub上传回执稍后保存PUBLICATION.json，PR草稿待依赖发布，不自动合并。
