# 55nm Attention：100/250MHz对照范围与最新修复

2026-11-09，Issue198 / PR199。55nm等效面积＝本项目raw65面积×0.81一次；能量、功率不缩放。旧SS100参考保留，新TT100/250因果配对独立列出。

## 本轮修复

独立FP32乘法器的功能与4ns时序原本通过；失败来自功耗报告默认只列正功耗单元，3309行少于3310个实际单元。修复后确认遗漏单元的工具报告值约−4.4pW（数值模型结果，不是物理负耗电），原默认筛选将其删去。已改为显式包含零/负报告值，保留严格清单校验；复用原网表、原始三seed激励和已完成两窗，补剩余13窗。不改变算术RTL、周期或验收约束。
这与已通过的BF16×BF16＋FP32累加FMA16/FMA64不是同一个模块；原250MHz乘加对照继续有效。
Bivium250仅在综合映射时收紧至3.9ns，正式STA仍4ns；RTL/输入不改，原−4ps负结果保留。

恢复数组 `38639075`。尚未全部完成；以下是本次实际查询快照，不能把已提交写成通过。

|恢复项|功耗窗口|状态|setup ns|
|---|---:|---|---:|
|bf_fpmul|15|calculated|0.002531|
|softmax_r8_bivium|0|running|待测|

## 100MHz应保留哪些对照，250MHz能做到哪里

主线保留四条数字对照及一条本方案。主配置K128/S64；独立R8输出数可变，记录实际结果数，不能将其自动称为固定S64或等质量。

|方案|100MHz已有证据|250MHz已有证据|
|---|---|---|
|稠密QK＋在线Softmax＋完整PV|旧原生模块＋当前小SRAM共享池局部回放|共享池局部回放和FMA/标量成本；标量补齐状态见价卡|
|SparQ K128＋数字Softmax＋完整PV|当前小SRAM局部回放；筛选与PV算术已测|对应局部回放；筛选与FMA已测，标量见价卡|
|SparQ K128＋数字Softmax＋独立R8 GF64＋PV采样|采样核实测，旧2.5MiB独立阵列整链回放|核已测且修复setup；最新小SRAM整链待接合|
|SparQ K128＋数字Softmax＋systematic S64＋PV采样|核实测及旧整链回放|核实测；最新小SRAM整链待接合|
|SparQ K128＋Ising GF64 S64＋PV加法|关钟/提前保持核＋当前模块合同|关钟/提前保持核＋当前模块合同|

Top64/128（含候选内Top64）作为确定性稀疏补充；Bivium作为随机前端消融；K256是备用。它们不需要阻塞K128主表，但估算与实测分栏。
**250MHz所需主要原语和采样核已基本覆盖；当前还不能称最新整层对照全部闭合。** 最主要剩余项是将数字R8/systematic接入最新小SRAM、共享FMA池和相同V缓存调度，并用真实采样地址回放。旧2.5MiB/独立QK-PV阵列的100MHz整层结果不可直接除以2.5。

## 同TT条件下已可比较的采样核

共同TT1.2V25C、额外setup/hold uncertainty0、IO max1ns/min0.02ns、20fF负载。K128旧S12/F4输入合同内做max-gap，输出采样结果；不含新FP32 max-gap前端、SRAM、QK或PV。用户允许hold暂缓闭合，原负hold仍保留。

|核|MHz|周期/query|nJ/query|面积mm²|setup ns|
|---|---:|---:|---:|---:|---:|
|ab_both|100|137.639|1.112228|0.04565494|0.349700|
|ab_both|250|137.639|1.128392|0.04723745|0.000938|
|softmax_r8_gf64|100|212.278|1.715504|0.07843953|0.253041|
|softmax_r8_gf64|250|212.278|1.749047|0.08056208|0.050210|
|softmax_systematic|100|166.000|1.209311|0.08074142|0.290508|
|softmax_systematic|250|166.000|1.248759|0.08322177|0.002174|

R8 GF64已采用修复后的合格行。旧失败值保存在COMPARISON.historical_rows，不再用作当前表。TT100/250与历史SS100的0.879nJ等值不是同PVT，不能互相替换。

## 在线Softmax标量价卡

SCALAR_CARDS.json给出原始面积、一次折算面积、三seed/15窗、setup/hold、stream gross、扣idle增量pJ及单独漏电/活动时钟功率。可用频率：[100, 250]MHz。未完成项ready=false，不填成零或有效价。

|单元|MHz|面积mm²|gross pJ/op|增量pJ/op|
|---|---:|---:|---:|---:|
|fpadd|100|0.00802629|7.063483|7.004139|
|fpmul|100|0.00893579|8.950676|8.889173|
|explut|100|0.00268797|2.627434|2.572649|
|recseed|100|0.00095616|0.958907|0.906426|
|fpadd|250|0.00890255|7.536630|7.481309|
|fpmul|250|0.00976452|9.307813|9.251291|
|explut|250|0.00320760|2.868560|2.815330|
|recseed|250|0.00095616|0.958435|0.906392|

接入方式：`architecture_tlm/attention55_compare_20261109/tt250_scalar_override/CALIBRATION.json`在250四算子全部合格后生成，仅替换units.fpadd/fpmul/explut/recseed；原共享FMA/筛选/转换/保持价格保留。100MHz另有TT敏感性价卡，不覆盖SS100默认。
SCALAR_REPRICING.json将既有局部回放原动作重新计价，时间、DRAM/SRAM字节和FMA资源不变；不是新调度仿真。转换、保持、控制预留仍有代理，不能称全数字链逐门PPA。
100MHz TT标量重计价仍保留原SS100 FMA/筛选价格，只是混合PVT敏感性分析；不能用来声称整个模块都已做同TT100配对。
能量按动作增量＋实例漏电×时间＋实际活动时钟成本；未工作单元根时钟关闭，不能再全时段收取idle动态，更不能把gross pJ与同一份背景重复相加。

## 后续与证据入口

1. 收齐修复结果并回填TT标量价格；随后供宿主显式采用，冻结结果不自动改写。
2. 数字R8/systematic与Ising统一当前缓存、GQA复用、端口/突发及实际地址，补局部整链回放；整机验收由宿主完成。
3. 论文使用Top64/128或最新K256时，再补对应资源映射/质量与标记为估算的核数据。

- 核及PV实测：../attention_tt250_followup_20261107/PAIRED_PPA_ZH.md、WRAPPER_PPA_ZH.md
- 当前共享池合同：../attention_digital_small_20261107/HANDOFF_ZH.md
- FP32宽分数先max-gap再量化：../attention_score_front_ppa_20261108/HANDOFF_ZH.md
- 新标量与修复：COMPARISON.json、RUN_STATUS.json、SOURCES.json、VALIDATION.json；原报告私有。
- 恢复命令：work/rayggxia/198/attention55_compare_20261109/recovery_status.py、collect_recovery.py；build_scalar_cards.py生成价卡。

本交接为前布局模块实测＋条件TLM估算；不代表芯片实测、后布局签核、等PPL或PR已合并。
