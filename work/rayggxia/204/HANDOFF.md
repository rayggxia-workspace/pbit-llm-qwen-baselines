## 2026-10-28 Issue204：成熟BF16本工艺N64 PPA完成，INT8经典划分已核对

rayggxia，task/204-bf16-baseline / PR209接续，源起点99bf019c。用户明确要求按经典流水划分做本工艺PPA，再查INT8；这是新授权，已实际运行EDA，不沿用上轮“无EDA”的历史结论。复用tmp/matrix-t32-issue204-20261028，未接管Issue107。结果入口architecture_tlm/bf16_ppa_20261028/results/REPORT_ZH.md、FINAL_SUMMARY.json及INT8_CLASSIC_ZH.md。

CVFPU77811635/common_cells9afda9ab精确上游，BF16×BF16/FP32乘加及独立乘/加；四lane非融合DOT4树+四FP32交错上下文，N64正常29拍valid、帧间隔30拍=300ns。五top45个三seed窗口、27696标量+108整帧功能比较及对应门级回放已完成；48个INT8派生帧另用Fraction精确点积核验。合成数据，无模型/PPL；不称单轮舍入fusedDOT4或最佳生产矩阵引擎。

N64原始面积55454.76µm²，raw×0.81等效0.044918mm²，normal平均1.923333mW、577.000pJ/完整64项点积；INT8派生输入556.200pJ。相对SC54(0.005524mm²/69.4633pJ/350ns)约8.13倍面积、8.31倍能量，SC帧间隔长16.67%。这是异精度/不同合成激励的计算核对照，不能宣称整片或同质量优势；既有INT822.19/38.80pJ仍比SC省能。

原共享reset0.02..1ns约束导致async removal负余量。相同SHA网表补充STA明示下降沿附近4.5..5.5ns释放，数据约束不变、无false/multicycle，N64setup/hold 0.000027/0.143288ns；四独立标量en→valid仍−0.061165ns hold，未修复。功耗表范围、高扇出和极小setup余量保留；无CTS/SDF/SPEF或复位分配实装，不称物理签核。

v1..v7负结果/源包/原始报告保留，原字节、远端SHA和全部报告成员核验。v6标量完整，v6 N64仅TB time变量裁剪失败；v7只修波形裁剪并核验全部RTL/bench/fixture/库绑定/约束后复用相同网表，未重综合。补充STA独立冻结。执行是base99bf019c+uncommitted快照，后续源码提交需按ZIP逐字绑定，不伪造执行提交。准确批次见work/rayggxia/204/bf16_ppa/RUN_LEDGER.json；本轮作业已结束，不重交。

中央run matrix-bf16-204-20261028；分支与根镜像分别向各自最新record集合增量登记，旧record字节均保留，绝不用分支子集覆盖完整镜像。准确数量、check/render及原件校验见REGISTRY_CHECK.json。源码/报告准备完毕；实际推送提交和PR状态以同目录PUBLICATION.json为准，PR待审未合并、Issue不关闭，Projects沿既有限制待维护者同步。

INT8经典实现采用signed8×8→16位积，output-stationary INT32反馈累加，或DOT4/8平衡树后累加；固定N64无bias最坏范围可用22位精确，但可复用长K/带bias经典基线应保留32位，再把22位列独立消融。Gemmini/NVDLA一手源码/文档已核查；推荐100MHz先用乘法级+累加级，是否树内增级交STA决定，无新INT8 PPA冒称。

## 2026-10-28 Issue204：已找到完整28nm BF16数字阵列功耗证据

rayggxia，task/204-bf16-baseline / PR209接续，源起点d6aa128997072acd837508c7703844bf950603ec。用户要求确认是否没有28/55nm BF16数字矩阵依据、缺乏时再自建仿真。二轮已找到MFSA完整正文和FlexBlock作者PDF，纠正首轮检索不足；两原PDF及表II/V原图已下载、SHA绑定、渲染核对。当前入口architecture_tlm/bf16_baseline_20261028/README_ZH.md、LITERATURE_RECHECK_ZH.md及literature_recheck.py。

MFSA2026-10-14预印本：28nm SS0.72V/125℃/1GHz，16×16全格式数字阵列，BF16输入/FP32累加；后布线RC+LLM门级轨迹稳态估算1.85W/1.024TOPS，排除reset/预装/排空。两op/MAC由256PE×两项×1GHz核验，得3.61328pJ/MAC、231.25pJ/64MAC；对SC54核69.4633pJ为3.329倍，仅异工艺/异精度/异边界归一，非N64冷启动延迟或整片节能。原73pJ摘要换算保留低完整度版本，不作为唯一参考。

FlexBlock作者文件头为2203.06673v1：65nm BF16 SA128×128、333MHz、9.84W、1.77TFLOPS；P/T约711.59pJ/64MAC，但吞吐只占乘法器理论峰值16.22%，属含利用率/周期模型的负载归一，不能据此宣布10倍优势；SRAM另CACTI。外部65nm面积不套本项目0.81。55nm严格同PVT/数据/接口仍未找到已核验匹配项，不断言不存在。

有了可用28nm参考，用户“确认没有才自建”的条件未成立，本轮未启动新RTL/EDA/Slurm/GPU/PPL，中央台账84条不变。后续本工艺表征仍是独立工作，不冒称已测。实际追加提交/回读见work/rayggxia/204/bf16_baseline/LITERATURE_PUBLICATION.json；PR209待审不合并，Projects沿既有限制。

## 2026-10-28 Issue204：BF16数字基线调研与可复算预算
发布切换：原PR205已于2026-10-28T10:51:05Z合并；本BF16补充改用task/204-bf16-baseline，基于main@7874891，准确新PR查PUBLICATION.json。原成果不重跑。

rayggxia，同task/204-matrix-t32 / PR205，复用tmp/matrix-t32-issue204-20261028；本轮读取既有证据及一手论文，无新RTL/EDA/Slurm/GPU/PPL，中央台账84条不变。结果architecture_tlm/bf16_baseline_20261028/REPORT_ZH.md及ESTIMATE.json；estimate.py核验旧SS/TT两份summary SHA、三seed单位和负时序，绑定旧RTL，重算预算。

主比较合同BF16×BF16、FP32累加。28nm Li等TCAS-II论文作者机构摘要可核实1761.41GFLOPS/W；条件按2 FLOPs/MAC为1.13545pJ/MAC、64项72.6691pJ，非55nm已测事务，全文累加/舍入/FLOP计数/面积/N64延迟未核验，不按工艺或0.81换能量。与本SC54计算核69.4633pJ接近，不能据此宣称巨大节能。SC需数字>1.08536/5.42682/10.85365pJ/MAC才分别持平/5倍/10倍，均未计两侧缺失前后端成本。

旧本工艺BF16标量KIND2在SS100MHz setup−26.219376ns、TT−10.537953ns；原731输入/5变长帧不是N64。其通用转换和26次依赖规格化循环值得优化，但未做新网表关键路径归因，不能用旧失败实现代表成熟基线。建议补专用乘法、树LZC FP32加法、融合MAC、共享处理DOT2/4/8与真实N64反馈/归约封装，验证35拍/350ns附近预算；两个算术lane不自动保证32拍。旧原件保留，不接管Issue107；BF16与SC W8/T32/OR4精度不同，匹配量化数字控制仍需保留。

研究稿/脚本本地完成；实际推送状态查work/rayggxia/204/bf16_baseline/PUBLICATION.json和PR205，不宣称新BF16 PPA已完成。Projects沿既有限制待有权限维护者同步。

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
