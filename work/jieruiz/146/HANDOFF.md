# Issue146：CIM 前端 RTL/PPA 交接

v2发布已确认：源码7b097d194f81042dfd771bf01b38599bacf01aae已推送，PR148 head经GitHub API核实一致；Issue146评论6366058954、PR148评论6366059597已发布。PR未合并，无EDA作业。详见V2_PUBLICATION.json。

2026-10-23 v2增量：沿原分支/PR148；原RTL/TB字节完全未改。新增RUN_BATCH_ZH、environment/submit/job/summary/collect/local_smoke/test_delivery，完善run/package与DC/PT分类统计，修复生成buffer的Tcl数组插值错误。版本包根sc_cim_frontend_ppa_20261023_v2.zip，49471B，SHA f2ef9036c30adcbccd4a2c2c24543fe27061ff04facb3d6a27948f294b701228；33源manifest项，SHA34d5b2031c141b41d8b8f14096d12539a969c5a1dbeb9027219f70b0d0caf856。VERIFY_V2.py/V2_VALIDATION.json保留命令和核对记录；11辅助测试、4小RTL/48窗口实际通过，无本轮DC/VCS/PT。Bash只读检查通过。第一次本地Icarus路径格式失败记录保留，第二次v2_local_check2成功。

v1 ZIP与原始证据保留；旧manifest另存project_archives/cim_frontend_20261023/SOURCE_MANIFEST_V1.json，旧台账只更新可恢复地址不改SHA；新台账cim-frontend-146-ppa-v2-prepared。读取根镜像时保留其他任务新增记录。根/canonical备忘录已追加本轮状态。

执行：上传v2 ZIP至BSCC项目根，source ~/.bashrc，unzip -o后进入sc_cim_frontend_ppa_20261023_v2，python3 package.py --verify；bash flow/submit.sh "$BASE/cim_frontend_runs/smoke_$(date +%Y%m%d_%H%M%S)" smoke。4类xSS/TT共8子项，M1/1seed/2PT窗口；正式all使用M64（SNG/Q探针M1）/3seed/36窗口。每项4核32GB12h、最多2并行。下载*_reports.tar.gz及logs，COMPLETE不等于STA签核，保留provisional告警。BUF_REF=AUTO为真实最小面积非反相BUF情景，不代表最优物理驱动。

本地已有修改work/jieruiz/146/PUSH.json未覆盖、不纳入本轮提交。最终源码发布/阻塞见V2_PUBLICATION.json；Projects原read:project限制待有权限维护者同步，不自动合并/关闭Issue。无远端运行任务。

2026-10-23，负责人 jieruiz。目标 workspace `rayggxia-workspace/pbit-llm-qwen-baselines`；分支 `task/146-cim-frontend`，base `pbit-tlm-attention-details-20261016` / `6966739a5223680888bf0315f7bb4f73423a1ae6`。独立 checkout 为 `C:/Users/86134/Documents/a_P_BIT/tmp/cim-frontend-issue146-20261023`。Issue146 已建立并核实；原计数器 Issue133/PR135 只读，head `7f38018b0de2c406a3ae0c9f4eb65eaef4794051`，未修改。

本地完成：`architecture_tlm/sc_cim_frontend_20261023`，包含SNG、驱动、W8原始门控、SRAM-Q数字探针、SPICE待绑定模板、DC/VCS/PT流程、中文说明。最终 compact 27配置/seed、13620周期对照通过；5流程检查、Tcl完整性、12实际小RTL波形窗口×115信号检查通过。较早完整N64/M64前端本地/外部源各3seed通过，但同轮独立大门阵列180秒超时；不冒充全部大配置通过。没有DC/VCS/PT/SPICE/布局、新PPL或服务器任务。

ZIP：根 `sc_cim_frontend_ppa_20261023_v1.zip`，36990字节，SHA256 `73bee486fd7d1f0fff0b3ba6bf915836715ed9496e92902351f86c18c68bda6d`。解压manifest和5流程检查通过；包可独立运行，不依赖Issue133目录。其通用波形/PVT助手副本来源保存在HELPER_PROVENANCE.json。

原始验证归档见 RAW_ARCHIVE.json、WAVE_ARCHIVE.json，位于 `C:/Users/86134/Documents/a_P_BIT/project_archives/cim_frontend_20261023/`，包含失败尝试、执行RTL原字节及命令/向量/日志。正式小结果在 `results/`；模型/数据SHA不适用，合成RTL激励，不是语言模型任务。源码绑定 SOURCE_MANIFEST.json 与 VALIDATION.json；生成波形/向量不提交Git。

下一步：用户在现有EDA环境按RUN_PPA_ZH.txt设置真实STD_DB/STD_MODEL/BUF_REF，先SS/TT M1 smoke，再M64正式。若buffer绑定/STA/超表/活动检查失败，保留原始日志，不更换成本口径掩盖失败。收到结果后在同Issue/PR新增运行记录至中央台账，不覆盖功能记录。SRAM小探针需真实晶体管网表；没有时保留参数，不阻塞数字功耗测量。

边界：旧计数器已有权重门控；初估只再加SNG和分发层次功耗。无新增概率/权重DFF副本；上游稳定概率/存储保持仍计费。SRAM全并行Q是待实现CIM接口，不宣称普通宏已有该能力。工程目标是初估，不是定制SRAM后布局签核。

发布以 PUBLICATION.json、REMOTE_VERIFY.json、ISSUE_UPDATE.json 为准；创建PR不等于合并，不自动关闭Issue。Projects权限状态以PROJECTS_CHECK.json为准，缺权限时待维护者同步。没有运行中作业，无需启动轮询。

发布更新：PR148（https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/148）已推送待审、未合并，科学交付74979fc；29个package manifest对应Git blob已核对。根台账保留其他任务记录，本轮增量后51条，任务base台账46条；合并时应保留union并render。原始临时向量/波形已归档逐成员验证，恢复见RAW_ARCHIVE/WAVE_ARCHIVE/ARCHIVE_VERIFY。
# 2026-10-24 CIM工艺预检恢复

沿用Issue146/task/146-cim-frontend；jieruiz；PR148已合并。未改功能RTL/工艺模型，新增timescale、DC复用校验、设计层级转储、VCS复合scope规范和直接常量连接核验。11项本地测试通过。原38362415/38362501编译失败；38372031移动到波形门禁后失败；38372265_2已通过SS门阵列两窗口；38372313_3/6/7通过，其余0/1/4/5在threshold[0] PT/VCD翻转率对照失败。现有四项组合预检通过，但含随机源前端未通过，不提交全尺寸重跑。最新提交包sc_cim_frontend_ppa_20261024_v5.zip，SHA8f201450f70ffd955b11851ef24a3aa70d2eb316c933ebc1b6bf29f51e3fab2e。v4未提交，v4a仅两项，所有快照不可改。下一步核对threshold[0]原始/归一化/标量VCD事件与PT，包括delta-cycle，不放宽误差门禁。原件本机project_archives/remote_job_audit_20261024/reports；远端BASE/cim_frontend_runs/smoke_recovery_20261024_v5。台账cim-20261024-recovery。发布以PUBLICATION_20261024.json为准，未自动合并，Projects待同步。PUSH.json先前他人改动保留未纳入。

