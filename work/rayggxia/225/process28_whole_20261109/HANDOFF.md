## 2026-11-09：28nm条件整机TLM已实现并通过三项冻结门禁

用户要求先搭建；复用既有3a7dd5e0679e有限bank/DMA/16KiB信用/预取/状态/回压模型，新增whole_model/run_whole/whole_pricing/verify_whole和两频WHOLE_CONFIG。28核18/34拍、1KiB有限暂存＋state/scale/codec，A单遍分数读取＋gap后端共用32拍加载；四头共享V miss，SparQ单位修正为每Q一次feature、每四头一次norm。所有周期重执行，不按旧总时间缩放。缺28nm SRAM/PV/DMA/向量/500FMA价格保留null，已知组件小计与完整值分开。

正式冻结执行b90c17725f50：250三核2层＋384词条head2.205336ms，首层1.091888ms；500两核1层0.980398ms；同500 SRAM返回延迟2拍0.981804ms，动作/字节守恒，慢0.1434%。三case SEAL、7源/配置SHA、工作量/转换/采样/V miss字节/有限信用/未知成本及双时钟边沿核验通过。完整151936head只全部tile/字节结构检查；实际head384含128尾块。没有运行完整36层或nativeLPDDR，没有新GPU/RTL/PT/工艺仿真，不把条件时间/部分PPA当芯片实测。

截断2层＋head时Norm仍按36层预取导致阻塞，已绑定截断测试真实逻辑深度，完整36语义保持；只终止本人两个本地诊断进程，服务器健康作业不动。v2一次MAC/字节预检误写也保留失败，不计有效结果。正式只认v3封存，旧源和诊断保留。

入口process_28nm/WHOLE_MODEL_ZH.md，代码run_whole.py；结果WHOLE_VALIDATION.json/WHOLE_RESULTS.csv；恢复work/rayggxia/225/process28_whole_20261109的EXECUTION/SOURCE_INDEX。新PPA到齐先更新价卡；周期/端口/状态改变再改宏并重放。55默认不变，PR249待审不合并；发布看PUBLICATION，Projects待同步。

精确本机执行目录、三封存路径/SHA和Python版本见SOURCE_INDEX；从仓库根运行verify_whole.py --work该目录 --out新的验证文件即可只读核验。不要改不可变execution_b90c17725f50，也不恢复已停止的两个partial-head诊断。完整36命令在正式说明；需要共享执行包的读权限，Git不复制其私有源码/大原始轨迹。
