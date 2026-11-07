## 2026-11-07 Issue225：100MHz共享QK真实bank供数接入

用户授权由宿主完成，不再追加Attention模块交付要求。新增architecture_tlm/qk_supply_100mhz_20261107：现有16B/1RW物理bank、1KiB转置SRAM＋128B转置暂存/组；另加四槽32B粗K操作数FIFO/组并分别计价。四Q广播、四context反馈、粗K64token分块、精K四8x8微块16B整字搬运均展开；SRAM仍1216KiB/304bank，组内固定8KiB划出，不扩容。原100MHz32成果、250MHz6文件SHA不变。

本地12配对（单/八组×三seed×旧宏/新供数）＋反馈8拍/FIFO1槽两敏感性完成，10类检查通过；MAC/ADD/样本/唯一V及外存字节/地址sum/xor守恒，队列排空。八组Attention均值128.43→154.62us，供数增26.19us/层、36层投影+.94284ms。条件覆盖面积41.463→41.562mm²，含新2KiB寄存器代理；供数额外SRAM动态.01416mJ/36层，加捕获及已知背景约.06717mJ已计小计，不是完整新能量。

含先前资源缩减prefix/head增量的整机条件外推约53.95ms含head、46.53ms扣head，不是新原生LPDDR完整运行。外存为136.4606GB/s/30ns解析代理，片上bank实际；反馈L4/II1沿既有宏合同。控制/布线/广播及新寄存器idle未独立标定。首次无前取串行诊断208.28us、仅单操作数198.71us及源码保留，不作推荐调度。无新服务器/GPU/RTL/PT/PPL或台账run，不干预198另一套2KiB暂存native/TT250结果。发布以本任务PUBLICATION为准，PR248保持待审，Projects待维护者同步。

---


