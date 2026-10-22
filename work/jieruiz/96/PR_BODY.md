FFN短流、Attention采样器和较细存储调度此前位于不同入口，不能作为统一整机结果比较。本PR新增可选完整decode事件TLM：固定W8＋四档PoT＋T32/K32，准确计数、FP32 SwiGLU与独立z编码；数字在线/GQA对照、比例PV、max4筛选，以及已有赢家保持/校正拒绝FSM接入同一资源、活跃缓冲与SRAM/DRAM接口。

随机源按用户要求只保留本地接口，随机流SRAM/FIFO和额外概率副本为0；共享/重放、候选独立响应及种子请求单列，后端由Issue95继续。必要激活、计数、部分和、映射和输出地址仍计入。没有把未知随机源/B4短流/FP32转换成本填成零，完整物理PPA保持null。

验证：21项新机制检查、18项已有并行采样器检查、10项历史v4回归通过；三模型导航/旧anchor和新dry-run通过。冻结源fba22b1已完成52项整机情景：Qwen2K/8K各8方案×3seed共48，Llama1/2各数字准确和SC/PV完整32层单seed共4。62原件SHA、22执行Git blob、764模型契约通过；汇总报告可按原字节重建。初始整机门禁W8尺度元数据按64×64块寻址问题已修复并增加回归，旧失败原件保留。

结果入口：[完整汇总](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/task/96-unified-tlm/architecture_tlm/unified_v6/RESULTS_ZH.md)、[实现与接口](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/task/96-unified-tlm/architecture_tlm/unified_v6/README_ZH.md)。当前时间估计显示W8数字对照快于SC；四档恢复/搬运、采样器偏移重写和输出直方图是优先核查项。只报告条件时间与物理流量，不能把缺项的能量小计当作总能效。

执行期间PR97已合入上游27bf9c48；本轮数据保持冻结，未启用该后端。只读加载新上游采样器的默认路径，49项覆盖检查通过；前两次本地临时目录/辅助脚本导入失败留有原件，源码和测试未改。上游合并兼容检查与冻结数值执行分开。

范围与限制：batch1完整decode含embedding/final norm/lm_head，初始KV/摘要已存在，不含prefill/TTFT。默认Link不是新DRAMSys实跑；合成logits/配置周期不是PPL、GPU或芯片实测。FFN仍有gu→SwiGLU→down屏障，不声称全局最优。原历史默认/证据保持。

Refs #96 #95 #87 #37。不接管他人随机源或Attention质量任务，不自动合并。

Projects已实际查询，当前凭据缺read:project，待同步；仓库分支/PR和Issue状态照常交付。无运行中任务，无新定时。
