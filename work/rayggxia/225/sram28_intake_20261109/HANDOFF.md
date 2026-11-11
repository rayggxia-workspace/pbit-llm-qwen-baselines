## 2026-11-09 28nm SRAM接入已发布

PR249科学源649e65c44fff4c1360d061bdd077776f1473d25b，24文件远端完整内容回读一致；Issue225评论6735776604。真实S0两频价/时序、3回放重计、12原件SHA、4PT整窗账本复现、中央台账check/render已完成。28面积×1、每16B读写增量＋停钟驻留，CIM权重普通SRAM代理不重复计费。现有条件整机中心更新8.209/8.240mm²、15.013/15.050mJ，时间45.901/40.991ms沿原外推，不是新全36层或芯片签核。55nm保持；PR待审未合并，Projects待同步。

---

## 2026-11-09 28nm SRAM真实宏已接入

Issue225/PR249，rayggxia接入，原表征jieruiz。S0真实4KiB/128bit/1RW、TT0.9V25°C，250/500各六窗；12原功耗报告SHA与归档校验、4完整PT读写窗口账本复现、3原集成回放重计通过。普通SRAM不再用55残差迁移价；240宏面积2.851229052mm²，28面积×1。

两频WHOLE_CONFIG已写真实随机读写价格与停钟增量基线，1拍返回/II1保持。whole_model/run_whole/whole_pricing已实际接接口，SRAM从未计列表移除。普通SRAM代理也用于驻留CIM权重每tile一次读；写入/面积/泄漏不重复。未改55nm或冻结任务，无新EDA/长时序回放。

原条件整机估计只更新SRAM后，250/500中心面积8.209/8.240mm²、时间45.901/40.991ms、片上15.013/15.050mJ，总4pJ情景188.208/188.268mJ。仍是小TLM＋36层/完整head外推，500FMA/PV/平台等原宏限制保留，不能写新完整芯片或原生全层结果。正式process_28nm/SRAM_INTAKE_20261109_ZH.md/json与SRAM_CALIBRATION；历史粗估原件不改。

受限1.5MB完整库表JSON保留本机/授权服务器，只公开所需标量、说明和SHA。中央记录sram28-s0-225-20261109沿原run归档，owner不改。发布状态看本次work/PUBLICATION.json，PR未合并；Projects待维护者同步。

复核命令：python -B architecture_tlm/process_28nm/intake_sram.py；保留原件，只有价格变化无需重跑时序。
