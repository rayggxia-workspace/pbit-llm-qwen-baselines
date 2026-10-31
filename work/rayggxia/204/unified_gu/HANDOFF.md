# g/u统一9位与总8位试验交接

负责人rayggxia，Issue204；本地沿原tmp/matrix-t32-issue204-20261028/task/204-bf16-baseline，只读依赖PR207@104a2e49。未修改jieruiz目录或旧执行。发布采用基于PR207的仅本轮文件增量，PR base为task/206-group64-scale，不携带此前预算宽历史；实际远端回执以PUBLICATION.json为准。

已完成两族三seed模型试验，BF16及旧控制严格复现。raw9=17.511391±0.246922、raw8=17.882045±0.286634，旧17.921546±0.266163、BF1613.566049，均为固定8片段/1024目标小测。直接复用裁剪幅值码shared9/shared8约20.9万/21.5万，失败原件保留；条件NL均值证实主要是编码失真。未改默认、无完整WT2/训练/新PPA。

成功合同：g8=signed8码RNE(8g)，直接接原Sigmoid表，幅值由abs(code)与原Sg做移位/RNE/饱和；g9=signed9码RNE(16g)，RNE(code/2)作Sigmoid地址，幅值同理。u分别1sign+7/8magnitude。每64组的原g/u四档尺度保持。范围、符号、满概率组合端点和两次舍入限制见正式报告。

执行源438d4eea432a(3502/3503/3504)和4b81b34fa28d(3507/3508/3509)均完成，最后本人队列无任务。CPU3499仅测试参考dtype错误、旧依赖3500/3501已撤销；失败源码ZIP/日志保留。没有重交健康任务。CPU3507为26通过2CUDA跳过，GPU3508为28全通过。

正式experiments/gu_unified_codec_20261030/；结果results/REPORT_ZH.md、SUMMARY_SMALL.json、SCORES.csv、RAW_FILES.json，精确源码ZIP三份。原件两份raw tar归档在本机project_archives/gu_unified_codec204_20261030，私有服务器根/home/Hongjie_Zeng/projects/pbit-gu-unified-code-20261030-issue204。SOURCE_RECOVERY.json含全部SHA、源码包/输出/作业与归档恢复路径；EXECUTION_INDEX.json记录门禁与边界。sacct关闭且scontrol保留期有限，不将缺失的调度器ExitCode编造为0:0。

复算：恢复两raw归档至results/对应源码前缀后，用本机primary Python执行experiments/gu_unified_codec_20261030/summarize.py；无需Torch/网络/GPU。原数值实验需冻结Issue206快照/已核验模型语料与其venv，源码ZIP可恢复原始运行合同。ops.py只作明确package/stage/status/collect，不能在恢复时无条件stage；当前全部结束，勿重交。

下一步可为raw9/raw8量化写入、幅度地址转换、Sigmoid组合表和实际SRAM读出/保持做模块PPA，再决定是否完整WT2确认。仅逻辑payload不等于宏面积或能耗；上游x仍P8+sign，数字第一层仍A9×W8。当前不自动执行更多模型/EDA或修改推荐。
