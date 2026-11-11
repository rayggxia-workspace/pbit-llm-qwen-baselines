## 2026-11-09：28nm SRAM仍为估计，最小工艺库校准需求已写

Issue225/PR249，核当前250/500 WHOLE_CONFIG及CACTI来源：没有接入真实28nm SRAM宏PPA，严格价仍null；粗估960KiB约1.6735mm²/2.41mJ来自CACTI＋55nm残差迁移。4/2ns服务仍是假设。没有因已有28nm逻辑PPA就宣称SRAM真实。正式process_28nm/SRAM_CHARACTERIZATION_REQUEST_ZH_20261109.md供用户EDA方执行。

最低S0=256×128b/4KiB/1RW，先TT/SS的lib/ds/lef面积/周期/读返回/功耗状态，再对一个S0跑250/500 TT六窗。S1=128×128、S2=512×128先只库提取，S3=256×64作fallback。明确延迟与II、clk-on/off、毛能量与增量/驻留不双计、真实宏不综合成FF、28面积×1、普通1RW不证明改造CIM全并行。宏库本体不上公开仓库；回传小表/原件路径及SHA，新增结果登记中央台账。

文档/现有空价/容量单位来源核验通过，无新EDA/GPU/TLM/数字仿真run，不改55/28默认和旧封存。用户尚未交付的库/结果不写已仿真。当前待执行方回传S0资料；PR249待审未合并，Projects待同步，发布以本work/PUBLICATION.json为准。

收到结果后先核PVT/端口/宏边界和原SHA，登记库提取/STA/PT实际状态。只更新成本可重计；最小周期、读延迟或组织改变需新冻结回放。不要重跑CACTI或复制工艺库代替缺失工艺表征。
