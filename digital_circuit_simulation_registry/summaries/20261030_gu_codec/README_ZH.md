# g/u单份9位或总8位码：软件模型验证

Issue204/rayggxia；2026-10-30。没有新增数字电路仿真run，没有新面积/能耗。

同后训练Qwen3-4B、准确SDPA、原共享四档/权重/采样的1024目标三seed小测：现有方案17.921546±0.266163；存g数值码的raw9为17.511391±0.246922，raw8为17.882045±0.286634；BF1613.566049。不是完整WT2，不宣称无损或已验收节能。直接从裁剪幅值码恢复Sigmoid的另一族严重失败，原件保留。

成功候选将同一份g数值码同时送Sigmoid与幅值移位/RNE/饱和转换。g8单位1/8、signed8；g9单位1/16、signed9。u仍各自共享尺度下的符号/幅值码。两者逻辑payload分别19456/21888B每9728对，尺度标签76B保持；Sigmoid地址/概率可组合派生。实际宏读口/保持、并行表、编解码PPA待表征，不把payload降幅换算成能耗。

[正式报告](../../../experiments/gu_unified_codec_20261030/results/REPORT_ZH.md)、[精简数值](../../../experiments/gu_unified_codec_20261030/results/SUMMARY_SMALL.json)、[执行与恢复](../../../work/rayggxia/204/unified_gu/HANDOFF.md)。这是一份软件证据入口，不计作硬件实测价格。
