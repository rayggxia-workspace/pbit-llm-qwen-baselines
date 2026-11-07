# Issue225 / PR249：250MHz返回保持16KiB

负责人rayggxia；task/225-tlm-unified250-20261107，独立目录tmp/tlm-unified250-issue225-20261107；远端基线2f706e3453b44739587e04ab6afd092a0c3ce090，PR base为100MHz任务分支，不合并PR。

用户授权250也改16。model.make_model与run.py默认16、显式24对照；请求信用256、3条/通道、4ns、1216KiB/304bank及32KiB历史返回SRAM预留均不改。价格按实际holding_bytes缩寄存器保持面积/等待代理，捕获动态按原事件，不缩外存或计算量。

3/2核完整冷第0层（含embedding无head，36层分配）解析136.4606GB/s/30ns配对已完成：3核1.085992→1.085980ms，2核1.114148→1.114144ms，仅3/1周期，视为不变。算术/样本、输入SHA、外存读写量及各类地址sum/xor一致，请求/队列排空，4ns tick通过，返回未落地峰9792B。默认16和显式24构造器也已核实。

覆盖面积代理3核22.594773、2核21.625293mm²，各少0.396265。原24KiB完整RESULT/BUDGET/SEAL不改，新原件位于本目录local_c3/local_c2；analyze.py从旧module_refresh_20261107原件核对，SUMMARY与RAW_RESULT_INDEX含SHA。正式250MHz/DMA16_ZH.md、DMA16_RESULTS.json说明边界；共享living report同步250新默认，100代码/参数不动。

没有新原生36层LPDDR/GPU/EDA/PPL/数字台账run；250短T/C19 PPA仍待收，本次沿用同一核价参考。后续新快照默认16，旧健康任务/快照不覆盖、不重复提交。32KiB SRAM预留若回收需另做物理bank布局，不把本次说成SRAM少8KiB。上传以PUBLICATION.json与PR249 head为准，待审未合并，Projects待同步。
