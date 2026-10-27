# Issue95：8位随机比较与LUT交接

负责人rayggxia，2026-10-27；正式仓库rayggxia-workspace/pbit-llm-qwen-baselines。工作目录为工作区下tmp/rng-pbit8-issue95-20261027，分支task/95-pbit8-characterization，基线main d83eeb1f。原生Git fetch报getaddrinfo thread失败，已通过GitHub连接器核实main精确SHA；发布用连接器，回执单独保存，不覆盖旧质量/服务目录的暂存状态。

正式源码architecture_tlm/random_service/pbit8_char；README说明能耗证据、q/256与signed8/8、五个核边界、运行命令、EDA步骤及疑点。P=12历史源SHA验证通过；旧16位p-bit/整片数据不是本次8位独立PPA。

执行命令：python run.py --out <新的归档目录> --iverilog <iverilog> --vvp <vvp> --ivl-dir <ivl>。本地Icarus依赖来自工作区sc_weight_storage_or4_20261014/tools/iverilog。rtl_v1因Windows沙箱DLL重定位未进入Icarus；同一源码rtl_v2在沙箱外成功，失败目录保留。没有远程作业或付费EDA。

结果results/VALIDATION.json和SOURCE_MANIFEST.json；75案例/307200计量拍，穷举与现有表一致。配置/向量/VCD/日志/编译产物完整归档到工作区project_archives/pbit8_char_issue95_20261027/rtl_v2.zip，SHA及字节见RAW_INDEX.json；可逐成员恢复。不要把RTL波形冒用为门级功耗。Tcl只有stub解析，待用户实际工具/库检查。

台账新增rng-pbit8-95-20261027；本机全局74记录check/render完成，未覆盖其他run。main没有整个registry工具，因此只向本PR增量提交该record，中央工具/其余run从维护分支整合；不得把本任务局部总览覆盖中央总表。没有新PPA数字。

发布只包含本次自编RTL/脚本/说明、小型汇总和索引，不上传工艺库、原始波形或其他任务资料。便携包路径/校验在DELIVERY.json；实际PR/提交在PUBLICATION.json。PR待审不关闭Issue95，不自动合并。Projects权限未更新。

下一步：用户选工艺库按五个top/三seed的实际输入模式跑DC、门级同TB、独立STA、PT；核验库单位、反标/XZ、setup/hold、库表告警，再追加同Issue真实PPA run。500MHz、16路LUT复制/共享、真实g定点转换、输入隔离/ICG与物理共享读出功耗仍未解决。不要重复已通过RTL矩阵来冒充这些验证。
