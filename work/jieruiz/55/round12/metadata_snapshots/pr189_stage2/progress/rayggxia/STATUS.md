# Issue204：计数器缩位分析（2026-10-28）

负责人rayggxia，沿用task/204-matrix-t32和PR205，base main@d83eeb1f。分析基线a288901fa783277a134bf7052e49d4e09437308f；既有EDA科学源5dcef4fd99200418f804cbd51f3bf325d1cbea60。独立目录architecture_tlm/matrix_counter_precision_20261028，不修改单尺度或四档冻结执行输入。

用户要求统计32拍各权重位平面累计，研究饱和/截断和低位舍弃，查论文是否必须全按最大值位宽。本轮只做冻结合成数据的数值回放与一手论文核查，不新跑模型、RTL/DC/PT或改变台账83个硬件run。BF16复跑/模型语料字段不适用：未做模型推理/PPL比较；Issue206只读权重量化合同和已封存源码成员SHA，不继承其质量或PPA。

已完成：功耗432输出、功能432输出全部独立重构等于原OR oracle，60个原始输入SHA核验；主M8统计384输出、24条驻留W行，各32拍。B0–B6平均绝对累计53–58、99分位166–220；B7平均1.36、最大32。9位饱和额外NRMSE0.242%；B0–B6用9位、B7用7位为70位状态；删除B0后61位、额外NRMSE1.063%。均以原OR输出RMS归一，不是模型准确率。全8位饱和10.681%、回绕74.642%，负面结果与极值功能退化均保留。64位混合校准例在seed1009留出误差1.072%，尚非模型候选验收。

理论修正：严格signed [-512,512]需11位，但10位只在最后一拍+512缺1；每平面误差≤1、8平面加权原始误差≤255。固定权重支持Gp个OR4组时，精确计数范围±32Gp，可依位平面进一步收紧。逐拍饱和不等于帧末饱和；截计数LSB会丢失逐拍小增量，相关断言已通过。

论文：REX-SC §II-C明确6位饱和对照；SC-DCNN §4.1/Fig7近似并行计数（非直接缩时间计数）；DS-CIM §III-D四拍latch缓存后更新宽累加器。原文链接和适用范围在SOURCES.json/REPORT_ZH.md，不把论文PPA移植成我方收益。Issue206冻结aa43d00d的PoT量化clamp(-127,127)，7个幅值平面；仅在采用这一接口后B7可无损删，不改旧完整INT8边界。

成果REPORT_ZH.md、RESULTS.json、MANIFEST.json、WEIGHT_CONTRACT_REFERENCE.json；复现命令python architecture_tlm/matrix_counter_precision_20261028/analyze.py、report.py。分析已推送，科学源904068b9e70bab558f93c93ff2c230216164cf51；13文件完整tree与6关键回读核验，PR205待审未合并；回执PUBLICATION.json。无新服务器作业；Projects既有权限限制待同步。

后续建议：11位精确对照，10位保守端点饱和，9位/低位删除候选；先补真实权重/激活分布和独立模型质量，再按同条件RTL/DC/PT测饱和与门控成本，不按状态位数直接推功耗。不要重跑已完成96窗口或启动昂贵模型任务。

---

# Issue204 单尺度INT8完成回执（2026-10-28）

发布确认：单尺度科学源5dcef4fd99200418f804cbd51f3bf325d1cbea60已推送PR205，217文件完整tree与8关键逐字/blob回读通过；Issue204正文已同步，PR ready/open未合并，本任务无遗留作业。

负责人rayggxia，task/204-matrix-t32，PR205 open/ready/unmerged，base main@d83eeb1fc6b89a3dff51b5b62bf79acf665c7166，科学输入基线cc04dee9890ea6dcfbeee872b0cab914d3b1c2c6。本地目录tmp/matrix-t32-issue204-20261028。沿用原Issue/PR，不改旧四档冻结输入、其他任务或整机/模型默认。

用户决定：64路共用一个尺度、真正signed INT8[-128,127]、N64/T32；每幅值位平面和符号先OR4，64→16个事件，再做精确并行计数。实现3版：V1直接实现；V2把每组正负各6位改为一个signed7时间计数；V3使用专用无符号popcount并隔离末端恢复输入，保留signed7组计数。mode3每拍popcount16再时间累计；mode6每组独立累计后求和，二者同事件OR oracle全等。SC内部20位，数字22位，输出符号扩展32位。

