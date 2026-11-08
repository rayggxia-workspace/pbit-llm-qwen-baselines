## 2026-11-08 Issue225：28nm250MHz 44功耗窗口消费端复核

用户问新矩阵结果是否需调TLM；确认44窗口为28HPC+ TT0.9V250MHz，非55nm新价格。复核3主归档及1715报告成员SHA通过：FFN8/BF1615/A921窗口，A9 PT hold−.099703仅诊断。合格FFN .373801302mm²、GU/Wd10.1625/9.254021pJ/DOT64，18/34拍、72/136ns，停源等待.6209mW（漏电.279mW）；28面积×1，不套.81。BF16/FMA16/C4 .06245379mm²、continuous3.304622pJ/FMA；mixed QK wrapper及其他系统模块需独立边界。

正式module_refresh_20261107/tsmc28_review_20261108：报告、review.py、CANDIDATE_COMPONENTS/COMPARISON/SOURCE_INDEX/VALIDATION。候选default_enabled=false；固定旧冷层工作量/时长，三FFN核47.34→13.21µJ/少72.10%，3核面积4.122→1.121mm²，不是新28整机TPOT/PPA。TIE功耗未知null、面积已计；500三配置待收。读取最新POWER_RESULTS而非老profile null；不修改owner204资料或55默认/冻结38629485，不新交TLM/EDA/PPL。接28整片时需同时调服务周期、数字价格/等面积、存储和其他模块，不能混工艺宣称全片收益。发布以本任务PUBLICATION为准，PR249待审不合并，Projects待同步。

---

