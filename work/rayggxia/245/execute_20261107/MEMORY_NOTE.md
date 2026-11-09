## 2026-11-07 Issue245：三模型硬件适配开始原生CPU验证

用户要求实际执行硬件评估。已核对官方配置/Meta SKU及当前198/204新数字模块，无须下载大权重、tokenizer或PPL基线。复用245/PR247最小checkout，新增跨模型试接，既有SharedMemory/BeatSRAM＋Ramulator派生8533，不改100/250默认或模块源码。四Q物理槽显式填充Llama3Q/Deep1Q；Deep32KV分四波；33024B元数据扩为36KiB、g/u尺度移至其后；960KiB物理bank轮转无越界。

四项CPU测试通过，覆盖24布局/面积、12完整FFN分包、三seed参考地址键。Llama250 SC及Deep250 W8 FFN完整尺寸本地模块回放完成，非整机性能。EDA数组38625522_[0-23%2]：每项1CPU10GiB2h、最多2项并发、0GPU，24完整尺寸单层pilot，未提交全层或含head任务。首个Qwen100 SC native已完成，127139840B权重守恒、队列排空、WORK_GATE PASS。freeze manifest bc8cbd87244c239d88774c71a860a939b41b880536e52fbe2dbdba68e7e9f529；目录与SHA在work/rayggxia/245/execute_20261107/SUBMISSION.json。

必须先对齐试接较串行的投影供数/PV重叠、250的r32→主线r16、norm/RoPE/残差实际访存和价格，再Qwen锚点回归及全模型；不能把pilot乘层数当主线token时间。250新短T合格PPA仍待收。正式EXECUTION_STATUS_ZH.md和HANDOFF列边界，原始PPA/模型权重未公开复制，无新RTL/PT或准确率结果。PR247仍待审未合并，远端交付以PUBLICATION.json为准，Projects待维护者同步。

---
