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
