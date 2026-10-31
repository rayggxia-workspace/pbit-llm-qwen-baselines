# 当前结果：8位比较器与32路共享Sigmoid

6配置、三seed、66PT，RTL和门级各13614逐拍检查通过。比较64份完整组合LUT，与每32路共享一份LUT、每路8位概率保持的CE/真实ICG版；保留weighted和OR4signed9两种Wd后端。所有比较器主体8位，q=0/256通过现有g符号区分，无概率精度改变。

主表按完整工作收费：full34拍/340ns，共享单银行66拍/660ns，每帧8个64项输出。不隐藏32拍加载；首帧prepare/sample只是阶段诊断。Wd自由运行时钟保持一致。SRAM、随机源/实际分发、GU、跨K/BF16和CTS/SDF/SPEF在外。

- [功率、能量、面积与时序实测表](results/REPORT_ZH.md)
- [精简数值与逐层分项](results/SUMMARY_SMALL.json)
- [原集成逐单元归因：LUT只约3.8%](results/EXISTING_COST_BREAKDOWN.json)
- [执行及源码SHA索引](results/SOURCE_INDEX.json)
- [完整小源码包](results/SOURCE_CODE.zip)：解压后使用Python≥3.10运行rebuild_fixtures.py，独立重建54份激励与窗口文件，逐字匹配冻结manifest；再使用包内成熟VCS/DC/PT流程。无工艺库/凭据/模型或大波形。

SS1.08V125℃100MHz，raw面积单次×.81，功耗/时间不缩放。合成四档尺度，非模型活动或PPL验收；STA/门控检查与功耗模型告警保留，不称物理签核。源码冻结base b411aaac3abb5be3fa72274cf34ea51ad7c6385a＋manifest/ZIP字节，不把交付commit当执行commit。统一run nonlinear-shared32-204-20261031。
