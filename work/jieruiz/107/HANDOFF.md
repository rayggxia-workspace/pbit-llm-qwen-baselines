# Issue107最新交付：8类SS/TT PPA脚本（2026-10-23）

发布前实时检查确认PR109/111已合并；本批改用task/107-digital-ppa8-ss-tt后续分支，仍为Issue107，复用本工作目录。已合入最新集成e8705765ed3286b225e042378d57e5d010e221ee，台账的digital-107-functional旧原件路径采用审核修复版，其他35条逐字节保留。后续PR编号/推送回读见ppa8/PUBLICATION.json。下文关于PR109的描述指本批开始时基线，不能作为当前PR状态。脚本包既定来源SHA不变，不重新生成同名不同字节包。

本轮按用户要求落实8类现成模块KIND0/2/4/5/6/7/8/21，不扩大为随机矩阵/SRAM/整机。脚本源码6bc3389de08fba8250a17f0991849a4368898205，正式architecture_tlm/digital_ppa_v1/ppa8；原RTL23e8d65f无改动。55nm SVT SS1.08V125C、TT1.2V25C；100MHz/10ns、setup2ns、hold0.1ns。2个smoke再14个remaining，或all16，不重复提交活跃任务。每项1次DC、1次VCS编译、12次数值检查、9个PT窗口；三个seed17/43/101，stress只功能，stream/burst/idle用于功耗。

源码包本机根digital_ppa8_ss_tt_100_20261023_v1.zip，2173363B，SHA ace9d1657e67f2db6ab8064c59fce071247fe9fdf768e6fd4044fe44eeea39d4。包内全部RTL/ROM/转换依赖和参考向量，不含PDK。最终解压96场景17070输出通过，6流程守卫/Python3.6语法/3.8运行/Tcl/Bash通过。首次本地Icarus正斜杠-B路径导致未启动编译，换Windows原生路径后通过；不是RTL修复。原始记录含失败保留于project_archives/digital_ppa8_20261023/LOCAL_VALIDATION_RAW.tar.gz，SHA ce744dc4c68e96074bf0eb0a84c39fb1807bf0f949a40fe8fae3eafc8b8e21fb。DELIVERY.json记录精确来源/校验。

重要：DC/VCS/PT均未在本地运行，没有新的功耗面积或STA结果。VCS脚本为零延迟门级，STA独立PT；不能由功能通过证明100MHz时序达标。功耗计入边界寄存器，分组另给；不含CTS/布线/真实毛刺。近似SwiGLU不继承PPL，编码按64元素组，恢复不得重复乘64/72。KIND2/8混合1/14/76/128/512帧流的单位能量不是单独S128实测，KIND8短帧仅部分和协议测试。

台账基线为PR111@2b7935f4，其目录被完整引用到本任务分支以便同PR登记，未改110工作树；新增记录digital-ppa8-20261023-prepared，现36条/532行，16行工艺阶段均not_run。发布时注明依赖PR111，保留既有记录。根目录台账只作为同步阅读镜像，不独立编辑。任务在本地完成，远端发布状态以ppa8/PUBLICATION.json为准；Projects仍待read:project。未提交任何BSCC任务。

