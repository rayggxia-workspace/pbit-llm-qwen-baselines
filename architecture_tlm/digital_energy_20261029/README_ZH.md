# BF16数字能耗标定与统一TLM接入

Issue210 / PR211，rayggxia，2026-10-29。当前默认nonfused_pair：PR209已公开的FPnew BF16乘法和FP32加法单元相加代理；沿用原非融合图，尚非集成MAC实测。FMA2/3另作成本情景，不自动改变模型数值。依据见[新结果](results/REPORT_ZH.md)、[逐模块CSV](results/MODULES.csv)和[精确JSON](results/RESULTS.json)。原[旧账本](../component_budget_audit_20261029/results/REPORT_ZH.md)原字节保留。

## 执行入口

统一入口仍为unified_v6，FullDecode.run输出digital_power。默认load非legacy配置已启用；旧完整config没有digital_power时继续旧账，显式选择legacy_proxy可作对照。digital_power.profile与idle_dynamic_keep均进入config及其SHA。CLI：

```powershell
python -m architecture_tlm --model qwen3_4b --digital-energy-profile nonfused_pair --digital-idle-keep 0.1 --output /new/run
python -m architecture_tlm --digital-energy-profile fma2 --output /new/sensitivity
python -m architecture_tlm --digital-energy-profile legacy_proxy --output /new/legacy-price
```

沿用既有DRAMSys bridge要求；不静默回退内存。此新增价格不改变DDR4默认、HBM候选、采样和资源速率，也不声称时序重新标定。

模型按实测normal窗口完成次数归一化，计入1036拍/1024次的标量排空；背景能量按参考拍和实际寿命、MAC忙时，漏电不随频率乘5。Ledger记录每动作/类别收费，在结束时移除bf16_mac原费后只添加一次数字MAC寿命费。其余FP32/PV/vector不混改；FP32_MAC未知仍保留。metrics与compact行同时显示数字profile、MAC能量和平均功率；完整芯片PPA仍null。

## 原36层候选重放

```powershell
python -m architecture_tlm.digital_energy_20261029.reprice --output /new/energy-replay
python -m unittest architecture_tlm.digital_energy_20261029.test_model
```

新三seed默认MAC 0.451426W，片上已价100.945118mJ/token、1.757236W、154.017521mm²等效；原为1.210401W/2.516212W/156.118460mm²。时间57.445385ms/token和所有活动、访存、随机源不变。FMA2/3分别得到片上1.618731/1.658065W。以上是旧500MHz条件时序上的能量重放，不是500MHz集成电路结果或新完整时序。外存另6.166060W仍是旧代理。

## 证据与限制

ANCHORS从PR209@9228b08ca20230600ac41eba479f14228d19b5be的FINAL_SUMMARY抽取，原SHA327a788e0e4477512b1bcb010cac0217c65706f5d727669ce11caf51ae7e4221；本轮未改其源码、原件、台账或待审状态。100MHz SS1.08V125℃，原始工艺名不改，面积只乘0.81一次。原run matrix-bf16-204-20261028已由PR209登记，本轮不新增假EDA run，PR209未合并也不误称已在main。

主要缺口是500MHz流水/hold、小型集成tile、真实ICG和回压/唤醒、模型活动和算术一致性、SRAM接口/互连/CTS。DOT64完整577pJ/30拍是另一组织，不能直接替换scalar费却保持原MAC吞吐。默认90%空闲动态消除仍为参数假设，JSON列0/.1/1敏感性。详见REPORT_ZH末节。

实际验证：主unified_v6原110测试及新9测试通过（含真实FullDecode与CLI分发小形状；CLI单测仅替换source_record/模型加载，不冒充完整正式运行）。无GPU/PPL/新EDA；原三seed摘要SHA、14项能量/面积/占比守恒通过。代码变更与新结果SHA见DELIVERY_MANIFEST；发布状态以work/rayggxia/210/DIGITAL_POWER_PUBLICATION.json为准。
