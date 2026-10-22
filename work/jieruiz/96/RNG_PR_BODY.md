本次核实新随机架构与统一整机TLM的接口，新增分层共享64输入前端和32位PV偏移打包。赢家保持/校正拒绝实际接入Issue95的TimedSamplerSource，各三seed检查通过；512路由26个Bivium端点供给，无隐藏分波。后端模型/RTL及其他成员STATUS保持。

验证冻结36d5e108：11项新连接＋21项整机回归＋19项源目录检查，共51通过、0失败/跳过；来源树与集成5dbd9e39一致。原始回执和日志在work/jieruiz/96/RNG_INTERFACE_VALIDATION.json。

结论与边界：接口可用，但FullDecode默认尚未启用新后端；全模型仍需源时钟、流式消费、筛选宽度、实例分配和成本去重适配，q/256响应不能继承理想源PPL。没有新PPL/GPU/PT/DRAMSys或芯片PPA。

报告：[RNG_COMPATIBILITY_ZH.md](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/task/96-unified-tlm/architecture_tlm/unified_v6/RNG_COMPATIBILITY_ZH.md)。原整机PR99已在本轮工作期间合并0575a633，仅含a7a4829及其原52项；本补充单独待审，不把新源连通写成已随99合并。Refs #96 #95 #99。

本人STATUS/HANDOFF和备忘录会同步本PR编号。Projects沿已有实测read:project权限待同步。
