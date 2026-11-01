## 当前Issue204：非线性到Wd实测及数字对照流程

负责人rayggxia；PR219，task/204-gu-unified-code，base task/206-group64-scale，open待审未合并。SC六配置科学结果26c4dd72613c9c44e9514d2d7df7c455b2b74c56：weighted全LUT436.6733pJ/340ns、共享CE724.02pJ/660ns、共享ICG566.61pJ/660ns；均8输出。66PT、RTL/门级各13614检查完成，原作业全部结束，勿重跑。

新增数字流程分析5207a7d3114ef3f82c8a20ac56b80fe20056b2c5：同g/u8、幅值裁剪、原g的Sigmoid表、W8及共享PoT尺度；直接两乘法或融合F[g,档位]表＋一次16×8乘法，再将P/2^16做RNE得到8位幅值＋符号z9，接A9×W8。块输出指数eg+eu+ew−8；尺度未省略。131072整数范围检查，F16/P24足够，z幅值最大253，不需满幅旁路。

这只是候选流程与条件预算，没有新RTL/EDA/模型/PPL，不新增run，也未验收z9量化质量。保留64路主并行对照；2/4路流式复用仅列另一资源点。已有A9满负载MAC按8输出预算约186.75pJ，给前端/控制留下约249.93pJ才有机会低于SC；不同激励/精度/帧节奏的模块数值不作完整集成PPA。BF16单列更高精度参考。旧A9原始PPA仍仅本地，不上传旧未批准归档/索引。

入口architecture_tlm/nonlinear_digital_comparison_20261031/PLAN_ZH.md、ANALYSIS.json；analyze.py只做离线范围/预算检查。恢复见本地work/rayggxia/204/digital_nonlinear_plan/PUBLICATION.json。下一步是在用户确认范围后实现两种数字前端并与Wd配对表征；不自动启动新昂贵实验。此前完整状态在[上一版本](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/327868a68146f356c1f096e6c4e19ce956bc60fa/progress/rayggxia/STATUS.md)，本地历史完整保留。
