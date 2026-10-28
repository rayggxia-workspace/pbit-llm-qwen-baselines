## 最新：参数化模块能耗库已发布（2026-10-28）

科学源080729c314e2e0e62efada3e32d4c27c7eac4bb5，同PR205待审。33配置/396窗口/99功能回放完成，67报告/2源包核验。恢复优先读module_energy/HANDOFF.md和architecture_tlm/module_energy_20261028/results/REPORT_ZH.md。无本任务遗留Slurm，旧位宽/单尺度结果如下保留。

---

## 最新：OR4计数位宽分析已发布（2026-10-28）

科学源904068b9e70bab558f93c93ff2c230216164cf51，同PR205，数值统计/一手论文核查，无新RTL/PPA。恢复先读counter_precision/HANDOFF.md与architecture_tlm/matrix_counter_precision_20261028/REPORT_ZH.md。原单尺度PPA和旧四档如下保留。

---

## 最新：单尺度INT8后续已发布（2026-10-28）

科学源5dcef4fd99200418f804cbd51f3bf325d1cbea60，同PR205待审未合并。新16核96窗口/1056帧、22报告/3源包已核验，83条台账联合检查通过。详细交接见work/rayggxia/204/single_scale/HANDOFF.md；旧四档结果如下保留，恢复应优先读单尺度交接。

---

# Issue204：T32矩阵改进验证

更新时间2026-10-28；负责人rayggxia。分支task/204-matrix-t32，PR base main@d83eeb1fc6b89a3dff51b5b62bf79acf665c7166；独立目录C:/Users/86134/Documents/a_P_BIT/tmp/matrix-t32-issue204-20261028。未修改Issue193/186源码或其执行快照。

本地首轮完成：六算法×M1/M8×三seed×15帧，v1/v2各540帧VCS功能通过；8个固定top完成综合、门级及48个SS1.08V125C100MHz PT窗口。恢复时队列已空，不重交EDA。27原始报告归档远端/本地SHA/大小与逐成员SHA均核验；9个执行包原字节保存。报告architecture_tlm/matrix_validation_20261028/results/REPORT_ZH.md及FINAL_SUMMARY.json，精确执行/终态见work/rayggxia/204/EXECUTION_INDEX.json。已推送PR205（ready/open、待审未合并），科学源f19b603578ba215433ae68809c7eed3f30c7bf55；144文件完整tree与本地一致、8关键文件逐字/blob回读通过，回执PUBLICATION.json与REMOTE_VERIFICATION.json。

M8共享输入计数相对S0：1331.137→479.067pJ/帧（−64.01%），174255.20→168423.79µm²（−3.35%），37→40周期（+8.11%）。M1位平面省能16.88%、面积多37.80%；M1先计数反而多耗能18.40%。普通OR4共享源同号同位权例低估75%。D1确定位串行34.467pJ/帧、11周期、22054.00µm²，低于M1 S0的165.994pJ/帧；尚未证明随机整体胜数字，M8数字同规模尚待扩展。

面积均已按用户要求raw×0.81并保留原始列。S0两尺寸hold−0.041792ns；S2 M8 setup仅0.000099ns，功耗表范围等警告保留。前布局，无CTS/SDF/SPEF、真实模型质量、存储/RNG/比较器/编码/最终浮点尺度及实际广播线成本。D0是未优化q9参考，不称成熟最佳INT8。SRAM/门控权重与内部位宽收紧属于后续，不伪称本轮全链路完成。

中央台账新增matrix-t32-204-20261028，82记录联合check/render、81旧record逐字保留；main缺全台账，本PR只交付增量record及校验回执，不复制别人记录。失败波形/别名/调试可见性版本保留；v3旧数字后处理实际已跑1分34秒后取消并由v9替代，如实记录。Projects既有权限限制待同步。下一步：审阅本轮PR，修hold/功耗表范围，M8数字控制、SC位宽/真实ICG及驻留权重端口验证；不自动启动新模型或昂贵作业。

恢复步骤：先读PUBLICATION.json与最新Issue204/PR，然后读REPORT/FINAL_SUMMARY、EXECUTION_INDEX和中央record。已有8核/48窗口不重跑。私有登录/Slurm/传输工具位于本工作目录private/，其内容不上传；读取EDA_SERVER_LOGIN_AND_FILES_ZH_20261028.txt使用现有helper。原始报告和执行包在C:/Users/86134/Documents/a_P_BIT/project_archives/matrix204_t32_20261028；源码/配置/报告成员SHA已绑定。27报告/9包已收，本轮无遗留作业。PR205待审未合并，不自动合并或关闭Issue。

修改冻结源码必须另建执行版本，不在当前EXECUTION_MANIFEST所列输入上原地修补。finalize.py为离线核验/报告生成，不执行EDA；update_registry.py为中央增量union，保留其他任务记录。中央镜像可能有并发新增，重新union后再同步，不能用旧catalog覆盖。
