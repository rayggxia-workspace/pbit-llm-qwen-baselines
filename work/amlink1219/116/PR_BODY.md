现有v6整机宏时序不能回答逐拍端口占用、有限缓冲回压和实际数据就绪。本PR新增独立`architecture_tlm/cycle_v1`周期执行后端，交付FFN tile、Attention query、共享KV的GQA分组、缩小版单层闭环和可运行v6算子配置桥；保留旧v6、random_service及历史结果。Refs #116。

- 整数ps多时钟、old-state提交规则、有限资源/完成端、真实字节内存、bank/窗口/RAW-WAR-WAW、在线native随机服务；cycle/event完整可观察轨迹相等。FFN保持W8与B4/T32/K32主参考，显式分档编码、平面计数、有限恢复和跨tile累加。Attention保留动态赢家/拒绝、实际V地址及样本multiplicity。
- Slurm2776：68真实Qwen裁剪片段+8合成用例全部通过。首轮2775的6个有限预取死锁已定位、修复并保留失败证据。最终81实现测试、71独立测试、43旧回归通过；矩阵独立复核302制品、34完整trace/98,340操作和4,597真实read hashes。另有3层裁剪FFN独立标量数学核验。
- 新增同Kernel的真实7query/1KVhead GQA，有限共享行、cache读口、operand响应、metadata和运行时union扫描；独审发现的免费union与无界响应均已修复。Slurm2782的5个S32 CLI及6个S16独审配置双模式通过，后者42个case/head的2,688值与独立FP32标量oracle逐bit相等。输入为Qwen层12/context64的已投影/RoPE数据。只发布白名单回执，原始张量和轨迹留服务器；未运行2K。
- 9协议RTL场景/252握手逐ps对应；ONNXim固定版本2官方+4自定义场景；缩小单层7成功+2容量拒绝；v6桥5例；PR122固定8007d98兼容复验12场景/1536恢复；8组有限资源敏感性。它们的证据范围分开记录。
- [实施报告 ](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/task/116-cycle-execution/architecture_tlm/cycle_v1/IMPLEMENTATION_ZH.md)、[独立审查 ](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/task/116-cycle-execution/architecture_tlm/cycle_v1/audit/REVIEW_ZH.md)、[恢复交接 ](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/task/116-cycle-execution/work/amlink1219/116/HANDOFF.md)。完整原件和私有fixture保留个人存储；Git包含代码、必要报告、选定trace及SHA索引。

原方案A–G尚未全部完成：真实全维整层、多token/2K/8K、完整Qwen/Llama与PPL、共享全模型状态/随机网络、在线DRAM命令后端和物理PPA仍待验收。context64 GQA分组不等于完整GQA层。32KiB权重信用只代表逻辑驻留额度，宽阵列供数未有物理闭合证据；延迟/II为声明的模型条件。新旧v6边界不同，speedup保持null。完整FFN接合和调度扩展在#123/PR#125继续，本PR提供正式可固定的后端依赖，不重复其完整fixture/STA交接工作。2K约93分钟为小probe风险外推，不是实跑结果。

集成注意：PR119/120/122/125均有并行记录，中央台账应合并独立record后重新生成catalog/总表，不能覆盖其他记录。本PR已有cycle-116-protocol-rtl及cycle-116-conditional-model；GQA另列独立record，原矩阵记录不改写。Projects缺read:project的限制已记录；不自动合并或关闭Issue。
