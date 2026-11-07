# Issue225：共享QK供数100MHz接入交接

负责人rayggxia，分支task/225-norm-stream-20261106，PR248，base main。工作目录tmp/norm-stream-issue225-20261106；沿用Issue225，不接管198/PR199的源码/任务。用户授权本轮宿主完成转置到TLM接入，已完成本地运行/验证，远端发布以PUBLICATION.json为准。

用户授权由宿主完成，不再追加Attention模块交付要求。新增architecture_tlm/qk_supply_100mhz_20261107：现有16B/1RW物理bank、1KiB转置SRAM＋128B转置暂存/组；另加四槽32B粗K操作数FIFO/组并分别计价。四Q广播、四context反馈、粗K64token分块、精K四8x8微块16B整字搬运均展开；SRAM仍1216KiB/304bank，组内固定8KiB划出，不扩容。原100MHz32成果、250MHz6文件SHA不变。

本地12配对（单/八组×三seed×旧宏/新供数）＋反馈8拍/FIFO1槽两敏感性完成，10类检查通过；MAC/ADD/样本/唯一V及外存字节/地址sum/xor守恒，队列排空。八组Attention均值128.43→154.62us，供数增26.19us/层、36层投影+.94284ms。条件覆盖面积41.463→41.562mm²，含新2KiB寄存器代理；供数额外SRAM动态.01416mJ/36层，加捕获及已知背景约.06717mJ已计小计，不是完整新能量。

含先前资源缩减prefix/head增量的整机条件外推约53.95ms含head、46.53ms扣head，不是新原生LPDDR完整运行。外存为136.4606GB/s/30ns解析代理，片上bank实际；反馈L4/II1沿既有宏合同。控制/布线/广播及新寄存器idle未独立标定。首次无前取串行诊断208.28us、仅单操作数198.71us及源码保留，不作推荐调度。无新服务器/GPU/RTL/PT/PPL或台账run，不干预198另一套2KiB暂存native/TT250结果。发布以本任务PUBLICATION为准，PR248保持待审，Projects待维护者同步。

---


正式实现model.py、run.py，RESULTS/VALIDATION/README在architecture_tlm/qk_supply_100mhz_20261107，根同字节镜像。运行原命令见README；最后输出final_replay，12配对＋2敏感性，无新远端作业。重算/检查`python -B work/rayggxia/225/qk_supply_100mhz_20261107/finalize.py`。RAW_INDEX.json列准确执行源/结果及SHA，不把replay2/replay3误称最终。早期replay1因inputs缺失未开始，后改只读引用198已有同SHA输入；没有合成替代真实代表索引或覆盖原runtime。

复现需已有冻结runtime manifest7c5cb9b6...，依赖a633d11f...及输入SAMPLES SHA7d23b364.../representative586be3c7...；bootstrap逐源检查，私有输入不上传Git。所有配置、源和结果完整SHA在RESULTS、SOURCE_MANIFEST、RAW_INDEX、final_replay/SEAL。没有新RTL仿真，故不重复创建数字电路台账run。

下一步可直接在首次事务前调用model.install(m)，默认四槽/反馈4；不必再向Attention对话追加前置要求。完整原生整机时序和新路由/控制PPA仅后续完善项，不把53.95ms条件外推当已完成整机。反馈8拍或FIFO1槽敏感性已做，不需要重复。原250MHz目录及198另一套2KiB暂存结果只读，不混入本轮100MHz价。PR待审不自动合并；Projects无写接口待维护者同步。

