# 实际验证与最终结果边界

- 真实GPU：Slurm1877重新核验模型配置、两份完整权重、分词器和WT2测试字节SHA。512/1024/2048各1024条QK行；原样BF16与捕获前向输出逐bit一致，maxdiff=0、greedy一致。记录在capture_validation/，不是PPL。
- 本地18项契约检查通过：3项LLaMA参数/地址/原生上下文，9项Attention候选物理K、稀疏V、比例预算、零预算元数据/直方图、宏面积/RNG、有限缓冲、能量/时序闭合，6项DRAM配置/拒错。命令与stdout/stderr见TEST_RESULTS.json。
- DRAM桥：两个rank、两个通道、scatter微事务通过；配置、原始日志及分项能量闭合见architecture_tlm/llama7b/dram/。这是微事务，和下面完整模型结果分开。
- 完整32层TLM：1878的60项Link、1879的18项Staggered DRAMSys、1896的4项NoPowerDown均已返回完整模型JSON，squeue不再存在运行项。服务器未启用sacct accounting；完成核查依据完整结果、82项唯一键和结果内验证，不伪造sacct记录。
- 82项后处理：模型形状32层/32Q32KV、K物理比例等于候选比例、V行去重、样本预算、无随机流SRAM、Ising宏调用/内部RNG不重计、配置/源SHA及整机能量闭合全部通过。计划集合与实际集合相等，无缺项或重复。
- 原执行快照62个文件SHA仍逐项一致，后续只增加结果、文档和独立后处理；没有修改已提交Slurm的源码快照。
- 主能耗基于完整DRAMSys和已核查Micron电流情景；Link的64pJ/byte及50mW背景只作单独结构对照。数字/随机核/互连与Ising的PPA有未标定参数，DRAM IO/PHY及板级时序也未认证。
- 新max4没有套用Qwen校准或旧LLaMA均值筛选PPL。单窗口BF16地址oracle不是随机FFN联合推理；三个地址种子不能作为FFN数值噪声或器件相关性验证。

正式成果：architecture_tlm/llama7b/results/current/{RESULTS_ZH.md,cases.csv,cases.json,summary.json,ARTIFACT_INDEX.json}。

最终发布还核对明确文件范围、UTF-8/LF（原始微事务日志依其局部-text归档）、相对文档链接、git diff --check与每份Git blob字节SHA。发布manifest记录实际文件哈希，不改写服务器原始结果。
