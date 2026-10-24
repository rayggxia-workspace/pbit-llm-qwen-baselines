Closes #179. Related #96, #173, #177.

main此前没有完整TLM。本PR仅导入集成版本d6d3399的最小可运行依赖与校准小文件，继续扩展unified_v6，提供统一入口`python -m architecture_tlm`，不合并其他研究PR或历史大型结果。

FFN切换为W8、x固定四档T64/K64、g/u固定四档P8、真实尺度signed8驱动LUT、联合32格三路AND直连Wd、7桶宽整数累加及最终BF16。删除该路径的动态absmax、精确SiLU、连续z落盘及z再编码；明确计入本地权重容量、系数/部分和/重放、随机吞吐和宏排空。保留原Attention及真实Issue95源，新增NL独立随机消费者为有限宏接口；Qwen3显式head_dim128/Q宽4096及QK归一化补齐。

验证：74项单元/机制检查通过；7组完整36层Qwen3-4B decode、8组完整形状单FFN敏感性、15组三seed小形状整机检查完成。校正拒绝的1152头/层均得到128有效输出，proposal/拒绝/输出、随机服务bit与阶段周期守恒。12份封存manifest（含保留的4组初版）原字节SHA通过；40个未修改导入文件与来源逐字节相同，无main历史文件删除。数值时序执行提交3a9ddfb1；结果见architecture_tlm/unified_v6/RESULTS_CURRENT_ZH.md。

默认100MHz条件下，新FFN＋准确Attention / 筛选PV / 筛选校正拒绝分别1412.979 / 1366.264 / 1585.054 ms/token。这里只是条件调度结果；不是同面积、同质量两种芯片的加速比。新FFN的单层完整形状敏感性默认20.088ms，非线性随机源降至20字供给后28.789ms，明确保留供给阻塞。

限制：GU定点恢复与训练FP32参考仍待数值对齐；新增独立随机源映射、权重本地宏及若干STA/PPA未闭合，完整能耗/面积保持null。本次DRAM用link后端，不是DRAMSys重跑；时间是宏参数条件估计，不是同面积/同质量芯片性能。用户已明确授权本轮验证后合入main。
