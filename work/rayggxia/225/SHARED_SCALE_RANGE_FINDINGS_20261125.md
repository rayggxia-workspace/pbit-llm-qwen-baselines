# 已测组共享配置：尺度范围实查

2026-11-25，本地只读统计，无新模型推理。范围是Issue206的G64/B4 risk4已测配置，不是T64训练检查点。

完整WT2已有结果：BF16 11.537160；G64/B4 14.883993±0.018381。x/g/u各连续64项共用一档，W8/PoT64，GU64、NL/Wd128，准确Attention，36层、2048/1024、299077目标。不得将本结果或尺度范围自动继承为T64训练权重16/32结果。

x原始校准：tmp/dual-gu-issue201-20261027/qwen3/results/dual_gu_20261027/inputs/fixed_xz_calibration.json，SHA1f4eb40e79cfc8c43053e6aa9cfbd777ba95d6d278411c91ab9c8861ef0b2b19，与Issue206 config期望完全一致，36层全部统计。每组四档比例[1,1/4,1/16,1/64]；S组范围1..512，基准指数0..9；所有候选尺度指数-6..9。

g/u使用project_archives/group64_scale_issue206_20261028/recal-tables-e8888a26dace-9a26ddde7c2e.json内risk4，SHA9a26ddde7c2ed935e652cefbadd5bf63b9f5b4f23a269775f47d38f0963987f7。g最高档指数-1..7，最高尺度128，全部档指数-6..7；u最高档指数-1..8，最高尺度256，全部档指数-6..8。

对这一份已核验配置，全部x/g/u激活尺度的指数都落在-6..9，共16个整数值，可用4bit偏置编码code=e+6表示，恢复S=2^(code-6)。若直接用二补码有符号指数，则为5bit；若传四档选择结果，则仅2bit，另由静态表查指数。权重/乘积/累加恢复的合并指数另计，不能因激活指数4bit就全链缩成4bit。

T64原生运行时仍有逐元素选档路径；此前PPL尺度范围审阅见PPL_SCALE_SCOPE_AUDIT_20261125.md。T64实际尺度表尚未同样统计，不声称它已经满足本4bit范围。
