# 实际验证（2026-10-17）

- 两组原始路由重建：24层×2token×14个查询头，原QK留存、GQA union有效K、Link256物理K字节全部与历史计数相同。
- 理论共享U公式与饱和概率统计基于同一分数/校准参数；不是新选择策略PPL。
- CLI再次完整重跑，输出JSON与已保存结果一致；重复输出路径明确拒绝。
- 校准原字节SHA匹配历史记录；published配置语义相同但换行散列不同，使用归档和-text保留。没有重写原结果。
- 归档输入保留原始CRLF；目录属性同时将CR视作行尾，允许diff检查而不改原字节。新生成报告/代码/JSON保持UTF-8/LF。
- 本地v5两场景的四项K/V字段与已发布v3值一致；初始化差异和本地未发布v6流程已归档。
- 3个新文档相对链接通过；git diff --check通过。发布时另核对明确文件范围、提交blob SHA和远端状态。
- 没有BF16/PPL、完整DRAMSys、RTL/DC/PT或芯片测试。合成高斯输入不能代表真实Qwen头间相关性；没有改变运行时默认。
- 复核命令：python architecture_tlm/audit_screen_k_traffic.py --output <new-temporary-file.json>。

发布核对：身份/仓库/base重新确认，明确文件范围提交，所有成果与暂存blob SHA匹配；原始校准byte保持不变。PR已创建，未合并。

## MHA/GQA与旧LLaMA实验补充

只读核对两套历史实验：joint_pv目录没有QK筛选；qk_ising目录确实包含QK块筛选。后者两种筛选方案各3种子×32层，逐项断言候选比例等于KV组并集，均值匹配原summary（26.1631%与26.0795%）。记录源码/结果SHA和已有语料/权重分片SHA出处，未重新核验大权重，也不猜缺失revision。筛选结果属于4096-token固定后缀协议，非完整WT2；Python仍gather全部候选V，逻辑比例不是物理DRAM读数。没有重跑PPL或修改旧结果。GQA/MHA的25%保留示例只作数学说明。
