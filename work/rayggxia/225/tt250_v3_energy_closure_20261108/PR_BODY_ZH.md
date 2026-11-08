本PR接续 #225、依赖 #248，提供独立250MHz完整decode事务模型；100MHz默认不变。当前3个FFN公共核、960KiB/240bank SRAM、16KiB返回保持、256共享FMA、64PV ADD、16路FP32归约。保留原主线的有限FIFO、bank仲裁、预取与回压重叠。

FFN现已接入通过前布局验收的delta_pipeline_v3：GU/Wd采样16/32，每帧19/35拍、76/140ns；单核55等效面积1.374062065mm²，总已覆盖面积22.086073mm²。历史时序失败的v1/v2和旧T64参考保留，不再用于当前核计费；v3的极小裕量和库表范围告警仍注明。这里不是整芯片签核。

新增ENERGY_LEDGER.json/CSV：26项已建模资源按活动、驻留、门控节省和外存逐项对账。FFN使用gross活动＋剩余核时idle，并检查与增量活动＋全驻留idle相等；旧FFN原本就遵循正确口径，没有发现该项重复计算。共享FMA/DMA、全部物理SRAM只收费一次。状态为模型边界内账本闭合；物理CIM接口、全片互连/CTS/PHY和部分控制成本仍明确未覆盖，格式/向量/PV2及外存pJ/bit保留代理标注。

原生LPDDR冷单层门禁38629484已完成：Qwen3-4B B1/2K、含embedding无head，1.195020ms，片上0.550405mJ，外存4pJ/bit为4.120609mJ，总4.671014mJ。五件输出和SEAL逐SHA核验，4项能量/合同单测、11项历史catalog隔离检查通过。解析外存单层为1.085720ms；不混作配对加速比。

完整36层＋最终norm＋lm_head三seed17/503/1009已提交CPU数组38629485，最多2项并发；完整token时间/能量尚待封存。冻结源不可改、健康任务不重交，元数据整理前后profile字节与SHA分别保存。无新PPL/RTL/PT。

配置末尾r16是归约lane数，SparQ仍32维；单层2621440 QK MAC已核对。当前[能量对账说明](architecture_tlm/sram1216_20261106/250MHz/ENERGY_CLOSURE_ZH.md)、[门禁摘要](work/rayggxia/225/tt250_v3_energy_closure_20261108/VERIFIED_GATE.json)、[账本CSV](work/rayggxia/225/tt250_v3_energy_closure_20261108/VERIFIED_GATE_LEDGER.csv)及[交接](work/rayggxia/225/tt250_v3_energy_closure_20261108/HANDOFF.md)。公开范围仅接合代码、校准数值与小型证据/SHA；私有owner执行包、原轨迹和工艺库不上传。PR待审未合并，Projects待维护者同步。
