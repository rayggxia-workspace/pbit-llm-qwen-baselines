## 2026-11-25 Issue225 / PR266：TLM／RTL对齐版已发布

复用tmp/cim-bank32-tlm-issue225-20261124，task/225-cim-bank32-20261124，PR266 ready/open未合并，source401d1db5715a1814d8e7e31aeceedd2c5f1e180b，25文件树核验、8关键blob回读一致。代码仍为architecture_tlm/process_28nm/cim_bank32_20261124；默认CURRENT_CIM指向新增ALIGNMENT_CONTRACT.json。正式报告ALIGNMENT_REPORT_ZH_20261125.md，RTL接口/布局RTL_CONTRACT_ZH_20261125.md；新HANDOFF为work/rayggxia/225/cim_alignment_20261125/HANDOFF.md。

五核、28nm/250MHz、每核8KiB/16bank/32×128bit单区、GU16/Wd32、616KiB有效SRAM＋原16KiB DMA保持不变。新增实体双结果槽、128列捕获、32项/拍四拍状态传输、结果槽/状态owner分别释放、输入缓存跨命令失效、共享DMA元数据和目标阻塞回放、逻辑tile随机状态接口。已有核PPA包含FIFO/缓存/本地随机生成，不再重复计价；当前周期×4ns只转换一次。

8项unit、父BeatSRAM、6个trace场景、5个损坏轨迹拒绝及完整首层SEAL通过。同解析外存136.4606GB/s/30ns首层1.106372→1.106300ms，面积6.776269mm²不变，片上0.342181→0.342178mJ。DMA峰值16320B、251在途、30描述符；无新36层/native/PPL/RTL/PPA或远端作业，不改旧51.132604ms/token。原件归档project_archives/cim_alignment225_20261125/RAW_AND_EXECUTED_SOURCE.zip（1524676B，SHA de69a693f7a88f32b22a1314289659bbe35f2b94d53e95202b6e2ec43479e5d3，86成员逐SHA核验）。

剩余：完整五核RTL按同合同实现/对照，随机起始状态提供器1拍/II1仍为条件宏且真实PPA待补，512B定制CIM外围仍为S0容量等效代理；超过64活跃描述符需补生产端等待，现峰值30。Projects待维护者同步。下一步优先接口/小形状核对，不重跑健康模型任务、不导入单核原型的串行限制。
