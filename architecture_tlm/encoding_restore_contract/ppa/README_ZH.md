# 编码/恢复 licensed STA/PPA 执行入口（Issue123）

本目录是可执行准备与报告门禁，真实 DC/VCS/PT **尚未运行**。prepare 输出
`status=not_run`，面积/功率/STA 均为 null；Python 测试不构成工具兼容性或工艺验证。
本轮执行交接给 GitHub `jieruiz`，见 [HANDOFF_JIERUI_ZH.md](HANDOFF_JIERUI_ZH.md)。

流程只实例化 PR122 ready/valid 包装：完整64值 BF16/FP32 编码和一次四档输出恢复，
DEPTH=3、TAG_W=32，包含结果槽、信用/队列指针及原算术核。无 SRAM、CDC、SC采样、
跨k FP32 add、最终 BF16 收窄或完整 FFN；没有实现 product-sign/magnitude 计数转换。
恢复总线必须是 input-sign/W8 two's-complement，bit7系数为−128。
当前Issue116接合的x/z内存和算术均按FP32；BF16编码是独立基线/未来配置，不能将它
的表征结果解释成当前x内存减半。本轮45case功能证据见results/rtl_2778，仍无licensed PPA。

`driver.py prepare` 共用 sim/validate_ready_valid.py 的固定顶层和 exact oracle 向量，
生成5个固定顶层×3seed及整个执行源码闭包SHA。`run` 单独执行一个角/一个顶层，
DC完整解析源码→映射→带真实单元模型的零延时VCS逐笔检查→VCD窗口X/Z审计→PTPX。
每阶段完成清单记录所有产物hash，完整阶段可复用；变更配置/源/库或损坏产物拒绝复用。
失败阶段与日志保持原样，需要诊断后新建准备目录，绝不自动覆盖失败结果。

`run` 要求绝对工具路径、库路径、明确库/OC名称、个人根与预期用户、CPU Slurm
allocation，且CUDA_VISIBLE_DEVICES显式为空。这些程序检查不替代操作前现场核验
实际账号、canonical home、个人根授权和分配节点；不得在登录节点执行。

约束固定100MHz：setup uncertainty2ns、hold0.1ns、slew0.1ns、IO max/min1/0.2ns、
输出0.02pF。只有report_units的1ns/1pF格式通过；库真实V/T必须对应SS1.08V125℃
或TT1.2V25℃。同步reset、ready/valid/tag/占用输出均受约束，不添加假路径。
Tcl或报告格式不被支持时失败，不猜测单位或把报告缺失转换成0。

首版只报告synthetic_active：完整协议测试的stage3先连续32拍预热，再截取64拍，
100MHz下640ns，64接受/64完成，不含reset/drain。idle/burst/stall功耗和真实模型
激励尚未表征；不能把这一窗口称作全FFN活动。T16/32/64只改变恢复计数位宽与除T。

PT必须有area/setup/hold/check_timing/constraints/library/units/power/activity/check_power。
X/Z、缺报告、错PVT/单位直接失败。负slack、未满活动覆盖及任何已捕获Warning均保留，
`accepted_for_tlm=false`；不能以工具exit0代替验收。每笔能量为窗口总功率×时长/完成数。
面积默认保留library area units；仅在STD_AREA_UNIT=um2且有工艺文档单位证据hash时
另填area_um2，该证据由执行者审阅确认，不从库名称猜测。

这仍是prelayout、零延时门级活动、理想时钟，无SDF/SPEF/CTS/真实毛刺或硅实测。
源、配置、工具与库hash可公开；工艺库/模型/工艺文档和可能包含受限信息的report_lib
留在原授权环境，只上传经审查的小型结果摘要、验收报告和hash索引。

本地预检：

```text
python -B -m unittest architecture_tlm.encoding_restore_contract.ppa.test_flow
python -B -m architecture_tlm.encoding_restore_contract.ppa.driver prepare --out /absolute/new/personal/prepared
```
