# Issue146：CIM 前端 RTL/PPA 交接

2026-10-23，负责人 jieruiz。目标 workspace `rayggxia-workspace/pbit-llm-qwen-baselines`；分支 `task/146-cim-frontend`，base `pbit-tlm-attention-details-20261016` / `6966739a5223680888bf0315f7bb4f73423a1ae6`。独立 checkout 为 `C:/Users/86134/Documents/a_P_BIT/tmp/cim-frontend-issue146-20261023`。Issue146 已建立并核实；原计数器 Issue133/PR135 只读，head `7f38018b0de2c406a3ae0c9f4eb65eaef4794051`，未修改。

本地完成：`architecture_tlm/sc_cim_frontend_20261023`，包含SNG、驱动、W8原始门控、SRAM-Q数字探针、SPICE待绑定模板、DC/VCS/PT流程、中文说明。最终 compact 27配置/seed、13620周期对照通过；5流程检查、Tcl完整性、12实际小RTL波形窗口×115信号检查通过。较早完整N64/M64前端本地/外部源各3seed通过，但同轮独立大门阵列180秒超时；不冒充全部大配置通过。没有DC/VCS/PT/SPICE/布局、新PPL或服务器任务。

ZIP：根 `sc_cim_frontend_ppa_20261023_v1.zip`，36990字节，SHA256 `73bee486fd7d1f0fff0b3ba6bf915836715ed9496e92902351f86c18c68bda6d`。解压manifest和5流程检查通过；包可独立运行，不依赖Issue133目录。其通用波形/PVT助手副本来源保存在HELPER_PROVENANCE.json。

原始验证归档见 RAW_ARCHIVE.json、WAVE_ARCHIVE.json，位于 `C:/Users/86134/Documents/a_P_BIT/project_archives/cim_frontend_20261023/`，包含失败尝试、执行RTL原字节及命令/向量/日志。正式小结果在 `results/`；模型/数据SHA不适用，合成RTL激励，不是语言模型任务。源码绑定 SOURCE_MANIFEST.json 与 VALIDATION.json；生成波形/向量不提交Git。

下一步：用户在现有EDA环境按RUN_PPA_ZH.txt设置真实STD_DB/STD_MODEL/BUF_REF，先SS/TT M1 smoke，再M64正式。若buffer绑定/STA/超表/活动检查失败，保留原始日志，不更换成本口径掩盖失败。收到结果后在同Issue/PR新增运行记录至中央台账，不覆盖功能记录。SRAM小探针需真实晶体管网表；没有时保留参数，不阻塞数字功耗测量。

边界：旧计数器已有权重门控；初估只再加SNG和分发层次功耗。无新增概率/权重DFF副本；上游稳定概率/存储保持仍计费。SRAM全并行Q是待实现CIM接口，不宣称普通宏已有该能力。工程目标是初估，不是定制SRAM后布局签核。

发布以 PUBLICATION.json、REMOTE_VERIFY.json、ISSUE_UPDATE.json 为准；创建PR不等于合并，不自动关闭Issue。Projects权限状态以PROJECTS_CHECK.json为准，缺权限时待维护者同步。没有运行中作业，无需启动轮询。

发布更新：PR148（https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/148）已推送待审、未合并，科学交付74979fc；29个package manifest对应Git blob已核对。根台账保留其他任务记录，本轮增量后51条，任务base台账46条；合并时应保留union并render。原始临时向量/波形已归档逐成员验证，恢复见RAW_ARCHIVE/WAVE_ARCHIVE/ARCHIVE_VERIFY。
