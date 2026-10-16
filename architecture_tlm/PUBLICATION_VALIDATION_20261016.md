# 发布验证

- 78 项标准库单元检查通过：Attention v3、筛选与 Ising v4、FFN 本地共享随机源、层次随机源、SRAM/CACTI适配、访存调度、DRAMSys协议及整机模型。
- Attention v3：10 组已保存结果的能量账本、资源因果顺序、流量和源码哈希检查通过。
- 筛选与 Ising v4：4 组已保存结果事务审计通过。
- 原有 DRAMSys：12 组发布结果的历史源码、配置哈希、有限队列与范围检查通过。
- 8 个随机计算功耗证据配置通过捆绑文件哈希与数值一致性检查。
- 当前 Python 环境没有 PyTorch，`test_attention_trace_torch_v3.py` 未运行；未运行真实 Qwen 推理、PPL 或重新编译 SystemC。

复现标准库测试时排除需要 PyTorch 的真实轨迹测试文件；Windows 如遇临时目录权限问题，请将 Python `tempfile.tempdir` 指向可写临时目录。

本次仅发布快照与可移植性整理。`run_mapping_dramsys_batch.py` 改用环境变量 `DRAMSYS_BRIDGE`（默认 `build/pbit_dram_bridge`），不再依赖原服务器绝对路径。

旧 DRAMSys 结果对应当时源码，不声称由新版 `system_decode.py` 生成。对应历史源码与证据配置保存在 `evidence/historical_dramsys/`，发布审计针对历史文件。新 Attention 模型及结果的源码一致性另行审计。

Attention 事务记录是合成事件，宏级参数不是芯片实测。QK筛选仍为独立Bernoulli判决，未实现本次讨论的原生p-bit直接驱动或块间耦合筛选。
