## 2026-11-07 Issue225：250MHz SRAM实际缩至960KiB

已读最新204/198交接：TT250短T/C19 setup−0.421007ns仍失败，去掉0.5uncertainty的＋79ps只作条件解释，未接受新核价/未改约束。用户授权执行上轮SRAM候选，本次250默认1216→960KiB：普通QKV/O/head权重两槽80→32KiB、删未使用DMA SRAM32KiB、八组Attention64→48KiB。16KiB寄存器返回保持/信用、3核GU16-Wd32、256FMA及FFN256权重/96状态KiB不变；100代码/默认/健康冻结任务不动。

真实bank由304→240（前端176→144、Attention128→96），16B/1RW/4ns，输出搬至47～48KiB，粗分数旧对象失效后复用，128项V缓存保留。四项布局/数据/冲突/全词表tile检查通过。三版同源同seed17完整冷单层：1216/1088/960分别1.085980/1.086184/1.085700ms，近似持平；动作/帧/外存各类地址与字节一致，实际SRAM读多400B计费，写入一致，队列排空/4ns通过。解析136.4606GB/s30ns，含embedding无head，按36层分配地址；非完整原生token/PPL。

按已折0.81的宏面积，SRAM8.18162→6.45918、旧TT核参考覆盖面积22.59477→20.87233mm²，少1.72245。SRAM动态约.189587mJ基本不变，漏电.65149→.51420µJ；含4pJ/bit外存参考4.701432→4.701292mJ/冷层，主要省面积。250物理4ns未签核、无新RTL/PT/GPU/PPL/台账run。正式250MHz/SRAM_COMPACT_ZH.md/RESULTS.json；源执行a63cf1de246fb59a6da939cacfca3b76940d4f14，九原件SHA及恢复命令在sram_compact250_20261107。原目录名保留，默认compact960；reference1216/compact1088显式可选。PR249交付/回读见PUBLICATION.json，待审未合并，Projects待同步。
