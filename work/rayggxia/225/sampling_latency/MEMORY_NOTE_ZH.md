## 2026-11-06 Issue225：T8/T32快速时序工具和1216KiB原生配对

用户要求Wg/Wu8次、非线性三AND直连Wd32次，快速改变T估算时间，并分列含/不含lm_head。已实现architecture_tlm/sampling_latency_20261106/fastsim.py：有限32权重槽、12核、2结果信用/核、2状态端口、K依赖和GU均衡窗口的tile事件模型，原T64阶段校准偏移保留；六组扫描本地约0.7秒，无GPU/原生库依赖。不能按T比例缩整机，当前FFN权重约2.69GB/token，136.46GB/s理想搬运19.71ms，已测FFN约21.8ms，故降T主要减核内工作而非大幅加速。

服务器已恢复，38616054两项完整COMPLETED/0:0与SEAL SHA重新核验。旧1952KiB/1024普通池T64/T64为49.93827ms含头、6.95415ms头、42.98412ms扣头；不是最新1216/640配置。“扣头”保留final norm和已重叠的少量lm_head预取，不等于取消全部头权重的硬件重跑。

当前1216KiB/640新快照4528b0b42a97：T64/64与T8/32两层38617086均完成，2.46395→2.46201ms（−0.0787%），FFN1.25171→1.24790ms；外存257484544B一致，MAC/跨K/Attention守恒，GU R8动作1/8、后级1/2已核。7本地＋7EDA门禁38617085通过，原始两层RESULT/SEAL已逐字节归档project_archives/sampling_latency225_20261106/native/prefix。

新完整38617087_[0-1]已RUNNING、0GPU/各1CPU、最多2并行，预计约2—2.5小时；不重交健康任务，不改冻结源，无自动化。最新实际状态见同任务STATUS/交接，不能凭本备忘录断言以后仍运行。旧1216失败计划未另行重复提交。当前两层外推＋旧head代理粗估前64后64约51.30/44.35ms、前8后32约51.25/44.29ms；不是新整token结果，需完整T64/T8结束后替换profile并验证快估误差。

实际delay按(T+2)×10ns改变GU/Wd帧，其他阶段保持；20依赖只读固定，SHA a633d11f4a52d47611a96cd8016695f47294d154cb900bec2b4edac914d90291。无新PPL/训练/RTL/PT/能量价格，不把T64 PPA按T打折。正式README/REFERENCE_PROFILE/CURRENT_PREFIX_PROFILE/NATIVE_PREFIX_RESULTS与QUICK_SCAN；辅助入口work/rayggxia/225/sampling_latency/HANDOFF.md和ops.py。沿Issue225/PR248，发布回执为准，Projects待维护者同步。

---

