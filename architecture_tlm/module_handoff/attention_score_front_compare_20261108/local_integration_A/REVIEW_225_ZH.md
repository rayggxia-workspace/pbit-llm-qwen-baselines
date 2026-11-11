# 主流程消费复核

2026-11-08，Issue225 / PR249，关联Issue198。已找到并收录侧对话local_integration_A补充；原adapter/verify/VALIDATION/HANDOFF字节保留。

## 复核结论

- 在约0.5MB独立只读输入快照中复跑原verify.py，25个来源SHA一致；192查询/24576分数、27组全有效旧S12接入、6912个固定激励递推输出通过。新VALIDATION与提供回执逐字节一致，原输入/回执未改。
- 显式A调用和P8 LUT边界已说明，接线不需要把A主线改成B。6912项只证明同阈值／同固定Python随机激励下的递推一致，不是GF64质量、RTL周期、回压或新完整PPL结果。
- 旧sampler.sv确实硬接candidate_mask全1、initial_index0；适配器拒绝非128全有效／非有限输入是正确约束。当前固定2K/K128且候选全部有效时不新增阻塞；短上下文、padding或通用mask另列后续接口范围，不要求本轮重做整个采样核。

## 现在能接什么、还缺什么

数值接口与计费合同可以作为后续接入依据；完整链价格仍保持null。优先复用旧S12 scores/max/gap/LUT，仅加四路FP32→S12转换及握手增量；或选择A＋去重gap后端，两条选一条，不重复做。

此次补充没有新增上述转换／握手增量的DC/PT，也没有完整连接后的准备/采样/等待分窗和握手时序。因此不能把独立A的面积、能量、65/67拍再整块加到旧sampler，不能把integrated_sampler_replacement_ready改true；也不能从旧核直接减完整A。下一步缺的是这个小边界的实际价卡／时序，不是重新证明S12数制或重新训练。

28nm仍需同工艺A或转换增量，不使用55nm乘频率/面积比例代替。侧对话提到的28nm准备脚本不作为实时队列证据，本次未提交或取消EDA任务。

本次只收录适配器、检查脚本、哈希与验证回执，没有携带私有前端包/大原始产物；异机复现须按VALIDATION.sources准备对应文件。本次未修改当前TLM源码/默认/冻结任务，未生成新整机PPA或新电路run。公开源和回读以work/rayggxia/225/score_front_audit_20261108/LOCAL_ADAPTER_PUBLICATION.json为准；PR249不合并，Projects待同步。
