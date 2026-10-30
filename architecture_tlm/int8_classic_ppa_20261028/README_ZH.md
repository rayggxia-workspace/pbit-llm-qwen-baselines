# 经典INT8 DOT4本工艺表征

最新结果：[REPORT_ZH.md](results/REPORT_ZH.md)、[完整数值与原件SHA](results/FINAL_SUMMARY.json)。

两配置：四lane INT8乘法、平衡整数归约、输出驻留INT32/INT22累加，固定N64一个输出。精确经典结构主参考为INT32，22位为N64无bias专用消融。源/输入以冻结manifest与ZIP为准，不覆盖v1失败或其他BF16源。

复现生成：python prepare.py；EDA入口flow/run_int8.py。本次已冻结源码，重跑或修改必须新建执行版本；model/corpus N/A，全部为合成事务。恢复看work/rayggxia/204/int8_classic_ppa/HANDOFF.md。
