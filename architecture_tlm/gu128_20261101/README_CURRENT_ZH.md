# 当前GU64g＋64u融合M128结果

K64/T64，100MHz目标、SS1.08V125℃，输出64g＋64u。同一输入SNG64和采样控制共享128列，对比两个各64列的分立核；后端均16个相同backend8块、128个20位累计器，无OR/缩位。

- [功耗面积与原生时序](results/REPORT_ZH.md)
- [三seed摘要和分项](results/SUMMARY_SMALL.json)
- [执行来源与SHA](results/SOURCE_INDEX.json)
- [完整源码ZIP](results/SOURCE_CODE.zip)：解压后运行`python -B rebuild_fixtures.py <空任务目录>`重建18份fixture并逐SHA验证。

两配置RTL/门级各6132逐拍PASS，18PT窗口。逻辑首valid640ns、服务660ns；以报告原生STA判断100MHz是否成立。55等效面积raw×0.81一次。外部x/W存储及保持、实际PRNG及上游广播、跨K/出口量化/BF16和CTS/SDF/SPEF在外，没有新模型/PPL。

两版统一采用backend8先映射、top保护16实例的层次流程，与旧平铺M64价格不同；只有本轮重新配对测量才作为融合收益。分立核第二source/clear端口全程与第一套相同，表示两物理核；整机若早已合并这些逻辑不能重复计入。停顿窗保留实际非零部分和和R8，主时钟仍运行。

统一run gu128-204-20261101。服务器源由d0776938起点加冻结未提交字节，以EXECUTION_MANIFEST/源ZIP为准；发布commit不是执行commit。旧GU四配置与T64非线性-Wd结果保持。
