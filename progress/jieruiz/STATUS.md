发布确认（2026-10-25T11:27:01.963799+00:00）：本轮LLMCompass代码/五配置结果/报告已推送并回读原字节，科学head 1bfaa067013853f1eee8ea9239ca77a050e28353；PR190开放待审、未合并，Issue186已同步。准确回执work/jieruiz/186/COMPASS_PUBLICATION.json。

# Issue186 / PR190：LLMCompass独立数字基线已本地完成

更新2026-10-25T11:19:45.927751+00:00；负责人jieruiz；分支task/186-mature-scheduling；目录tmp/mature-scheduling-issue186-20261025；base仍task/182-memory-hierarchy，PR190待审未合并。本轮代码与结果本地已完成，远端发布状态以COMPASS_PUBLICATION.json为准。

公开上游LLMCompass固定2e015fd2，最终执行3b06f295/CPU Slurm3052五配置全部completed；初轮4aef5971/3047保留（补选词与RMS计数前）。5项合同测试各配置通过，真实GQA tile/Softmax mapping完成，136上游文件SHA不变；模型形状/执行/配置/结果SHA核验。无GPU/PPL/RTL/PT。

2K B1 Qwen3-4B数字服务ms/token：A1004.162（旧launch代理20.989，非实测）；小资源HBM256=177.808、HBM186=178.006、补共享SRAM限制350.977；当前TLM402.629。共有4.626251776G MAC。小配置MAC下界90.356ms，SRAM16.705GB/64GBs下界261.020ms。原生GEMV忽略L2，当前TLM则串行shared fill/read/compute；Softmax/部分和位宽/阵列也不同，净差不等于调度可节省。完整结论architecture_tlm/unified_v6/LLMCOMPASS_COMPARISON_ZH.md；结果results/llmcompass_20261025/final，记录本O12。

远端原件/home/Hongjie_Zeng/projects/pbit-scheduling-issue186-20261025/compass_2e015fd2/run_3b06f295；source与upstream不可修改，lookup只在scratch。恢复先核Issue186/PR190、运行collect_compass.py再report_compass.py核SHA和阶段表，无需重跑。下一步先明确数字参考资源档位，再实装共享SRAM/本地供数/计算的有界重叠；Attention内部模型单独比较。保留现有TLM默认和HBM旧结果。Projects无read:project，待有权限成员同步；不自动合并。

---
# Issue186 / PR190：HBM完整25项已核验

发布确认：HBM代码、报告和25项结果已推送并逐字回读核验，科学head 092fe9e8dea2deae9ec943f744f8a144bbc334c1；PR190开放待审、未合并。HBM_PUBLICATION.json为准确回执。

更新2026-10-25T10:44:17.130922+00:00；负责人jieruiz；分支task/186-mature-scheduling；目录tmp/mature-scheduling-issue186-20261025；base task/182-memory-hierarchy，PR190待审未合并。

本地实现和25项全部completed/SHA/36层验证：e7505ee4的Slurm3019/3020（17项），43b7b1ff的3037/3038（8项）。104回归，36微基准；旧DDR四模式逐段时间/能量不变。2K ms/token：BF16 599.340→402.629；W8 426.364→333.664；SC R8准确503.639→438.038；SC R8筛选PV三seed474.154→407.167。核心100MHz、共享8MiB/64GBs SRAM、随机采样不变。HBM16GiB理论256GB/s、实际连续读185.786；新增256B主机事务/有效64admitted，PV32→128分批。源快照不可改。

成果architecture_tlm/unified_v6/HBM_RESULTS_ZH.md、HBM_TIMING_ZH.md、results/hbm_20261025、记录本O11；work/jieruiz/186/HBM_DELIVERY_AUDIT.json。原始RESULT/trace保留个人远端pbit-scheduling-issue186-20261025/hbm_e7505ee4和hbm_43b7b1ff；无运行中本任务，无GPU/PPL/RTL/PT。HBM占位电流禁用，总物理能量/面积null，不比较不完整小计。GU数值宏/普通算术吞吐未签核。FFN主体约267ms不随HBM显著变快；KV同组单通道热点尚在，可另测XOR映射，未宣称已优化。

本轮发布状态以HBM_PUBLICATION.json为准；尚未生成回执时仅本地完成。保持Issue186开放，PR不自动合并。看板缺read:project，待有权限成员同步。恢复先核远端Issue/PR、collect_hbm.py及--pipeline，analyze_hbm.py --require-complete，再report_hbm.py；勿重跑健康/已完成任务。