全部完成：V1 672帧、V2 96帧、V3 288帧，共1056帧功能PASS；16个综合变体、96个active/idle PT窗口，SS1.08V125C100MHz。3原始执行包和22报告归档远端/本地SHA/大小及逐成员校验；Slurm全部COMPLETED/0:0，本任务无遗留作业。执行索引EXECUTION_INDEX.json，结果architecture_tlm/matrix_single_scale_20261028/results/FINAL_SUMMARY.json和REPORT_ZH.md；源包/报告在project_archives/matrix204_single_scale_20261028。不得重复昂贵测量或改写冻结输入。

M1：精确树179.906pJ、OR4-popcount16优化版101.932pJ（能量-43.34%、面积-16.51%），16路signed7独立时间累计优化版348.483pJ；数字位串行38.797pJ。M8优化OR4 790.767pJ/帧、数字位串行262.133pJ/帧，每帧8点积。还不能证明SC能效胜数字。共同尺度省去bin选择/移位，但新旧码域、刺激及位宽也改变，不能作纯尺度消融归因。

主PPA为16帧驻留权重、uniform signed INT8输入、公共R8，三seed均值；SC原始期望=数字点积/4。OR损失另报，时间计数硬件改动不改变OR结果；真实模型单尺度质量未验。面积raw×0.81保留双列，不缩放功耗/时间。外部权重存储/保持读口、RNG/比较器、输入量化/尺度选择、最终浮点恢复、物理广播线及CTS/SDF/SPEF在外，CE未冒称ICG。全部时序与功耗警告保留。

中央新run matrix-single-scale-204-20261028，增量union check/render并保留其他record；结果见REGISTRY_CHECK.json。源码/结果已推送，科学源5dcef4fd99200418f804cbd51f3bf325d1cbea60；发布回执见PUBLICATION.json和最新PR205。Projects既有权限限制仍待维护者同步。下一步审阅计数实现、hold/功耗表告警；真实ICG、SRAM驻留端口及真实后训练模型同质量验证独立开展，不自动启动昂贵模型实验。

---

# Issue204：T32矩阵改进验证

更新时间2026-10-28；负责人rayggxia。分支task/204-matrix-t32，PR base main@d83eeb1fc6b89a3dff51b5b62bf79acf665c7166；独立目录C:/Users/86134/Documents/a_P_BIT/tmp/matrix-t32-issue204-20261028。未修改Issue193/186源码或其执行快照。

本地首轮完成：六算法×M1/M8×三seed×15帧，v1/v2各540帧VCS功能通过；8个固定top完成综合、门级及48个SS1.08V125C100MHz PT窗口。恢复时队列已空，不重交EDA。27原始报告归档远端/本地SHA/大小与逐成员SHA均核验；9个执行包原字节保存。报告architecture_tlm/matrix_validation_20261028/results/REPORT_ZH.md及FINAL_SUMMARY.json，精确执行/终态见work/rayggxia/204/EXECUTION_INDEX.json。已推送PR205（ready/open、待审未合并），科学源f19b603578ba215433ae68809c7eed3f30c7bf55；144文件完整tree与本地一致、8关键文件逐字/blob回读通过，回执work/rayggxia/204/PUBLICATION.json与REMOTE_VERIFICATION.json。

M8共享输入计数相对S0：1331.137→479.067pJ/帧（−64.01%），174255.20→168423.79µm²（−3.35%），37→40周期（+8.11%）。M1位平面省能16.88%、面积多37.80%；M1先计数反而多耗能18.40%。普通OR4共享源同号同位权例低估75%。D1确定位串行34.467pJ/帧、11周期、22054.00µm²，低于M1 S0的165.994pJ/帧；尚未证明随机整体胜数字，M8数字同规模尚待扩展。

面积均已按用户要求raw×0.81并保留原始列。S0两尺寸hold−0.041792ns；S2 M8 setup仅0.000099ns，功耗表范围等警告保留。前布局，无CTS/SDF/SPEF、真实模型质量、存储/RNG/比较器/编码/最终浮点尺度及实际广播线成本。D0是未优化q9参考，不称成熟最佳INT8。SRAM/门控权重与内部位宽收紧属于后续，不伪称本轮全链路完成。

中央台账新增matrix-t32-204-20261028，82记录联合check/render、81旧record逐字保留；main缺全台账，本PR只交付增量record及校验回执，不复制别人记录。失败波形/别名/调试可见性版本保留；v3旧数字后处理实际已跑1分34秒后取消并由v9替代，如实记录。Projects既有权限限制待同步。下一步：审阅本轮PR，修hold/功耗表范围，M8数字控制、SC位宽/真实ICG及驻留权重端口验证；不自动启动新模型或昂贵作业。
