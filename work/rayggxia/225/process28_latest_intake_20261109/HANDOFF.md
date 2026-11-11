## 2026-11-09：最新28nm交接已刷新，当前概率路径未变

已核204/198终态资料；此前已用随机FFN/state/codec/scale和SparQ/S12front/gapIsing，本次补500exp及250 code8非线性/W8Wd（整数GU原已注册）。新数字/exp不在当前SC dispatch，不重复收费。两频各13严格Attention卡、两张hold待修条件卡单列；四PV均setup失败，只诊断，不能因用户暂缓hold就视为通过。500优化SC面积.45458028但setup-.009314未替换，仍.564451146；500FMA无合格完整价，交接这一批已终态而非仍运行。

9源JSON SHA、6绑定检查、3项原SEAL及旧/新价格精确复算通过；三BUDGET全等，活动服务合同不变，无新调度/RTL/PT/Slurm/GPU。正式LATEST_INTAKE_20261109_ZH.md/JSON；BINDINGS可用资源刷新，但新增数字整模型未执行、完整PPA仍缺。原v3封存和55默认不改。PR249发布见work/rayggxia/225/process28_latest_intake_20261109/PUBLICATION；未合并，Projects待同步。

恢复：运行prepare_bindings、6单测及reprice.py；旧3case/source保留。新price/service确实改变时停止“全等”断言，建立新的结果/冻结版本；禁止写入旧结果。条件卡不覆盖严格价；四PV setup未过，不能自动选入主账。
