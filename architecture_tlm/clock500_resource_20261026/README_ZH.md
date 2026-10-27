# 500MHz、扩资源与时钟门控条件探索

Issue186 / PR192；统一模型仍为 unified_v6。本目录增加显式实验 profile，不改变正式默认配置。
范围：Qwen3-4B 后训练模型形状、36层、B1 decode、2K上下文；计入 lm_head。行为logits产生注意力事务，不是PPL或模型推理。
注意力保留上一轮 screen_pv（QK筛选＋准确Softmax＋PV采样），方便只比较资源变化，不据此宣称 Ising 已完成本轮速度测试。

- 核心和本地随机服务500MHz；SRAM宏保持80MHz，HBM标准配置与时序保持。
- 扩算力：SC 8→32 个64×64；普通数字512→2048 MAC/拍；桶归约64→256、恢复16→64、宽累加32→128路。
- 扩存储并行：8MiB容量不变，F宏64bank/64GBs→E宏512bank/512GBs。双本地权重bank64→256KiB，完整DMA回包缓存32→128KiB，数字tile仍64KiB。
- GU64采样；NL64用于原配置对照，NL128为新主候选。R8是部分和驻留8个K64块，非8个输入组同时计算。
- 门控：计算模块排空后空闲8拍关钟，请求时1拍唤醒，寄存器保留。SRAM/HBM、随机网络、种子和配置总线不在门控范围。没有假定门控可消除漏电。
- 500MHz为待STA验证的目标；保持原逻辑延迟与II，不等于原100MHz RTL可直接5倍提频。MAC本地读出吞吐同样尚未验证。
- RNG在500MHz仍按100MHz参考每时钟边沿能量计费，避免每次更新能量错误变小5倍。此端点暂未拆分漏电，因此为保守边沿成本代理。
- HBM配置的电流为零占位：只用于时序，完整物理能耗、面积保持未知，不把未定价当零。
- 新Issue193功耗锚为SS/1.08V/125°C/100MHz/prelayout，500MHz动态功率按频率条件外推，泄漏不乘5。真实ICG/CTS/唤醒能量待表征。

运行：python -m architecture_tlm.clock500_resource_20261026.run_case INDEX --matrix ... --manifest ... --bridge ... --output ...
提交/采集：work/jieruiz/186/submit_clock500.py、collect_clock500.py。源SHA提交后冻结；只接受completed且原件SHA一致的结果。

完整12项已完成：[结果与模块PPA](RESULTS_ZH.md)、[机器可读对照](COMPARISON.json)、[周期与假设](CYCLES_AND_UNCERTAINTY_ZH.md)。

后续论文主模型的算子依据、调度改进顺序与校准口径见[PAPER_MODELING_POLICY_ZH.md](PAPER_MODELING_POLICY_ZH.md)（2026-10-27用户确认；本次文档尚未改变封存结果）。