用户操作：上传根ZIP到远端pbit_chimera_pipeline_20260920，unzip -o，进入release目录，python3 package.py，bash submit.sh smoke；SS/TT KIND21通过再bash submit.sh remaining。下载results/<arrayJobID>_<index>_reports.tar.gz及logs/*.out/*.err。失败按相同release/库使用REUSE_RUN=<原ID> bash submit.sh <index>；源码/库变更必须新目录。恢复前查已运行作业，不重交健康任务。下一步收到实际报告后新增真实run台账，不把计划记录改成另一执行版本。

# Issue107最新补充：仿真需求分析（2026-10-22）

接续用户“最新TLM还需哪些Verilog具体仿真”，jieruiz沿用本task/107分支、PR109、tmp/tlm-digital-issue107-20261022。没有新建全量工作树；原RTL/功能证据/结果包不改。新成果已实际推送科学head e7b5d256ca00a725394c4ee8decf4d562a672f5c，8关键远端blob回读一致；PR109及Issue107已更新，待审未合并。publication和远端核验在latest_gap/PUBLICATION.json、REMOTE_VERIFY_SCIENCE.json；后续metadata不改变原报告/来源。

正式文件LATEST_TLM_RTL_GAPS_ZH.md、LATEST_TLM_RTL_REQUESTS.json、PPA_RETURN_TEMPLATE.json在architecture_tlm/digital_ppa_v1。11组任务标出P0/P1、具体接口参数/位宽/并行度/活动、边界/计费单位与TLM替换字段；可直接跑的现成probe和仍缺整合RTL分开。特别指出SC计数状态48KiB/8tile、32KiB权重驻留契约、DMA6.4GB/s与16GB/s假设的缺口、完整赢家计数/选秩不同于现有0/1/多树、9bit驱动码与R8不同。

只读对象PR103 b05fb36d8104eb07b33a9af13c747ca2722728cf、PR111 2b7935f4bbb16c37cb1f59c5a2a394ae005e2b8b、原RTL23e8d65fbd84cf548ab82a6c9cfe423d37e59ae4；源/SHA/派生数在latest_gap/SOURCE_INDEX。check_plan.py验证32源、引用路径/位宽/带宽、288组精确档内加权和等价；VALIDATION_FINAL含9626内部断言，绝大多数为逐平面上界，不作为电路测试数。不重跑原功能或用户EDA。提议的新顶层不是已交付RTL；后续按各任务新增整合/功能后再送工艺，原nativeRNG/SRAM宏匹配结果复用。

无GPU/Slurm/模型PPL/训练/RTL/DC/PT/STA/新TLM执行；台账只读，没有把需求记成新仿真run。新结果用户做完后按中央台账追加记录。Project看板沿read:project不足，PR109不自动合并/Issue107不关闭。当前没有本任务运行作业，下一步等PR109评审和实际工艺表征；本轮没有运行中作业，报告/SHA/Issue/状态已同步，保留最小待审目录。以下保留原完整RTL交接。

# Issue107 交接

2026-10-22，jieruiz，task/107-tlm-cycle-digital-rtl，基线eb317e4f6fb1b0d8844887401f3275f128ef8a83。独立目录C:/Users/86134/Documents/a_P_BIT/tmp/tlm-digital-issue107-20261022；目标rayggxia-workspace/pbit-llm-qwen-baselines，PR base=pbit-tlm-attention-details-20261016。

## 已完成与准确版本

正式入口architecture_tlm/digital_ppa_v1/README_ZH.md、CYCLES_MEMORY_AND_RTL_ZH.md、PPA_TASK_ZH.md。52封存情景从eb317e4f原blob读取，字节/阶段和/唯一配置核验；新观察只读引用PR105 fa4ef7b，不更改该任务。cycle_audit.py和write_report.py可重建周期表；没有重跑模型或TLM。

最终RTL/测试源23e8d65fbd84cf548ab82a6c9cfe423d37e59ae4。Icarus10.1，Python3.12.14；66功能组/12870逐位输出、63活动场景（21KIND×三模式，seed7、128拍）通过；29份源码/ROM/测试/独立参考与该Git提交原字节一致。原JSON results/RTL_VALIDATION.json不重写，bytecheck另存。Tcl仅结构解析，无许可工具执行。21KIND之外有SRAM/DMA控制及4lane数组功能测试；不能把功能仿真一拍当STA可达10ns。没有新PPL/GPU/Slurm/DC/PT/实际DRAMSys或随机源实现。

便携源码包本机C:/Users/86134/Documents/a_P_BIT/digital_ppa_v1_20261022.zip，113124B，SHA d8004f0fdf586dc020e99c3d6e6ed3b29050a652a55af037220af898c03aafb2，44成员逐字节核验；BUNDLE.json。包括所需旧转换RTL/数值参考，工艺库/工具/大波形/模型不在包中。Git正式源码可供其他成员；本机ZIP路径只在本机可访问，不宣称已上传共享盘。

## 失败、原件与清理

最初Icarus沙箱DLL重定位失败，已有工具在允许环境运行成功。compile_v1有hex/三元运算词法预检错误；validation_v1捕获subnormal负指数与unsigned bin混算导致true-one错误，已明确signed整数后修正。v2为首轮通过；v3含新增边界/活动通过但部分历史源码Windows检出CRLF，原输入单独ZIP保留；v4恢复Git字节通过；v5加入最后一次平均/转换输入隔离通过；v6改善RoPE及正域非线性功耗刺激、补翻转和来源检查后最终通过。未放松数值容差。

原始编译/向量/命令/波形/逐次验证本地归档project_archives/tlm_digital_issue107_20261022/RAW_VALIDATION.zip和RAW_INDEX.json，全部成员SHA核验后仅回收本任务compile_v1、validation_v1..v6。RAW_ARCHIVE.json记录最终总数/大小/SHA。主待审工作树保留；没有删他人工作树或唯一结果。V3原源码ZIP/换行索引也在同归档目录。format_conversion新增.gitattributes只固定源文件LF，未修改任何算术代码或冻结结果。

## 当前状态、限制和恢复

科学成果7b12fea03bd2596cc206f3f0c32571196688e665已推送；PR109 ready/open待审、未合并：https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/109 。9关键远端blob原字节核验通过，PUBLICATION/REMOTE_VERIFY封存该科学head，最终任务分支head见Issue107回执及本地project_archives/tlm_digital_issue107_20261022/FINAL_REMOTE_VERIFY.json。不自动合并/关闭。无本任务远端运行作业或定时。PR105/103仍分开；不接管95随机源或7已有Q10表征。Projects本轮GraphQL实测见PROJECTS_CHECK；缺read:project待同步，不影响repo admin/push。

1. 读长期记忆0/1/12与本主题、最新Issue107/PR/STATUS，复用本目录。
2. 周期重建用cycle_audit.py/write_report.py；依赖基线52原件和PR105观察Git对象，精简检出不要漏依赖。
3. RTL验证从Git根运行README中validate.py命令，--out为个人目录全新路径。最终执行完整命令与输入SHA在归档validation_v6/COMMANDS.json；每次先提交源，保存结果后不改原件。不要把旧正常结果又重跑为新的模型结果。
4. 用户按PPA_TASK提供同PVT/频率/位宽、WNS/TNS、latency/II、有效活动/能量、面积与覆盖；先查STA，再按真实服务契约回填时序和成本，删对应旧代理收费。
5. 保留阵列权重驻留、计数/局部状态、随机源速率、转换/归约、CDC和DRAM条件等缺口。近似非线性/融合恢复须另验证质量；不能继承旧FP32 PPL。
