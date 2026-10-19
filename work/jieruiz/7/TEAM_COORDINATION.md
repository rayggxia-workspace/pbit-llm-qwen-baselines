# 本任务补充的并行分工

负责人仍为 GitHub jieruiz；全部接续 Issue #7 / PR #8，无重复 Issue。

- 主工作树：`tmp/ffn-cim-issue-7-20261017/`，`task/7-ffn-cim-scheduling`，基线 `db3a79c876f46f4738274cc010a2066562dd27d2`。负责经典结构比较、有限范围服务计数、正式报告、验证与发布。
- `gpu_asic_swiglu_sources`：只读调研 vLLM、TensorRT-LLM、TPU、Gemmini、NVDLA 原始来源，不修改文件、不提交、不管理 Issue/PR。
- `rtl_baseline_scope`：只读检查已有矩阵/转换 RTL 与工具，避免重复实现，审查新候选位宽、符号与对照口径。不修改文件。
- `swiglu_rtl_impl`：独立工作树 `tmp/ffn-epilogue-rtl-issue7-20261017/`，`task/7-ffn-epilogue-characterization`，同一基线；只修改 `architecture_tlm/rtl/ffn_epilogue_20261017/`，负责后处理候选和功能/活动仿真。不推送或创建 PR，由主工作树审查后集成。

主工作树不覆盖或切换子工作树；不在子工作树准备发布。集成采用明确的源提交 cherry-pick，源提交与实际测试记录追加在交接中。没有取得用户工艺库或 DC/PT 结果，不将 Icarus 功能验证称作功耗验证。
